"""
Ingestion management API.

Endpoints:
  GET  /ingestion/status          — health + per-job stats for all collectors
  POST /ingestion/trigger/{job}   — fire a collector immediately (manual run)
  GET  /ingestion/sources         — list configured ingestion sources in DB
  POST /ingestion/sources         — add a new source (RSS feed / FB page)
  DELETE /ingestion/sources/{id}  — remove a source

These endpoints are intentionally minimal — the scheduler does the
heavy lifting.  Authentication is handled by the upstream API gateway
(internal use only in production; exposed only when DEBUG=True or via
internal network).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, HttpUrl

from app.core.database import get_supabase
from app.ingestion.scheduler import get_scheduler
import structlog

log = structlog.get_logger()
router = APIRouter(prefix="/ingestion", tags=["ingestion"])


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def ingestion_status() -> Dict[str, Any]:
    """Return scheduler state and per-collector stats."""
    scheduler = get_scheduler()

    # Gather rich stats per job
    jobs: List[Dict[str, Any]] = []
    for cfg_stat in await _simple_status(scheduler):
        jobs.append(cfg_stat)

    enabled = sum(1 for j in jobs if j["enabled"])
    return {
        "scheduler_running": scheduler._scheduler.running,
        "jobs_enabled": enabled,
        "jobs_total": len(jobs),
        "jobs": jobs,
    }


async def _simple_status(scheduler) -> List[Dict[str, Any]]:
    """Build per-job status rows without the broken .then() call."""
    from app.ingestion.scheduler import JOB_CONFIGS
    from datetime import timezone, datetime

    rows: List[Dict[str, Any]] = []
    for cfg in JOB_CONFIGS:
        job_id = cfg["id"]
        enabled = job_id in scheduler._collectors
        sched_job = (
            scheduler._scheduler.get_job(job_id)
            if scheduler._scheduler.running else None
        )
        in_mem = scheduler._job_stats.get(job_id, {})

        # Fetch Redis stats for enabled collectors
        redis_stats: Dict[str, str] = {}
        if enabled:
            try:
                stats_tracker = await scheduler._collectors[job_id]._get_stats()
                redis_stats = await stats_tracker.get_all()
            except Exception:
                pass

        rows.append({
            "job_id": job_id,
            "description": cfg["description"],
            "platform": cfg["collector_cls"].platform.value,
            "enabled": enabled,
            "interval_minutes": cfg["interval_minutes"],
            "next_run": (
                sched_job.next_run_time.isoformat()
                if sched_job and sched_job.next_run_time else None
            ),
            "last_run": in_mem.get("last_run"),
            "last_status": in_mem.get("last_status"),
            "runs_total": in_mem.get("runs_total", 0),
            "errors_total": in_mem.get("errors_total", 0),
            "posts_collected_total": int(redis_stats.get("posts_collected_total", 0)),
            "posts_ingested_total": int(redis_stats.get("posts_ingested_total", 0)),
            "rate_limit_hits": int(redis_stats.get("rate_limit_hits", 0)),
            "circuit_state": redis_stats.get("circuit_state", "closed"),
            "last_error": redis_stats.get("last_error"),
        })

    return rows


# ── Manual trigger ────────────────────────────────────────────────────────────

VALID_JOB_IDS = {"ingest_rss", "ingest_twitter", "ingest_facebook", "ingest_tiktok"}


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str) -> Dict[str, Any]:
    """
    Immediately run the named collector once, outside its schedule.

    Returns the result dict from run_once().
    """
    if job_id not in VALID_JOB_IDS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown job '{job_id}'. Valid: {sorted(VALID_JOB_IDS)}",
        )

    scheduler = get_scheduler()
    log.info("Manual ingestion trigger via API", job=job_id)
    result = await scheduler.trigger(job_id)

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return result


# ── Ingestion sources CRUD ────────────────────────────────────────────────────

class SourceCreate(BaseModel):
    platform: str           # "news" | "facebook" | "twitter" etc.
    source_name: str
    config: Dict[str, Any]  # platform-specific config (feed_url, page_id, …)
    is_active: bool = True


class SourceResponse(BaseModel):
    id: str
    platform: str
    source_name: str
    config: Dict[str, Any]
    is_active: bool
    created_at: str


@router.get("/sources", response_model=List[SourceResponse])
async def list_sources(platform: Optional[str] = None) -> List[SourceResponse]:
    db = get_supabase()
    q = db.table("ingestion_sources").select("*").order("created_at", desc=True)
    if platform:
        q = q.eq("platform", platform)
    result = q.execute()
    return result.data or []


@router.post("/sources", response_model=SourceResponse, status_code=201)
async def create_source(body: SourceCreate) -> SourceResponse:
    """
    Add a new data source.

    Examples:

    RSS feed:
      { "platform": "news", "source_name": "Harakah Daily",
        "config": { "feed_url": "https://harakahdaily.net/feed/", "source_name": "Harakah" } }

    Facebook page:
      { "platform": "facebook", "source_name": "Parti Amanah",
        "config": { "page_id": "partiamanahnegara", "page_name": "Amanah" } }
    """
    db = get_supabase()
    result = db.table("ingestion_sources").insert({
        "platform": body.platform,
        "source_name": body.source_name,
        "config": body.config,
        "is_active": body.is_active,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create source")

    return result.data[0]


@router.patch("/sources/{source_id}")
async def toggle_source(
    source_id: str,
    is_active: bool = Body(..., embed=True),
) -> Dict[str, Any]:
    db = get_supabase()
    result = (
        db.table("ingestion_sources")
        .update({"is_active": is_active})
        .eq("id", source_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Source not found")
    return {"id": source_id, "is_active": is_active}


@router.delete("/sources/{source_id}", status_code=204, response_model=None)
async def delete_source(source_id: str):
    db = get_supabase()
    db.table("ingestion_sources").delete().eq("id", source_id).execute()


# ── Rate-limit state inspection ───────────────────────────────────────────────

@router.get("/rate-limits")
async def rate_limit_state() -> Dict[str, Any]:
    """
    Return remaining call budget for each platform rate limiter.
    Useful for ops dashboards.
    """
    import redis.asyncio as aioredis
    from app.core.config import settings
    from app.ingestion.base import RateLimiter

    configs = [
        ("twitter",  "twitter:search",   14,  900),
        ("tiktok",   "tiktok:research",  950, 86400),
        ("facebook", "facebook:graph",   160, 3600),
        ("rss",      "rss:fetch",         30,    60),
    ]

    r = await aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    result: Dict[str, Any] = {}
    try:
        for platform, ns, max_calls, window in configs:
            limiter = RateLimiter(r, ns, max_calls, window)
            remaining = await limiter.remaining()
            result[platform] = {
                "remaining": remaining,
                "limit": max_calls,
                "window_seconds": window,
                "pct_used": round((1 - remaining / max_calls) * 100, 1),
            }
    finally:
        await r.aclose()

    return result
