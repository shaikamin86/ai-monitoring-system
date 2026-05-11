"""
Facebook Graph API collector — public page posts.

Uses a long-lived Page Access Token (or App Token) to read the
/{page-id}/posts endpoint for a curated list of Malaysian public pages.

Token requirements:
  - pages_read_engagement permission
  - Long-lived user token (≥60 days) OR non-expiring Page token
    (can be obtained via Business Manager → System User)

Rate limits (server-side / app-level):
  - 200 calls / hour per app (Business Use Case rate limit)
  - Each page query = 1 call
  - We leave a 20 % headroom → cap at 160 / hour

Pagination:
  - Graph API returns a `paging.cursors.after` value.
  - We store it per page in Redis; on the next run we pass it as
    `after` to resume from where we left off.
  - First run fetches the last 7 days of posts (since= parameter).

Env vars required:
  FACEBOOK_ACCESS_TOKEN     — long-lived user/page/system-user token
  FACEBOOK_APP_ID           — your app ID (for rate-limit calculation)

Optional:
  FACEBOOK_EXTRA_PAGES      — JSON array of {"id": "...", "name": "..."}
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.core.config import settings
from app.ingestion.base import BaseCollector, RateLimiter, RateLimitExceeded
from app.models.post import Platform, PostIngest

log = structlog.get_logger()

GRAPH_BASE = "https://graph.facebook.com/v19.0"

# Curated Malaysian public Facebook pages (politics, news, civil society)
DEFAULT_PAGES: List[Dict[str, str]] = [
    # News outlets
    {"id": "malaymail",           "name": "Malay Mail"},
    {"id": "freemalaysiatodayFMT","name": "Free Malaysia Today"},
    {"id": "thestaronline",       "name": "The Star"},
    {"id": "BernamaNews",         "name": "Bernama"},
    {"id": "AstroAwaniNews",      "name": "Astro Awani"},
    {"id": "sinarharian",         "name": "Sinar Harian"},
    {"id": "beritaharian.my",     "name": "Berita Harian"},
    {"id": "MalaysiaKini",        "name": "Malaysiakini"},
    # Political parties (official pages)
    {"id": "umno.official",       "name": "UMNO"},
    {"id": "pkrofficial",         "name": "PKR"},
    {"id": "DAP.Malaysia",        "name": "DAP"},
    {"id": "PartiBersatu",        "name": "Bersatu"},
    # Government / PM office
    {"id": "pmomalaysia",         "name": "Prime Minister's Office"},
]

POST_FIELDS = (
    "id,message,story,created_time,from,"
    "reactions.summary(true).limit(0),"
    "shares,"
    "comments.summary(true).limit(0),"
    "full_picture,permalink_url"
)


class FacebookCollector(BaseCollector):
    """Collects public page posts via the Facebook Graph API."""

    platform = Platform.facebook

    def __init__(self, redis_url: str) -> None:
        super().__init__(redis_url)
        self._token = settings.FACEBOOK_ACCESS_TOKEN
        # 160 calls / 3600 s = ~1 call per 22 s
        self._rate_limiter: Optional[RateLimiter] = None

    async def _limiter(self) -> RateLimiter:
        if self._rate_limiter is None:
            r = await self._get_redis()
            self._rate_limiter = RateLimiter(
                redis=r,
                namespace="facebook:graph",
                max_calls=160,
                window_seconds=3600,
            )
        return self._rate_limiter

    async def _active_pages(self) -> List[Dict[str, str]]:
        pages = list(DEFAULT_PAGES)

        extra_raw = getattr(settings, "FACEBOOK_EXTRA_PAGES", "[]")
        try:
            extra = json.loads(extra_raw) if extra_raw else []
            if isinstance(extra, list):
                pages.extend(extra)
        except (json.JSONDecodeError, TypeError):
            pass

        # Pull additional pages from ingestion_sources table
        try:
            from app.core.database import get_supabase
            db = get_supabase()
            result = (
                db.table("ingestion_sources")
                .select("config")
                .eq("platform", "facebook")
                .eq("is_active", True)
                .execute()
            )
            for row in (result.data or []):
                cfg = row.get("config", {})
                page_id = cfg.get("page_id")
                page_name = cfg.get("page_name", page_id)
                if page_id:
                    pages.append({"id": page_id, "name": page_name})
        except Exception as exc:
            log.warning("Could not load custom Facebook pages", error=str(exc))

        return pages

    async def collect(self) -> List[PostIngest]:
        if not self._token:
            log.warning("FACEBOOK_ACCESS_TOKEN not set — skipping")
            return []

        pages = await self._active_pages()
        limiter = await self._limiter()
        state = await self._get_state()
        posts: List[PostIngest] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Validate token before batching (cheap introspection call)
            if not await self._token_is_valid(client):
                log.error("Facebook token invalid or expired")
                return []

            for page in pages:
                page_id = page["id"]
                page_name = page["name"]
                cursor_key = f"cursor:{page_id}"
                after = await state.get(cursor_key)

                batch, next_after = await self._fetch_page_posts(
                    client, limiter, page_id, page_name, after
                )
                posts.extend(batch)
                if next_after:
                    await state.set(cursor_key, next_after)
                elif after:
                    # No more pages; clear cursor so next run starts fresh
                    # (Graph API cursors expire; safer to re-fetch from since=)
                    await state.delete(cursor_key)

        return posts

    async def _token_is_valid(self, client: httpx.AsyncClient) -> bool:
        """Quick /me call to test the token is still alive."""
        try:
            resp = await client.get(
                f"{GRAPH_BASE}/me",
                params={"access_token": self._token, "fields": "id"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def _fetch_page_posts(
        self,
        client: httpx.AsyncClient,
        limiter: RateLimiter,
        page_id: str,
        page_name: str,
        after: Optional[str],
    ) -> tuple[List[PostIngest], Optional[str]]:
        await limiter.wait_and_acquire()

        params: Dict[str, Any] = {
            "access_token": self._token,
            "fields": POST_FIELDS,
            "limit": 100,
        }

        if after:
            params["after"] = after
        else:
            # First run or cursor expired — collect last 7 days
            since_dt = datetime.now(timezone.utc) - timedelta(days=7)
            params["since"] = int(since_dt.timestamp())

        try:
            resp = await client.get(
                f"{GRAPH_BASE}/{page_id}/posts",
                params=params,
            )
        except httpx.RequestError as exc:
            raise ConnectionError(f"Facebook HTTP error: {exc}") from exc

        if resp.status_code == 429:
            # Graph API encodes retry info differently; just back off 60 s.
            raise RateLimitExceeded(retry_after=60.0)

        if resp.status_code in (400, 401, 403):
            body = resp.json()
            err = body.get("error", {})
            code = err.get("code", resp.status_code)
            msg = err.get("message", "unknown")
            # Error 190 = token expired; 200 = permission missing
            log.error(
                "Facebook Graph error",
                page=page_id,
                code=code,
                message=msg,
            )
            return [], None

        if resp.status_code != 200:
            log.error("Facebook API error", page=page_id, status=resp.status_code)
            return [], None

        data = resp.json()
        raw_posts: List[Dict] = data.get("data", [])
        paging = data.get("paging", {})
        next_after: Optional[str] = paging.get("cursors", {}).get("after")
        # If there's no next page, don't store a cursor.
        has_next = bool(paging.get("next"))

        log.debug("Facebook page posts", page=page_name, count=len(raw_posts))
        return _parse_posts(raw_posts, page_name), (next_after if has_next else None)


# ── Mapping helpers ───────────────────────────────────────────────────────────

def _parse_posts(
    raw_posts: List[Dict[str, Any]], page_name: str
) -> List[PostIngest]:
    posts: List[PostIngest] = []
    for p in raw_posts:
        post_id: str = p.get("id", "")
        if not post_id:
            continue

        # `message` is user-written text; `story` is auto-generated
        # (e.g. "Page X updated their cover photo") — prefer message.
        content: str = (p.get("message") or p.get("story") or "").strip()
        if not content or len(content) < 10:
            continue

        from_info = p.get("from", {})
        author_id = from_info.get("id")
        author_name = from_info.get("name", page_name)

        reactions = p.get("reactions", {}).get("summary", {}).get("total_count", 0)
        shares = p.get("shares", {}).get("count", 0)
        comments = p.get("comments", {}).get("summary", {}).get("total_count", 0)

        url: Optional[str] = p.get("permalink_url")

        try:
            posted_at = datetime.fromisoformat(
                p["created_time"].replace("+0000", "+00:00")
            )
        except (KeyError, ValueError):
            posted_at = datetime.now(timezone.utc)

        posts.append(
            PostIngest(
                external_id=post_id,
                platform=Platform.facebook,
                content=content[:4000],
                author_id=author_id or None,
                author_username=author_name,
                author_display_name=author_name,
                author_followers=0,  # requires a separate API call; skip for now
                author_verified=False,
                url=url,
                likes_count=int(reactions),
                shares_count=int(shares),
                comments_count=int(comments),
                views_count=0,
                is_repost=False,
                posted_at=posted_at,
                metadata={
                    "page_name": page_name,
                    "has_image": bool(p.get("full_picture")),
                },
            )
        )
    return posts
