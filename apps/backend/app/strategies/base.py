"""Base strategy interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.strategies.ema_pullback import SignalResult


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy name identifier."""
        ...

    @abstractmethod
    def evaluate(
        self,
        features_15m: dict,
        features_1h: dict,
        features_4h: dict,
    ) -> SignalResult:
        """Evaluate features and return a trade signal."""
        ...
