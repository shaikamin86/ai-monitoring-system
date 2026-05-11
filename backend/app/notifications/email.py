"""
SMTP email notifier (uses stdlib smtplib via asyncio.to_thread).

Supports:
- TLS STARTTLS on port 587 (default)
- SSL on port 465
- Plain on port 25 (dev/relay only)

No new dependencies — smtplib is part of the Python standard library.
"""
import asyncio
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List

import structlog

from app.core.config import settings

log = structlog.get_logger()

_SEVERITY_COLOR = {
    "critical": "#dc2626",
    "high":     "#ea580c",
    "medium":   "#d97706",
    "low":      "#16a34a",
}
_SEVERITY_BG = {
    "critical": "#fef2f2",
    "high":     "#fff7ed",
    "medium":   "#fffbeb",
    "low":      "#f0fdf4",
}


def _html_body(alert: Dict[str, Any]) -> str:
    severity    = alert.get("severity", "medium")
    title       = alert.get("title", "Alert")
    description = alert.get("description") or ""
    alert_type  = alert.get("alert_type", "").replace("_", " ").title()
    post_count  = alert.get("post_count") or 0
    platforms   = alert.get("affected_platforms") or []
    trigger     = alert.get("trigger_data") or {}
    now_str     = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    color    = _SEVERITY_COLOR.get(severity, "#d97706")
    bg_color = _SEVERITY_BG.get(severity, "#fffbeb")

    platform_html = (
        f"<tr><td style='padding:4px 0;color:#6b7280;'>Platforms</td>"
        f"<td style='padding:4px 8px;'>{', '.join(platforms)}</td></tr>"
        if platforms else ""
    )
    post_count_html = (
        f"<tr><td style='padding:4px 0;color:#6b7280;'>Posts involved</td>"
        f"<td style='padding:4px 8px;'><b>{post_count:,}</b></td></tr>"
        if post_count else ""
    )

    trigger_rows = ""
    for k, v in list(trigger.items())[:6]:
        trigger_rows += (
            f"<tr><td style='padding:2px 0;color:#9ca3af;font-size:12px;'>{k}</td>"
            f"<td style='padding:2px 8px;font-size:12px;'>{v}</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1);">

        <!-- Header -->
        <tr>
          <td style="background:{color};padding:20px 32px;">
            <p style="margin:0;font-size:11px;color:rgba(255,255,255,.8);text-transform:uppercase;letter-spacing:1px;">
              SENTINEL ALERT — {severity.upper()}
            </p>
            <h1 style="margin:6px 0 0;font-size:20px;color:#ffffff;line-height:1.3;">
              {title}
            </h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:24px 32px;background:{bg_color};">
            <p style="margin:0 0 16px;font-size:14px;color:#374151;line-height:1.6;">
              {description}
            </p>
            <table cellpadding="0" cellspacing="0" style="width:100%;font-size:13px;color:#1f2937;">
              <tr>
                <td style="padding:4px 0;color:#6b7280;">Alert Type</td>
                <td style="padding:4px 8px;">{alert_type}</td>
              </tr>
              {post_count_html}
              {platform_html}
              <tr>
                <td style="padding:4px 0;color:#6b7280;">Detected</td>
                <td style="padding:4px 8px;">{now_str}</td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Trigger data -->
        {"<tr><td style='padding:16px 32px;border-top:1px solid #e5e7eb;'><p style='margin:0 0 8px;font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;'>Trigger Details</p><table cellpadding=0 cellspacing=0 style='width:100%;'>" + trigger_rows + "</table></td></tr>" if trigger_rows else ""}

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px;background:#f9fafb;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center;">
              Malaysia AI Social Monitor · SENTINEL Platform<br>
              This is an automated alert. Do not reply to this email.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _plain_body(alert: Dict[str, Any]) -> str:
    lines = [
        f"SENTINEL ALERT — {alert.get('severity','').upper()}",
        "=" * 50,
        f"Title:       {alert.get('title','')}",
        f"Type:        {alert.get('alert_type','').replace('_',' ').title()}",
        f"Description: {alert.get('description') or ''}",
    ]
    if alert.get("post_count"):
        lines.append(f"Posts:       {alert['post_count']:,}")
    if alert.get("affected_platforms"):
        lines.append(f"Platforms:   {', '.join(alert['affected_platforms'])}")
    lines += [
        f"Detected:    {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "-- Malaysia AI Social Monitor",
    ]
    return "\n".join(lines)


def _build_message(
    to_address: str,
    alert: Dict[str, Any],
) -> MIMEMultipart:
    severity = alert.get("severity", "medium")
    subject  = f"[{severity.upper()}] SENTINEL: {alert.get('title', 'Alert')}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = settings.SMTP_FROM or settings.SMTP_USERNAME
    msg["To"]      = to_address

    msg.attach(MIMEText(_plain_body(alert), "plain", "utf-8"))
    msg.attach(MIMEText(_html_body(alert),  "html",  "utf-8"))
    return msg


def _smtp_send(to_address: str, msg: MIMEMultipart) -> None:
    """Blocking SMTP send — called via asyncio.to_thread."""
    host = settings.SMTP_HOST
    port = settings.SMTP_PORT
    user = settings.SMTP_USERNAME
    pwd  = settings.SMTP_PASSWORD

    if port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if user:
                server.login(user, pwd)
            server.sendmail(msg["From"], to_address, msg.as_string())
    else:
        with smtplib.SMTP(host, port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if user:
                server.login(user, pwd)
            server.sendmail(msg["From"], to_address, msg.as_string())


async def send_email_alert(
    recipients: List[str],
    alert: Dict[str, Any],
) -> Dict[str, bool]:
    """
    Send an HTML email alert to every recipient.

    Returns a dict mapping address → success (bool).
    """
    if not settings.SMTP_HOST or not settings.SMTP_USERNAME:
        log.debug("SMTP not configured — skipping email notification")
        return {}

    results: Dict[str, bool] = {}

    for address in recipients:
        try:
            msg = _build_message(address, alert)
            await asyncio.to_thread(_smtp_send, address, msg)
            results[address] = True
            log.info(
                "Email alert sent",
                to=address,
                alert_type=alert.get("alert_type"),
                severity=alert.get("severity"),
            )
        except Exception as exc:
            results[address] = False
            log.error("Email send failed", to=address, error=str(exc))

    return results
