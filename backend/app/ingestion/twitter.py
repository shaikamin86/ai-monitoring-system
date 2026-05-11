"""
Twitter/X API v2 collector.

Uses the Recent Search endpoint (/2/tweets/search/recent) with a
Bearer Token.  One RateLimiter governs the 15-req / 15-min app-auth
window.  Since-ID checkpoints (one per search query) prevent
re-fetching already-seen tweets.

Tier assumptions (Basic, $100/mo):
  - 15 requests / 15 min  per search endpoint per app
  - 500 000 tweets / month

Env vars required:
  TWITTER_BEARER_TOKEN
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.core.config import settings
from app.ingestion.base import BaseCollector, RateLimiter, RateLimitExceeded
from app.models.post import Platform, PostIngest

log = structlog.get_logger()

# ── Malaysia-focused search queries ──────────────────────────────────────────
# Mixed Bahasa Malaysia / English.  Keep them narrow to conserve quota.
SEARCH_QUERIES: List[str] = [
    # Politics / governance
    "(Malaysia OR Malaysia) lang:ms -is:retweet",
    "(kerajaan OR pembangkang OR Anwar OR UMNO OR PKR OR DAP) lang:ms -is:retweet",
    # Economy / cost of living
    "(kos hidup OR subsidi OR inflasi) lang:ms -is:retweet",
    # English political
    "(Malaysia politics OR Malaysian government OR Anwar Ibrahim) lang:en -is:retweet",
    # Sensitive / misinformation signals
    "(fitnah OR berita palsu OR fake news Malaysia) -is:retweet",
    # Trending social issues
    "#Malaysia OR #BolehlandNews OR #MalaysiaBoleh -is:retweet",
]

TWEET_FIELDS = (
    "id,text,created_at,author_id,public_metrics,"
    "entities,lang,in_reply_to_user_id,referenced_tweets"
)
USER_FIELDS = "id,name,username,public_metrics,verified,description"
EXPANSIONS = "author_id"
BASE_URL = "https://api.twitter.com/2"


class TwitterCollector(BaseCollector):
    """Collects tweets for each configured query using Recent Search."""

    platform = Platform.twitter

    def __init__(self, redis_url: str) -> None:
        super().__init__(redis_url)
        self._bearer = settings.TWITTER_BEARER_TOKEN
        # 15 requests per 900-second window (15 min), with a small safety buffer
        self._rate_limiter: Optional[RateLimiter] = None

    async def _limiter(self) -> RateLimiter:
        if self._rate_limiter is None:
            r = await self._get_redis()
            self._rate_limiter = RateLimiter(
                redis=r,
                namespace="twitter:search",
                max_calls=14,       # leave 1 request as headroom
                window_seconds=900, # 15 minutes
            )
        return self._rate_limiter

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._bearer}"}

    async def collect(self) -> List[PostIngest]:
        if not self._bearer:
            log.warning("TWITTER_BEARER_TOKEN not set — skipping")
            return []

        state = await self._get_state()
        limiter = await self._limiter()
        posts: List[PostIngest] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for query in SEARCH_QUERIES:
                since_id = await state.get(f"since_id:{query[:40]}")
                raw = await self._search(client, limiter, query, since_id)
                if not raw:
                    continue

                parsed, newest_id = _parse_tweets(raw)
                posts.extend(parsed)

                if newest_id:
                    await state.set(f"since_id:{query[:40]}", newest_id)

        return posts

    async def _search(
        self,
        client: httpx.AsyncClient,
        limiter: RateLimiter,
        query: str,
        since_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """One paginated search call.  Returns the raw API response dict."""
        await limiter.wait_and_acquire()

        params: Dict[str, Any] = {
            "query": query,
            "max_results": 100,
            "tweet.fields": TWEET_FIELDS,
            "user.fields": USER_FIELDS,
            "expansions": EXPANSIONS,
        }
        if since_id:
            params["since_id"] = since_id

        try:
            resp = await client.get(
                f"{BASE_URL}/tweets/search/recent",
                headers=self._headers(),
                params=params,
            )
        except httpx.RequestError as exc:
            raise ConnectionError(f"Twitter HTTP error: {exc}") from exc

        if resp.status_code == 429:
            # x-rate-limit-reset header gives the UNIX timestamp when the
            # window resets.
            reset_ts = float(resp.headers.get("x-rate-limit-reset", 0))
            retry_after = max(1.0, reset_ts - datetime.now(timezone.utc).timestamp())
            raise RateLimitExceeded(retry_after)

        if resp.status_code == 401:
            log.error("Twitter auth failed — check TWITTER_BEARER_TOKEN")
            return None

        if resp.status_code != 200:
            log.error("Twitter API error", status=resp.status_code, body=resp.text[:400])
            return None

        data = resp.json()
        meta = data.get("meta", {})
        result_count = meta.get("result_count", 0)
        log.debug(
            "Twitter search",
            query=query[:60],
            count=result_count,
            newest_id=meta.get("newest_id"),
        )
        return data if result_count else None


# ── Mapping helpers ───────────────────────────────────────────────────────────

def _parse_tweets(data: Dict[str, Any]) -> tuple[List[PostIngest], Optional[str]]:
    """Convert raw API response → list of PostIngest + newest tweet ID."""
    tweets: List[Dict] = data.get("data", [])
    users: Dict[str, Dict] = {
        u["id"]: u for u in data.get("includes", {}).get("users", [])
    }
    newest_id: Optional[str] = data.get("meta", {}).get("newest_id")

    posts: List[PostIngest] = []
    for tw in tweets:
        author_id = tw.get("author_id", "")
        user = users.get(author_id, {})
        metrics = tw.get("public_metrics", {})
        u_metrics = user.get("public_metrics", {})

        # Skip pure retweets (content starts with "RT @")
        text: str = tw.get("text", "")
        if text.startswith("RT @"):
            continue

        # Build URL
        tweet_url = (
            f"https://twitter.com/{user.get('username', 'unknown')}/status/{tw['id']}"
            if user.get("username") else None
        )

        # Extract any attached hashtag entities
        entities = tw.get("entities", {})
        hashtag_entities = [
            f"#{h['tag']}" for h in entities.get("hashtags", [])
        ]

        try:
            posted_at = datetime.fromisoformat(tw["created_at"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            posted_at = datetime.now(timezone.utc)

        posts.append(
            PostIngest(
                external_id=tw["id"],
                platform=Platform.twitter,
                content=text,
                author_id=author_id or None,
                author_username=user.get("username"),
                author_display_name=user.get("name"),
                author_followers=u_metrics.get("followers_count", 0),
                author_verified=user.get("verified", False),
                url=tweet_url,
                likes_count=metrics.get("like_count", 0),
                shares_count=metrics.get("retweet_count", 0),
                comments_count=metrics.get("reply_count", 0),
                views_count=metrics.get("impression_count", 0),
                is_repost=bool(tw.get("referenced_tweets")),
                posted_at=posted_at,
                metadata={
                    "lang": tw.get("lang"),
                    "quote_count": metrics.get("quote_count", 0),
                    "bookmark_count": metrics.get("bookmark_count", 0),
                    "hashtags": hashtag_entities,
                },
            )
        )

    return posts, newest_id
