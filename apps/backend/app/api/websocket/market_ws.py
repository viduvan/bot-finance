"""Endpoint WebSocket cho luồng dữ liệu thị trường trực tiếp tới frontend.

Frontend kết nối tới /api/v1/ws/market và nhận được:
- cập nhật ticker (giá, khối lượng)
- cập nhật kline (dữ liệu nến)

Xác thực thông qua tham số truy vấn (query parameter) token.
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
    """Endpoint WebSocket cho dữ liệu thị trường thời gian thực.

    Frontend kết nối qua: ws://host/api/v1/ws/market?token=JWT_TOKEN

    Tin nhắn gửi cho client:
    - {"type": "ticker", "symbol": "BTCUSDT", "price": "50000.00", ...}
    - {"type": "kline", "symbol": "BTCUSDT", "close": "50000.00", "is_closed": true, ...}
    - {"type": "ping"} — giữ kết nối (keepalive)
    """
    # Xác thực (Authenticate)
    if not token:
        await ws.close(code=4001, reason="Thiếu token (Missing token)")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await ws.close(code=4001, reason="Loại token không hợp lệ")
            return
    except AuthenticationError:
        await ws.close(code=4001, reason="Token không hợp lệ (Invalid token)")
        return

    await ws.accept()
    logger.info("ws_client_connected", user_id=payload.get("sub"))

    # Đăng ký client để nhận broadcast từ Binance WS manager
    ws_manager.register_frontend_client(ws)

    try:
        # Gửi xác nhận kết nối ban đầu
        await ws.send_json({
            "type": "connected",
            "message": "Luồng dữ liệu thị trường đã kích hoạt",
        })

        # Giữ kết nối (Keepalive) bằng các ping định kỳ
        # Đồng thời lắng nghe các tin nhắn từ client (vd: subscribe/unsubscribe)
        while True:
            try:
                # Chờ tin nhắn từ client kèm theo timeout để gửi keepalive
                data = await asyncio.wait_for(ws.receive_text(), timeout=30.0)

                # Xử lý các lệnh từ client
                try:
                    msg = json.loads(data)
                    cmd = msg.get("type")

                    if cmd == "ping":
                        await ws.send_json({"type": "pong"})
                    elif cmd == "subscribe":
                        # Tương lai: đăng ký theo từng cặp tiền (per-symbol)
                        await ws.send_json({"type": "subscribed", "symbols": msg.get("symbols", [])})

                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Gửi ping giữ kết nối
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
