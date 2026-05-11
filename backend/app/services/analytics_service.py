"""
Analytics service: trend computation, sentiment aggregation,
influencer scoring, and snapshot generation.
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from app.core.database import get_supabase
import structlog

log = structlog.get_logger()


def _empty_dashboard() -> Dict[str, Any]:
    """Return a zero-state dashboard when tables are unavailable."""
    now = datetime.now(timezone.utc)
    return {
        "total_posts_24h": 0,
        "active_alerts": 0,
        "active_narratives": 0,
        "critical_alerts": 0,
        "sentiment_distribution": {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
        "platform_distribution": {},
        "top_hashtags": [],
        "emerging_narratives": [],
        "recent_alerts": [],
        "hourly_volume": [
            {
                "time": (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0).isoformat(),
                "count": 0,
            }
            for i in range(24, 0, -1)
        ],
        "_schema_ready": False,
    }


async def get_dashboard_metrics() -> Dict[str, Any]:
    db = get_supabase()
    now = datetime.now(timezone.utc)
    last_24h = (now - timedelta(hours=24)).isoformat()

    try:
        # Parallel fetches
        total_posts = db.table("posts").select("id", count="exact").gte("posted_at", last_24h).execute()
        active_alerts = db.table("alerts").select("id", count="exact").eq("status", "active").execute()
        active_narratives = db.table("narratives").select("id", count="exact").in_("status", ["emerging", "active"]).execute()
        critical_alerts = db.table("alerts").select("id", count="exact").eq("status", "active").eq("severity", "critical").execute()
    except Exception as exc:
        log.warning("Dashboard metrics: schema not ready", error=str(exc))
        return _empty_dashboard()

    try:
        # Sentiment distribution (last 24h)
        sentiment_result = (
            db.table("posts")
            .select("sentiment")
            .gte("posted_at", last_24h)
            .execute()
        )
        sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
        for post in sentiment_result.data or []:
            s = post.get("sentiment", "neutral") or "neutral"
            sentiment_dist[s] = sentiment_dist.get(s, 0) + 1
    except Exception:
        sentiment_dist = {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}

    try:
        # Platform distribution
        platform_result = (
            db.table("posts")
            .select("platform")
            .gte("posted_at", last_24h)
            .execute()
        )
        platform_dist: Dict[str, int] = {}
        for post in platform_result.data or []:
            p = post.get("platform", "other")
            platform_dist[p] = platform_dist.get(p, 0) + 1
    except Exception:
        platform_dist = {}

    try:
        top_hashtags = (
            db.table("hashtags")
            .select("tag, total_count")
            .order("total_count", desc=True)
            .limit(10)
            .execute()
        ).data or []
    except Exception:
        top_hashtags = []

    try:
        emerging = (
            db.table("narratives")
            .select(
                "id, title, threat_level, post_count, virality_score, status, "
                "last_activity, first_detected, unique_authors, engagement_total, "
                "sentiment_distribution, languages, platforms, is_coordinated, "
                "key_themes, key_hashtags, momentum_score, coordination_score"
            )
            .in_("status", ["emerging", "active"])
            .order("virality_score", desc=True)
            .limit(10)
            .execute()
        ).data or []
    except Exception:
        emerging = []

    try:
        recent_alerts = (
            db.table("alerts")
            .select("*")
            .eq("status", "active")
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        ).data or []
    except Exception:
        recent_alerts = []

    try:
        hourly_volume = await get_hourly_volume(hours=24)
    except Exception:
        hourly_volume = [
            {
                "time": (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0).isoformat(),
                "count": 0,
            }
            for i in range(24, 0, -1)
        ]

    return {
        "total_posts_24h": total_posts.count or 0,
        "active_alerts": active_alerts.count or 0,
        "active_narratives": active_narratives.count or 0,
        "critical_alerts": critical_alerts.count or 0,
        "sentiment_distribution": sentiment_dist,
        "platform_distribution": platform_dist,
        "top_hashtags": top_hashtags,
        "emerging_narratives": emerging,
        "recent_alerts": recent_alerts,
        "hourly_volume": hourly_volume,
        "_schema_ready": True,
    }


async def get_hourly_volume(hours: int = 24) -> List[Dict[str, Any]]:
    """Get post volume per hour for the last N hours (single query, Python bucketing)."""
    db = get_supabase()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    try:
        rows = (
            db.table("posts")
            .select("posted_at")
            .gte("posted_at", cutoff.isoformat())
            .execute()
        ).data or []
    except Exception:
        rows = []

    # Build hour-keyed buckets
    buckets: Dict[str, int] = {}
    for i in range(hours, 0, -1):
        key = (now - timedelta(hours=i)).replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[key] = 0

    for row in rows:
        dt = datetime.fromisoformat(row["posted_at"].replace("Z", "+00:00"))
        key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        if key in buckets:
            buckets[key] += 1

    return [{"time": k, "count": v} for k, v in buckets.items()]


async def get_trend_data(
    metric: str = "posts",
    interval: str = "hour",
    hours: int = 168,
    platform: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get trend data for charts."""
    db = get_supabase()
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=hours)).isoformat()

    try:
        query = db.table("posts").select("posted_at, sentiment, platform, engagement_score").gte("posted_at", cutoff)
        if platform:
            query = query.eq("platform", platform)
        result = query.execute()
        posts = result.data or []
    except Exception:
        return []

    # Group by interval
    buckets: Dict[str, Dict] = {}
    for post in posts:
        dt = datetime.fromisoformat(post["posted_at"].replace("Z", "+00:00"))
        if interval == "hour":
            key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        elif interval == "day":
            key = dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        else:
            key = dt.replace(minute=0, second=0, microsecond=0).isoformat()

        if key not in buckets:
            buckets[key] = {"time": key, "count": 0, "positive": 0, "negative": 0, "neutral": 0, "engagement": 0}

        buckets[key]["count"] += 1
        s = post.get("sentiment", "neutral") or "neutral"
        buckets[key][s] = buckets[key].get(s, 0) + 1
        buckets[key]["engagement"] += post.get("engagement_score", 0) or 0

    return sorted(buckets.values(), key=lambda x: x["time"])


async def update_influencer_scores() -> None:
    """Recalculate influence scores for monitored influencers."""
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    influencers = (
        db.table("influencers")
        .select("id, platform_user_id, followers_count")
        .eq("is_monitored", True)
        .execute()
    ).data or []

    for inf in influencers:
        iid = inf["id"]
        platform_uid = inf.get("platform_user_id")
        if not platform_uid:
            continue
        posts = (
            db.table("posts")
            .select("engagement_score, sentiment")
            .eq("author_id", platform_uid)
            .gte("posted_at", cutoff)
            .execute()
        ).data or []

        if not posts:
            continue

        total_engagement = sum(p.get("engagement_score", 0) for p in posts)
        avg_engagement = total_engagement / len(posts)
        followers = inf.get("followers_count", 1) or 1
        engagement_rate = avg_engagement / followers * 100

        influence_score = min(100.0, (
            (followers ** 0.4) * 0.3
            + total_engagement * 0.3
            + engagement_rate * 10 * 0.2
            + len(posts) * 0.2
        ))

        db.table("influencers").update({
            "influence_score": influence_score,
            "avg_engagement_rate": engagement_rate,
            "last_active": datetime.now(timezone.utc).isoformat(),
        }).eq("id", iid).execute()


async def generate_analytics_snapshot() -> None:
    """Compute and store hourly analytics snapshot."""
    db = get_supabase()
    metrics = await get_dashboard_metrics()

    bucket = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    snapshot = {
        "bucket": bucket.isoformat(),
        "total_posts": metrics["total_posts_24h"],
        "posts_by_platform": metrics["platform_distribution"],
        "sentiment_distribution": metrics["sentiment_distribution"],
        "top_hashtags": metrics["top_hashtags"],
        "top_narratives": metrics["emerging_narratives"],
        "active_alerts": metrics["active_alerts"],
    }

    db.table("analytics_snapshots").upsert(snapshot, on_conflict="bucket").execute()
    log.info("Analytics snapshot generated", bucket=bucket.isoformat())
