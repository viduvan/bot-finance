"""Technical Indicator Engine.

Computes OHLCV-based indicators using pandas-ta.
All outputs use Decimal for consistency with financial data.

Supported indicators:
- EMA (9, 21, 50, 200)
- RSI (14)
- MACD (12, 26, 9)
- Bollinger Bands (20, 2)
- ATR (14)
- Stochastic RSI (14)
- OBV (On-Balance Volume)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
import pandas_ta as ta
import structlog

logger = structlog.get_logger(__name__)


def _to_decimal(val: float | np.floating | None) -> Decimal | None:
    """Convert float/numpy value to Decimal, return None if NaN."""
    if val is None:
        return None
    if isinstance(val, (float, np.floating)) and np.isnan(val):
        return None
    return Decimal(str(round(float(val), 8)))


def _candles_to_df(candles: list[dict]) -> pd.DataFrame:
    """Convert list of candle dicts to a pandas DataFrame sorted by open_time."""
    if not candles:
        return pd.DataFrame()

    df = pd.DataFrame(candles)
    df = df.sort_values("open_time").reset_index(drop=True)

    # Ensure numeric columns are float
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].apply(lambda x: float(x) if x is not None else np.nan)

    return df


class IndicatorEngine:
    """Computes technical indicators from OHLCV candle data.

    All methods accept a list of candle dicts and return indicator values
    as Decimal (or None when insufficient data).
    """

    # ── EMA ─────────────────────────────────────────────────────────

    def compute_ema(self, candles: list[dict], period: int = 21) -> list[Decimal | None]:
        """Compute Exponential Moving Average for all candles.

        Args:
            candles: list of OHLCV dicts with 'close' field
            period: EMA period (default 21)

        Returns:
            List of EMA values (None for initial periods)
        """
        df = _candles_to_df(candles)
        if df.empty or len(df) < period:
            return [None] * len(candles)

        ema = ta.ema(df["close"], length=period)
        if ema is None:
            return [None] * len(candles)
        return [_to_decimal(v) for v in ema]

    def compute_emas(self, candles: list[dict]) -> dict[str, list[Decimal | None]]:
        """Compute multiple EMA periods at once (9, 21, 50, 200).

        Returns dict: {'ema_9': [...], 'ema_21': [...], 'ema_50': [...], 'ema_200': [...]}
        """
        df = _candles_to_df(candles)
        if df.empty:
            return {f"ema_{p}": [None] * len(candles) for p in [9, 21, 50, 200]}

        result = {}
        for period in [9, 21, 50, 200]:
            ema = ta.ema(df["close"], length=period)
            if ema is None:
                result[f"ema_{period}"] = [None] * len(candles)
            else:
                result[f"ema_{period}"] = [_to_decimal(v) for v in ema]

        return result

    def latest_emas(self, candles: list[dict]) -> dict[str, Decimal | None]:
        """Get the most recent EMA values for all periods.

        Returns dict: {'ema_9': value, 'ema_21': value, ...}
        """
        all_emas = self.compute_emas(candles)
        return {key: vals[-1] if vals else None for key, vals in all_emas.items()}

    # ── RSI ─────────────────────────────────────────────────────────

    def compute_rsi(self, candles: list[dict], period: int = 14) -> list[Decimal | None]:
        """Compute Relative Strength Index.

        Args:
            candles: list of OHLCV dicts
            period: RSI period (default 14)

        Returns:
            List of RSI values 0-100 (None for initial periods)
        """
        df = _candles_to_df(candles)
        if df.empty or len(df) < period + 1:
            return [None] * len(candles)

        rsi = ta.rsi(df["close"], length=period)
        return [_to_decimal(v) for v in rsi]

    def latest_rsi(self, candles: list[dict], period: int = 14) -> Decimal | None:
        """Get the most recent RSI value."""
        values = self.compute_rsi(candles, period)
        return values[-1] if values else None

    def rsi_zone(self, rsi: Decimal | None) -> str:
        """Classify RSI value into zone: OVERSOLD, NEUTRAL, OVERBOUGHT."""
        if rsi is None:
            return "UNKNOWN"
        if rsi < 30:
            return "OVERSOLD"
        if rsi > 70:
            return "OVERBOUGHT"
        return "NEUTRAL"

    # ── MACD ────────────────────────────────────────────────────────

    def compute_macd(
        self,
        candles: list[dict],
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> dict[str, list[Decimal | None]]:
        """Compute MACD line, Signal line, and Histogram.

        Returns:
            dict with keys: 'macd', 'signal', 'histogram'
        """
        df = _candles_to_df(candles)
        n = len(candles)

        if df.empty or len(df) < slow + signal:
            return {
                "macd": [None] * n,
                "signal": [None] * n,
                "histogram": [None] * n,
            }

        macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
        if macd_df is None or macd_df.empty:
            return {"macd": [None] * n, "signal": [None] * n, "histogram": [None] * n}

        # pandas-ta column names: MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
        cols = macd_df.columns.tolist()
        macd_col = next((c for c in cols if c.startswith("MACD_")), None)
        hist_col = next((c for c in cols if c.startswith("MACDh_")), None)
        sig_col = next((c for c in cols if c.startswith("MACDs_")), None)

        return {
            "macd": [_to_decimal(v) for v in (macd_df[macd_col] if macd_col else [None] * n)],
            "signal": [_to_decimal(v) for v in (macd_df[sig_col] if sig_col else [None] * n)],
            "histogram": [_to_decimal(v) for v in (macd_df[hist_col] if hist_col else [None] * n)],
        }

    def latest_macd(self, candles: list[dict]) -> dict[str, Decimal | None]:
        """Get the most recent MACD values."""
        macd = self.compute_macd(candles)
        return {key: vals[-1] if vals else None for key, vals in macd.items()}

    def macd_signal(self, candles: list[dict]) -> str:
        """Get MACD signal: BULLISH_CROSS, BEARISH_CROSS, BULLISH, BEARISH, NEUTRAL."""
        macd = self.compute_macd(candles)
        hist = macd["histogram"]

        if len(hist) < 2:
            return "NEUTRAL"

        prev = hist[-2]
        curr = hist[-1]

        if prev is None or curr is None:
            return "NEUTRAL"

        if prev < 0 and curr > 0:
            return "BULLISH_CROSS"
        if prev > 0 and curr < 0:
            return "BEARISH_CROSS"
        if curr > 0:
            return "BULLISH"
        if curr < 0:
            return "BEARISH"
        return "NEUTRAL"

    # ── Bollinger Bands ──────────────────────────────────────────────

    def compute_bbands(
        self,
        candles: list[dict],
        period: int = 20,
        std_dev: float = 2.0,
    ) -> dict[str, list[Decimal | None]]:
        """Compute Bollinger Bands (upper, middle/SMA, lower, bandwidth, %B).

        Returns:
            dict with keys: 'upper', 'middle', 'lower', 'bandwidth', 'pct_b'
        """
        df = _candles_to_df(candles)
        n = len(candles)
        empty = {k: [None] * n for k in ["upper", "middle", "lower", "bandwidth", "pct_b"]}

        if df.empty or len(df) < period:
            return empty

        bb = ta.bbands(df["close"], length=period, std=std_dev)
        if bb is None or bb.empty:
            return empty

        cols = bb.columns.tolist()
        upper_col = next((c for c in cols if "BBU" in c), None)
        mid_col = next((c for c in cols if "BBM" in c), None)
        lower_col = next((c for c in cols if "BBL" in c), None)
        bw_col = next((c for c in cols if "BBB" in c), None)
        pctb_col = next((c for c in cols if "BBP" in c), None)

        return {
            "upper": [_to_decimal(v) for v in (bb[upper_col] if upper_col else [None] * n)],
            "middle": [_to_decimal(v) for v in (bb[mid_col] if mid_col else [None] * n)],
            "lower": [_to_decimal(v) for v in (bb[lower_col] if lower_col else [None] * n)],
            "bandwidth": [_to_decimal(v) for v in (bb[bw_col] if bw_col else [None] * n)],
            "pct_b": [_to_decimal(v) for v in (bb[pctb_col] if pctb_col else [None] * n)],
        }

    def latest_bbands(self, candles: list[dict]) -> dict[str, Decimal | None]:
        """Get the most recent Bollinger Band values."""
        bb = self.compute_bbands(candles)
        return {key: vals[-1] if vals else None for key, vals in bb.items()}

    def price_bb_position(self, price: Decimal, bb: dict[str, Decimal | None]) -> str:
        """Classify price position relative to Bollinger Bands."""
        upper = bb.get("upper")
        middle = bb.get("middle")
        lower = bb.get("lower")

        if upper is None or lower is None or middle is None:
            return "UNKNOWN"

        if price >= upper:
            return "ABOVE_UPPER"
        if price >= middle:
            return "UPPER_HALF"
        if price >= lower:
            return "LOWER_HALF"
        return "BELOW_LOWER"

    # ── ATR ─────────────────────────────────────────────────────────

    def compute_atr(self, candles: list[dict], period: int = 14) -> list[Decimal | None]:
        """Compute Average True Range (volatility measure).

        Args:
            candles: list of OHLCV dicts with 'high', 'low', 'close'
            period: ATR period (default 14)

        Returns:
            List of ATR values in price units
        """
        df = _candles_to_df(candles)
        if df.empty or len(df) < period + 1:
            return [None] * len(candles)

        atr = ta.atr(df["high"], df["low"], df["close"], length=period)
        return [_to_decimal(v) for v in atr]

    def latest_atr(self, candles: list[dict], period: int = 14) -> Decimal | None:
        """Get the most recent ATR value."""
        values = self.compute_atr(candles, period)
        return values[-1] if values else None

    def atr_percent(self, candles: list[dict]) -> Decimal | None:
        """ATR as a percentage of close price (normalized volatility)."""
        atr = self.latest_atr(candles)
        if not candles or atr is None:
            return None
        close = Decimal(str(candles[-1]["close"]))
        if close == 0:
            return None
        return (atr / close * 100).quantize(Decimal("0.0001"))

    # ── Stochastic RSI ───────────────────────────────────────────────

    def compute_stoch_rsi(
        self,
        candles: list[dict],
        rsi_period: int = 14,
        stoch_period: int = 14,
        smooth_k: int = 3,
        smooth_d: int = 3,
    ) -> dict[str, list[Decimal | None]]:
        """Compute Stochastic RSI (%K and %D lines).

        Returns:
            dict with keys: 'k', 'd'
        """
        df = _candles_to_df(candles)
        n = len(candles)

        if df.empty or len(df) < rsi_period + stoch_period + smooth_k:
            return {"k": [None] * n, "d": [None] * n}

        stochrsi = ta.stochrsi(
            df["close"],
            length=rsi_period,
            rsi_length=stoch_period,
            k=smooth_k,
            d=smooth_d,
        )

        if stochrsi is None or stochrsi.empty:
            return {"k": [None] * n, "d": [None] * n}

        cols = stochrsi.columns.tolist()
        k_col = next((c for c in cols if "STOCHRSIk" in c), None)
        d_col = next((c for c in cols if "STOCHRSId" in c), None)

        return {
            "k": [_to_decimal(v) for v in (stochrsi[k_col] if k_col else [None] * n)],
            "d": [_to_decimal(v) for v in (stochrsi[d_col] if d_col else [None] * n)],
        }

    def latest_stoch_rsi(self, candles: list[dict]) -> dict[str, Decimal | None]:
        """Get the most recent Stochastic RSI values."""
        stoch = self.compute_stoch_rsi(candles)
        return {key: vals[-1] if vals else None for key, vals in stoch.items()}

    # ── OBV ─────────────────────────────────────────────────────────

    def compute_obv(self, candles: list[dict]) -> list[Decimal | None]:
        """Compute On-Balance Volume."""
        df = _candles_to_df(candles)
        if df.empty or len(df) < 2:
            return [None] * len(candles)

        obv = ta.obv(df["close"], df["volume"])
        return [_to_decimal(v) for v in obv]

    def latest_obv(self, candles: list[dict]) -> Decimal | None:
        """Get the most recent OBV value."""
        values = self.compute_obv(candles)
        return values[-1] if values else None

    # ── Composite ───────────────────────────────────────────────────

    def compute_all(self, candles: list[dict]) -> dict[str, Any]:
        """Compute all indicators and return the latest values.

        Returns a flat dict of the most recent value for each indicator.
        Suitable for storage in TechnicalFeature.features (JSONB).
        """
        if not candles or len(candles) < 2:
            return {}

        emas = self.latest_emas(candles)
        rsi = self.latest_rsi(candles)
        macd = self.latest_macd(candles)
        bb = self.latest_bbands(candles)
        atr = self.latest_atr(candles)
        stoch = self.latest_stoch_rsi(candles)
        obv = self.latest_obv(candles)

        close = Decimal(str(candles[-1]["close"]))

        result: dict[str, Any] = {
            # EMA values
            **{k: str(v) if v is not None else None for k, v in emas.items()},
            # RSI
            "rsi_14": str(rsi) if rsi is not None else None,
            "rsi_zone": self.rsi_zone(rsi),
            # MACD
            "macd_line": str(macd["macd"]) if macd["macd"] is not None else None,
            "macd_signal": str(macd["signal"]) if macd["signal"] is not None else None,
            "macd_histogram": str(macd["histogram"]) if macd["histogram"] is not None else None,
            "macd_signal_type": self.macd_signal(candles),
            # Bollinger Bands
            "bb_upper": str(bb["upper"]) if bb["upper"] is not None else None,
            "bb_middle": str(bb["middle"]) if bb["middle"] is not None else None,
            "bb_lower": str(bb["lower"]) if bb["lower"] is not None else None,
            "bb_bandwidth": str(bb["bandwidth"]) if bb["bandwidth"] is not None else None,
            "bb_pct_b": str(bb["pct_b"]) if bb["pct_b"] is not None else None,
            "bb_position": self.price_bb_position(close, bb),
            # ATR
            "atr_14": str(atr) if atr is not None else None,
            "atr_pct": str(self.atr_percent(candles)),
            # Stochastic RSI
            "stoch_rsi_k": str(stoch["k"]) if stoch["k"] is not None else None,
            "stoch_rsi_d": str(stoch["d"]) if stoch["d"] is not None else None,
            # OBV
            "obv": str(obv) if obv is not None else None,
        }

        # EMA trend signals
        ema_9 = emas.get("ema_9")
        ema_21 = emas.get("ema_21")
        ema_50 = emas.get("ema_50")

        if ema_9 is not None and ema_21 is not None:
            result["ema_9_21_bullish"] = ema_9 > ema_21
        if ema_21 is not None and ema_50 is not None:
            result["ema_21_50_bullish"] = ema_21 > ema_50

        return result


# Shared singleton
indicator_engine = IndicatorEngine()
