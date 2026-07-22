"""Volume feature computation.

Computes volume-based features used by agents to assess
buying/selling pressure and trend conviction.
"""

from __future__ import annotations

from decimal import Decimal

import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


def _to_decimal(val: float | None) -> Decimal | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    return Decimal(str(round(float(val), 8)))


class VolumeFeatures:
    """Computes volume-based technical features."""

    def compute(self, candles: list[dict], sma_period: int = 20) -> dict:
        """Compute all volume features for the most recent candle.

        Args:
            candles: list of OHLCV dicts, sorted oldest-first
            sma_period: lookback period for average volume

        Returns:
            dict with volume feature values
        """
        if not candles:
            return {}

        n = len(candles)
        volumes = [float(c["volume"]) for c in candles]
        closes = [float(c["close"]) for c in candles]

        current_vol = volumes[-1]
        current_close = closes[-1]

        result: dict = {
            "volume_current": str(_to_decimal(current_vol)),
        }

        # Volume SMA
        if n >= sma_period:
            vol_window = volumes[-sma_period:]
            vol_sma = sum(vol_window) / len(vol_window)
            result["volume_sma_20"] = str(_to_decimal(vol_sma))

            # Relative volume (how many times current > average)
            if vol_sma > 0:
                rel_vol = current_vol / vol_sma
                result["volume_relative"] = str(_to_decimal(rel_vol))
                result["volume_spike"] = rel_vol > 2.0  # >2x average = spike
            else:
                result["volume_relative"] = None
                result["volume_spike"] = False
        else:
            result["volume_sma_20"] = None
            result["volume_relative"] = None
            result["volume_spike"] = False

        # Volume trend (3-candle slope)
        if n >= 3:
            recent_vols = volumes[-3:]
            # Simple linear regression slope
            x = np.array([0.0, 1.0, 2.0])
            slope = float(np.polyfit(x, recent_vols, 1)[0])
            result["volume_trend_slope"] = str(_to_decimal(slope))
            result["volume_increasing"] = slope > 0
        else:
            result["volume_trend_slope"] = None
            result["volume_increasing"] = None

        # Volume Weighted Average Price (VWAP) — intraday approximation
        if n >= 2:
            vwap = self._compute_vwap(candles[-min(n, 96):])  # Last 24h of 15m candles
            result["vwap"] = str(vwap) if vwap else None

            if vwap and current_close:
                result["price_above_vwap"] = Decimal(str(current_close)) > vwap
        else:
            result["vwap"] = None
            result["price_above_vwap"] = None

        # Buy vs Sell volume estimation via candle body direction
        result.update(self._compute_buy_sell_pressure(candles[-20:]))

        return result

    def _compute_vwap(self, candles: list[dict]) -> Decimal | None:
        """Compute VWAP using typical price × volume."""
        total_tv = Decimal("0")
        total_vol = Decimal("0")

        for c in candles:
            typical = (Decimal(str(c["high"])) + Decimal(str(c["low"])) + Decimal(str(c["close"]))) / 3
            vol = Decimal(str(c["volume"]))
            total_tv += typical * vol
            total_vol += vol

        if total_vol == 0:
            return None
        return (total_tv / total_vol).quantize(Decimal("0.00000001"))

    def _compute_buy_sell_pressure(self, candles: list[dict]) -> dict:
        """Estimate buy/sell pressure from candle body direction.

        Green candles (close > open) = buying pressure.
        Red candles (close < open) = selling pressure.
        """
        buy_vol = Decimal("0")
        sell_vol = Decimal("0")

        for c in candles:
            vol = Decimal(str(c["volume"]))
            if Decimal(str(c["close"])) >= Decimal(str(c["open"])):
                buy_vol += vol
            else:
                sell_vol += vol

        total = buy_vol + sell_vol
        if total == 0:
            return {"buy_pressure_pct": None, "sell_pressure_pct": None}

        buy_pct = (buy_vol / total * 100).quantize(Decimal("0.01"))
        sell_pct = (sell_vol / total * 100).quantize(Decimal("0.01"))

        return {
            "buy_pressure_pct": str(buy_pct),
            "sell_pressure_pct": str(sell_pct),
            "pressure_bias": "BULLISH" if buy_pct > 55 else ("BEARISH" if sell_pct > 55 else "NEUTRAL"),
        }


# Shared singleton
volume_features = VolumeFeatures()
