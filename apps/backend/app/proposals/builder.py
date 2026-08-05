"""Proposal Builder — constructs TradeProposal dicts from AnalysisResult.

Takes the output of the multi-agent orchestrator and builds a
structured proposal dict ready for DB insertion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

DIRECTION_TO_RECOMMENDATION = {
    "LONG": "BUY",
    "SHORT": "SELL",
    "NO_SIGNAL": "HOLD",
}


class ProposalBuilder:
    """Builds a trade proposal dict from an analysis result.

    The result dict can be directly inserted into TradeProposal DB model.
    """

    def build(
        self,
        analysis_result: dict[str, Any],
        current_price: Decimal,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Build a proposal from analysis result.

        Args:
            analysis_result: Full AnalysisResult.to_dict() output
            current_price: Latest market price (used as current_price snapshot)
            created_by: User or system identifier

        Returns:
            dict ready for DB insertion into TradeProposal

        Raises:
            ValueError: If analysis result does not recommend proceeding
        """
        if not analysis_result.get("proceed_to_proposal"):
            raise ValueError(
                "Cannot build proposal: analysis result does not recommend proceed_to_proposal. "
                f"proceed={analysis_result.get('proceed_to_proposal')}"
            )

        direction = analysis_result.get("final_direction", "NO_SIGNAL")
        recommendation = DIRECTION_TO_RECOMMENDATION.get(direction, "HOLD")
        consensus_score = float(analysis_result.get("consensus_score", 0))

        # Extract from risk assessment
        risk = analysis_result.get("risk_assessment") or {}
        stop_loss = self._to_decimal(risk.get("stop_loss"))
        take_profit = self._to_decimal(risk.get("take_profit"))
        quantity = self._to_decimal(risk.get("quantity"))
        risk_amount = self._to_decimal(risk.get("risk_amount"))
        rr_ratio = self._to_decimal(risk.get("risk_reward_ratio"))
        fee = self._to_decimal(risk.get("estimated_fee"))
        slippage = self._to_decimal(risk.get("estimated_slippage"))

        # Extract from strategy signal for entry zone
        strategy = analysis_result.get("strategy_signal") or {}
        entry_low = self._to_decimal(strategy.get("entry_zone_low"))
        entry_high = self._to_decimal(strategy.get("entry_zone_high"))

        # Suggested price = current price or mid of entry zone
        if entry_low and entry_high:
            suggested_price = (entry_low + entry_high) / 2
        else:
            suggested_price = current_price

        # Build TP structure (allow multiple targets in future)
        take_profit_prices = {}
        if take_profit:
            take_profit_prices = {"tp1": str(take_profit)}

        # Build agent consensus snapshot
        agent_consensus = {
            "direction": direction,
            "consensus_score": round(consensus_score, 1),
            "market_regime": (analysis_result.get("market_regime") or {}).get("regime", "UNKNOWN"),
            "technical_signal": (analysis_result.get("technical") or {}).get("signal", "NEUTRAL"),
            "flow_bias": (analysis_result.get("order_flow") or {}).get("flow_bias", "NEUTRAL"),
            "risk_rating": (analysis_result.get("risk_analysis") or {}).get("risk_rating", "HIGH"),
            "critic_recommendation": (analysis_result.get("critic") or {}).get(
                "final_recommendation", "HOLD"
            ),
        }

        # Supporting reasons + warnings
        critic = analysis_result.get("critic") or {}
        risk_analysis = analysis_result.get("risk_analysis") or {}
        supporting_reasons = [
            critic.get("summary", ""),
            critic.get("strongest_bullish_argument", ""),
        ]
        supporting_reasons = [r for r in supporting_reasons if r]

        risk_warnings = risk_analysis.get("primary_risks", [])
        critic_objections = critic.get("contradictions_found", [])

        # Estimated profit
        estimated_profit = None
        if risk_amount and rr_ratio:
            estimated_profit = risk_amount * rr_ratio

        # Expiration
        expires_at = datetime.now(UTC) + timedelta(seconds=settings.proposal_expiration_seconds)

        # Confidence: normalize consensus score to 0-1
        confidence = min(1.0, max(0.0, abs(consensus_score) / 100))

        proposal = {
            "workflow_id": analysis_result.get("workflow_id"),
            "symbol": analysis_result["symbol"],
            "market": "SPOT",
            "recommendation": recommendation,
            "status": "DRAFT",
            "current_price": current_price,
            "entry_zone_min": entry_low,
            "entry_zone_max": entry_high,
            "suggested_order_type": "LIMIT",
            "suggested_price": suggested_price,
            "suggested_quantity": quantity,
            "stop_loss_price": stop_loss,
            "take_profit_prices": take_profit_prices,
            "estimated_risk_amount": risk_amount,
            "estimated_profit_amount": estimated_profit,
            "risk_reward_ratio": rr_ratio,
            "estimated_fee": fee,
            "estimated_slippage": slippage,
            "confidence": Decimal(str(round(confidence, 4))),
            "agent_consensus": agent_consensus,
            "supporting_reasons": supporting_reasons,
            "risk_warnings": risk_warnings,
            "critic_objections": critic_objections,
            "environment": settings.trading_mode.value,
            "version": 1,
            "created_by": created_by or "system",
            "expires_at": expires_at,
        }

        logger.info(
            "proposal_built",
            symbol=proposal["symbol"],
            recommendation=recommendation,
            direction=direction,
            confidence=str(confidence),
            suggested_price=str(suggested_price),
        )

        return proposal

    @staticmethod
    def _to_decimal(value: Any) -> Decimal | None:
        """Safely convert a value to Decimal."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None
