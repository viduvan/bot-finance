"""Market structure analysis.

Identifies key support/resistance levels, trend direction,
swing highs/lows, and Higher High / Lower Low patterns.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MarketStructure:
    """Identifies market structure from OHLCV data.

    Provides:
    - Trend direction (BULLISH / BEARISH / RANGING)
    - Swing high/low detection
    - Support and resistance levels
    - Higher High/Higher Low or Lower High/Lower Low patterns
    """

    def compute(self, candles: list[dict], swing_lookback: int = 5) -> dict:
        """Compute market structure features.

        Args:
            candles: OHLCV candle list (at least 50 recommended)
            swing_lookback: number of candles on each side to define a swing point

        Returns:
            dict of market structure features
        """
        if not candles or len(candles) < swing_lookback * 2 + 1:
            return {}

        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        closes = [float(c["close"]) for c in candles]

        result: dict[str, Any] = {}

        # Swing points
        swing_highs = self._find_swing_highs(highs, lookback=swing_lookback)
        swing_lows = self._find_swing_lows(lows, lookback=swing_lookback)

        result["swing_highs"] = [str(Decimal(str(round(v, 8)))) for v in swing_highs]
        result["swing_lows"] = [str(Decimal(str(round(v, 8)))) for v in swing_lows]

        # Trend from swing structure (HH/HL or LH/LL)
        trend = self._determine_trend(swing_highs, swing_lows)
        result["trend_direction"] = trend

        # EMA-based trend confirmation (50-period simple check using closes)
        if len(closes) >= 50:
            sma50 = sum(closes[-50:]) / 50
            result["price_above_sma50"] = closes[-1] > sma50
            result["sma50"] = str(Decimal(str(round(sma50, 8))))
        else:
            result["price_above_sma50"] = None
            result["sma50"] = None

        # Key support and resistance levels from recent swings
        recent_highs = swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs
        recent_lows = swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows

        result["nearest_resistance"] = (
            str(Decimal(str(round(min(h for h in recent_highs if h > closes[-1]), 8))))
            if any(h > closes[-1] for h in recent_highs)
            else None
        )
        result["nearest_support"] = (
            str(Decimal(str(round(max(l for l in recent_lows if l < closes[-1]), 8))))
            if any(l < closes[-1] for l in recent_lows)
            else None
        )

        # Price position: distance from nearest S/R
        if result["nearest_resistance"] and result["nearest_support"]:
            res = float(result["nearest_resistance"])
            sup = float(result["nearest_support"])
            price = closes[-1]
            sr_range = res - sup

            if sr_range > 0:
                pct_in_range = ((price - sup) / sr_range) * 100
                result["sr_position_pct"] = str(Decimal(str(round(pct_in_range, 2))))
                if pct_in_range > 70:
                    result["sr_zone"] = "NEAR_RESISTANCE"
                elif pct_in_range < 30:
                    result["sr_zone"] = "NEAR_SUPPORT"
                else:
                    result["sr_zone"] = "MID_RANGE"
            else:
                result["sr_position_pct"] = None
                result["sr_zone"] = None
        else:
            result["sr_position_pct"] = None
            result["sr_zone"] = None

        return result

    def _find_swing_highs(self, highs: list[float], lookback: int = 5) -> list[float]:
        """Find swing high points (local maxima)."""
        swing_highs = []
        n = len(highs)

        for i in range(lookback, n - lookback):
            is_high = all(highs[i] >= highs[i - j] for j in range(1, lookback + 1))
            is_high = is_high and all(highs[i] >= highs[i + j] for j in range(1, lookback + 1))
            if is_high:
                swing_highs.append(highs[i])

        return swing_highs

    def _find_swing_lows(self, lows: list[float], lookback: int = 5) -> list[float]:
        """Find swing low points (local minima)."""
        swing_lows = []
        n = len(lows)

        for i in range(lookback, n - lookback):
            is_low = all(lows[i] <= lows[i - j] for j in range(1, lookback + 1))
            is_low = is_low and all(lows[i] <= lows[i + j] for j in range(1, lookback + 1))
            if is_low:
                swing_lows.append(lows[i])

        return swing_lows

    def _determine_trend(
        self,
        swing_highs: list[float],
        swing_lows: list[float],
    ) -> str:
        """Determine trend from swing structure.

        BULLISH:  Higher Highs + Higher Lows
        BEARISH:  Lower Highs + Lower Lows
        RANGING:  Mixed or insufficient data
        """
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return "RANGING"

        # Check last 2 swing highs and lows
        hh = swing_highs[-1] > swing_highs[-2]   # Higher High
        hl = swing_lows[-1] > swing_lows[-2]      # Higher Low
        lh = swing_highs[-1] < swing_highs[-2]    # Lower High
        ll = swing_lows[-1] < swing_lows[-2]      # Lower Low

        if hh and hl:
            return "BULLISH"
        if lh and ll:
            return "BEARISH"
        return "RANGING"


# Shared singleton
market_structure = MarketStructure()
