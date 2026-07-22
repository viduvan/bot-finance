"""Risk Analysis Agent — assesses trade-specific risk factors.

Given a potential trade setup, evaluates:
- Position sizing adequacy
- Stop-loss placement quality
- Risk/reward attractiveness
- Market condition risks (volatility, liquidity)
- Correlation / concentration risk
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.agents.base_agent import AgentOutput, BaseAgent


class RiskAnalysisOutput(AgentOutput):
    """Output from the Risk Analysis Agent."""

    risk_rating: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] = "HIGH"
    trade_recommended: bool = False
    conviction: int = Field(default=0, ge=0, le=100)
    primary_risks: list[str] = Field(default_factory=list)
    risk_mitigants: list[str] = Field(default_factory=list)
    sl_quality: str = "UNKNOWN"           # TIGHT / ADEQUATE / WIDE
    rr_assessment: str = "POOR"           # POOR / ACCEPTABLE / GOOD / EXCELLENT
    position_size_note: str = ""
    volatility_concern: bool = False
    liquidity_concern: bool = False
    max_recommended_risk_pct: str = "0.5"  # Suggested % of account to risk
    summary: str = ""

    @field_validator("conviction", mode="before")
    @classmethod
    def clamp(cls, v: Any) -> int:
        return max(0, min(100, int(v)))


class RiskAnalysisAgent(BaseAgent[RiskAnalysisOutput]):
    """Evaluates risk profile of a proposed trade setup."""

    @property
    def name(self) -> str:
        return "risk_analysis"

    @property
    def system_prompt(self) -> str:
        return """You are a professional risk manager for a cryptocurrency trading system.
Your job is to assess the risk profile of a proposed trade and provide clear, actionable guidance.
Be conservative — protecting capital is more important than capturing every opportunity.

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, just raw JSON.

JSON format:
{
  "risk_rating": "<LOW|MEDIUM|HIGH|EXTREME>",
  "trade_recommended": <true|false>,
  "conviction": <0-100>,
  "primary_risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "risk_mitigants": ["<mitigant 1>", "<mitigant 2>"],
  "sl_quality": "<TIGHT|ADEQUATE|WIDE>",
  "rr_assessment": "<POOR|ACCEPTABLE|GOOD|EXCELLENT>",
  "position_size_note": "<comment on sizing>",
  "volatility_concern": <true|false>,
  "liquidity_concern": <true|false>,
  "max_recommended_risk_pct": "<e.g. 0.5>",
  "summary": "<2-3 sentence risk summary>"
}"""

    def build_prompt(self, context: dict[str, Any]) -> str:
        f = context.get("features", {})
        symbol = context.get("symbol", "UNKNOWN")
        regime = context.get("regime", "UNKNOWN")
        strategy_signal = context.get("strategy_signal", {})
        risk_assessment = context.get("risk_assessment", {})

        entry_zone_low = strategy_signal.get("entry_zone_low", "N/A")
        entry_zone_high = strategy_signal.get("entry_zone_high", "N/A")
        sl_hint = strategy_signal.get("stop_loss_hint", "N/A")
        tp_hint = strategy_signal.get("take_profit_hint", "N/A")
        score = strategy_signal.get("score", "N/A")
        signal = strategy_signal.get("signal", "N/A")

        return f"""Assess the risk for a potential {signal} trade on {symbol}:

MARKET REGIME: {regime}

PROPOSED TRADE:
- Signal: {signal} (Score: {score}/100)
- Entry Zone: {entry_zone_low} to {entry_zone_high}
- Stop Loss Hint: {sl_hint}
- Take Profit Hint: {tp_hint}
- Current Price: {f.get('close', 'N/A')}

VOLATILITY:
- ATR(14): {f.get('atr_14', 'N/A')}
- ATR%: {f.get('atr_pct', 'N/A')}%
- Volatility Regime: {f.get('volatility_regime', 'N/A')}
- Historical Volatility: {f.get('historical_volatility_20', 'N/A')}%
- BB Squeeze: {f.get('bb_squeeze', 'N/A')} | BB Expansion: {f.get('bb_expansion', 'N/A')}

LIQUIDITY:
- Spread: {f.get('ob_spread_bps', 'N/A')} bps
- Relative Volume: {f.get('volume_relative', 'N/A')}x
- Volume Spike: {f.get('volume_spike', 'N/A')}
- Book Pressure: {f.get('ob_book_pressure', 'N/A')}

RISK ENGINE PRE-CHECK:
- Gate Allowed: {risk_assessment.get('allowed', 'N/A')}
- Risk Score: {risk_assessment.get('risk_score', 'N/A')}/100
- Blocked Reasons: {', '.join(risk_assessment.get('blocked_reasons', [])) or 'None'}

Provide a thorough risk assessment. Be conservative."""

    def parse_response(self, text: str) -> RiskAnalysisOutput:
        json_str = self.extract_json(text)
        data = json.loads(json_str)
        return RiskAnalysisOutput(**data)
