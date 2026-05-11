"""
NLP service: language detection, entity recognition, keyword matching,
and text normalization for Malaysian social media content.
"""
import re
import json
from typing import List, Dict, Any, Optional, Tuple
from openai import AsyncOpenAI
from langdetect import detect, LangDetectException
from tenacity import retry, stop_after_attempt, wait_exponential
from app.core.config import settings
import structlog

log = structlog.get_logger()

# Common BM slang / abbreviations normalization map
BM_SLANG_MAP = {
    "xde": "tidak ada", "xnak": "tidak nak", "xleh": "tidak boleh",
    "nk": "nak", "psl": "pasal", "sbb": "sebab", "dgn": "dengan",
    "utk": "untuk", "pd": "pada", "kt": "kat", "dh": "dah",
    "jgn": "jangan", "mcm": "macam", "cmne": "macam mana",
    "blh": "boleh", "klu": "kalau", "skrg": "sekarang",
    "tgh": "tengah", "lg": "lagi", "je": "sahaja", "pun": "pun",
    "la": "", "lah": "", "kan": "", "tau": "tahu",
    "guna": "guna", "aje": "sahaja", "kena": "kena",
    "mane": "mana", "bile": "bila", "sape": "siapa",
}

# Hashtag extraction regex
HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)
MENTION_RE = re.compile(r"@(\w+)", re.UNICODE)
URL_RE = re.compile(r"https?://\S+|www\.\S+")


def extract_hashtags(text: str) -> List[str]:
    return [tag.lower() for tag in HASHTAG_RE.findall(text)]


def extract_mentions(text: str) -> List[str]:
    return [m.lower() for m in MENTION_RE.findall(text)]


def normalize_text(text: str) -> str:
    """Strip URLs, mentions, normalize BM slang."""
    text = URL_RE.sub("", text)
    text = MENTION_RE.sub("", text)
    words = text.split()
    normalized = []
    for word in words:
        lower = word.lower().strip(".,!?;:'\"")
        mapped = BM_SLANG_MAP.get(lower, word)
        if mapped:
            normalized.append(mapped)
    return " ".join(normalized).strip()


def detect_language(text: str) -> str:
    """Detect language: ms, en, mixed, or other."""
    clean = URL_RE.sub("", text)
    clean = HASHTAG_RE.sub("", clean).strip()
    if len(clean) < 10:
        return "mixed"

    bm_markers = ["dan", "yang", "untuk", "dengan", "dalam", "adalah",
                  "tidak", "boleh", "ialah", "saya", "kita", "mereka",
                  "kerajaan", "negara", "rakyat", "Malaysia"]
    bm_count = sum(1 for w in bm_markers if re.search(rf"\b{w}\b", clean, re.IGNORECASE))

    try:
        detected = detect(clean)
    except LangDetectException:
        detected = "unknown"

    if detected == "ms" or bm_count >= 3:
        if bm_count >= 2 and detected == "en":
            return "mixed"
        return "ms"
    elif detected == "en":
        return "en"
    elif bm_count >= 1:
        return "mixed"
    return "other"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
async def extract_entities_and_topics(
    text: str, language: str
) -> Dict[str, Any]:
    """Use OpenAI to extract entities, topics, and sentiment."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    system_prompt = """You are an expert NLP analyst specializing in Malaysian social media content.
Extract structured information from social media posts in Bahasa Malaysia, English, or mixed language.

Return ONLY valid JSON with this exact structure:
{
  "entities": [{"name": "string", "type": "PERSON|ORG|LOCATION|EVENT|PRODUCT|TOPIC", "relevance": 0.0-1.0}],
  "topics": ["string"],
  "sentiment": "positive|negative|neutral|mixed",
  "sentiment_score": -1.0 to 1.0,
  "key_claims": ["string"],
  "is_opinion": true/false,
  "is_news": true/false,
  "potential_misinformation": true/false,
  "urgency_level": 0-5
}"""

    user_prompt = f"""Analyze this Malaysian social media post (language: {language}):

"{text}"

Extract entities, topics, sentiment, and key claims. Be thorough with Malaysian political figures, government agencies, places, and current issues."""

    try:
        response = await client.chat.completions.create(
            model=settings.OPENAI_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=800,
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        log.error("Entity extraction failed", error=str(e))
        return {
            "entities": [],
            "topics": [],
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "key_claims": [],
            "is_opinion": False,
            "is_news": False,
            "potential_misinformation": False,
            "urgency_level": 0,
        }


async def analyze_coordinated_behavior(posts: List[Dict]) -> Dict[str, Any]:
    """Detect coordinated inauthentic behavior patterns."""
    if len(posts) < 5:
        return {"is_coordinated": False, "confidence": 0.0, "signals": []}

    signals = []
    post_times = [p.get("posted_at") for p in posts if p.get("posted_at")]
    unique_authors = len(set(p.get("author_id") for p in posts if p.get("author_id")))
    total = len(posts)

    # Check author diversity ratio
    diversity_ratio = unique_authors / total if total > 0 else 1.0
    if diversity_ratio < 0.3:
        signals.append("low_author_diversity")

    # Check for identical or near-identical content
    contents = [p.get("content", "") for p in posts]
    unique_contents = len(set(contents))
    if unique_contents / len(contents) < 0.5:
        signals.append("duplicate_content")

    # Check for account age patterns (if available)
    new_accounts = sum(1 for p in posts if p.get("metadata", {}).get("account_age_days", 365) < 30)
    if new_accounts / total > 0.4:
        signals.append("many_new_accounts")

    is_coordinated = len(signals) >= 2
    confidence = min(1.0, len(signals) * 0.35)

    return {
        "is_coordinated": is_coordinated,
        "confidence": confidence,
        "signals": signals,
    }
