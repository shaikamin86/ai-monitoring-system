"""
WebSocket endpoint for real-time dashboard updates.
Broadcasts new alerts, narrative changes, and post metrics.
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.database import get_supabase
import structlog

router = APIRouter(tags=["websocket"])
log = structlog.get_logger()

_connections: Set[WebSocket] = set()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    log.info("WebSocket connected", total=len(_connections))

    try:
        # Send initial state
        await _send_initial_state(websocket)

        # Keep alive with periodic updates
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "ts": datetime.now(timezone.utc).isoformat()})
            except asyncio.TimeoutError:
                # Send periodic update
                await _send_live_update(websocket)
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        _connections.discard(websocket)
        log.info("WebSocket disconnected", total=len(_connections))


async def broadcast(event_type: str, data: dict):
    """Broadcast an event to all connected clients."""
    if not _connections:
        return
    message = json.dumps({"type": event_type, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    _connections -= dead


async def _send_initial_state(websocket: WebSocket):
    from app.services.analytics_service import get_dashboard_metrics
    try:
        metrics = await get_dashboard_metrics()
        await websocket.send_json({
            "type": "initial_state",
            "data": metrics,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        log.error("Failed to send initial state", error=str(e))


async def _send_live_update(websocket: WebSocket):
    db = get_supabase()
    try:
        # Send latest alert count
        active_alerts = db.table("alerts").select("id", count="exact").eq("status", "active").execute()
        critical = db.table("alerts").select("id", count="exact").eq("status", "active").eq("severity", "critical").execute()

        await websocket.send_json({
            "type": "metrics_update",
            "data": {
                "active_alerts": active_alerts.count or 0,
                "critical_alerts": critical.count or 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        log.error("Failed to send live update", error=str(e))
