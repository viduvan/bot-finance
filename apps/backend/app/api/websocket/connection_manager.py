"""WebSocket connection manager — broadcast to multiple frontend clients.

Provides a shared manager for pushing real-time events to all
connected authenticated clients.

Event types pushed:
  - proposal_update: when a proposal changes status
  - position_update: unrealized PnL tick for open positions
  - analysis_complete: when a new analysis finishes
  - order_filled: when a paper order is filled
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import structlog
from fastapi import WebSocket

logger = structlog.get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcast logic."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info("ws_connected", total=len(self._connections))

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a disconnected WebSocket."""
        async with self._lock:
            if ws in self._connections:
                self._connections.remove(ws)
        logger.info("ws_disconnected", total=len(self._connections))

    async def broadcast(self, event_type: str, payload: dict[str, Any]) -> None:
        """Broadcast an event to all connected clients.

        Silently removes clients that fail to receive.
        """
        if not self._connections:
            return

        message = json.dumps({"type": event_type, **payload})
        dead: list[WebSocket] = []

        for ws in list(self._connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        # Clean up dead connections
        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_personal(self, ws: WebSocket, event_type: str, payload: dict[str, Any]) -> None:
        """Send an event to a single client."""
        try:
            await ws.send_json({"type": event_type, **payload})
        except Exception as e:
            logger.warning("ws_send_personal_failed", error=str(e))

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton — shared across all WebSocket routes
event_manager = ConnectionManager()
