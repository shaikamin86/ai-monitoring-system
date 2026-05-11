"""
Ingestion job scheduler.

Uses APScheduler (AsyncIOScheduler) so all collectors share the same
asyncio event loop as FastAPI — no extra processes or threads needed.

Schedule (default):
  RSS         every 10 min   — high-frequency; no API key needed
  Twitter/X   every  5 min   — search API, 15 req/15 min window
  Facebook    every 15 min   — Graph API, 200 calls/hour
  TikTok      every 30 min   — Research API, 1 000 calls/day

Each job:
  1. Calls collector.run_once()
  2. run_once() handles rate limiting, circuit breaker, and retry
  3. Errors are caught and logged; the scheduler keeps running

The scheduler exposes a thin status API used by /api/v1/ingestion/status.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.ingestion.facebook import FacebookCollector
from app.ingestion.rss import RSSCollector
from app.ingestion.tiktok import TikTokCollector
from app.ingestion.twitter import TwitterCollector

log = structlog.get_logger()

# ── Job definitions ───────────────────────────────────────────────────────────
# Each entry drives one APScheduler job.
def _job_configs() -> List[Dict[str, Any]]:
    """Build job config list from live settings (allows env overrides)."""
    return [
        {
            "id": "ingest_rss",
            "collector_cls": RSSCollector,
            "interval_minutes": settings.INGESTION_RSS_INTERVAL_MIN,
            "enabled_setting": None,
            "description": "RSS / Atom news feeds",
        },
        {
            "id": "ingest_twitter",
            "collector_cls": TwitterCollector,
            "interval_minutes": settings.INGESTION_TWITTER_INTERVAL_MIN,
            "enabled_setting": "TWITTER_BEARER_TOKEN",
            "description": "Twitter/X recent search",
        },
        {
            "id": "ingest_facebook",
            "collector_cls": FacebookCollector,
            "interval_minutes": settings.INGESTION_FACEBOOK_INTERVAL_MIN,
            "enabled_setting": "FACEBOOK_ACCESS_TOKEN",
            "description": "Facebook public pages",
        },
        {
            "id": "ingest_tiktok",
            "collector_cls": TikTokCollector,
            "interval_minutes": settings.INGESTION_TIKTOK_INTERVAL_MIN,
            "enabled_setting": "TIKTOK_CLIENT_KEY",
            "description": "TikTok Research API",
        },
    ]


# Module-level alias used by the API route
JOB_CONFIGS: List[Dict[str, Any]] = []  # populated on first start()


class IngestionScheduler:
    """
    Wraps APScheduler and manages collector lifecycles.

    Usage (inside FastAPI lifespan):
        scheduler = IngestionScheduler()
        scheduler.start()
        # ... app runs ...
        scheduler.stop()
    """

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone="UTC")
        self._collectors: Dict[str, Any] = {}
        self._job_stats: Dict[str, Dict[str, Any]] = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        global JOB_CONFIGS
        if not settings.INGESTION_ENABLED:
            log.info("Ingestion disabled via INGESTION_ENABLED=false")
            return

        JOB_CONFIGS = _job_configs()
        redis_url = settings.REDIS_URL
        registered = 0

        for cfg in JOB_CONFIGS:
            # Skip if the platform requires a credential that isn't set
            cred_key = cfg["enabled_setting"]
            if cred_key and not getattr(settings, cred_key, ""):
                log.info(
                    "Ingestion job disabled (missing credential)",
                    job=cfg["id"],
                    missing=cred_key,
                )
                continue

            collector = cfg["collector_cls"](redis_url)
            self._collectors[cfg["id"]] = collector
            self._job_stats[cfg["id"]] = {
                "description": cfg["description"],
                "interval_minutes": cfg["interval_minutes"],
                "last_run": None,
                "last_status": None,
                "runs_total": 0,
                "errors_total": 0,
            }

            self._scheduler.add_job(
                self._run_job,
                trigger=IntervalTrigger(minutes=cfg["interval_minutes"]),
                id=cfg["id"],
                name=cfg["description"],
                kwargs={"job_id": cfg["id"]},
                # Coalesce: if a run is missed, only fire once on recovery
                coalesce=True,
                # Don't start a new run if the previous one is still going
                max_instances=1,
                # Fire first run 30 s after startup (stagger them slightly)
                next_run_time=_stagger_start(registered * 8),
            )
            registered += 1
            log.info(
                "Ingestion job registered",
                job=cfg["id"],
                every_minutes=cfg["interval_minutes"],
            )

        if registered:
            self._scheduler.start()
            log.info("Ingestion scheduler started", jobs=registered)
        else:
            log.warning(
                "Ingestion scheduler: no jobs enabled "
                "(check TWITTER_BEARER_TOKEN, FACEBOOK_ACCESS_TOKEN, etc.)"
            )

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("Ingestion scheduler stopped")

    # ── Job runner ─────────────────────────────────────────────────────────────

    async def _run_job(self, job_id: str) -> None:
        collector = self._collectors.get(job_id)
        if not collector:
            return

        stats = self._job_stats[job_id]
        stats["last_run"] = datetime.now(timezone.utc).isoformat()
        stats["runs_total"] += 1

        log.info("Ingestion job starting", job=job_id)
        try:
            result = await collector.run_once()
            stats["last_status"] = result.get("status", "ok")
            log.info("Ingestion job complete", job=job_id, **result)
        except Exception as exc:
            stats["last_status"] = "error"
            stats["errors_total"] += 1
            log.error("Ingestion job failed", job=job_id, error=str(exc))

    # ── Manual trigger ─────────────────────────────────────────────────────────

    async def trigger(self, job_id: str) -> Dict[str, Any]:
        """Immediately run one collector outside its normal schedule."""
        if job_id not in self._collectors:
            # Try to initialise it on-demand (e.g. if it was skipped at start)
            matched = [c for c in JOB_CONFIGS if c["id"] == job_id]
            if not matched:
                return {"error": f"Unknown job: {job_id}"}
            cfg = matched[0]
            collector = cfg["collector_cls"](settings.REDIS_URL)
            self._collectors[job_id] = collector
            self._job_stats[job_id] = {
                "description": cfg["description"],
                "interval_minutes": cfg["interval_minutes"],
                "last_run": None,
                "last_status": None,
                "runs_total": 0,
                "errors_total": 0,
            }

        log.info("Manual ingestion trigger", job=job_id)
        try:
            result = await self._collectors[job_id].run_once()
            self._job_stats[job_id]["last_run"] = datetime.now(timezone.utc).isoformat()
            self._job_stats[job_id]["last_status"] = result.get("status", "ok")
            self._job_stats[job_id]["runs_total"] += 1
            return result
        except Exception as exc:
            self._job_stats[job_id]["errors_total"] += 1
            return {"error": str(exc)}

    # ── Status reporting ───────────────────────────────────────────────────────

    async def status(self) -> List[Dict[str, Any]]:
        """Return rich status for every configured job (enabled or not)."""
        rows: List[Dict[str, Any]] = []

        for cfg in JOB_CONFIGS:
            job_id = cfg["id"]
            enabled = job_id in self._collectors
            sched_job = self._scheduler.get_job(job_id) if self._scheduler.running else None

            # Pull platform-level stats from Redis
            redis_stats: Dict[str, str] = {}
            if enabled:
                try:
                    stats_obj = await self._collectors[job_id]._get_stats()
                    redis_stats = await stats_obj.get_all()
                except Exception:
                    pass

            in_mem = self._job_stats.get(job_id, {})
            rows.append(
                {
                    "job_id": job_id,
                    "description": cfg["description"],
                    "platform": cfg["collector_cls"].platform.value,
                    "enabled": enabled,
                    "interval_minutes": cfg["interval_minutes"],
                    "next_run": (
                        sched_job.next_run_time.isoformat()
                        if sched_job and sched_job.next_run_time
                        else None
                    ),
                    "last_run": in_mem.get("last_run"),
                    "last_status": in_mem.get("last_status"),
                    "runs_total": in_mem.get("runs_total", 0),
                    "errors_total": in_mem.get("errors_total", 0),
                    "posts_collected_total": int(
                        redis_stats.get("posts_collected_total", 0)
                    ),
                    "posts_ingested_total": int(
                        redis_stats.get("posts_ingested_total", 0)
                    ),
                    "rate_limit_hits": int(
                        redis_stats.get("rate_limit_hits", 0)
                    ),
                    "circuit_state": redis_stats.get("circuit_state", "closed"),
                }
            )

        return rows


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stagger_start(offset_seconds: int) -> datetime:
    """Return a datetime `offset_seconds` from now (UTC)."""
    from datetime import timedelta
    return datetime.now(timezone.utc) + timedelta(seconds=30 + offset_seconds)


# ── Singleton ─────────────────────────────────────────────────────────────────

_scheduler_instance: Optional[IngestionScheduler] = None


def get_scheduler() -> IngestionScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = IngestionScheduler()
    return _scheduler_instance
