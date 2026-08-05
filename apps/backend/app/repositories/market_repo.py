"""Repository dữ liệu thị trường — Các thao tác CRUD cho nến và ảnh chụp nhanh (snapshots).

Repository bất đồng bộ sử dụng SQLAlchemy để lưu trữ và truy vấn dữ liệu thị trường.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

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
            values.append(
                {
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
                }
            )

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

    async def get_candle_count_by_timeframe(self, symbol: str) -> dict[str, int]:
        """Đếm số lượng nến hiện có trong DB cho mỗi timeframe.

        Trả về dict: {'15m': 500, '1h': 250, '4h': 120}
        """
        result = await self.db.execute(
            select(MarketCandle.timeframe, func.count().label("cnt"))
            .where(MarketCandle.symbol == symbol)
            .group_by(MarketCandle.timeframe)
        )
        return {row.timeframe: row.cnt for row in result.all()}

    async def get_candle_time_range(
        self, symbol: str, timeframe: str
    ) -> dict[str, datetime | None]:
        """Lấy thời gian nến cũ nhất và mới nhất trong DB.

        Trả về dict: {'oldest': datetime, 'newest': datetime, 'count': int}
        """
        result = await self.db.execute(
            select(
                func.min(MarketCandle.open_time).label("oldest"),
                func.max(MarketCandle.open_time).label("newest"),
                func.count().label("count"),
            ).where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
        )
        row = result.one_or_none()
        if row is None:
            return {"oldest": None, "newest": None, "count": 0}
        return {
            "oldest": row.oldest,
            "newest": row.newest,
            "count": row.count or 0,
        }

    async def get_candles_paginated(
        self,
        symbol: str,
        timeframe: str,
        before_time: datetime | None = None,
        limit: int = 500,
    ) -> Sequence[MarketCandle]:
        """Lấy nến với pagination theo thời gian (dùng để lazy load chart).

        - Không có before_time: lấy `limit` nến MỚI NHẤT (desc) — dùng cho initial load
        - Có before_time: lấy `limit` nến CŨ HƠN before_time (asc) — dùng cho lazy load quá khứ
        """
        if before_time:
            # Lazy load: lấy nến cũ hơn before_time, sắp xếp cũ→mới để chart append đúng
            query = (
                select(MarketCandle)
                .where(
                    MarketCandle.symbol == symbol,
                    MarketCandle.timeframe == timeframe,
                    MarketCandle.open_time < before_time,
                )
                .order_by(MarketCandle.open_time.asc())
                .limit(limit)
            )
        else:
            # Initial load: lấy nến mới nhất trước, rồi đảo ngược để chart nhận đúng thứ tự cũ→mới
            query = (
                select(MarketCandle)
                .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == timeframe)
                .order_by(MarketCandle.open_time.desc())
                .limit(limit)
            )

        result = await self.db.execute(query)
        candles = list(result.scalars().all())

        # Đảo ngược khi initial load để đảm bảo thứ tự cũ→mới cho chart
        if not before_time:
            candles.reverse()

        return candles

    # ── Ảnh chụp nhanh (Snapshots) ────────────────────────────────────────────────

    async def save_snapshot(self, snapshot_data: dict) -> MarketSnapshot:
        """Lưu một ảnh chụp nhanh thị trường."""
        # Filter to only known model columns — builder may return extra fields
        # (e.g. quote_volume_24h, price_change_24h) that aren't in the ORM model
        valid_fields = {c.key for c in MarketSnapshot.__table__.columns}
        filtered = {k: v for k, v in snapshot_data.items() if k in valid_fields}
        snapshot = MarketSnapshot(**filtered)
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
