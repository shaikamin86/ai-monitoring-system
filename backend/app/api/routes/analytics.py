from fastapi import APIRouter, Query
from typing import Optional
from app.services.analytics_service import (
    get_dashboard_metrics,
    get_trend_data,
    get_hourly_volume,
)
from app.core.database import get_supabase

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def dashboard_metrics():
    return await get_dashboard_metrics()


@router.get("/trends")
async def trend_data(
    metric: str = "posts",
    interval: str = "hour",
    hours: int = Query(default=168, le=720),
    platform: Optional[str] = None,
):
    return await get_trend_data(metric=metric, interval=interval, hours=hours, platform=platform)


@router.get("/hashtags")
async def top_hashtags(
    limit: int = Query(default=20, le=100),
    hours: int = Query(default=24, le=720),
):
    from datetime import datetime, timedelta, timezone
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    result = (
        db.table("hashtag_trends")
        .select("hashtag_id, count, bucket")
        .gte("bucket", cutoff)
        .execute()
    ).data or []

    # Aggregate by hashtag
    totals: dict = {}
    for item in result:
        hid = item["hashtag_id"]
        totals[hid] = totals.get(hid, 0) + item["count"]

    # Fetch tag names
    top_ids = sorted(totals, key=lambda x: totals[x], reverse=True)[:limit]
    tags = []
    for hid in top_ids:
        tag_result = db.table("hashtags").select("tag, total_count").eq("id", hid).single().execute()
        if tag_result.data:
            tags.append({**tag_result.data, "period_count": totals[hid]})

    return {"hashtags": tags, "hours": hours}


@router.get("/entities")
async def top_entities(
    entity_type: Optional[str] = None,
    limit: int = Query(default=20, le=100),
):
    db = get_supabase()
    query = db.table("entities").select("*")
    if entity_type:
        query = query.eq("type", entity_type)
    result = query.order("importance_score", desc=True).limit(limit).execute()
    return {"entities": result.data or []}


@router.get("/sentiment-timeline")
async def sentiment_timeline(hours: int = Query(default=24, le=168)):
    from datetime import datetime, timedelta, timezone
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    result = (
        db.table("posts")
        .select("posted_at, sentiment, sentiment_score")
        .gte("posted_at", cutoff)
        .order("posted_at")
        .execute()
    ).data or []

    # Bucket by hour
    buckets: dict = {}
    for post in result:
        from datetime import datetime
        dt = datetime.fromisoformat(post["posted_at"].replace("Z", "+00:00"))
        key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
        if key not in buckets:
            buckets[key] = {"time": key, "positive": 0, "negative": 0, "neutral": 0, "mixed": 0, "avg_score": []}
        s = post.get("sentiment") or "neutral"
        buckets[key][s] = buckets[key].get(s, 0) + 1
        if post.get("sentiment_score") is not None:
            buckets[key]["avg_score"].append(post["sentiment_score"])

    timeline = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        scores = b.pop("avg_score")
        b["avg_score"] = sum(scores) / len(scores) if scores else 0
        timeline.append(b)

    return {"timeline": timeline}


@router.get("/platform-breakdown")
async def platform_breakdown(hours: int = Query(default=24, le=720)):
    from datetime import datetime, timedelta, timezone
    db = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    result = (
        db.table("posts")
        .select("platform, sentiment, engagement_score")
        .gte("posted_at", cutoff)
        .execute()
    ).data or []

    breakdown: dict = {}
    for post in result:
        p = post.get("platform", "other")
        if p not in breakdown:
            breakdown[p] = {"platform": p, "count": 0, "positive": 0, "negative": 0, "neutral": 0, "avg_engagement": []}
        breakdown[p]["count"] += 1
        s = post.get("sentiment") or "neutral"
        breakdown[p][s] = breakdown[p].get(s, 0) + 1
        if post.get("engagement_score"):
            breakdown[p]["avg_engagement"].append(post["engagement_score"])

    platforms = []
    for p, data in breakdown.items():
        eng = data.pop("avg_engagement")
        data["avg_engagement"] = sum(eng) / len(eng) if eng else 0
        platforms.append(data)

    return {"platforms": sorted(platforms, key=lambda x: x["count"], reverse=True)}
