"""Feature API endpoints.

REST endpoints for computing, retrieving features,
and evaluating strategy signals.
"""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query

from app.dependencies import CurrentUser, DBSession
from app.features.engine import FeatureEngine
from app.strategies.registry import strategy_registry

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/features/{symbol}")
async def get_latest_features(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get the most recently computed features for a symbol."""
    engine = FeatureEngine(db)
    features = await engine.get_latest_features(symbol)
    if features is None:
        return {
            "message": f"No features found for {symbol}. Trigger /features/{symbol}/compute first."
        }
    return features


@router.post("/features/{symbol}/compute")
async def compute_features(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    include_orderbook: bool = Query(default=True, description="Fetch live order book data"),
) -> dict:
    """Compute and store fresh features for a symbol (manual trigger).

    This fetches latest candles from DB and runs all feature modules.
    """
    engine = FeatureEngine(db)
    features = await engine.compute_and_store(symbol, include_orderbook=include_orderbook)
    if not features:
        return {"status": "error", "message": "No candle data available. Run initial-load first."}
    return {
        "status": "ok",
        "symbol": symbol,
        "feature_count": len(features),
        "computed_at": features.get("computed_at"),
    }


@router.get("/strategy/{symbol}/signal")
async def get_strategy_signal(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    strategy: str = Query(default="ema_pullback", description="Strategy name"),
) -> dict:
    """Evaluate strategy signal using the latest stored features.

    Returns the current trade signal (LONG / SHORT / NO_SIGNAL) with score and reasoning.
    """
    engine = FeatureEngine(db)

    # Get features for all timeframes
    features_15m = await engine.get_latest_features(symbol) or {}

    # For now use same features — in future fetch each timeframe separately
    # TODO: store per-timeframe features separately
    features_1h = {
        k.removeprefix("tf1h_"): v for k, v in features_15m.items() if k.startswith("tf1h_")
    }
    features_4h = {
        k.removeprefix("tf4h_"): v for k, v in features_15m.items() if k.startswith("tf4h_")
    }

    result = strategy_registry.evaluate(strategy, features_15m, features_1h, features_4h)

    return {
        "symbol": symbol,
        "strategy": strategy,
        "signal": result.signal,
        "score": result.score,
        "confidence": result.confidence,
        "reasons": result.reasons,
        "entry_zone_low": str(result.entry_zone_low) if result.entry_zone_low else None,
        "entry_zone_high": str(result.entry_zone_high) if result.entry_zone_high else None,
        "stop_loss_hint": str(result.stop_loss_hint) if result.stop_loss_hint else None,
        "take_profit_hint": str(result.take_profit_hint) if result.take_profit_hint else None,
    }


@router.get("/strategy/list")
async def list_strategies(user: CurrentUser) -> dict:
    """List all available strategies."""
    return {"strategies": strategy_registry.list_strategies()}
