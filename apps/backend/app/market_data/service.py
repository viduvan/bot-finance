"""Market data service — orchestration layer.

Coordinates between REST client, WebSocket manager, repository,
validator, and snapshot builder to provide a unified market data API.
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
    """High-level market data service.

    Provides:
    - Initial data fetch and backfill
    - Candle storage and retrieval
    - Snapshot management
    - Data quality monitoring
    - Gap detection and backfill
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

    # ── Initial Data Load ────────────────────────────────────────

    async def fetch_and_store_candles(
        self,
        symbol: str,
        timeframe: str = ENTRY_TIMEFRAME,
        limit: int = 500,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Fetch candles from Binance REST API and store in database.

        Returns dict with count and quality report.
        """
        # Convert datetime to millisecond timestamps
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
            return {"count": 0, "quality": {"is_healthy": False, "warnings": ["No data returned"]}}

        # Validate data quality
        quality = self._validator.validate_candles(candles, symbol, timeframe)

        # Store in database
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
        """Load initial historical data for a symbol across all timeframes.

        Fetches 500 candles per timeframe (most recent).
        """
        timeframes = [ENTRY_TIMEFRAME, TREND_CONFIRMATION_TIMEFRAME, MACRO_TREND_TIMEFRAME]
        results = {}

        for tf in timeframes:
            result = await self.fetch_and_store_candles(symbol, tf, limit=500)
            results[tf] = result

        logger.info("initial_data_load_complete", symbol=symbol, timeframes=list(results.keys()))
        return results

    # ── Candle Access ────────────────────────────────────────────

    async def get_candles(
        self,
        symbol: str,
        timeframe: str = ENTRY_TIMEFRAME,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list:
        """Get candles from database."""
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
        """Get latest price from Binance REST API."""
        return await self._client.get_ticker_price(symbol)

    # ── Snapshots ────────────────────────────────────────────────

    async def build_and_save_snapshot(self, symbol: str) -> dict:
        """Build a fresh market snapshot and save it to the database."""
        snapshot_data = await self._snapshot_builder.build_snapshot(symbol)
        snapshot = await self._repo.save_snapshot(snapshot_data)
        await self.db.commit()
        return snapshot_data

    async def get_latest_snapshot(self, symbol: str) -> dict | None:
        """Get the most recent snapshot for a symbol."""
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

    # ── Order Book ───────────────────────────────────────────────

    async def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Get order book depth from Binance."""
        return await self._client.get_depth(symbol, limit=limit)

    # ── Data Quality ─────────────────────────────────────────────

    async def check_data_quality(self, symbol: str, timeframe: str = ENTRY_TIMEFRAME) -> dict:
        """Check data quality for a symbol/timeframe combination."""
        # Get recent candles
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

        # Add staleness info
        latest = await self._repo.get_latest_candle(symbol, timeframe)
        staleness = self._validator.check_staleness(
            latest.open_time if latest else None, symbol
        )

        # Update Prometheus metric
        if staleness["staleness_seconds"] is not None:
            MARKET_DATA_STALENESS.labels(symbol=symbol).set(staleness["staleness_seconds"])

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            **quality,
            "staleness": staleness,
        }

    # ── Gap Backfill ─────────────────────────────────────────────

    async def backfill_gaps(self, symbol: str, timeframe: str, hours_back: int = 24) -> dict:
        """Detect and backfill gaps in candle data.

        Fetches missing candles from Binance REST API.
        """
        end_time = datetime.now(UTC)
        start_time = end_time - timedelta(hours=hours_back)

        # Get existing candles
        candles = await self._repo.get_candles(symbol, timeframe, limit=2000, start_time=start_time)
        candle_dicts = [{"open_time": c.open_time} for c in candles]

        # Find gaps
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

    # ── Exchange Info ────────────────────────────────────────────

    async def get_symbol_info(self, symbol: str) -> dict:
        """Get trading rules for a symbol."""
        return await self._client.get_exchange_info(symbol)

    # ── Cleanup ──────────────────────────────────────────────────

    async def cleanup_old_data(self, days: int = 90) -> dict:
        """Remove candle data older than N days."""
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
