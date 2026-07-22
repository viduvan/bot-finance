"""EMA Pullback Strategy — Rule-based signal generation.

This strategy identifies entries when price pulls back to an EMA
in a trending market, supported by multiple confirmation signals.

Entry logic:
  LONG:
    1. EMA 21 > EMA 50 (uptrend on entry timeframe)
    2. EMA 50 > EMA 200 (macro uptrend on higher timeframe, optional)
    3. Price pulls back to within 1×ATR of EMA 21
    4. RSI > 40 (not oversold) and < 70 (not overbought)
    5. MACD histogram turning positive (or already positive)
    6. Price above VWAP (intraday bias)

  SHORT:
    1. EMA 21 < EMA 50 (downtrend)
    2. Price rallies to within 1×ATR of EMA 21
    3. RSI < 60 and > 30
    4. MACD histogram turning negative
    5. Price below VWAP

Signal strength scoring (0-100):
  Each satisfied condition adds points → signal_score
  Only emit signal if score >= MIN_SCORE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)

# Minimum score required to emit a signal
MIN_SIGNAL_SCORE = 60
MIN_CANDLES = 60  # Need at least 60 candles for EMA200 to stabilize


@dataclass
class SignalResult:
    """Output from strategy evaluation."""

    signal: Literal["LONG", "SHORT", "NO_SIGNAL"]
    score: int                          # 0-100
    reasons: list[str] = field(default_factory=list)
    entry_zone_low: Decimal | None = None
    entry_zone_high: Decimal | None = None
    stop_loss_hint: Decimal | None = None  # Suggested SL price (Risk Engine will finalize)
    take_profit_hint: Decimal | None = None
    confidence: str = "LOW"             # LOW / MEDIUM / HIGH


class EMAPullbackStrategy:
    """Rule-based EMA Pullback strategy.

    Consumes pre-computed feature dicts from the FeatureEngine.
    Does NOT call external APIs — pure deterministic logic.
    """

    def evaluate(
        self,
        features_15m: dict,
        features_1h: dict,
        features_4h: dict,
    ) -> SignalResult:
        """Evaluate strategy across all timeframes.

        Args:
            features_15m: feature dict for entry timeframe (15m)
            features_1h: feature dict for trend timeframe (1h)
            features_4h: feature dict for macro timeframe (4h)

        Returns:
            SignalResult with signal direction, score, and metadata
        """
        # Check data sufficiency
        if not features_15m or not features_1h:
            return SignalResult(signal="NO_SIGNAL", score=0, reasons=["Insufficient features"])

        long_result = self._evaluate_long(features_15m, features_1h, features_4h)
        short_result = self._evaluate_short(features_15m, features_1h, features_4h)

        # Take the higher scoring signal
        if long_result.score > short_result.score and long_result.score >= MIN_SIGNAL_SCORE:
            return long_result
        if short_result.score > long_result.score and short_result.score >= MIN_SIGNAL_SCORE:
            return short_result

        # Both below threshold or tied
        best_score = max(long_result.score, short_result.score)
        reasons = long_result.reasons if long_result.score >= short_result.score else short_result.reasons
        return SignalResult(
            signal="NO_SIGNAL",
            score=best_score,
            reasons=reasons + [f"Score {best_score} below threshold {MIN_SIGNAL_SCORE}"],
        )

    def _evaluate_long(
        self,
        f15: dict,
        f1h: dict,
        f4h: dict,
    ) -> SignalResult:
        """Score LONG setup conditions."""
        score = 0
        reasons = []
        disqualifiers = []

        # ── Trend Confirmation ────────────────────────────────────

        # 1. EMA 21 > EMA 50 on 15m (core condition) — 20 pts
        ema_21 = self._get_decimal(f15, "ema_21")
        ema_50 = self._get_decimal(f15, "ema_50")
        if ema_21 and ema_50:
            if ema_21 > ema_50:
                score += 20
                reasons.append("EMA21 > EMA50 (15m uptrend)")
            else:
                disqualifiers.append("EMA21 < EMA50 (15m downtrend)")

        # 2. Price above EMA 50 on 1h (trend filter) — 15 pts
        close_1h = self._get_decimal(f1h, "close") or self._get_decimal(f1h, "last_price")
        ema_50_1h = self._get_decimal(f1h, "ema_50")
        if close_1h and ema_50_1h:
            if close_1h > ema_50_1h:
                score += 15
                reasons.append("Price > EMA50 (1h bullish)")
            else:
                disqualifiers.append("Price < EMA50 on 1h")

        # 3. Macro trend on 4h: EMA21 > EMA50 — 10 pts (optional)
        ema_21_4h = self._get_decimal(f4h, "ema_21")
        ema_50_4h = self._get_decimal(f4h, "ema_50")
        if ema_21_4h and ema_50_4h:
            if ema_21_4h > ema_50_4h:
                score += 10
                reasons.append("EMA21 > EMA50 (4h macro bullish)")

        # Hard stop if core trend not met
        if disqualifiers:
            return SignalResult(
                signal="LONG",
                score=score,
                reasons=reasons + disqualifiers,
            )

        # ── Pullback to EMA ───────────────────────────────────────

        # 4. Price within 1×ATR of EMA 21 (pullback zone) — 20 pts
        close_15 = self._get_decimal(f15, "close") or self._get_decimal(f15, "last_price")
        atr = self._get_decimal(f15, "atr_14")

        entry_zone_low = entry_zone_high = None
        if close_15 and ema_21 and atr:
            distance = abs(close_15 - ema_21)
            in_pullback_zone = distance <= atr
            entry_zone_low = ema_21 - atr * Decimal("0.5")
            entry_zone_high = ema_21 + atr * Decimal("0.5")

            if in_pullback_zone:
                score += 20
                reasons.append(f"Price within 1×ATR of EMA21 (pullback zone)")
            elif close_15 > ema_21 + atr * 2:
                disqualifiers.append("Price too extended from EMA21")

        # ── Momentum Confirmation ─────────────────────────────────

        # 5. RSI between 40-65 (healthy pullback in uptrend) — 15 pts
        rsi = self._get_decimal(f15, "rsi_14")
        if rsi is not None:
            if Decimal("40") <= rsi <= Decimal("65"):
                score += 15
                reasons.append(f"RSI {rsi} in healthy zone (40-65)")
            elif rsi < 30:
                disqualifiers.append(f"RSI {rsi} oversold — potential downtrend")
            elif rsi > 70:
                reasons.append(f"RSI {rsi} overbought — momentum strong but risk of reversal")

        # 6. MACD histogram positive or turning positive — 10 pts
        macd_hist = self._get_decimal(f15, "macd_histogram")
        macd_signal_type = f15.get("macd_signal_type", "")
        if macd_hist is not None:
            if macd_hist > 0:
                score += 10
                reasons.append("MACD histogram positive (bullish momentum)")
            elif macd_signal_type == "BULLISH_CROSS":
                score += 10
                reasons.append("MACD bullish cross (momentum turning)")

        # 7. Price above VWAP — 5 pts
        price_above_vwap = f15.get("price_above_vwap")
        if price_above_vwap is True:
            score += 5
            reasons.append("Price above VWAP (intraday bullish bias)")

        # 8. Volume confirmation — 5 pts
        volume_increasing = f15.get("volume_increasing")
        pressure_bias = f15.get("pressure_bias", "")
        if pressure_bias == "BULLISH":
            score += 5
            reasons.append("Buy pressure dominant in recent candles")

        # Compute stop loss hint (below EMA50 or recent swing low)
        stop_loss = None
        if ema_50 and atr:
            stop_loss = ema_50 - atr  # SL below EMA50

        # Compute take profit hint (1.5× risk from entry)
        take_profit = None
        if close_15 and stop_loss and close_15 > stop_loss:
            risk = close_15 - stop_loss
            take_profit = close_15 + risk * Decimal("2")  # 2:1 R/R target

        # Confidence level
        if score >= 80:
            confidence = "HIGH"
        elif score >= 65:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        return SignalResult(
            signal="LONG",
            score=score,
            reasons=reasons,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            stop_loss_hint=stop_loss,
            take_profit_hint=take_profit,
            confidence=confidence,
        )

    def _evaluate_short(
        self,
        f15: dict,
        f1h: dict,
        f4h: dict,
    ) -> SignalResult:
        """Score SHORT setup conditions (mirror of long logic)."""
        score = 0
        reasons = []
        disqualifiers = []

        # 1. EMA 21 < EMA 50 on 15m — 20 pts
        ema_21 = self._get_decimal(f15, "ema_21")
        ema_50 = self._get_decimal(f15, "ema_50")
        if ema_21 and ema_50:
            if ema_21 < ema_50:
                score += 20
                reasons.append("EMA21 < EMA50 (15m downtrend)")
            else:
                disqualifiers.append("EMA21 > EMA50 (15m uptrend — not short)")

        # 2. Price below EMA 50 on 1h — 15 pts
        close_1h = self._get_decimal(f1h, "close") or self._get_decimal(f1h, "last_price")
        ema_50_1h = self._get_decimal(f1h, "ema_50")
        if close_1h and ema_50_1h:
            if close_1h < ema_50_1h:
                score += 15
                reasons.append("Price < EMA50 (1h bearish)")
            else:
                disqualifiers.append("Price > EMA50 on 1h — not short")

        if disqualifiers:
            return SignalResult(
                signal="SHORT",
                score=score,
                reasons=reasons + disqualifiers,
            )

        # 3. Macro trend 4h — 10 pts
        ema_21_4h = self._get_decimal(f4h, "ema_21")
        ema_50_4h = self._get_decimal(f4h, "ema_50")
        if ema_21_4h and ema_50_4h and ema_21_4h < ema_50_4h:
            score += 10
            reasons.append("EMA21 < EMA50 (4h macro bearish)")

        # 4. Price within 1×ATR of EMA 21 (rally to resistance) — 20 pts
        close_15 = self._get_decimal(f15, "close") or self._get_decimal(f15, "last_price")
        atr = self._get_decimal(f15, "atr_14")

        entry_zone_low = entry_zone_high = None
        if close_15 and ema_21 and atr:
            distance = abs(close_15 - ema_21)
            if distance <= atr:
                score += 20
                reasons.append("Price within 1×ATR of EMA21 (rally to resistance)")
            entry_zone_low = ema_21 - atr * Decimal("0.5")
            entry_zone_high = ema_21 + atr * Decimal("0.5")

        # 5. RSI between 35-60 — 15 pts
        rsi = self._get_decimal(f15, "rsi_14")
        if rsi is not None:
            if Decimal("35") <= rsi <= Decimal("60"):
                score += 15
                reasons.append(f"RSI {rsi} in healthy zone for short")

        # 6. MACD histogram negative or turning negative — 10 pts
        macd_hist = self._get_decimal(f15, "macd_histogram")
        macd_signal_type = f15.get("macd_signal_type", "")
        if macd_hist is not None:
            if macd_hist < 0:
                score += 10
                reasons.append("MACD histogram negative (bearish momentum)")
            elif macd_signal_type == "BEARISH_CROSS":
                score += 10
                reasons.append("MACD bearish cross")

        # 7. Below VWAP — 5 pts
        price_above_vwap = f15.get("price_above_vwap")
        if price_above_vwap is False:
            score += 5
            reasons.append("Price below VWAP (intraday bearish bias)")

        # 8. Sell pressure — 5 pts
        if f15.get("pressure_bias") == "BEARISH":
            score += 5
            reasons.append("Sell pressure dominant")

        # Stop loss and target
        stop_loss = None
        take_profit = None
        if ema_50 and atr:
            stop_loss = ema_50 + atr  # SL above EMA50
        if close_15 and stop_loss and close_15 < stop_loss:
            risk = stop_loss - close_15
            take_profit = close_15 - risk * Decimal("2")

        confidence = "HIGH" if score >= 80 else ("MEDIUM" if score >= 65 else "LOW")

        return SignalResult(
            signal="SHORT",
            score=score,
            reasons=reasons,
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
            stop_loss_hint=stop_loss,
            take_profit_hint=take_profit,
            confidence=confidence,
        )

    @staticmethod
    def _get_decimal(features: dict, key: str) -> Decimal | None:
        """Safely extract a Decimal value from a feature dict."""
        val = features.get(key)
        if val is None:
            return None
        try:
            return Decimal(str(val))
        except Exception:
            return None


# Shared singleton
ema_pullback_strategy = EMAPullbackStrategy()
