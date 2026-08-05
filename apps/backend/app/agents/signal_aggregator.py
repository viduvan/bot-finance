"""Signal Aggregator — weighted consensus from all agent outputs.

Combines outputs from 4 analysis agents into a single consensus signal.
Uses configurable weights from constants.AGENT_WEIGHTS.

Aggregation logic:
1. Map each agent's signal to a numeric score (-2 to +2)
2. Apply agent weights
3. Compute weighted average
4. Map back to final direction + consensus score
"""

from __future__ import annotations

from typing import Any, Literal

import structlog

from app.core.constants import DEFAULT_AGENT_WEIGHTS as AGENT_WEIGHTS

logger = structlog.get_logger(__name__)

SIGNAL_SCORES: dict[str, float] = {
    "STRONG_BUY": 2.0,
    "BUY": 1.0,
    "NEUTRAL": 0.0,
    "HOLD": 0.0,
    "SELL": -1.0,
    "STRONG_SELL": -2.0,
    "AVOID": -1.5,
    "LONG_BIAS": 1.0,
    "SHORT_BIAS": -1.0,
    "UNKNOWN": 0.0,
}


class AggregatedSignal:
    """Result of the signal aggregation process."""

    def __init__(
        self,
        direction: Literal["LONG", "SHORT", "NO_SIGNAL"],
        consensus_score: float,  # -100 to +100
        agent_scores: dict[str, float],
        weights_used: dict[str, float],
        agreement_pct: float,  # % of agents that agree on direction
    ) -> None:
        self.direction = direction
        self.consensus_score = consensus_score
        self.agent_scores = agent_scores
        self.weights_used = weights_used
        self.agreement_pct = agreement_pct

    @property
    def is_actionable(self) -> bool:
        """True if consensus is strong enough to warrant a proposal."""
        return abs(self.consensus_score) >= 50 and self.agreement_pct >= 60

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "consensus_score": round(self.consensus_score, 1),
            "agent_scores": {k: round(v, 2) for k, v in self.agent_scores.items()},
            "weights_used": self.weights_used,
            "agreement_pct": round(self.agreement_pct, 1),
            "is_actionable": self.is_actionable,
        }


class SignalAggregator:
    """Aggregates agent signals using weighted consensus.

    Weights (from constants.AGENT_WEIGHTS):
    - market_regime:  0.25
    - technical:      0.30
    - order_flow:     0.20
    - risk_analysis:  0.25
    """

    def aggregate(
        self,
        regime_output: dict,
        technical_output: dict,
        order_flow_output: dict,
        risk_output: dict,
        strategy_signal: dict,
    ) -> AggregatedSignal:
        """Compute weighted consensus signal.

        Returns direction LONG / SHORT / NO_SIGNAL and consensus score.
        """
        weights = AGENT_WEIGHTS

        # Extract signal fields
        regime_signal = regime_output.get("trading_bias", "NEUTRAL")
        tech_signal = technical_output.get("signal", "NEUTRAL")
        flow_signal = order_flow_output.get("flow_bias", "NEUTRAL")
        risk_recommended = risk_output.get("trade_recommended", False)

        # Strategy rule-based signal
        strategy_direction = strategy_signal.get("signal", "NO_SIGNAL")
        strategy_score = strategy_signal.get("score", 0)

        # Map to numeric scores
        regime_score = SIGNAL_SCORES.get(regime_signal, 0.0)
        tech_score = SIGNAL_SCORES.get(tech_signal, 0.0)
        flow_score = SIGNAL_SCORES.get(flow_signal, 0.0)
        risk_score = 1.0 if risk_recommended else -0.5  # Risk veto if not recommended

        agent_scores = {
            "market_regime": regime_score,
            "technical": tech_score,
            "order_flow": flow_score,
            "risk_analysis": risk_score,
        }

        # Weighted sum (range -2 to +2)
        w_regime = weights.get("market_regime", 0.25)
        w_tech = weights.get("technical", 0.30)
        w_flow = weights.get("order_flow", 0.20)
        w_risk = weights.get("risk_analysis", 0.25)

        weighted_sum = (
            regime_score * w_regime
            + tech_score * w_tech
            + flow_score * w_flow
            + risk_score * w_risk
        )

        # Normalize to -100 to +100 scale
        consensus_score = weighted_sum * 50  # max weighted_sum ~2.0 → 100

        # Factor in rule-based strategy (10% weight)
        if strategy_direction in ("LONG", "SHORT"):
            strategy_numeric = (strategy_score - 50) / 50  # 0-100 → -1 to +1
            if strategy_direction == "SHORT":
                strategy_numeric = -strategy_numeric
            consensus_score = consensus_score * 0.9 + strategy_numeric * 50 * 0.1

        # Determine direction
        if consensus_score >= 30:
            direction = "LONG"
        elif consensus_score <= -30:
            direction = "SHORT"
        else:
            direction = "NO_SIGNAL"

        # Agreement percentage
        bullish_count = sum(1 for s in agent_scores.values() if s > 0)
        bearish_count = sum(1 for s in agent_scores.values() if s < 0)
        total = len(agent_scores)

        if direction == "LONG":
            agreement_pct = (bullish_count / total) * 100
        elif direction == "SHORT":
            agreement_pct = (bearish_count / total) * 100
        else:
            agreement_pct = 0.0

        logger.info(
            "signal_aggregated",
            direction=direction,
            consensus_score=round(consensus_score, 1),
            agreement_pct=round(agreement_pct, 1),
            agent_scores=agent_scores,
        )

        return AggregatedSignal(
            direction=direction,
            consensus_score=consensus_score,
            agent_scores=agent_scores,
            weights_used={
                "market_regime": w_regime,
                "technical": w_tech,
                "order_flow": w_flow,
                "risk_analysis": w_risk,
            },
            agreement_pct=agreement_pct,
        )
