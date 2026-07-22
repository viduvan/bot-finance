"""Critic Agent — adversarial review of all other agent outputs.

The Critic challenges the analysis, identifies contradictions,
and provides an independent final recommendation.
It prevents groupthink by actively looking for what could go wrong.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, field_validator

from app.agents.base_agent import AgentOutput, BaseAgent


class CriticOutput(AgentOutput):
    """Output from the Critic Agent."""

    final_recommendation: Literal["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL", "AVOID"] = "HOLD"
    conviction: int = Field(default=0, ge=0, le=100)
    agrees_with_consensus: bool = True
    contradictions_found: list[str] = Field(default_factory=list)
    strongest_bearish_argument: str = ""
    strongest_bullish_argument: str = ""
    critical_warning: str = ""            # Empty if no major warning
    quality_score: int = Field(default=0, ge=0, le=100)  # Quality of overall analysis
    proceed_to_proposal: bool = False     # True only if trade should be proposed
    rejection_reason: str = ""           # If not proceeding, why
    summary: str = ""

    @field_validator("conviction", "quality_score", mode="before")
    @classmethod
    def clamp(cls, v: Any) -> int:
        return max(0, min(100, int(v)))


class CriticAgent(BaseAgent[CriticOutput]):
    """Adversarial critic that reviews the full analysis pipeline output."""

    @property
    def name(self) -> str:
        return "critic"

    @property
    def system_prompt(self) -> str:
        return """You are an adversarial critic and risk manager for a cryptocurrency trading system.
Your job is to challenge the analysis, find contradictions, and prevent overconfident trading decisions.
You should actively look for reasons NOT to trade.
Capital preservation is the highest priority.

Key questions to answer:
1. Do the agents agree with each other?
2. What could go wrong with this trade?
3. Is the risk/reward actually worth it given the regime?
4. Are there any red flags being ignored?

You MUST respond with ONLY a valid JSON object. No explanation, no markdown, just raw JSON.

JSON format:
{
  "final_recommendation": "<STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL|AVOID>",
  "conviction": <0-100>,
  "agrees_with_consensus": <true|false>,
  "contradictions_found": ["<contradiction 1>", "<contradiction 2>"],
  "strongest_bearish_argument": "<most compelling bearish point>",
  "strongest_bullish_argument": "<most compelling bullish point>",
  "critical_warning": "<major warning if any, else empty string>",
  "quality_score": <0-100, quality of overall analysis>,
  "proceed_to_proposal": <true|false>,
  "rejection_reason": "<reason if not proceeding, else empty string>",
  "summary": "<2-3 sentence final assessment>"
}"""

    def build_prompt(self, context: dict[str, Any]) -> str:
        symbol = context.get("symbol", "UNKNOWN")
        regime_out = context.get("market_regime_output", {})
        tech_out = context.get("technical_output", {})
        flow_out = context.get("order_flow_output", {})
        risk_out = context.get("risk_analysis_output", {})
        strategy_signal = context.get("strategy_signal", {})

        return f"""You are reviewing a trade analysis for {symbol}. Be highly critical.

═══ AGENT SUMMARIES ═══

MARKET REGIME AGENT:
- Regime: {regime_out.get('regime', 'N/A')}
- Bias: {regime_out.get('trading_bias', 'N/A')}
- Conviction: {regime_out.get('conviction', 'N/A')}/100
- Summary: {regime_out.get('summary', 'N/A')}

TECHNICAL AGENT:
- Signal: {tech_out.get('signal', 'N/A')}
- EMA Alignment: {tech_out.get('ema_alignment', 'N/A')}
- RSI: {tech_out.get('rsi_signal', 'N/A')}
- Pattern: {tech_out.get('pattern_detected', 'None')}
- Entry Rationale: {tech_out.get('entry_rationale', 'N/A')}
- Conviction: {tech_out.get('conviction', 'N/A')}/100

ORDER FLOW AGENT:
- Flow Bias: {flow_out.get('flow_bias', 'N/A')}
- Volume Signal: {flow_out.get('volume_signal', 'N/A')}
- VWAP Position: {flow_out.get('vwap_position', 'N/A')}
- Book Pressure: {flow_out.get('book_pressure', 'N/A')}
- Summary: {flow_out.get('summary', 'N/A')}
- Conviction: {flow_out.get('conviction', 'N/A')}/100

RISK ANALYSIS AGENT:
- Risk Rating: {risk_out.get('risk_rating', 'N/A')}
- Trade Recommended: {risk_out.get('trade_recommended', 'N/A')}
- Primary Risks: {', '.join(risk_out.get('primary_risks', [])) or 'None listed'}
- SL Quality: {risk_out.get('sl_quality', 'N/A')}
- R/R Assessment: {risk_out.get('rr_assessment', 'N/A')}
- Max Risk %: {risk_out.get('max_recommended_risk_pct', 'N/A')}
- Summary: {risk_out.get('summary', 'N/A')}

RULE-BASED STRATEGY:
- Signal: {strategy_signal.get('signal', 'N/A')}
- Score: {strategy_signal.get('score', 'N/A')}/100
- Confidence: {strategy_signal.get('confidence', 'N/A')}

═══ YOUR TASK ═══
Challenge every aspect of this analysis. Find contradictions.
Only recommend proceeding to proposal if there is STRONG confluence across ALL agents.
When in doubt, AVOID."""

    def parse_response(self, text: str) -> CriticOutput:
        json_str = self.extract_json(text)
        data = json.loads(json_str)
        return CriticOutput(**data)
