"""Repository dữ liệu thị trường — Các thao tác CRUD cho nến và ảnh chụp nhanh (snapshots).

Repository bất đồng bộ sử dụng SQLAlchemy để lưu trữ và truy vấn dữ liệu thị trường.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Sequence

import structlog
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.market import MarketCandle, MarketSnapshot

logger = structlog.get_logger(__name__)


class MarketDataRepository:
    """Repository cho dữ liệu nến và ảnh chụp nhanh thị trường."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Nến (Candles) ───────────────────────────────────────────────────

    async def upsert_candles(self, symbol: str, timeframe: str, candles: list[dict]) -> int:
        """Cập nhật hoặc chèn (upsert) hàng loạt nến (insert hoặc update khi trùng lặp).

        Sử dụng PostgreSQL ON CONFLICT DO UPDATE để đảm bảo ghi idempotent.
        Trả về số lượng hàng bị ảnh hưởng.
        """
        if not candles:
            return 0

        values = []
        for c in candles:
            values.append({
                "symbol": symbol,
                "timeframe": timeframe,
                "open_time": c["open_time"],
                "close_time": c["close_time"],
                "open": c["open"],
                "high": c["high"],
                "low": c["low"],
                "close": c["close"],
                "volume": c["volume"],
                "quote_volume": c.get("quote_volume"),
                "trades_count": c.get("trades_count"),
                "source": c.get("source", "BINANCE"),
            })

        stmt = pg_insert(MarketCandle).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "open_time"],
            set_={
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "quote_volume": stmt.excluded.quote_volume,
                "trades_count": stmt.excluded.trades_count,
            },
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        count = result.rowcount or len(values)
        logger.debug("candles_upserted", symbol=symbol, timeframe=timeframe, count=count)
        return count

    async def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Sequence[MarketCandle]:
        """Lấy danh sách nến sắp xếp theo thời gian mở cửa (open_time) giảm dần."""
        query = (
            select(MarketCandle)
            .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
            .order_by(MarketCandle.open_time.desc())
            .limit(limit)
        )

        if start_time:
            query = query.where(MarketCandle.open_time >= start_time)
        if end_time:
            query = query.where(MarketCandle.open_time <= end_time)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_latest_candle(self, symbol: str, timeframe: str) -> MarketCandle | None:
        """Lấy cây nến gần nhất cho một cặp giao dịch/khung thời gian."""
        result = await self.db.execute(
            select(MarketCandle)
            .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
            .order_by(MarketCandle.open_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_candles(
        self, symbol: str, timeframe: str, start_time: datetime, end_time: datetime
    ) -> int:
        """Đếm số lượng nến trong một khoảng thời gian."""
        result = await self.db.execute(
            select(func.count())
            .select_from(MarketCandle)
            .where(
                MarketCandle.symbol == symbol,
                MarketCandle.timeframe == timeframe,
                MarketCandle.open_time >= start_time,
                MarketCandle.open_time <= end_time,
            )
        )
        return result.scalar() or 0

    async def delete_old_candles(self, symbol: str, timeframe: str, before: datetime) -> int:
        """Xóa các nến cũ hơn một thời điểm nhất định."""
        result = await self.db.execute(
            delete(MarketCandle).where(
                MarketCandle.symbol == symbol,
                MarketCandle.timeframe == timeframe,
                MarketCandle.open_time < before,
            )
        )
        await self.db.commit()
        return result.rowcount or 0

    # ── Ảnh chụp nhanh (Snapshots) ────────────────────────────────────────────────

    async def save_snapshot(self, snapshot_data: dict) -> MarketSnapshot:
        """Lưu một ảnh chụp nhanh thị trường."""
        snapshot = MarketSnapshot(**snapshot_data)
        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_latest_snapshot(self, symbol: str) -> MarketSnapshot | None:
        """Lấy ảnh chụp nhanh mới nhất cho một cặp giao dịch."""
        result = await self.db.execute(
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_snapshots(
        self,
        symbol: str,
        limit: int = 20,
        start_time: datetime | None = None,
    ) -> Sequence[MarketSnapshot]:
        """Lấy danh sách các ảnh chụp nhanh gần đây cho một cặp giao dịch."""
        query = (
            select(MarketSnapshot)
            .where(MarketSnapshot.symbol == symbol)
            .order_by(MarketSnapshot.timestamp.desc())
            .limit(limit)
        )
        if start_time:
            query = query.where(MarketSnapshot.timestamp >= start_time)

        result = await self.db.execute(query)
        return result.scalars().all()
