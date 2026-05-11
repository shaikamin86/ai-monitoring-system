"""
TikTok Research API collector.

Requires an approved TikTok Research API application.
Docs: https://developers.tiktok.com/products/research-api/

Auth flow:
  POST /v2/oauth/token/ with client_key + client_secret
  → access_token (expires in 7200s by default)

Search endpoint:
  POST /v2/research/video/query/
  - filter by keyword / hashtag_name / region_code
  - cursor-based pagination

Rate limits:
  - 1 000 requests / day (shared across all endpoints)
  - Burst: no documented burst limit

Env vars required:
  TIKTOK_CLIENT_KEY
  TIKTOK_CLIENT_SECRET
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.core.config import settings
from app.ingestion.base import BaseCollector, RateLimiter, RateLimitExceeded
from app.models.post import Platform, PostIngest

log = structlog.get_logger()

BASE_URL = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{BASE_URL}/oauth/token/"
QUERY_URL = f"{BASE_URL}/research/video/query/"

# Malaysia-focused hashtags and keywords to collect.
# Each entry is a separate API call (to respect cursor independence).
HASHTAG_TARGETS: List[str] = [
    "malaysia",
    "malaysiapolitik",
    "kerajaanmalaysia",
    "malaysianews",
    "beritamalaysia",
    "politikmalaysia",
    "koshibup",          # cost of living slang
    "subsidimalaysia",
    "malaysiahari ini",
]

# Video fields we request
VIDEO_FIELDS = (
    "id,create_time,username,region_code,video_description,"
    "like_count,comment_count,share_count,view_count,"
    "hashtag_names,is_stem_verified,effect_ids"
)


class TikTokCollector(BaseCollector):
    """Collects TikTok videos via the Research API."""

    platform = Platform.tiktok

    def __init__(self, redis_url: str) -> None:
        super().__init__(redis_url)
        self._client_key = settings.TIKTOK_CLIENT_KEY
        self._client_secret = settings.TIKTOK_CLIENT_SECRET
        # 950 / 86400s ≈ 1 call per 90s; use 950 to leave headroom
        self._rate_limiter: Optional[RateLimiter] = None

    async def _limiter(self) -> RateLimiter:
        if self._rate_limiter is None:
            r = await self._get_redis()
            self._rate_limiter = RateLimiter(
                redis=r,
                namespace="tiktok:research",
                max_calls=950,
                window_seconds=86400,  # 24 hours
            )
        return self._rate_limiter

    async def _get_access_token(self, client: httpx.AsyncClient) -> Optional[str]:
        """
        Client-credentials token.  Cache in Redis for (expires_in - 60)s.
        """
        state = await self._get_state()
        token = await state.get("access_token")
        if token:
            return token

        resp = await client.post(
            TOKEN_URL,
            data={
                "client_key": self._client_key,
                "client_secret": self._client_secret,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if resp.status_code != 200:
            log.error("TikTok token fetch failed", status=resp.status_code, body=resp.text[:300])
            return None

        body = resp.json()
        token = body.get("access_token")
        expires_in = int(body.get("expires_in", 7200))
        if token:
            await state.set("access_token", token, ttl=expires_in - 60)
        return token

    async def collect(self) -> List[PostIngest]:
        if not self._client_key or not self._client_secret:
            log.warning("TIKTOK_CLIENT_KEY/SECRET not set — skipping")
            return []

        limiter = await self._limiter()
        state = await self._get_state()
        posts: List[PostIngest] = []

        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._get_access_token(client)
            if not token:
                return []

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            for hashtag in HASHTAG_TARGETS:
                cursor_key = f"cursor:{hashtag}"
                cursor = await state.get(cursor_key)

                batch, next_cursor = await self._query_hashtag(
                    client, headers, limiter, hashtag, cursor
                )
                posts.extend(batch)
                if next_cursor:
                    await state.set(cursor_key, str(next_cursor))

        return posts

    async def _query_hashtag(
        self,
        client: httpx.AsyncClient,
        headers: Dict[str, str],
        limiter: RateLimiter,
        hashtag: str,
        cursor: Optional[str],
    ) -> tuple[List[PostIngest], Optional[int]]:
        await limiter.wait_and_acquire()

        # Date window: last 7 days (API requires start/end as YYYYMMDD)
        from datetime import timedelta
        today = datetime.now(timezone.utc)
        start = (today - timedelta(days=7)).strftime("%Y%m%d")
        end = today.strftime("%Y%m%d")

        body: Dict[str, Any] = {
            "query": {
                "and": [
                    {"operation": "IN", "field_name": "hashtag_name", "field_values": [hashtag]},
                    {"operation": "EQ", "field_name": "region_code", "field_values": ["MY"]},
                ]
            },
            "start_date": start,
            "end_date": end,
            "max_count": 100,
            "fields": VIDEO_FIELDS,
        }
        if cursor:
            body["cursor"] = int(cursor)

        try:
            resp = await client.post(QUERY_URL, headers=headers, json=body)
        except httpx.RequestError as exc:
            raise ConnectionError(f"TikTok HTTP error: {exc}") from exc

        if resp.status_code == 429:
            raise RateLimitExceeded(retry_after=3600.0)

        if resp.status_code == 401:
            # Token might have expired mid-session; clear cached token.
            st = await self._get_state()
            await st.delete("access_token")
            log.warning("TikTok token expired, cleared cache")
            return [], None

        if resp.status_code != 200:
            log.error("TikTok API error", status=resp.status_code, body=resp.text[:400])
            return [], None

        data = resp.json().get("data", {})
        videos: List[Dict] = data.get("videos", [])
        has_more: bool = data.get("has_more", False)
        next_cursor: Optional[int] = data.get("cursor") if has_more else None

        log.debug("TikTok query", hashtag=hashtag, count=len(videos), has_more=has_more)
        return _parse_videos(videos), next_cursor


# ── Mapping helpers ───────────────────────────────────────────────────────────

def _parse_videos(videos: List[Dict[str, Any]]) -> List[PostIngest]:
    posts: List[PostIngest] = []
    for v in videos:
        vid_id = str(v.get("id", ""))
        if not vid_id:
            continue

        username = v.get("username", "")
        description = (v.get("video_description") or "").strip()
        if not description:
            # Skip videos with no description text — nothing to analyse.
            continue

        hashtags = v.get("hashtag_names", []) or []
        hashtag_str = " ".join(f"#{h}" for h in hashtags)
        content = f"{description} {hashtag_str}".strip()

        create_ts = v.get("create_time")
        try:
            posted_at = datetime.fromtimestamp(int(create_ts), tz=timezone.utc)
        except (TypeError, ValueError):
            posted_at = datetime.now(timezone.utc)

        url = f"https://www.tiktok.com/@{username}/video/{vid_id}" if username else None

        posts.append(
            PostIngest(
                external_id=vid_id,
                platform=Platform.tiktok,
                content=content,
                author_id=username or None,
                author_username=username or None,
                author_display_name=username or None,
                author_followers=0,  # Research API doesn't return follower count
                author_verified=bool(v.get("is_stem_verified", False)),
                url=url,
                likes_count=int(v.get("like_count", 0) or 0),
                shares_count=int(v.get("share_count", 0) or 0),
                comments_count=int(v.get("comment_count", 0) or 0),
                views_count=int(v.get("view_count", 0) or 0),
                is_repost=False,
                posted_at=posted_at,
                metadata={
                    "region_code": v.get("region_code"),
                    "hashtags": hashtags,
                    "effect_ids": v.get("effect_ids", []),
                },
            )
        )
    return posts
