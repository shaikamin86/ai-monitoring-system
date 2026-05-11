from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.core.database import get_supabase

router = APIRouter(prefix="/influencers", tags=["influencers"])


@router.get("")
async def list_influencers(
    platform: Optional[str] = None,
    is_flagged: Optional[bool] = None,
    min_influence: Optional[float] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    sort_by: str = "influence_score",
):
    db = get_supabase()
    query = db.table("influencers").select("*").eq("is_monitored", True)

    if platform:
        query = query.eq("platform", platform)
    if is_flagged is not None:
        query = query.eq("is_flagged", is_flagged)
    if min_influence is not None:
        query = query.gte("influence_score", min_influence)

    allowed_sorts = ["influence_score", "followers_count", "avg_engagement_rate", "last_active"]
    if sort_by not in allowed_sorts:
        sort_by = "influence_score"

    result = query.order(sort_by, desc=True).limit(limit).offset(offset).execute()
    total = db.table("influencers").select("id", count="exact").eq("is_monitored", True).execute()

    return {"influencers": result.data or [], "total": total.count or 0}


@router.get("/{influencer_id}")
async def get_influencer(influencer_id: str):
    db = get_supabase()
    result = db.table("influencers").select("*").eq("id", influencer_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer not found")

    inf = result.data

    # Recent posts
    posts = (
        db.table("posts")
        .select("id, content, platform, sentiment, posted_at, engagement_score")
        .eq("author_id", inf.get("platform_user_id"))
        .order("posted_at", desc=True)
        .limit(10)
        .execute()
    ).data or []

    # Activity timeline
    activity = (
        db.table("influencer_activity")
        .select("*")
        .eq("influencer_id", influencer_id)
        .order("bucket", desc=False)
        .limit(30)
        .execute()
    ).data or []

    return {**inf, "recent_posts": posts, "activity_timeline": activity}


@router.patch("/{influencer_id}/flag")
async def flag_influencer(influencer_id: str, reason: str):
    db = get_supabase()
    result = (
        db.table("influencers")
        .update({"is_flagged": True, "flag_reason": reason})
        .eq("id", influencer_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return result.data[0]


@router.patch("/{influencer_id}/unflag")
async def unflag_influencer(influencer_id: str):
    db = get_supabase()
    result = (
        db.table("influencers")
        .update({"is_flagged": False, "flag_reason": None})
        .eq("id", influencer_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return result.data[0]
