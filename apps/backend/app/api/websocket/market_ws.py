"""WebSocket endpoint for real-time market data streaming to frontend.

Frontend connects to /api/v1/ws/market and receives:
- ticker updates (price, volume)
- kline updates (candle data)

Authentication via token query parameter.
"""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.security import decode_token
from app.core.exceptions import AuthenticationError
from app.market_data.binance_ws import ws_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.websocket("/market")
async def market_websocket(
    ws: WebSocket,
    token: str = Query(default=""),
) -> None:
    """WebSocket endpoint for real-time market data.

    Frontend connects with: ws://host/api/v1/ws/market?token=JWT_TOKEN

    Messages sent to client:
    - {"type": "ticker", "symbol": "BTCUSDT", "price": "50000.00", ...}
    - {"type": "kline", "symbol": "BTCUSDT", "close": "50000.00", "is_closed": true, ...}
    - {"type": "ping"} — keepalive
    """
    # Authenticate
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

    await ws.accept()
    logger.info("ws_client_connected", user_id=payload.get("sub"))

    # Register client for broadcasts from Binance WS manager
    ws_manager.register_frontend_client(ws)

    try:
        # Send initial connection confirmation
        await ws.send_json({
            "type": "connected",
            "message": "Market data stream active",
        })

        # Keep connection alive with periodic pings
        # Also listen for client messages (e.g. subscribe/unsubscribe)
        while True:
            try:
                # Wait for client messages with timeout for keepalive
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)

                # Handle client commands
                try:
                    msg = json.loads(data)
                    cmd = msg.get("type")

                    if cmd == "ping":
                        await ws.send_json({"type": "pong"})
                    elif cmd == "subscribe":
                        # Future: per-symbol subscription
                        await ws.send_json({"type": "subscribed", "symbols": msg.get("symbols", [])})

                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected", user_id=payload.get("sub"))
    except Exception as e:
        logger.error("ws_client_error", error=str(e))
    finally:
        ws_manager.unregister_frontend_client(ws)
