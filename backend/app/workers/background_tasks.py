"""
Periodic background tasks: alert checks, narrative clustering,
analytics snapshots, influencer scoring, ingestion scheduler,
and notification dispatch.
"""
import asyncio
from datetime import datetime, timezone
import structlog

log = structlog.get_logger()


async def run_periodic_tasks():
    """Main background task runner. Runs forever."""
    log.info("Background task runner started")

    # Start the ingestion scheduler (APScheduler handles its own timing)
    _start_ingestion_scheduler()

    tasks = [
        _run_every(run_alert_checks,            interval_seconds=60),
        _run_every(run_narrative_clustering,    interval_seconds=300),
        _run_every(run_analytics_snapshot,      interval_seconds=3600),
        _run_every(run_influencer_scoring,      interval_seconds=3600),
        _run_every(run_narrative_status_update, interval_seconds=1800),
        _run_every(run_narrative_merge,         interval_seconds=21600),  # 6 h
    ]
    await asyncio.gather(*tasks)


def _start_ingestion_scheduler() -> None:
    """Start the APScheduler-based ingestion jobs (non-blocking)."""
    try:
        from app.ingestion.scheduler import get_scheduler
        scheduler = get_scheduler()
        scheduler.start()
    except Exception as exc:
        log.error("Failed to start ingestion scheduler", error=str(exc))


async def _run_every(coro_func, interval_seconds: int):
    while True:
        try:
            await coro_func()
        except Exception as e:
            log.error(f"Background task {coro_func.__name__} failed", error=str(e))
        await asyncio.sleep(interval_seconds)


async def run_alert_checks():
    from app.services.alert_service import (
        check_narrative_spikes,
        check_hashtag_surges,
        check_sentiment_shifts,
        check_influencer_amplification,
        check_viral_content,
        check_coordinated_behavior,
    )
    results = await asyncio.gather(
        check_narrative_spikes(),
        check_hashtag_surges(),
        check_sentiment_shifts(),
        check_influencer_amplification(),
        check_viral_content(),
        check_coordinated_behavior(),
        return_exceptions=True,
    )
    total = sum(len(r) for r in results if isinstance(r, list))
    if total > 0:
        log.info("Alert checks completed", alerts_created=total)

    # Dispatch notifications for any new alerts
    try:
        from app.notifications import get_dispatcher
        dispatched = await get_dispatcher().dispatch_new_alerts(since_minutes=3)
        if dispatched > 0:
            log.info("Notifications dispatched", count=dispatched)
    except Exception as exc:
        log.error("Notification dispatch failed", error=str(exc))


async def run_narrative_clustering():
    from app.services.narrative_service import cluster_unassigned_posts
    result = await cluster_unassigned_posts()
    log.info("Narrative clustering done", **result)


async def run_analytics_snapshot():
    from app.services.analytics_service import generate_analytics_snapshot
    await generate_analytics_snapshot()
    log.info("Analytics snapshot generated", ts=datetime.now(timezone.utc).isoformat())


async def run_influencer_scoring():
    from app.services.analytics_service import update_influencer_scores
    await update_influencer_scores()
    log.info("Influencer scores updated")


async def run_narrative_status_update():
    from app.services.narrative_service import update_narrative_statuses
    await update_narrative_statuses()
    log.info("Narrative statuses updated")


async def run_narrative_merge():
    from app.services.narrative_service import merge_related_narratives
    result = await merge_related_narratives()
    log.info("Narrative merge/link pass completed", **result)
