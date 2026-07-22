"""Market Regime Agent — classifies the current market environment.

Analyzes volatility, trend strength, and macro conditions to determine
the trading regime. Helps other agents calibrate their risk appetite.

Output: regime label + conviction score + key observations.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.agents.base_agent import AgentOutput, BaseAgent

MarketRegimeType = Literal[
    "STRONG_BULL",
    "BULL",
    "RANGING",
    "BEAR",
    "STRONG_BEAR",
    "HIGH_VOLATILITY",
    "UNKNOWN",
]


class MarketRegimeOutput(AgentOutput):
    """Output from the Market Regime Agent."""

    regime: MarketRegimeType = "UNKNOWN"
    conviction: int = Field(default=0, ge=0, le=100, description="Confidence 0-100")
    trend_direction: str = "NEUTRAL"
    volatility_level: str = "NORMAL"
    key_observations: list[str] = Field(default_factory=list)
    trading_bias: Literal["LONG_BIAS", "SHORT_BIAS", "NEUTRAL", "AVOID"] = "NEUTRAL"
    summary: str = ""

    @field_validator("conviction", mode="before")
    @classmethod
    def clamp_conviction(cls, v: Any) -> int:
        return max(0, min(100, int(v)))


class MarketRegimeAgent(BaseAgent[MarketRegimeOutput]):
    """Analyzes macro market regime from multi-timeframe features."""

    @property
    def name(self) -> str:
        return "market_regime"

    @property
    def system_prompt(self) -> str:
        return """You are an expert quantitative analyst specializing in market regime classification.
Your job is to analyze technical indicators across multiple timeframes and classify the current market regime.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, just raw JSON.

JSON format:
{
  "regime": "<STRONG_BULL|BULL|RANGING|BEAR|STRONG_BEAR|HIGH_VOLATILITY>",
  "conviction": <0-100 integer>,
  "trend_direction": "<BULLISH|BEARISH|NEUTRAL>",
  "volatility_level": "<LOW|NORMAL|HIGH|EXTREME>",
  "key_observations": ["<observation 1>", "<observation 2>", "<observation 3>"],
  "trading_bias": "<LONG_BIAS|SHORT_BIAS|NEUTRAL|AVOID>",
  "summary": "<1-2 sentence market summary>"
}"""

    def build_prompt(self, context: dict[str, Any]) -> str:
        features = context.get("features", {})
        symbol = context.get("symbol", "UNKNOWN")

        # Extract key indicators
        ema_21 = features.get("ema_21", "N/A")
        ema_50 = features.get("ema_50", "N/A")
        ema_200 = features.get("ema_200", "N/A")
        rsi = features.get("rsi_14", "N/A")
        atr_pct = features.get("atr_pct", "N/A")
        trend = features.get("trend_direction", "N/A")
        vol_regime = features.get("volatility_regime", "N/A")
        macd_type = features.get("macd_signal_type", "N/A")
        hv = features.get("historical_volatility_20", "N/A")
        price = features.get("close", "N/A")

        # 4h macro context
        ema_21_4h = features.get("tf4h_ema_21", "N/A")
        ema_50_4h = features.get("tf4h_ema_50", "N/A")
        trend_4h = features.get("tf4h_trend_direction", "N/A")

        return f"""Analyze the market regime for {symbol}:

PRICE: {price}

15-MINUTE TIMEFRAME:
- EMA 21: {ema_21} | EMA 50: {ema_50} | EMA 200: {ema_200}
- RSI(14): {rsi}
- ATR%: {atr_pct}% (Volatility: {vol_regime})
- Historical Volatility (annualized): {hv}%
- MACD Signal: {macd_type}
- Market Structure Trend: {trend}

4-HOUR TIMEFRAME (MACRO):
- EMA 21: {ema_21_4h} | EMA 50: {ema_50_4h}
- Trend: {trend_4h}

Based on this data, classify the current market regime. Be precise and data-driven."""

    def parse_response(self, text: str) -> MarketRegimeOutput:
        json_str = self.extract_json(text)
        data = json.loads(json_str)
        return MarketRegimeOutput(**data)
