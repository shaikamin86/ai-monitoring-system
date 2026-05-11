"""
RSS / Atom news-feed collector.

Polls a curated list of Malaysian news outlets on a configurable
interval (default: every 10 minutes).

No API credentials needed — all feeds are publicly accessible.

Deduplication key: entry URL (stored per-feed in Redis as a sorted set
of seen GUIDs keyed by publish timestamp; entries older than
SEEN_TTL_DAYS are expired automatically).

Dependencies:
  feedparser  — universal feed parser (RSS 0.9x/1.0/2.0, Atom 0.3/1.0)
  httpx       — async HTTP for feed fetching

Env vars:
  None required (optional: RSS_EXTRA_FEEDS — JSON array of extra feed URLs)
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Dict, List, Optional

import feedparser
import httpx
import structlog

from app.core.config import settings
from app.ingestion.base import BaseCollector, RateLimiter
from app.models.post import Platform, PostIngest

log = structlog.get_logger()

SEEN_TTL_DAYS = 14
SEEN_TTL_SECONDS = SEEN_TTL_DAYS * 86400

# ── Curated Malaysian news RSS feeds ─────────────────────────────────────────
DEFAULT_FEEDS: List[Dict[str, str]] = [
    # English outlets
    {"url": "https://www.malaymail.com/feed", "source": "Malay Mail"},
    {"url": "https://www.freemalaysiatoday.com/feed/", "source": "Free Malaysia Today"},
    {"url": "https://www.thestar.com.my/rss/news/nation/", "source": "The Star"},
    {"url": "https://www.nst.com.my/rss/news", "source": "New Straits Times"},
    {"url": "https://www.malaysiakini.com/rss", "source": "Malaysiakini"},
    {"url": "https://www.bernama.com/feed/index.php", "source": "Bernama"},
    # Malay-language outlets
    {"url": "https://www.astroawani.com/rss", "source": "Astro Awani"},
    {"url": "https://www.sinarharian.com.my/feed", "source": "Sinar Harian"},
    {"url": "https://www.bharian.com.my/rss.xml", "source": "Berita Harian"},
    {"url": "https://www.utusan.com.my/feed/", "source": "Utusan Malaysia"},
    # Online / alternative
    {"url": "https://english.astroawani.com/rss", "source": "Astro Awani (EN)"},
    {"url": "https://www.malaysiakini.com/news/rss", "source": "Malaysiakini News"},
]


class RSSCollector(BaseCollector):
    """Polls RSS/Atom feeds and converts entries to PostIngest records."""

    platform = Platform.news

    def __init__(self, redis_url: str) -> None:
        super().__init__(redis_url)
        # Light rate limiter — no real API limits but be polite to servers
        # Max 30 feed fetches per minute (2 per feed if ~15 feeds)
        self._rate_limiter: Optional[RateLimiter] = None

    async def _limiter(self) -> RateLimiter:
        if self._rate_limiter is None:
            r = await self._get_redis()
            self._rate_limiter = RateLimiter(
                redis=r,
                namespace="rss:fetch",
                max_calls=30,
                window_seconds=60,
            )
        return self._rate_limiter

    async def _active_feeds(self) -> List[Dict[str, str]]:
        """Merge default feeds with any extra feeds stored in Supabase."""
        from app.core.database import get_supabase
        feeds = list(DEFAULT_FEEDS)

        # Extra feeds from env
        extra_raw = getattr(settings, "RSS_EXTRA_FEEDS", "[]")
        try:
            extra = json.loads(extra_raw)
            if isinstance(extra, list):
                feeds.extend(extra)
        except (json.JSONDecodeError, TypeError):
            pass

        # Active RSS sources from ingestion_sources table
        try:
            db = get_supabase()
            result = (
                db.table("ingestion_sources")
                .select("config")
                .eq("platform", "news")
                .eq("is_active", True)
                .execute()
            )
            for row in (result.data or []):
                cfg = row.get("config", {})
                url = cfg.get("feed_url")
                source = cfg.get("source_name", "Custom")
                if url:
                    feeds.append({"url": url, "source": source})
        except Exception as exc:
            log.warning("Could not load custom RSS sources", error=str(exc))

        return feeds

    async def collect(self) -> List[PostIngest]:
        feeds = await self._active_feeds()
        limiter = await self._limiter()
        r = await self._get_redis()
        posts: List[PostIngest] = []

        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "SentinelBot/1.0 (+https://sentinel.my/bot)"},
        ) as client:
            for feed_cfg in feeds:
                feed_url = feed_cfg["url"]
                source_name = feed_cfg.get("source", feed_url)
                seen_key = f"ingestion:rss:seen:{_feed_key(feed_url)}"

                await limiter.wait_and_acquire()

                try:
                    raw_xml = await _fetch_feed(client, feed_url)
                except Exception as exc:
                    log.warning("RSS fetch failed", url=feed_url, error=str(exc))
                    continue

                if not raw_xml:
                    continue

                feed = feedparser.parse(raw_xml)
                if feed.bozo and not feed.entries:
                    log.debug("Bad feed", url=feed_url, exception=str(feed.bozo_exception))
                    continue

                new_guids: List[tuple[str, float]] = []

                for entry in feed.entries:
                    guid = _entry_guid(entry)
                    if not guid:
                        continue

                    # Check seen set (O(1) via Redis ZSCORE)
                    already_seen = await r.zscore(seen_key, guid)
                    if already_seen is not None:
                        continue

                    post = _entry_to_post(entry, source_name, feed_url)
                    if post:
                        posts.append(post)
                        new_guids.append((guid, time.time()))

                if new_guids:
                    await r.zadd(seen_key, {g: ts for g, ts in new_guids})
                    # Remove entries older than TTL
                    cutoff = time.time() - SEEN_TTL_SECONDS
                    await r.zremrangebyscore(seen_key, "-inf", cutoff)
                    await r.expire(seen_key, SEEN_TTL_SECONDS * 2)
                    log.debug("RSS new entries", source=source_name, count=len(new_guids))

        return posts


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_feed(client: httpx.AsyncClient, url: str) -> Optional[bytes]:
    resp = await client.get(url)
    if resp.status_code not in (200, 301, 302):
        return None
    return resp.content


def _feed_key(url: str) -> str:
    """Short stable key derived from the feed URL."""
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _entry_guid(entry: Any) -> Optional[str]:
    """Return a stable unique ID for a feed entry."""
    return (
        entry.get("id")
        or entry.get("link")
        or entry.get("guid")
    )


def _parse_date(entry: Any) -> datetime:
    """Try multiple date fields; fall back to now."""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(field)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass

    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            except Exception:
                pass

    return datetime.now(timezone.utc)


def _entry_to_post(
    entry: Any, source_name: str, feed_url: str
) -> Optional[PostIngest]:
    """Map a feedparser Entry to a PostIngest.  Returns None if unusable."""
    link: str = entry.get("link", "")
    title: str = (entry.get("title") or "").strip()
    summary: str = (entry.get("summary") or entry.get("description") or "").strip()

    # Strip HTML tags from summary
    import re
    summary = re.sub(r"<[^>]+>", " ", summary).strip()
    summary = re.sub(r"\s{2,}", " ", summary)

    # Compose content: title + summary (deduplicated)
    if summary and summary.lower() != title.lower():
        content = f"{title}. {summary}" if title else summary
    else:
        content = title or summary

    if not content or len(content) < 20:
        return None

    # Stable external ID from URL or GUID
    guid = _entry_guid(entry)
    external_id = hashlib.sha1((guid or content[:100]).encode()).hexdigest()[:32]

    author = ""
    if entry.get("authors"):
        author = entry["authors"][0].get("name", "")
    elif entry.get("author"):
        author = entry.get("author", "")

    posted_at = _parse_date(entry)

    tags = [t.get("term", "") for t in entry.get("tags", []) if t.get("term")]
    hashtag_str = " ".join(f"#{t.replace(' ', '')}" for t in tags[:5] if t)
    if hashtag_str:
        content = f"{content} {hashtag_str}"

    return PostIngest(
        external_id=external_id,
        platform=Platform.news,
        content=content[:4000],  # guard against enormous articles
        author_id=None,
        author_username=author[:100] if author else source_name,
        author_display_name=source_name,
        author_followers=0,
        author_verified=True,  # established news outlets
        url=link or None,
        likes_count=0,
        shares_count=0,
        comments_count=0,
        views_count=0,
        is_repost=False,
        posted_at=posted_at,
        metadata={
            "source": source_name,
            "feed_url": feed_url,
            "tags": tags,
            "original_guid": guid,
        },
    )
