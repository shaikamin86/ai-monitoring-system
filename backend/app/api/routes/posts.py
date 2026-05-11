from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from app.models.post import PostIngest, PostSearchRequest, PostSearchResponse, PostResponse
from app.services.ingestion_service import ingest_post, ingest_batch
from app.services.embedding_service import generate_embedding
from app.core.database import get_supabase
import structlog

router = APIRouter(prefix="/posts", tags=["posts"])
log = structlog.get_logger()


@router.post("/ingest", status_code=202)
async def ingest_single_post(post: PostIngest, background_tasks: BackgroundTasks):
    """Ingest a single social media post."""
    background_tasks.add_task(_run_clustering_if_needed)
    result = await ingest_post(post)
    if result is None:
        return {"status": "skipped", "reason": "duplicate"}
    return {"status": "accepted", "post_id": result["id"]}


@router.post("/ingest/batch", status_code=202)
async def ingest_batch_posts(posts: List[PostIngest], background_tasks: BackgroundTasks):
    """Ingest a batch of posts (max 500)."""
    if len(posts) > 500:
        raise HTTPException(status_code=400, detail="Max 500 posts per batch")
    result = await ingest_batch(posts)
    background_tasks.add_task(_run_clustering_if_needed)
    return result


@router.post("/search", response_model=PostSearchResponse)
async def search_posts(req: PostSearchRequest):
    """Search posts with full-text, filters, and semantic search."""
    db = get_supabase()

    query = db.table("posts").select(
        "id, external_id, platform, content, author_username, author_display_name, "
        "author_followers, author_verified, url, language, sentiment, sentiment_score, "
        "engagement_score, likes_count, shares_count, comments_count, views_count, "
        "posted_at, collected_at"
    )

    if req.platforms:
        query = query.in_("platform", [p.value for p in req.platforms])
    if req.languages:
        query = query.in_("language", [l.value for l in req.languages])
    if req.sentiments:
        query = query.in_("sentiment", [s.value for s in req.sentiments])
    if req.date_from:
        query = query.gte("posted_at", req.date_from.isoformat())
    if req.date_to:
        query = query.lte("posted_at", req.date_to.isoformat())
    if req.min_engagement:
        query = query.gte("engagement_score", req.min_engagement)
    if req.author_username:
        query = query.ilike("author_username", f"%{req.author_username}%")
    if req.query:
        query = query.ilike("content", f"%{req.query}%")

    # Semantic search using embedding similarity
    if req.semantic_query:
        embedding = await generate_embedding(req.semantic_query)
        result = db.rpc(
            "match_posts",
            {
                "query_embedding": embedding,
                "match_threshold": 0.75,
                "match_count": req.limit,
            },
        ).execute()
        posts = result.data or []
        return PostSearchResponse(posts=posts, total=len(posts), limit=req.limit, offset=0)

    count_result = query.execute()
    total = len(count_result.data or [])

    result = query.order("posted_at", desc=True).limit(req.limit).offset(req.offset).execute()

    return PostSearchResponse(
        posts=result.data or [],
        total=total,
        limit=req.limit,
        offset=req.offset,
    )


@router.get("/{post_id}")
async def get_post(post_id: str):
    db = get_supabase()
    result = db.table("posts").select("*").eq("id", post_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Post not found")

    # Fetch related
    hashtags = db.table("post_hashtags").select("hashtags(tag)").eq("post_id", post_id).execute()
    entities = db.table("post_entities").select("entities(name, type)").eq("post_id", post_id).execute()
    narratives = db.table("post_narratives").select("narrative_id, similarity_score").eq("post_id", post_id).execute()

    return {
        **result.data,
        "hashtags": [r["hashtags"]["tag"] for r in (hashtags.data or []) if r.get("hashtags")],
        "entities": [r["entities"] for r in (entities.data or []) if r.get("entities")],
        "narratives": narratives.data or [],
    }


async def _run_clustering_if_needed():
    """Trigger narrative clustering in background."""
    from app.services.narrative_service import cluster_unassigned_posts
    try:
        result = await cluster_unassigned_posts()
        log.info("Clustering completed", **result)
    except Exception as e:
        log.error("Clustering failed", error=str(e))
