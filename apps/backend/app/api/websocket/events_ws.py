"""WebSocket endpoint for real-time proposal + system events.

Frontend connects via: ws://host/api/v1/ws/events?token=JWT_TOKEN

Events pushed:
  - {type: "connected"}
  - {type: "proposal_update", proposal: {...}, old_status, new_status}
  - {type: "analysis_complete", symbol, direction, consensus_score, proceed}
  - {type: "order_filled", symbol, side, fill_price, quantity}
  - {type: "position_update", position_id, symbol, unrealized_pnl, current_price}
  - {type: "ping"}
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.websocket.connection_manager import event_manager
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/events")
async def events_websocket(
    ws: WebSocket,
    token: str = Query(default=""),
) -> None:
    """Real-time event stream: proposals, analysis, orders, positions.

    Auth: pass JWT as query param  ?token=<ACCESS_TOKEN>
    """
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await ws.close(code=4001, reason="Invalid token type")
            return
    except AuthenticationError:
        await ws.close(code=4001, reason="Invalid token")
        return

    await event_manager.connect(ws)
    user_id = payload.get("sub", "unknown")
    logger.info("events_ws_connected", user_id=user_id)

    try:
        await event_manager.send_personal(
            ws,
            "connected",
            {
                "message": "ACTA event stream active",
                "user_id": user_id,
            },
        )

        # Keep alive loop
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await event_manager.send_personal(ws, "pong", {})
                except json.JSONDecodeError:
                    pass

            except TimeoutError:
                try:
                    await event_manager.send_personal(ws, "ping", {})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("events_ws_disconnected", user_id=user_id)
    except Exception as e:
        logger.error("events_ws_error", error=str(e), user_id=user_id)
    finally:
        await event_manager.disconnect(ws)
