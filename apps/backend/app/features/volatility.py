"""Volatility feature computation.

ATR-based volatility classification, Bollinger Band squeeze,
and historical volatility metrics.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import structlog

from app.features.indicators import IndicatorEngine

logger = structlog.get_logger(__name__)
_engine = IndicatorEngine()


class VolatilityFeatures:
    """Computes volatility-based features from OHLCV data."""

    def compute(self, candles: list[dict]) -> dict:
        """Compute all volatility features for the most recent candle.

        Returns:
            dict with volatility metrics
        """
        if not candles or len(candles) < 15:
            return {}

        result: dict = {}

        # ATR-based metrics
        atr = _engine.latest_atr(candles)
        atr_pct = _engine.atr_percent(candles)
        result["atr_14"] = str(atr) if atr is not None else None
        result["atr_pct"] = str(atr_pct) if atr_pct is not None else None

        # Volatility regime
        if atr_pct is not None:
            result["volatility_regime"] = self._classify_volatility(float(atr_pct))

        # Bollinger Band width — proxy for squeeze/expansion
        bb = _engine.latest_bbands(candles)
        bw = bb.get("bandwidth")
        result["bb_bandwidth"] = str(bw) if bw is not None else None

        if bw is not None:
            # Compute average bandwidth over last 20 candles for squeeze detection
            bb_all = _engine.compute_bbands(candles)
            bandwidths = [float(v) for v in bb_all["bandwidth"] if v is not None]
            if len(bandwidths) >= 20:
                avg_bw = sum(bandwidths[-20:]) / 20
                result["bb_squeeze"] = (
                    float(bw) < avg_bw * 0.5
                )  # Squeeze = BW < 50% of 20-period avg
                result["bb_expansion"] = float(bw) > avg_bw * 1.5
            else:
                result["bb_squeeze"] = None
                result["bb_expansion"] = None

        # Historical Volatility (close-to-close log returns, annualized)
        hv = self._compute_historical_volatility(candles, period=20, timeframe_minutes=15)
        result["historical_volatility_20"] = str(hv) if hv is not None else None

        # Candle body size (% of range) — measures indecision vs conviction
        last = candles[-1]
        candle_range = float(last["high"]) - float(last["low"])
        candle_body = abs(float(last["close"]) - float(last["open"]))

        if candle_range > 0:
            body_pct = (candle_body / candle_range) * 100
            result["candle_body_pct"] = str(Decimal(str(round(body_pct, 2))))
            result["candle_type"] = self._classify_candle(body_pct)
        else:
            result["candle_body_pct"] = None
            result["candle_type"] = "DOJI"

        return result

    def _classify_volatility(self, atr_pct: float) -> str:
        """Classify volatility regime from ATR as % of price."""
        if atr_pct < 0.5:
            return "LOW"
        if atr_pct < 1.5:
            return "NORMAL"
        if atr_pct < 3.0:
            return "HIGH"
        return "EXTREME"

    def _compute_historical_volatility(
        self,
        candles: list[dict],
        period: int = 20,
        timeframe_minutes: int = 15,
    ) -> Decimal | None:
        """Compute annualized historical volatility from log returns.

        Standard close-to-close HV formula.
        """
        if len(candles) < period + 1:
            return None

        closes = [float(c["close"]) for c in candles[-(period + 1) :]]

        # Log returns
        log_returns = [
            np.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0
        ]

        if len(log_returns) < period:
            return None

        std_dev = float(np.std(log_returns, ddof=1))

        # Annualize: sqrt(candles_per_year)
        candles_per_day = 24 * 60 / timeframe_minutes
        candles_per_year = candles_per_day * 365
        annualized_hv = std_dev * np.sqrt(candles_per_year) * 100  # as percentage

        return Decimal(str(round(annualized_hv, 2)))

    def _classify_candle(self, body_pct: float) -> str:
        """Classify candle type based on body-to-range ratio."""
        if body_pct < 20:
            return "DOJI"  # Very small body — indecision
        if body_pct < 50:
            return "SPINNING_TOP"  # Moderate body
        return "MARUBOZU"  # Large body — conviction


# Shared singleton
volatility_features = VolatilityFeatures()
