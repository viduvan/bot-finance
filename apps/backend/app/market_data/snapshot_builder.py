"""Trình tạo ảnh chụp nhanh thị trường (Market snapshot builder).

Tạo các ảnh chụp nhanh thị trường tại một thời điểm từ dữ liệu REST API, kết hợp 
giá ticker, sổ lệnh và dữ liệu nến thành một MarketSnapshot thống nhất.
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
    """Tạo các ảnh chụp nhanh thị trường toàn diện từ dữ liệu Binance."""

    def __init__(self, client: BinanceRestClient) -> None:
        self._client = client

    async def build_snapshot(self, symbol: str) -> dict:
        """Tạo ảnh chụp nhanh thị trường bằng cách lấy dữ liệu ticker và sổ lệnh.

        Trả về một dict sẵn sàng để insert vào model MarketSnapshot.
        """
        import asyncio

        try:
            # Use asyncio.gather instead of create_task — gather works inside
            # both a running loop (FastAPI) and a new loop (_run_async in Celery)
            ticker, book = await asyncio.gather(
                self._client.get_ticker_24h(symbol),
                self._client.get_book_ticker(symbol),
            )
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

        # Kiểm tra tính hợp lệ của dữ liệu snapshot
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
        """Kiểm tra xem ảnh chụp nhanh còn đủ mới để phân tích hay không."""
        timestamp = getattr(snapshot, "timestamp", None) or snapshot.get("timestamp")
        if timestamp is None:
            return False

        age = (datetime.now(UTC) - timestamp).total_seconds()
        return age <= max_age
