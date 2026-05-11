"""
Telegram Bot API notifier.

Sends alert messages to one or more Telegram chat IDs / channel usernames.
Uses httpx with a 10-second timeout; failures are logged but never re-raised
so a single bad chat ID cannot block other notification channels.
"""
import html
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
import structlog

from app.core.config import settings

log = structlog.get_logger()

_TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Severity → emoji prefix
_SEVERITY_EMOJI = {
    "critical": "🚨",
    "high":     "⚠️",
    "medium":   "🔔",
    "low":      "ℹ️",
}

# Alert type → display label
_TYPE_LABEL = {
    "narrative_spike":        "Narrative Spike",
    "hashtag_surge":          "Hashtag Surge",
    "sentiment_shift":        "Sentiment Shift",
    "influencer_activity":    "Influencer Alert",
    "viral_content":          "Viral Content",
    "coordinated_behavior":   "Coordinated Activity",
    "keyword_match":          "Watch-Term Match",
    "emerging_narrative":     "Emerging Narrative",
}


def _format_message(alert: Dict[str, Any]) -> str:
    """Build an HTML-formatted Telegram message for the alert."""
    severity    = alert.get("severity", "medium")
    alert_type  = alert.get("alert_type", "")
    title       = html.escape(alert.get("title", "Alert"))
    description = html.escape(alert.get("description") or "")
    post_count  = alert.get("post_count") or 0
    platforms   = alert.get("affected_platforms") or []
    now_str     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    emoji      = _SEVERITY_EMOJI.get(severity, "🔔")
    type_label = _TYPE_LABEL.get(alert_type, alert_type.replace("_", " ").title())
    sev_label  = severity.upper()

    lines = [
        f"{emoji} <b>{sev_label} — {type_label}</b>",
        "",
        f"📌 <b>{title}</b>",
    ]
    if description:
        lines.append(f"📄 {description}")
    if post_count:
        lines.append(f"📊 Posts involved: <b>{post_count:,}</b>")
    if platforms:
        lines.append(f"🌐 Platforms: {', '.join(platforms)}")
    lines += [
        f"🕐 Detected: {now_str}",
        "",
        "<i>#SentinelAlert #MalaysiaMonitor</i>",
    ]
    return "\n".join(lines)


async def send_telegram_alert(
    chat_ids: List[str],
    alert: Dict[str, Any],
) -> Dict[str, bool]:
    """
    Send an alert to every chat ID in the list.

    Returns a dict mapping chat_id → success (bool).
    """
    if not settings.TELEGRAM_BOT_TOKEN:
        log.debug("Telegram token not configured — skipping")
        return {}

    url     = _TELEGRAM_API.format(token=settings.TELEGRAM_BOT_TOKEN)
    message = _format_message(alert)
    results: Dict[str, bool] = {}

    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in chat_ids:
            try:
                resp = await client.post(
                    url,
                    json={
                        "chat_id":    chat_id,
                        "text":       message,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": True,
                    },
                )
                if resp.status_code == 200:
                    results[chat_id] = True
                    log.info(
                        "Telegram alert sent",
                        chat_id=chat_id,
                        alert_type=alert.get("alert_type"),
                        severity=alert.get("severity"),
                    )
                else:
                    results[chat_id] = False
                    log.warning(
                        "Telegram API error",
                        chat_id=chat_id,
                        status=resp.status_code,
                        body=resp.text[:200],
                    )
            except Exception as exc:
                results[chat_id] = False
                log.error("Telegram send failed", chat_id=chat_id, error=str(exc))

    return results
