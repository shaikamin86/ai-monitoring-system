"""
Notification dispatcher.

Routing model:
  1. Load active notification_channels from DB (cached for 5 min).
  2. For each new alert, find matching channels (severity ≥ min_severity,
     alert_type in allowed list or list is empty).
  3. Dedup: skip if a notification_history row exists for this
     alert_id + channel_id (prevents re-notifying on restart/retry).
  4. Send via the appropriate notifier (Telegram / Email / Webhook).
  5. Write a notification_history row for audit.
  6. Always broadcast over WebSocket.

The dispatcher is a lightweight singleton — no global state beyond a
tiny channel cache.  All IO is async.
"""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import structlog

from app.core.config import settings
from app.core.database import get_supabase

log = structlog.get_logger()

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}

# Simple in-process cache: (channels_list, expires_at)
_channel_cache: tuple = (None, None)  # (List[Dict] | None, datetime | None)
_CACHE_TTL_SECONDS = 300


class NotificationDispatcher:

    # ── Public API ────────────────────────────────────────────────────────

    async def dispatch_new_alerts(self, since_minutes: int = 3) -> int:
        """
        Pull alerts created in the last `since_minutes` minutes that have
        not yet been dispatched, send notifications, and return the count.

        Called from the 60-second background task loop.
        """
        db = get_supabase()
        cutoff = (
            datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        ).isoformat()

        # Fetch recent alerts
        alerts_result = (
            db.table("alerts")
            .select("*")
            .gte("created_at", cutoff)
            .eq("status", "active")
            .order("created_at", desc=False)
            .execute()
        )
        alerts = alerts_result.data or []
        if not alerts:
            return 0

        # IDs already dispatched (any channel) in this window
        already_ids_result = (
            db.table("notification_history")
            .select("alert_id")
            .gte("sent_at", cutoff)
            .in_("status", ["sent", "suppressed"])
            .execute()
        )
        already_notified = {
            r["alert_id"] for r in (already_ids_result.data or [])
        }

        new_alerts = [a for a in alerts if a["id"] not in already_notified]
        if not new_alerts:
            return 0

        dispatched = 0
        for alert in new_alerts:
            await self._dispatch_one(db, alert)
            dispatched += 1

        return dispatched

    async def dispatch_single(self, alert: Dict[str, Any]) -> None:
        """Dispatch a specific alert immediately (used by API trigger endpoint)."""
        db = get_supabase()
        await self._dispatch_one(db, alert)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _dispatch_one(self, db, alert: Dict[str, Any]) -> None:
        # 1. WebSocket broadcast (always, never suppressed)
        await _broadcast_ws(alert)

        # 2. Load active channels (cached)
        channels = await _load_channels(db)
        if not channels:
            return

        severity_rank = _SEVERITY_RANK.get(alert.get("severity", "medium"), 1)
        alert_type    = alert.get("alert_type", "")

        for channel in channels:
            # Severity gate
            min_rank = _SEVERITY_RANK.get(channel.get("min_severity", "high"), 2)
            if severity_rank < min_rank:
                continue

            # Alert-type filter (empty list = allow all)
            allowed_types: List[str] = channel.get("alert_types") or []
            if allowed_types and alert_type not in allowed_types:
                continue

            # Per-channel dedup (skip for synthetic env channels — no real UUID)
            channel_id_str = str(channel["id"])
            if not channel_id_str.startswith("__env_"):
                if _already_dispatched(db, alert["id"], channel_id_str):
                    continue

            # Send
            success, error = await _send_to_channel(channel, alert)

            # Record history (synthetic env channels have no real UUID)
            real_channel_id = (
                None if str(channel["id"]).startswith("__env_")
                else channel["id"]
            )
            _record_history(
                db,
                alert_id=alert["id"],
                channel_id=real_channel_id,
                channel_type=channel["channel_type"],
                channel_target=_channel_target(channel),
                status="sent" if success else "failed",
                error_message=error,
            )


# ── Module-level helpers ─────────────────────────────────────────────────────

def _settings_channels() -> List[Dict]:
    """
    Synthesise notification channels from environment config.

    TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS produce one virtual channel per
    chat ID, scoped to narrative_spike alerts at TELEGRAM_MIN_SEVERITY.
    These run alongside any DB-configured channels without replacing them.
    """
    channels: List[Dict] = []
    if not settings.TELEGRAM_BOT_TOKEN:
        return channels
    try:
        chat_ids: List[str] = json.loads(settings.TELEGRAM_CHAT_IDS)
    except Exception:
        chat_ids = []
    for chat_id in chat_ids:
        channels.append({
            # Synthetic ID — stable per chat_id so dedup keys are consistent
            "id":           f"__env_telegram_{chat_id}",
            "channel_type": "telegram",
            "channel_name": f"Telegram {chat_id} (env)",
            "config":       {"chat_id": chat_id},
            "min_severity": settings.TELEGRAM_MIN_SEVERITY,
            # Restrict to narrative spikes; extend the list here to cover more
            "alert_types":  ["narrative_spike"],
            "is_active":    True,
        })
    return channels


async def _load_channels(db) -> List[Dict]:
    """Return active channels; refreshes cache every 5 minutes."""
    global _channel_cache
    cached_list, expires_at = _channel_cache
    if cached_list is not None and expires_at and datetime.now(timezone.utc) < expires_at:
        return cached_list

    try:
        result = (
            db.table("notification_channels")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        db_channels = result.data or []
    except Exception:
        db_channels = []

    channels = db_channels + _settings_channels()
    _channel_cache = (
        channels,
        datetime.now(timezone.utc) + timedelta(seconds=_CACHE_TTL_SECONDS),
    )
    return channels


def _already_dispatched(db, alert_id: str, channel_id: str) -> bool:
    result = (
        db.table("notification_history")
        .select("id")
        .eq("alert_id", alert_id)
        .eq("channel_id", channel_id)
        .in_("status", ["sent", "suppressed"])
        .limit(1)
        .execute()
    )
    return bool(result.data)


def _channel_target(channel: Dict) -> Optional[str]:
    cfg = channel.get("config") or {}
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    return cfg.get("chat_id") or cfg.get("address") or cfg.get("url")


def _record_history(
    db,
    *,
    alert_id: str,
    channel_id: Optional[str],
    channel_type: str,
    channel_target: Optional[str],
    status: str,
    error_message: Optional[str] = None,
) -> None:
    try:
        db.table("notification_history").insert({
            "alert_id":       alert_id,
            "channel_id":     channel_id,
            "channel_type":   channel_type,
            "channel_target": channel_target,
            "status":         status,
            "error_message":  error_message,
        }).execute()
    except Exception as exc:
        log.warning("Failed to record notification history", error=str(exc))


async def _send_to_channel(
    channel: Dict[str, Any],
    alert: Dict[str, Any],
) -> tuple[bool, Optional[str]]:
    """Dispatch to a single channel; returns (success, error_str|None)."""
    channel_type = channel.get("channel_type", "")
    cfg = channel.get("config") or {}
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}

    try:
        if channel_type == "telegram":
            chat_id = cfg.get("chat_id", "")
            if not chat_id:
                return False, "No chat_id configured"
            from app.notifications.telegram import send_telegram_alert
            results = await send_telegram_alert([chat_id], alert)
            ok = results.get(chat_id, False)
            return ok, None if ok else "Telegram API error"

        elif channel_type == "email":
            address = cfg.get("address", "")
            if not address:
                return False, "No email address configured"
            from app.notifications.email import send_email_alert
            results = await send_email_alert([address], alert)
            ok = results.get(address, False)
            return ok, None if ok else "SMTP error"

        elif channel_type == "webhook":
            url = cfg.get("url", "")
            if not url:
                return False, "No webhook URL configured"
            import httpx
            headers: Dict[str, str] = {"Content-Type": "application/json"}
            if cfg.get("secret"):
                headers["X-Sentinel-Secret"] = cfg["secret"]
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=alert, headers=headers)
                if resp.status_code < 300:
                    return True, None
                return False, f"HTTP {resp.status_code}"

        else:
            return False, f"Unknown channel type: {channel_type}"

    except Exception as exc:
        return False, str(exc)


async def _broadcast_ws(alert: Dict[str, Any]) -> None:
    try:
        from app.api.routes.websocket import broadcast
        await broadcast("new_alert", alert)
    except Exception as exc:
        log.debug("WS broadcast failed", error=str(exc))
