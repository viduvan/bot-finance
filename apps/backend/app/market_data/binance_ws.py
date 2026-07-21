"""Binance WebSocket manager.

Manages persistent connections to Binance WebSocket streams:
- Kline (candlestick) streams per symbol/timeframe
- Ticker streams for real-time price
- Auto-reconnect with exponential backoff
- Stale data detection
- Broadcast to connected frontend clients
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Callable

import structlog
import websockets
from websockets.exceptions import ConnectionClosed

from app.config import settings
from app.core.constants import WS_MAX_RECONNECT_DELAY, WS_PING_INTERVAL, WS_RECONNECT_DELAY
from app.core.metrics import BINANCE_WS_CONNECTED, MARKET_DATA_STALENESS

logger = structlog.get_logger(__name__)

# Type for callback functions
MessageCallback = Callable[[dict], Any]


class BinanceWebSocketManager:
    """Manages WebSocket connections to Binance streams.

    Handles:
    - Multiple symbol/timeframe subscriptions
    - Auto-reconnect with exponential backoff
    - Heartbeat monitoring (ping/pong)
    - Data staleness detection
    - Callback-based message dispatch
    """

    def __init__(self) -> None:
        self._connections: dict[str, asyncio.Task] = {}
        self._callbacks: dict[str, list[MessageCallback]] = {}
        self._last_message_time: dict[str, datetime] = {}
        self._reconnect_delays: dict[str, float] = {}
        self._running = False
        self._frontend_clients: set[Any] = set()

    @property
    def ws_base_url(self) -> str:
        return settings.binance_active_ws_url

    def _stream_url(self, streams: list[str]) -> str:
        """Build combined stream URL."""
        stream_str = "/".join(streams)
        return f"{self.ws_base_url}/{stream_str}"

    # ── Public API ───────────────────────────────────────────────

    async def start(self, symbols: list[str] | None = None) -> None:
        """Start WebSocket connections for configured symbols."""
        self._running = True
        symbols = symbols or settings.trading_symbols

        for symbol in symbols:
            sym_lower = symbol.lower()
            streams = [
                f"{sym_lower}@kline_15m",
                f"{sym_lower}@kline_1h",
                f"{sym_lower}@kline_4h",
                f"{sym_lower}@miniTicker",
            ]
            task = asyncio.create_task(
                self._connect_and_listen(symbol, streams),
                name=f"ws-{symbol}",
            )
            self._connections[symbol] = task

        logger.info("ws_manager_started", symbols=symbols)
        BINANCE_WS_CONNECTED.set(1)

    async def stop(self) -> None:
        """Stop all WebSocket connections."""
        self._running = False
        for symbol, task in self._connections.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info("ws_connection_stopped", symbol=symbol)

        self._connections.clear()
        BINANCE_WS_CONNECTED.set(0)
        logger.info("ws_manager_stopped")

    def on_kline(self, callback: MessageCallback) -> None:
        """Register callback for kline updates."""
        self._callbacks.setdefault("kline", []).append(callback)

    def on_ticker(self, callback: MessageCallback) -> None:
        """Register callback for ticker updates."""
        self._callbacks.setdefault("ticker", []).append(callback)

    def register_frontend_client(self, ws: Any) -> None:
        """Register a frontend WebSocket client for broadcasts."""
        self._frontend_clients.add(ws)

    def unregister_frontend_client(self, ws: Any) -> None:
        """Unregister a frontend WebSocket client."""
        self._frontend_clients.discard(ws)

    def get_staleness(self, symbol: str) -> float | None:
        """Get seconds since last message for a symbol."""
        last = self._last_message_time.get(symbol)
        if last is None:
            return None
        return (datetime.now(UTC) - last).total_seconds()

    # ── Internal Connection Management ───────────────────────────

    async def _connect_and_listen(self, symbol: str, streams: list[str]) -> None:
        """Connect to WebSocket and listen for messages with auto-reconnect."""
        url = self._stream_url(streams)
        reconnect_delay = WS_RECONNECT_DELAY

        while self._running:
            try:
                logger.info("ws_connecting", symbol=symbol, url=url[:80])

                async with websockets.connect(
                    url,
                    ping_interval=WS_PING_INTERVAL,
                    ping_timeout=10,
                    close_timeout=5,
                    max_size=2**20,  # 1MB max message size
                ) as ws:
                    # Reset reconnect delay on successful connection
                    reconnect_delay = WS_RECONNECT_DELAY
                    self._reconnect_delays[symbol] = reconnect_delay
                    logger.info("ws_connected", symbol=symbol)
                    BINANCE_WS_CONNECTED.set(1)

                    async for raw_msg in ws:
                        try:
                            msg = json.loads(raw_msg)
                            self._last_message_time[symbol] = datetime.now(UTC)
                            MARKET_DATA_STALENESS.labels(symbol=symbol).set(0)
                            await self._dispatch_message(symbol, msg)
                        except json.JSONDecodeError:
                            logger.warning("ws_invalid_json", symbol=symbol)
                        except Exception as e:
                            logger.error("ws_message_error", symbol=symbol, error=str(e))

            except ConnectionClosed as e:
                logger.warning("ws_connection_closed", symbol=symbol, code=e.code, reason=str(e.reason)[:100])
            except asyncio.CancelledError:
                logger.info("ws_connection_cancelled", symbol=symbol)
                return
            except Exception as e:
                logger.error("ws_connection_error", symbol=symbol, error=str(e))

            if not self._running:
                return

            # Exponential backoff reconnect
            BINANCE_WS_CONNECTED.set(0)
            logger.info("ws_reconnecting", symbol=symbol, delay=reconnect_delay)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, WS_MAX_RECONNECT_DELAY)

    async def _dispatch_message(self, symbol: str, msg: dict) -> None:
        """Parse and dispatch a WebSocket message to registered callbacks."""
        # Combined stream format: {"stream": "btcusdt@kline_15m", "data": {...}}
        data = msg.get("data", msg)
        event_type = data.get("e", "")

        if event_type == "kline":
            parsed = self._parse_kline(symbol, data)
            for cb in self._callbacks.get("kline", []):
                try:
                    result = cb(parsed)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error("kline_callback_error", error=str(e))

            # Broadcast to frontend clients
            await self._broadcast_to_frontend({
                "type": "kline",
                "symbol": symbol,
                "timeframe": parsed["timeframe"],
                "open": str(parsed["open"]),
                "high": str(parsed["high"]),
                "low": str(parsed["low"]),
                "close": str(parsed["close"]),
                "volume": str(parsed["volume"]),
                "is_closed": parsed["is_closed"],
                "timestamp": parsed["close_time"].isoformat(),
            })

        elif event_type == "24hrMiniTicker":
            parsed = self._parse_mini_ticker(symbol, data)
            for cb in self._callbacks.get("ticker", []):
                try:
                    result = cb(parsed)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error("ticker_callback_error", error=str(e))

            # Broadcast to frontend
            await self._broadcast_to_frontend({
                "type": "ticker",
                "symbol": symbol,
                "price": str(parsed["close"]),
                "volume_24h": str(parsed["quote_volume"]),
                "timestamp": datetime.now(UTC).isoformat(),
            })

    def _parse_kline(self, symbol: str, data: dict) -> dict:
        """Parse a kline WebSocket message into standardized format."""
        k = data["k"]
        return {
            "symbol": symbol,
            "timeframe": k["i"],
            "open_time": datetime.fromtimestamp(k["t"] / 1000, tz=UTC),
            "close_time": datetime.fromtimestamp(k["T"] / 1000, tz=UTC),
            "open": Decimal(str(k["o"])),
            "high": Decimal(str(k["h"])),
            "low": Decimal(str(k["l"])),
            "close": Decimal(str(k["c"])),
            "volume": Decimal(str(k["v"])),
            "quote_volume": Decimal(str(k["q"])),
            "trades_count": int(k["n"]),
            "is_closed": k["x"],  # True when candle is finalized
        }

    def _parse_mini_ticker(self, symbol: str, data: dict) -> dict:
        """Parse a 24hr mini ticker message."""
        return {
            "symbol": symbol,
            "close": Decimal(str(data["c"])),
            "open": Decimal(str(data["o"])),
            "high": Decimal(str(data["h"])),
            "low": Decimal(str(data["l"])),
            "volume": Decimal(str(data["v"])),
            "quote_volume": Decimal(str(data["q"])),
            "timestamp": datetime.fromtimestamp(data["E"] / 1000, tz=UTC),
        }

    async def _broadcast_to_frontend(self, message: dict) -> None:
        """Broadcast a message to all connected frontend WebSocket clients."""
        if not self._frontend_clients:
            return

        payload = json.dumps(message)
        disconnected = set()

        for client in self._frontend_clients:
            try:
                await client.send_text(payload)
            except Exception:
                disconnected.add(client)

        # Cleanup disconnected clients
        self._frontend_clients -= disconnected


# Singleton instance
ws_manager = BinanceWebSocketManager()
