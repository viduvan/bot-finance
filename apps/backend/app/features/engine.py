"""Feature Engine — Orchestration layer for all feature computation.

Pulls candle data from the database, runs all feature modules,
and stores versioned results in the technical_features table.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ENTRY_TIMEFRAME, MACRO_TREND_TIMEFRAME, TREND_CONFIRMATION_TIMEFRAME
from app.features.indicators import indicator_engine
from app.features.market_structure import market_structure
from app.features.orderbook_features import orderbook_features
from app.features.volatility import volatility_features
from app.features.volume import volume_features
from app.market_data.binance_rest import binance_client
from app.repositories.feature_repo import FeatureRepository
from app.repositories.market_repo import MarketDataRepository

logger = structlog.get_logger(__name__)

FEATURE_VERSION = "v1"


class FeatureEngine:
    """Orchestrates feature computation across all modules.

    Usage:
        engine = FeatureEngine(db)
        features = await engine.compute_and_store(symbol="BTCUSDT")
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._market_repo = MarketDataRepository(db)
        self._feature_repo = FeatureRepository(db)

    async def compute_and_store(
        self,
        symbol: str,
        candle_limit: int = 250,
        include_orderbook: bool = True,
    ) -> dict[str, Any]:
        """Compute all features for a symbol and persist to DB.

        Args:
            symbol: trading pair e.g. 'BTCUSDT'
            candle_limit: number of candles to load for computation
            include_orderbook: whether to fetch live order book data

        Returns:
            Merged feature dict saved to DB
        """
        now = datetime.now(UTC)

        # Load candles for all 3 timeframes
        candles_15m = await self._load_candles(symbol, ENTRY_TIMEFRAME, candle_limit)
        candles_1h = await self._load_candles(symbol, TREND_CONFIRMATION_TIMEFRAME, candle_limit)
        candles_4h = await self._load_candles(symbol, MACRO_TREND_TIMEFRAME, candle_limit)

        if not candles_15m:
            logger.warning("no_candles_for_features", symbol=symbol)
            return {}

        # Compute indicators for each timeframe
        features_15m = self._compute_timeframe_features(candles_15m, ENTRY_TIMEFRAME)
        features_1h = self._compute_timeframe_features(candles_1h, TREND_CONFIRMATION_TIMEFRAME)
        features_4h = self._compute_timeframe_features(candles_4h, MACRO_TREND_TIMEFRAME)

        # Add timeframe prefix to avoid key collisions
        merged: dict[str, Any] = {}
        for key, val in features_15m.items():
            merged[f"tf15_{key}"] = val
        for key, val in features_1h.items():
            merged[f"tf1h_{key}"] = val
        for key, val in features_4h.items():
            merged[f"tf4h_{key}"] = val

        # Flat copies for primary timeframe (no prefix — for strategy use)
        merged.update(features_15m)

        # Order book features (live from Binance)
        if include_orderbook:
            try:
                book = await binance_client.get_depth(symbol, limit=20)
                ob_features = orderbook_features.compute(book)
                merged.update({f"ob_{k}": v for k, v in ob_features.items()})
            except Exception as e:
                logger.warning("orderbook_features_failed", symbol=symbol, error=str(e))

        merged["computed_at"] = now.isoformat()
        merged["symbol"] = symbol

        # Persist to DB
        await self._feature_repo.save(
            symbol=symbol,
            timeframe=ENTRY_TIMEFRAME,
            features=merged,
            computed_at=now,
            version=FEATURE_VERSION,
        )

        logger.info("features_computed_and_stored", symbol=symbol, feature_count=len(merged))
        return merged

    async def get_latest_features(self, symbol: str) -> dict[str, Any] | None:
        """Retrieve the most recent feature set from DB."""
        record = await self._feature_repo.get_latest(symbol, ENTRY_TIMEFRAME)
        if record is None:
            return None
        return record.features

    async def _load_candles(self, symbol: str, timeframe: str, limit: int) -> list[dict]:
        """Load candles from DB and convert to feature-ready dicts."""
        db_candles = await self._market_repo.get_candles(symbol, timeframe, limit)
        return [
            {
                "open_time": c.open_time,
                "close_time": c.close_time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in reversed(db_candles)  # repo returns newest-first, reverse to oldest-first
        ]

    def _compute_timeframe_features(self, candles: list[dict], timeframe: str) -> dict[str, Any]:
        """Run all feature modules on a single timeframe."""
        if not candles:
            return {}

        features: dict[str, Any] = {}

        # Technical indicators
        try:
            features.update(indicator_engine.compute_all(candles))
        except Exception as e:
            logger.error("indicator_engine_failed", timeframe=timeframe, error=str(e))

        # Volume
        try:
            features.update(volume_features.compute(candles))
        except Exception as e:
            logger.error("volume_features_failed", timeframe=timeframe, error=str(e))

        # Volatility
        try:
            features.update(volatility_features.compute(candles))
        except Exception as e:
            logger.error("volatility_features_failed", timeframe=timeframe, error=str(e))

        # Market structure (needs more candles)
        if len(candles) >= 30:
            try:
                features.update(market_structure.compute(candles))
            except Exception as e:
                logger.error("market_structure_failed", timeframe=timeframe, error=str(e))

        # Add raw price for strategy use
        if candles:
            features["close"] = str(candles[-1]["close"])
            features["high"] = str(candles[-1]["high"])
            features["low"] = str(candles[-1]["low"])
            features["open"] = str(candles[-1]["open"])
            features["volume"] = str(candles[-1]["volume"])
            features["candle_count"] = len(candles)

        return features
