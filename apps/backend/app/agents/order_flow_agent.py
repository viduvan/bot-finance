"""Order Flow Agent — analyzes volume and order book pressure.

Examines buying/selling pressure from volume distribution,
VWAP position, OBV trend, and order book imbalance.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.agents.base_agent import AgentOutput, BaseAgent


class OrderFlowOutput(AgentOutput):
    """Output from the Order Flow Agent."""

    flow_bias: Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"] = "NEUTRAL"
    conviction: int = Field(default=0, ge=0, le=100)
    volume_signal: str = "NEUTRAL"  # ABOVE_AVERAGE / BELOW_AVERAGE / SPIKE / DRYING_UP
    vwap_position: str = "NEUTRAL"  # ABOVE / BELOW / AT
    obv_trend: str = "NEUTRAL"  # RISING / FALLING / FLAT
    book_pressure: str = "NEUTRAL"  # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
    buy_pressure_pct: str = "50"  # Percentage of volume that is buying
    key_observations: list[str] = Field(default_factory=list)
    summary: str = ""

    @field_validator("conviction", mode="before")
    @classmethod
    def clamp(cls, v: Any) -> int:
        return max(0, min(100, int(v)))


class OrderFlowAgent(BaseAgent[OrderFlowOutput]):
    """Analyzes volume and order book data to assess smart money flow."""

    @property
    def name(self) -> str:
        return "order_flow"

    @property
    def system_prompt(self) -> str:
        return """You are an expert order flow analyst for cryptocurrency markets.
You analyze volume, VWAP, OBV, and order book data to identify institutional buying or selling pressure.
Focus on unusual volume, VWAP deviation, and order book imbalances.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, just raw JSON.

JSON format:
{
  "flow_bias": "<STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL>",
  "conviction": <0-100>,
  "volume_signal": "<ABOVE_AVERAGE|BELOW_AVERAGE|SPIKE|DRYING_UP>",
  "vwap_position": "<ABOVE|BELOW|AT>",
  "obv_trend": "<RISING|FALLING|FLAT>",
  "book_pressure": "<STRONG_BUY|BUY|NEUTRAL|SELL|STRONG_SELL>",
  "buy_pressure_pct": "<percentage string, e.g. '62'>",
  "key_observations": ["<observation 1>", "<observation 2>"],
  "summary": "<1-2 sentence summary of order flow>"
}"""

    def build_prompt(self, context: dict[str, Any]) -> str:
        f = context.get("features", {})
        symbol = context.get("symbol", "UNKNOWN")

        return f"""Analyze order flow for {symbol}:

VOLUME ANALYSIS:
- Current Volume: {f.get("volume_current", "N/A")}
- Volume SMA(20): {f.get("volume_sma_20", "N/A")}
- Relative Volume: {f.get("volume_relative", "N/A")}x average
- Volume Spike: {f.get("volume_spike", "N/A")}
- Volume Trend (3-candle slope): {f.get("volume_trend_slope", "N/A")}
- Volume Increasing: {f.get("volume_increasing", "N/A")}

BUYING/SELLING PRESSURE:
- Buy Pressure: {f.get("buy_pressure_pct", "N/A")}%
- Sell Pressure: {f.get("sell_pressure_pct", "N/A")}%
- Pressure Bias: {f.get("pressure_bias", "N/A")}

VWAP:
- VWAP: {f.get("vwap", "N/A")}
- Price Above VWAP: {f.get("price_above_vwap", "N/A")}
- Current Price: {f.get("close", "N/A")}

ON-BALANCE VOLUME:
- OBV: {f.get("obv", "N/A")}

ORDER BOOK (if available):
- Best Bid: {f.get("ob_best_bid", "N/A")} | Best Ask: {f.get("ob_best_ask", "N/A")}
- Spread: {f.get("ob_spread_bps", "N/A")} bps
- Order Imbalance: {f.get("ob_order_imbalance_pct", "N/A")}%
- Book Pressure: {f.get("ob_book_pressure", "N/A")}
- Bid Wall: {f.get("ob_bid_wall", "N/A")} | Ask Wall: {f.get("ob_ask_wall", "N/A")}

Based on this data, determine if smart money is accumulating or distributing."""

    def parse_response(self, text: str) -> OrderFlowOutput:
        json_str = self.extract_json(text)
        data = json.loads(json_str)
        return OrderFlowOutput(**data)
