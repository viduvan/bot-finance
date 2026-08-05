"""Strategy registry — manage and dispatch trading strategies."""

from __future__ import annotations

from typing import Protocol

import structlog

from app.strategies.ema_pullback import SignalResult, ema_pullback_strategy

logger = structlog.get_logger(__name__)


class Strategy(Protocol):
    """Interface that all strategies must implement."""

    def evaluate(
        self,
        features_15m: dict,
        features_1h: dict,
        features_4h: dict,
    ) -> SignalResult: ...


class StrategyRegistry:
    """Registry mapping strategy names to instances.

    Allows the analysis pipeline to select strategies by name
    without direct coupling to concrete implementations.
    """

    def __init__(self) -> None:
        self._registry: dict[str, Strategy] = {}

    def register(self, name: str, strategy: Strategy) -> None:
        """Register a strategy under a given name."""
        self._registry[name] = strategy
        logger.info("strategy_registered", name=name)

    def get(self, name: str) -> Strategy | None:
        """Retrieve a strategy by name."""
        return self._registry.get(name)

    def evaluate(
        self,
        strategy_name: str,
        features_15m: dict,
        features_1h: dict,
        features_4h: dict,
    ) -> SignalResult:
        """Evaluate a named strategy with multi-timeframe features."""
        strategy = self.get(strategy_name)
        if strategy is None:
            logger.warning("strategy_not_found", name=strategy_name)
            return SignalResult(
                signal="NO_SIGNAL", score=0, reasons=[f"Strategy '{strategy_name}' not found"]
            )

        try:
            result = strategy.evaluate(features_15m, features_1h, features_4h)
            logger.info(
                "strategy_evaluated",
                name=strategy_name,
                signal=result.signal,
                score=result.score,
            )
            return result
        except Exception as e:
            logger.error("strategy_evaluation_failed", name=strategy_name, error=str(e))
            return SignalResult(signal="NO_SIGNAL", score=0, reasons=[f"Strategy error: {str(e)}"])

    def list_strategies(self) -> list[str]:
        """Return list of registered strategy names."""
        return list(self._registry.keys())


# Shared registry with default strategies
strategy_registry = StrategyRegistry()
strategy_registry.register("ema_pullback", ema_pullback_strategy)
