"""Dịch vụ dữ liệu thị trường — Lớp điều phối (orchestration layer).

Phối hợp giữa REST client, WebSocket manager, repository, validator, và 
snapshot builder để cung cấp một API dữ liệu thị trường thống nhất.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import ENTRY_TIMEFRAME, MACRO_TREND_TIMEFRAME, TREND_CONFIRMATION_TIMEFRAME
from app.core.exceptions import StaleDataError
from app.core.metrics import MARKET_DATA_STALENESS
from app.market_data.binance_rest import BinanceRestClient, binance_client
from app.market_data.binance_ws import ws_manager
from app.market_data.data_validator import DataValidator, data_validator, TIMEFRAME_INTERVALS
from app.market_data.snapshot_builder import SnapshotBuilder
from app.repositories.market_repo import MarketDataRepository

logger = structlog.get_logger(__name__)


class MarketDataService:
    """Dịch vụ dữ liệu thị trường cấp cao.

    Cung cấp:
    - Tải dữ liệu ban đầu và điền dữ liệu còn thiếu (backfill)
    - Lưu trữ và truy xuất nến (candles)
    - Quản lý ảnh chụp nhanh (snapshot)
    - Giám sát chất lượng dữ liệu
    - Phát hiện khoảng trống (gaps) và điền bổ sung
    """

    def __init__(
        self,
        db: AsyncSession,
        client: BinanceRestClient | None = None,
        validator: DataValidator | None = None,
    ) -> None:
        self._client = client or binance_client
        self._repo = MarketDataRepository(db)
        self._validator = validator or data_validator
        self._snapshot_builder = SnapshotBuilder(self._client)
        self.db = db

    # ── Tải dữ liệu ban đầu ────────────────────────────────────────

    async def fetch_and_store_candles(
        self,
        symbol: str,
        timeframe: str = ENTRY_TIMEFRAME,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Lấy nến từ Binance REST API và lưu vào cơ sở dữ liệu.

        Trả về dict chứa số lượng (count) và báo cáo chất lượng (quality report).
        """
        # Chuyển đổi datetime sang timestamp millisecond
        start_ms = int(start_time.timestamp() * 1000) if start_time else None
        end_ms = int(end_time.timestamp() * 1000) if end_time else None

        candles = await self._client.get_klines(
            symbol=symbol,
            interval=timeframe,
            limit=limit,
            start_time=start_ms,
            end_time=end_ms,
        )

        if not candles:
            return {"count": 0, "quality": {"is_healthy": False, "warnings": ["Không có dữ liệu trả về"]}}

        # Kiểm tra chất lượng dữ liệu
        quality = self._validator.validate_candles(candles, symbol, timeframe)

        # Lưu vào cơ sở dữ liệu
        count = await self._repo.upsert_candles(symbol, timeframe, candles)

        logger.info(
            "candles_fetched_and_stored",
            symbol=symbol,
            timeframe=timeframe,
            count=count,
            gaps=quality.get("gap_count", 0),
            healthy=quality["is_healthy"],
        )

        return {"count": count, "quality": quality}

    async def initial_data_load(self, symbol: str) -> dict:
        """Tải dữ liệu lịch sử ban đầu cho một cặp giao dịch trên tất cả các khung thời gian.

        Tải về 500 nến mỗi khung thời gian (mới nhất).
        """
        timeframes = [ENTRY_TIMEFRAME, TREND_CONFIRMATION_TIMEFRAME, MACRO_TREND_TIMEFRAME]
        results = {}

        for tf in timeframes:
            result = await self.fetch_and_store_candles(symbol, tf, limit=500)
            results[tf] = result

        logger.info("initial_data_load_complete", symbol=symbol, timeframes=list(results.keys()))
        return results

    # ── Truy xuất Nến ────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = ENTRY_TIMEFRAME,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list:
        """Lấy dữ liệu nến từ cơ sở dữ liệu."""
        return list(
            await self._repo.get_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
                start_time=start_time,
                end_time=end_time,
            )
        )

    async def get_latest_price(self, symbol: str) -> dict:
        """Lấy giá mới nhất từ Binance REST API."""
        return await self._client.get_ticker_price(symbol)

    # ── Ảnh chụp nhanh (Snapshots) ────────────────────────────────────────────────

    async def build_and_save_snapshot(self, symbol: str) -> dict:
        """Tạo một ảnh chụp nhanh thị trường mới và lưu vào cơ sở dữ liệu."""
        snapshot_data = await self._snapshot_builder.build_snapshot(symbol)
        snapshot = await self._repo.save_snapshot(snapshot_data)
        await self.db.commit()
        return snapshot_data

    async def get_latest_snapshot(self, symbol: str) -> dict | None:
        """Lấy ảnh chụp nhanh mới nhất cho một cặp giao dịch."""
        snapshot = await self._repo.get_latest_snapshot(symbol)
        if snapshot is None:
            return None
        return {
            "id": str(snapshot.id),
            "symbol": snapshot.symbol,
            "timestamp": snapshot.timestamp,
            "source": snapshot.source,
            "last_price": snapshot.last_price,
            "best_bid": snapshot.best_bid,
            "best_ask": snapshot.best_ask,
            "bid_qty": snapshot.bid_qty,
            "ask_qty": snapshot.ask_qty,
            "spread_bps": snapshot.spread_bps,
            "volume_24h": snapshot.volume_24h,
            "is_stale": snapshot.is_stale,
        }

    # ── Sổ lệnh (Order Book) ───────────────────────────────────────────────

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Lấy độ sâu sổ lệnh từ Binance."""
        return await self._client.get_depth(symbol, limit=limit)

    # ── Chất lượng dữ liệu ─────────────────────────────────────────────

    async def check_data_quality(self, symbol: str, timeframe: str = ENTRY_TIMEFRAME) -> dict:
        """Kiểm tra chất lượng dữ liệu cho một cặp giao dịch/khung thời gian."""
        # Lấy các nến gần đây
        candles = await self._repo.get_candles(symbol, timeframe, limit=200)
        candle_dicts = [
            {
                "open_time": c.open_time,
                "close_time": c.close_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]

        quality = self._validator.validate_candles(candle_dicts, symbol, timeframe)

        # Thêm thông tin về độ trễ (staleness)
        latest = await self._repo.get_latest_candle(symbol, timeframe)
        staleness = self._validator.check_staleness(
            latest.open_time if latest else None, symbol
        )

        # Cập nhật Prometheus metric
        if staleness["staleness_seconds"] is not None:
            MARKET_DATA_STALENESS.labels(symbol=symbol).set(staleness["staleness_seconds"])

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **quality,
            "staleness": staleness,
        }

    # ── Bổ sung khoảng trống (Gap Backfill) ─────────────────────────────────────────────

    async def backfill_gaps(self, symbol: str, timeframe: str, hours_back: int = 24) -> dict:
        """Phát hiện và điền các khoảng trống (gaps) trong dữ liệu nến.

        Lấy các nến bị thiếu từ Binance REST API.
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours_back)

        # Lấy các nến hiện có
        candles = await self._repo.get_candles(symbol, timeframe, limit=2000, start_time=start_time)
        candle_dicts = [{"open_time": c.open_time} for c in candles]

        # Tìm khoảng trống
        gaps = self._validator.find_gaps(candle_dicts, timeframe, start_time, end_time)

        if not gaps:
            return {"gaps_found": 0, "candles_backfilled": 0}

        total_backfilled = 0

        for gap in gaps:
            gap_start = gap["start"]
            gap_end = gap["end"]

            start_ms = int(gap_start.timestamp() * 1000)
            end_ms = int(gap_end.timestamp() * 1000)

            try:
                fill_candles = await self._client.get_klines(
                    symbol=symbol,
                    interval=timeframe,
                    start_time=start_ms,
                    end_time=end_ms,
                    limit=1000,
                )
                if fill_candles:
                    count = await self._repo.upsert_candles(symbol, timeframe, fill_candles)
                    total_backfilled += count

            except Exception as e:
                logger.error("backfill_gap_failed", symbol=symbol, gap_start=str(gap_start), error=str(e))

        logger.info(
            "backfill_complete",
            symbol=symbol,
            timeframe=timeframe,
            gaps_found=len(gaps),
            candles_backfilled=total_backfilled,
        )

        return {"gaps_found": len(gaps), "candles_backfilled": total_backfilled}

    # ── Thông tin sàn (Exchange Info) ────────────────────────────────────────────

    async def get_symbol_info(self, symbol: str) -> dict:
        """Lấy quy tắc giao dịch của một cặp tiền."""
        return await self._client.get_exchange_info(symbol)

    # ── Dọn dẹp (Cleanup) ──────────────────────────────────────────────────

    async def cleanup_old_data(self, days: int = 90) -> dict:
        """Xóa dữ liệu nến cũ hơn N ngày."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        results = {}
        for symbol in settings.trading_symbols:
            for tf in [ENTRY_TIMEFRAME, TREND_CONFIRMATION_TIMEFRAME, MACRO_TREND_TIMEFRAME]:
                deleted = await self._repo.delete_old_candles(symbol, tf, cutoff)
                if deleted:
                    results[f"{symbol}/{tf}"] = deleted

        if results:
            logger.info("old_data_cleaned", results=results)
        return results
