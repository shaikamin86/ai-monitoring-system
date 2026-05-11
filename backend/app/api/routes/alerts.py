"""
Alerts REST API.

Endpoints:
  GET  /alerts                    — list/filter alerts
  GET  /alerts/{id}               — single alert
  PATCH /alerts/{id}              — acknowledge / resolve / add notes
  POST /alerts/run-checks         — manually trigger all detectors
  POST /alerts/test-notification  — send a test message to all active channels

  GET  /alerts/channels           — list notification channels
  POST /alerts/channels           — create a channel
  PATCH /alerts/channels/{id}     — update a channel
  DELETE /alerts/channels/{id}    — delete a channel
  POST /alerts/channels/{id}/test — test a single channel
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.database import get_supabase
from app.models.alert import AlertListResponse, AlertUpdateRequest
import structlog

router = APIRouter(prefix="/alerts", tags=["alerts"])
log = structlog.get_logger()


# ── Alert list (fixed path must precede /{alert_id}) ─────────────────────────

@router.get("", response_model=AlertListResponse)
async def list_alerts(
    status: Optional[str]     = None,
    severity: Optional[str]   = None,
    alert_type: Optional[str] = None,
    limit: int                = Query(default=20, le=100),
    offset: int               = 0,
):
    db = get_supabase()
    query = db.table("alerts").select("*")

    if status:
        query = query.eq("status", status)
    if severity:
        query = query.eq("severity", severity)
    if alert_type:
        query = query.eq("alert_type", alert_type)

    result   = query.order("created_at", desc=True).limit(limit).offset(offset).execute()
    total    = db.table("alerts").select("id", count="exact").execute()
    critical = db.table("alerts").select("id", count="exact").eq("status", "active").eq("severity", "critical").execute()
    high     = db.table("alerts").select("id", count="exact").eq("status", "active").eq("severity", "high").execute()

    return AlertListResponse(
        alerts=result.data or [],
        total=total.count or 0,
        active_critical=critical.count or 0,
        active_high=high.count or 0,
    )


@router.post("/run-checks")
async def run_alert_checks():
    """Manually trigger all six alert detectors."""
    from app.services.alert_service import (
        check_narrative_spikes,
        check_hashtag_surges,
        check_sentiment_shifts,
        check_influencer_amplification,
        check_viral_content,
        check_coordinated_behavior,
    )
    import asyncio

    results = await asyncio.gather(
        check_narrative_spikes(),
        check_hashtag_surges(),
        check_sentiment_shifts(),
        check_influencer_amplification(),
        check_viral_content(),
        check_coordinated_behavior(),
        return_exceptions=True,
    )
    labels = [
        "narrative_spikes", "hashtag_surges", "sentiment_shifts",
        "influencer_amplification", "viral_content", "coordinated_behavior",
    ]
    details = {
        labels[i]: results[i] if isinstance(results[i], list) else []
        for i in range(len(labels))
    }
    total = sum(len(v) for v in details.values())

    # Dispatch notifications for newly created alerts
    try:
        from app.notifications import get_dispatcher
        dispatched = await get_dispatcher().dispatch_new_alerts(since_minutes=1)
    except Exception:
        dispatched = 0

    return {
        "alerts_created": total,
        "notifications_dispatched": dispatched,
        "details": details,
    }


# ── Test notification ─────────────────────────────────────────────────────────

@router.post("/test-notification")
async def test_notification():
    """Send a test alert to all active notification channels."""
    test_alert: Dict[str, Any] = {
        "id":           "test-00000000-0000-0000-0000-000000000000",
        "title":        "SENTINEL Test Notification",
        "description":  "This is a test message from the Malaysia AI Social Monitor.",
        "severity":     "medium",
        "status":       "active",
        "alert_type":   "keyword_match",
        "source_id":    None,
        "source_type":  None,
        "trigger_data": {"note": "Manual test from /alerts/test-notification"},
        "affected_platforms": [],
        "post_count":   0,
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }

    db = get_supabase()
    channels = (
        db.table("notification_channels")
        .select("*")
        .eq("is_active", True)
        .execute()
    ).data or []

    if not channels:
        return {"message": "No active notification channels configured", "sent": 0}

    from app.notifications.dispatcher import _send_to_channel
    sent = failed = 0
    errors: List[str] = []

    for ch in channels:
        ok, err = await _send_to_channel(ch, test_alert)
        if ok:
            sent += 1
        else:
            failed += 1
            if err:
                errors.append(f"{ch['channel_name']}: {err}")

    return {
        "channels_tested": len(channels),
        "sent": sent,
        "failed": failed,
        "errors": errors,
    }


# ── Notification history ──────────────────────────────────────────────────────

@router.get("/history")
async def notification_history(
    limit: int = Query(default=50, le=200),
    offset: int = 0,
):
    db = get_supabase()
    result = (
        db.table("notification_history")
        .select("*")
        .order("sent_at", desc=True)
        .limit(limit)
        .offset(offset)
        .execute()
    )
    return result.data or []


# ── Notification channel CRUD ─────────────────────────────────────────────────

class ChannelCreate(BaseModel):
    channel_type: str = Field(..., pattern="^(telegram|email|webhook)$")
    channel_name: str
    config: Dict[str, Any] = {}
    min_severity: str = Field(default="high", pattern="^(low|medium|high|critical)$")
    alert_types: List[str] = []
    is_active: bool = True


class ChannelUpdate(BaseModel):
    channel_name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    min_severity: Optional[str] = Field(default=None, pattern="^(low|medium|high|critical)$")
    alert_types: Optional[List[str]] = None
    is_active: Optional[bool] = None


@router.get("/channels", response_model=List[Dict[str, Any]])
async def list_channels():
    db = get_supabase()
    result = (
        db.table("notification_channels")
        .select("id, channel_type, channel_name, min_severity, alert_types, is_active, created_at")
        .order("created_at")
        .execute()
    )
    # Omit raw config (may contain secrets) from list response
    return result.data or []


@router.post("/channels", status_code=201)
async def create_channel(body: ChannelCreate):
    db = get_supabase()
    result = db.table("notification_channels").insert(body.model_dump()).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create channel")
    # Invalidate cache
    _invalidate_channel_cache()
    return result.data[0]


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: str, body: ChannelUpdate):
    db = get_supabase()
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update fields provided")
    result = db.table("notification_channels").update(update_data).eq("id", channel_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")
    _invalidate_channel_cache()
    return result.data[0]


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: str):
    db = get_supabase()
    result = db.table("notification_channels").delete().eq("id", channel_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")
    _invalidate_channel_cache()


@router.post("/channels/{channel_id}/test")
async def test_channel(channel_id: str):
    """Send a test message to a specific notification channel."""
    db = get_supabase()
    result = db.table("notification_channels").select("*").eq("id", channel_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Channel not found")

    test_alert: Dict[str, Any] = {
        "id":           f"test-{channel_id[:8]}",
        "title":        "SENTINEL Channel Test",
        "description":  f"Test from channel \"{result.data['channel_name']}\".",
        "severity":     "medium",
        "alert_type":   "keyword_match",
        "trigger_data": {"channel_id": channel_id},
        "affected_platforms": [],
        "post_count":   0,
        "created_at":   datetime.now(timezone.utc).isoformat(),
    }

    from app.notifications.dispatcher import _send_to_channel
    ok, error = await _send_to_channel(result.data, test_alert)
    return {
        "channel_id":   channel_id,
        "channel_name": result.data["channel_name"],
        "success":      ok,
        "error":        error,
    }


# ── Single-alert routes (parameterized — must come after all fixed paths) ─────

@router.get("/{alert_id}")
async def get_alert(alert_id: str):
    db = get_supabase()
    result = db.table("alerts").select("*").eq("id", alert_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result.data


@router.patch("/{alert_id}")
async def update_alert(alert_id: str, req: AlertUpdateRequest):
    db = get_supabase()
    update_data = req.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update fields provided")

    if req.status == "acknowledged" and req.acknowledged_by:
        update_data["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    elif req.status == "resolved":
        update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()

    result = db.table("alerts").update(update_data).eq("id", alert_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result.data[0]


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _invalidate_channel_cache() -> None:
    """Reset the in-process channel cache after a mutation."""
    try:
        import app.notifications.dispatcher as _disp
        _disp._channel_cache = (None, None)
    except Exception:
        pass
