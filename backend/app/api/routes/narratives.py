from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from app.models.narrative import NarrativeListResponse, NarrativeDetailResponse
from app.core.database import get_supabase
import structlog

router = APIRouter(prefix="/narratives", tags=["narratives"])
log = structlog.get_logger()


@router.get("", response_model=NarrativeListResponse)
async def list_narratives(
    status: Optional[str] = None,
    min_threat: Optional[int] = None,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    sort_by: str = "virality_score",
):
    db = get_supabase()
    query = db.table("narratives").select("*")

    if status:
        query = query.eq("status", status)
    if min_threat is not None:
        query = query.gte("threat_level", min_threat)

    allowed_sorts = ["virality_score", "threat_level", "post_count", "last_activity", "first_detected"]
    if sort_by not in allowed_sorts:
        sort_by = "virality_score"

    result = query.order(sort_by, desc=True).limit(limit).offset(offset).execute()
    all_result = db.table("narratives").select("id", count="exact").execute()

    return NarrativeListResponse(
        narratives=result.data or [],
        total=all_result.count or 0,
    )


@router.get("/{narrative_id}", response_model=NarrativeDetailResponse)
async def get_narrative(narrative_id: str):
    db = get_supabase()
    result = db.table("narratives").select("*").eq("id", narrative_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Narrative not found")

    narrative = result.data

    # Timeline
    timeline = (
        db.table("narrative_timeline")
        .select("*")
        .eq("narrative_id", narrative_id)
        .order("bucket", desc=False)
        .execute()
    ).data or []

    # Sample posts
    post_ids_result = (
        db.table("post_narratives")
        .select("post_id, similarity_score")
        .eq("narrative_id", narrative_id)
        .order("similarity_score", desc=True)
        .limit(10)
        .execute()
    ).data or []

    sample_posts = []
    for item in post_ids_result[:5]:
        post_result = (
            db.table("posts")
            .select("id, content, platform, author_username, sentiment, posted_at, engagement_score")
            .eq("id", item["post_id"])
            .single()
            .execute()
        )
        if post_result.data:
            sample_posts.append({**post_result.data, "similarity": item["similarity_score"]})

    # Related narratives (same themes)
    related = (
        db.table("narratives")
        .select("id, title, status, post_count, threat_level")
        .neq("id", narrative_id)
        .in_("status", ["emerging", "active"])
        .order("virality_score", desc=True)
        .limit(3)
        .execute()
    ).data or []

    return {
        **narrative,
        "timeline": timeline,
        "sample_posts": sample_posts,
        "related_narratives": related,
    }


@router.get("/{narrative_id}/posts")
async def get_narrative_posts(
    narrative_id: str,
    limit: int = Query(default=20, le=100),
    offset: int = 0,
):
    db = get_supabase()
    post_ids = (
        db.table("post_narratives")
        .select("post_id, similarity_score")
        .eq("narrative_id", narrative_id)
        .order("similarity_score", desc=True)
        .limit(limit)
        .offset(offset)
        .execute()
    ).data or []

    posts = []
    for item in post_ids:
        result = (
            db.table("posts")
            .select("id, content, platform, author_username, sentiment, posted_at, engagement_score, url")
            .eq("id", item["post_id"])
            .single()
            .execute()
        )
        if result.data:
            posts.append({**result.data, "similarity": item["similarity_score"]})

    return {"posts": posts, "narrative_id": narrative_id}
