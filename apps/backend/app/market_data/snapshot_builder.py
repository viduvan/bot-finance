"""Market snapshot builder.

Creates point-in-time snapshots from REST API data, combining
ticker, order book, and candle data into a unified MarketSnapshot.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from app.core.constants import MAX_SNAPSHOT_AGE_SECONDS
from app.market_data.binance_rest import BinanceRestClient

logger = structlog.get_logger(__name__)


class SnapshotBuilder:
    """Builds comprehensive market snapshots from Binance data."""

    def __init__(self, client: BinanceRestClient) -> None:
        self._client = client

    async def build_snapshot(self, symbol: str) -> dict:
        """Build a market snapshot by fetching ticker and book data.

        Returns a dict ready for MarketSnapshot model insertion.
        """
        # Fetch ticker and book data concurrently
        import asyncio

        ticker_task = asyncio.create_task(self._client.get_ticker_24h(symbol))
        book_task = asyncio.create_task(self._client.get_book_ticker(symbol))

        try:
            ticker = await ticker_task
            book = await book_task
        except Exception as e:
            logger.error("snapshot_build_failed", symbol=symbol, error=str(e))
            raise

        now = datetime.now(UTC)

        snapshot = {
            "symbol": symbol,
            "timestamp": now,
            "source": "BINANCE",
            "last_price": ticker["price"],
            "best_bid": book["bid"],
            "best_ask": book["ask"],
            "bid_qty": book["bid_qty"],
            "ask_qty": book["ask_qty"],
            "spread_bps": book["spread_bps"],
            "volume_24h": ticker["volume_24h"],
            "quote_volume_24h": ticker["quote_volume_24h"],
            "price_change_24h": ticker["price_change_24h"],
            "price_change_pct_24h": ticker["price_change_pct_24h"],
            "open_24h": ticker["open_price"],
            "high_24h": ticker["high_price"],
            "low_24h": ticker["low_price"],
            "trades_count_24h": ticker["trades_count"],
            "data_quality": "GOOD",
            "is_stale": False,
        }

        # Validate snapshot data
        if snapshot["last_price"] <= 0:
            snapshot["data_quality"] = "BAD"
            logger.warning("snapshot_invalid_price", symbol=symbol, price=snapshot["last_price"])

        if snapshot["spread_bps"] > Decimal("100"):
            snapshot["data_quality"] = "DEGRADED"
            logger.warning("snapshot_wide_spread", symbol=symbol, spread_bps=snapshot["spread_bps"])

        logger.debug(
            "snapshot_built",
            symbol=symbol,
            price=str(snapshot["last_price"]),
            spread_bps=str(snapshot["spread_bps"]),
        )

        return snapshot

    def is_snapshot_fresh(self, snapshot: dict | Any, max_age: float = MAX_SNAPSHOT_AGE_SECONDS) -> bool:
        """Check if a snapshot is still fresh enough for analysis."""
        timestamp = getattr(snapshot, "timestamp", None) or snapshot.get("timestamp")
        if timestamp is None:
            return False

        age = (datetime.now(UTC) - timestamp).total_seconds()
        return age <= max_age
