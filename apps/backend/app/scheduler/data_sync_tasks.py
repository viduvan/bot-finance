"""Celery tasks for market data synchronization.

Scheduled tasks:
- Periodic candle sync (every 15 min)
- Market snapshot refresh (every 60 sec)
- Data gap backfill (every hour)
- Old data cleanup (daily)
"""

from __future__ import annotations

import asyncio

import structlog

from app.config import settings
from app.scheduler.worker import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async function in a new event loop (for sync Celery workers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="market.sync_candles", max_retries=2, default_retry_delay=30)
def sync_candles_task(self, symbol: str | None = None, timeframe: str = "15m") -> dict:
    """Fetch latest candles from Binance and store in database.

    Runs every 15 minutes via Celery Beat.
    """
    async def _sync():
        from app.database.session import async_session_factory
        from app.market_data.service import MarketDataService

        symbols = [symbol] if symbol else settings.trading_symbols

        results = {}
        async with async_session_factory() as db:
            service = MarketDataService(db)
            for sym in symbols:
                try:
                    result = await service.fetch_and_store_candles(sym, timeframe, limit=50)
                    results[sym] = {"count": result["count"], "healthy": result["quality"]["is_healthy"]}
                except Exception as e:
                    logger.error("candle_sync_failed", symbol=sym, error=str(e))
                    results[sym] = {"error": str(e)}

        return results

    try:
        return _run_async(_sync())
    except Exception as e:
        logger.error("sync_candles_failed", error=str(e))
        raise self.retry(exc=e)


@celery_app.task(bind=True, name="market.refresh_snapshots", max_retries=2, default_retry_delay=10)
def refresh_snapshots_task(self) -> dict:
    """Refresh market snapshots for all symbols.

    Runs every 60 seconds via Celery Beat.
    """
    async def _refresh():
        from app.database.session import async_session_factory
        from app.market_data.service import MarketDataService

        results = {}
        async with async_session_factory() as db:
            service = MarketDataService(db)
            for symbol in settings.trading_symbols:
                try:
                    snapshot = await service.build_and_save_snapshot(symbol)
                    results[symbol] = {
                        "price": str(snapshot["last_price"]),
                        "spread_bps": str(snapshot["spread_bps"]),
                    }
                except Exception as e:
                    logger.error("snapshot_refresh_failed", symbol=symbol, error=str(e))
                    results[symbol] = {"error": str(e)}

        return results

    try:
        return _run_async(_refresh())
    except Exception as e:
        logger.error("refresh_snapshots_failed", error=str(e))
        raise self.retry(exc=e)


@celery_app.task(name="market.backfill_gaps")
def backfill_gaps_task(hours_back: int = 24) -> dict:
    """Detect and backfill candle data gaps.

    Runs every hour via Celery Beat.
    """
    async def _backfill():
        from app.database.session import async_session_factory
        from app.market_data.service import MarketDataService

        results = {}
        async with async_session_factory() as db:
            service = MarketDataService(db)
            for symbol in settings.trading_symbols:
                for tf in ["15m", "1h", "4h"]:
                    try:
                        result = await service.backfill_gaps(symbol, tf, hours_back)
                        if result["gaps_found"] > 0:
                            results[f"{symbol}/{tf}"] = result
                    except Exception as e:
                        logger.error("backfill_failed", symbol=symbol, timeframe=tf, error=str(e))

        return results

    return _run_async(_backfill())


@celery_app.task(name="market.cleanup_old_data")
def cleanup_old_data_task(days: int = 90) -> dict:
    """Remove candle data older than N days.

    Runs daily via Celery Beat.
    """
    async def _cleanup():
        from app.database.session import async_session_factory
        from app.market_data.service import MarketDataService

        async with async_session_factory() as db:
            service = MarketDataService(db)
            return await service.cleanup_old_data(days)

    return _run_async(_cleanup())


@celery_app.task(name="market.initial_load")
def initial_load_task(symbol: str) -> dict:
    """Load initial historical data for a symbol.

    Called manually or on first startup.
    """
    async def _load():
        from app.database.session import async_session_factory
        from app.market_data.service import MarketDataService

        async with async_session_factory() as db:
            service = MarketDataService(db)
            return await service.initial_data_load(symbol)

    return _run_async(_load())
