"""Technical Agent — pattern recognition and indicator-based signal analysis.

Analyzes EMA structure, RSI divergence, MACD crossovers, and Bollinger Band
position to provide a directional trade signal with entry/exit rationale.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.agents.base_agent import AgentOutput, BaseAgent


class TechnicalOutput(AgentOutput):
    """Output from the Technical Analysis Agent."""

    signal: Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"] = "NEUTRAL"
    conviction: int = Field(default=0, ge=0, le=100)
    ema_alignment: str = "MIXED"  # BULLISH_STACK / BEARISH_STACK / MIXED
    rsi_signal: str = "NEUTRAL"  # OVERSOLD / NEUTRAL / OVERBOUGHT / DIVERGENCE
    macd_signal: str = "NEUTRAL"  # BULLISH_CROSS / BEARISH_CROSS / BULLISH / BEARISH
    bb_signal: str = "NEUTRAL"  # NEAR_UPPER / NEAR_LOWER / SQUEEZE / EXPANSION
    pattern_detected: str = ""  # Named pattern if found (e.g. 'EMA PULLBACK')
    entry_rationale: str = ""
    risk_note: str = ""
    key_levels: list[str] = Field(default_factory=list)

    @field_validator("conviction", mode="before")
    @classmethod
    def clamp(cls, v: Any) -> int:
        return max(0, min(100, int(v)))


class TechnicalAgent(BaseAgent[TechnicalOutput]):
    """Performs technical analysis and identifies trade setups."""

    @property
    def name(self) -> str:
        return "technical"

    @property
    def system_prompt(self) -> str:
        return """You are an expert technical analyst for cryptocurrency markets.
You analyze indicator data and identify high-probability trade setups.
Focus on EMA alignment (trend), RSI zones, MACD momentum, and Bollinger Band position.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, just raw JSON.

JSON format:
{
  "signal": "<STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL>",
  "conviction": <0-100>,
  "ema_alignment": "<BULLISH_STACK|BEARISH_STACK|MIXED>",
  "rsi_signal": "<OVERSOLD|NEUTRAL|OVERBOUGHT|DIVERGENCE>",
  "macd_signal": "<BULLISH_CROSS|BEARISH_CROSS|BULLISH|BEARISH|NEUTRAL>",
  "bb_signal": "<NEAR_UPPER|NEAR_LOWER|SQUEEZE|EXPANSION|NEUTRAL>",
  "pattern_detected": "<pattern name or empty string>",
  "entry_rationale": "<why to enter or not>",
  "risk_note": "<specific risk to watch>",
  "key_levels": ["<level 1>", "<level 2>"]
}"""

    def build_prompt(self, context: dict[str, Any]) -> str:
        f = context.get("features", {})
        symbol = context.get("symbol", "UNKNOWN")
        regime = context.get("regime", "UNKNOWN")

        return f"""Perform technical analysis for {symbol} (Market Regime: {regime}):

PRICE ACTION:
- Current Price: {f.get("close", "N/A")}
- Open: {f.get("open", "N/A")} | High: {f.get("high", "N/A")} | Low: {f.get("low", "N/A")}
- Candle Type: {f.get("candle_type", "N/A")}

EMA STRUCTURE (15m):
- EMA 9: {f.get("ema_9", "N/A")}
- EMA 21: {f.get("ema_21", "N/A")}
- EMA 50: {f.get("ema_50", "N/A")}
- EMA 200: {f.get("ema_200", "N/A")}
- EMA 9>21 (bullish): {f.get("ema_9_21_bullish", "N/A")}
- EMA 21>50 (bullish): {f.get("ema_21_50_bullish", "N/A")}

MOMENTUM:
- RSI(14): {f.get("rsi_14", "N/A")} [{f.get("rsi_zone", "N/A")}]
- MACD Line: {f.get("macd_line", "N/A")}
- MACD Signal: {f.get("macd_signal", "N/A")}
- MACD Histogram: {f.get("macd_histogram", "N/A")}
- MACD Signal Type: {f.get("macd_signal_type", "N/A")}
- Stoch RSI K: {f.get("stoch_rsi_k", "N/A")} | D: {f.get("stoch_rsi_d", "N/A")}

BOLLINGER BANDS (20,2):
- Upper: {f.get("bb_upper", "N/A")} | Middle: {f.get("bb_middle", "N/A")} | Lower: {f.get("bb_lower", "N/A")}
- %B: {f.get("bb_pct_b", "N/A")} | Bandwidth: {f.get("bb_bandwidth", "N/A")}
- Price Position: {f.get("bb_position", "N/A")}

STRUCTURE:
- Trend: {f.get("trend_direction", "N/A")}
- Nearest Resistance: {f.get("nearest_resistance", "N/A")}
- Nearest Support: {f.get("nearest_support", "N/A")}
- S/R Zone: {f.get("sr_zone", "N/A")}

Identify if an EMA Pullback or any high-probability setup is present."""

    def parse_response(self, text: str) -> TechnicalOutput:
        json_str = self.extract_json(text)
        data = json.loads(json_str)
        return TechnicalOutput(**data)
