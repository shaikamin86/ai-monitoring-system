"""
Post ingestion pipeline: normalize → embed → NLP → store → cluster → alert.
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.database import get_supabase
from app.services.embedding_service import generate_embedding
from app.services.nlp_service import (
    detect_language, normalize_text, extract_hashtags,
    extract_mentions, extract_entities_and_topics
)
from app.services.alert_service import check_keyword_matches
from app.models.post import PostIngest
import structlog

log = structlog.get_logger()


async def ingest_post(post: PostIngest) -> Optional[Dict[str, Any]]:
    """Full ingestion pipeline for a single post."""
    db = get_supabase()

    # Dedup check
    existing = (
        db.table("posts")
        .select("id")
        .eq("platform", post.platform.value)
        .eq("external_id", post.external_id)
        .execute()
    )
    if existing.data:
        log.debug("Duplicate post skipped", external_id=post.external_id)
        return None

    # Language detection
    language = detect_language(post.content)

    # Compute engagement score
    likes = post.likes_count
    shares = post.shares_count
    comments = post.comments_count
    followers = max(post.author_followers, 1)
    raw_engagement = likes + (shares * 3) + (comments * 2)
    engagement_rate = raw_engagement / followers * 100
    import math
    engagement_score = min(100.0, math.log(max(1, raw_engagement) + 1) * 10 + engagement_rate)

    # Extract hashtags
    hashtags = extract_hashtags(post.content)
    normalized_content = normalize_text(post.content)

    # Generate embedding
    try:
        embedding = await generate_embedding(normalized_content or post.content)
    except Exception as e:
        log.error("Embedding failed", error=str(e))
        embedding = None

    # NLP analysis
    try:
        nlp_result = await extract_entities_and_topics(post.content, language)
        sentiment = nlp_result.get("sentiment", "neutral")
        sentiment_score = nlp_result.get("sentiment_score", 0.0)
        entities = nlp_result.get("entities", [])
        topics = nlp_result.get("topics", [])
    except Exception as e:
        log.error("NLP analysis failed", error=str(e))
        sentiment = "neutral"
        sentiment_score = 0.0
        entities = []
        topics = []

    # Insert post
    post_data = {
        "external_id": post.external_id,
        "platform": post.platform.value,
        "content": post.content,
        "content_normalized": normalized_content,
        "author_id": post.author_id,
        "author_username": post.author_username,
        "author_display_name": post.author_display_name,
        "author_followers": post.author_followers,
        "author_verified": post.author_verified,
        "url": str(post.url) if post.url else None,
        "language": language,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "embedding": embedding,
        "engagement_score": engagement_score,
        "likes_count": post.likes_count,
        "shares_count": post.shares_count,
        "comments_count": post.comments_count,
        "views_count": post.views_count,
        "is_repost": post.is_repost,
        "posted_at": post.posted_at.isoformat(),
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "metadata": post.metadata,
    }

    result = db.table("posts").insert(post_data).execute()
    if not result.data:
        log.error("Post insertion failed")
        return None

    inserted = result.data[0]
    post_id = inserted["id"]

    # Process hashtags
    await _process_hashtags(db, post_id, hashtags)

    # Process entities
    await _process_entities(db, post_id, entities)

    # Update influencer profile
    if post.author_id:
        await _upsert_influencer(db, post)

    # Check watch terms
    await check_keyword_matches(post.content, post_id)

    log.info(
        "Post ingested",
        post_id=post_id,
        platform=post.platform.value,
        language=language,
        sentiment=sentiment,
    )
    return inserted


async def _process_hashtags(db, post_id: str, hashtags: List[str]) -> None:
    for tag in hashtags:
        tag_lower = tag.lower().strip()
        if not tag_lower:
            continue
        # Upsert hashtag
        result = db.table("hashtags").upsert(
            {"tag": tag_lower}, on_conflict="tag"
        ).execute()
        if result.data:
            hashtag_id = result.data[0]["id"]
            db.table("post_hashtags").upsert(
                {"post_id": post_id, "hashtag_id": hashtag_id},
                on_conflict="post_id,hashtag_id",
            ).execute()


async def _process_entities(db, post_id: str, entities: List[Dict]) -> None:
    for entity in entities:
        name = entity.get("name", "").strip()
        etype = entity.get("type", "TOPIC")
        if not name:
            continue

        normalized = name.lower().strip()
        result = db.table("entities").upsert(
            {"name": name, "type": etype, "normalized_name": normalized},
            on_conflict="normalized_name,type",
        ).execute()
        if result.data:
            entity_id = result.data[0]["id"]
            db.table("post_entities").upsert(
                {
                    "post_id": post_id,
                    "entity_id": entity_id,
                    "confidence": entity.get("relevance", 1.0),
                }
            ).execute()


async def _upsert_influencer(db, post: PostIngest) -> None:
    if not post.author_id:
        return
    db.table("influencers").upsert(
        {
            "platform": post.platform.value,
            "platform_user_id": post.author_id,
            "username": post.author_username or post.author_id,
            "display_name": post.author_display_name,
            "followers_count": post.author_followers,
            "verified": post.author_verified,
            "last_active": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="platform,platform_user_id",
    ).execute()


async def ingest_batch(posts: List[PostIngest]) -> Dict[str, int]:
    """Ingest a batch of posts concurrently."""
    semaphore = asyncio.Semaphore(10)

    async def _ingest_safe(post: PostIngest):
        async with semaphore:
            try:
                return await ingest_post(post)
            except Exception as e:
                log.error("Batch ingest error", error=str(e))
                return None

    results = await asyncio.gather(*[_ingest_safe(p) for p in posts])
    ingested = sum(1 for r in results if r is not None)
    skipped = len(results) - ingested

    return {"ingested": ingested, "skipped": skipped, "total": len(posts)}
