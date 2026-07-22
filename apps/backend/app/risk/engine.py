"""Risk Engine — Orchestration layer for all risk management components.

This is the single entry point for risk evaluation. It:
1. Gathers risk context (daily loss, exposure, market conditions)
2. Runs the Risk Gate (15 conditions)
3. Computes position size
4. Calculates SL/TP levels
5. Applies exchange filters
6. Returns a complete RiskAssessment

The Risk Engine is DETERMINISTIC — no LLM, no external calls beyond
checking daily loss from Redis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import structlog

from app.core.metrics import DAILY_DRAWDOWN, RISK_REJECTIONS
from app.risk.daily_tracker import DailyLossTracker
from app.risk.exchange_filter import ExchangeFilter
from app.risk.fee_slippage import FeeSlippageEstimator
from app.risk.position_sizer import PositionSizer
from app.risk.risk_gate import RiskGate
from app.risk.risk_reward import RiskRewardCalculator
from app.risk.sltp_calculator import SLTPCalculator

logger = structlog.get_logger(__name__)


@dataclass
class RiskAssessment:
    """Complete risk assessment result for a proposed trade."""

    # Gate result
    allowed: bool
    blocked_reasons: list[str] = field(default_factory=list)
    risk_score: int = 0

    # Position sizing
    quantity: Decimal | None = None
    notional_value: Decimal | None = None
    risk_amount: Decimal | None = None

    # SL/TP levels
    stop_loss: Decimal | None = None
    take_profit: Decimal | None = None
    sl_distance: Decimal | None = None

    # Exchange-adjusted values
    adjusted_quantity: Decimal | None = None
    adjusted_entry: Decimal | None = None

    # Cost estimates
    estimated_fee: Decimal | None = None
    estimated_slippage: Decimal | None = None
    round_trip_cost: Decimal | None = None

    # R/R
    risk_reward_ratio: Decimal | None = None

    # Metadata
    was_quantity_capped: bool = False
    symbol: str = ""
    direction: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "allowed": self.allowed,
            "blocked_reasons": self.blocked_reasons,
            "risk_score": self.risk_score,
            "quantity": str(self.quantity) if self.quantity else None,
            "notional_value": str(self.notional_value) if self.notional_value else None,
            "risk_amount": str(self.risk_amount) if self.risk_amount else None,
            "stop_loss": str(self.stop_loss) if self.stop_loss else None,
            "take_profit": str(self.take_profit) if self.take_profit else None,
            "adjusted_quantity": str(self.adjusted_quantity) if self.adjusted_quantity else None,
            "adjusted_entry": str(self.adjusted_entry) if self.adjusted_entry else None,
            "estimated_fee": str(self.estimated_fee) if self.estimated_fee else None,
            "round_trip_cost": str(self.round_trip_cost) if self.round_trip_cost else None,
            "risk_reward_ratio": str(self.risk_reward_ratio) if self.risk_reward_ratio else None,
            "was_quantity_capped": self.was_quantity_capped,
            "symbol": self.symbol,
            "direction": self.direction,
        }


class RiskEngine:
    """Orchestrates all risk management logic for a trade proposal.

    Usage:
        engine = RiskEngine(daily_tracker=tracker)
        assessment = engine.assess(proposal_context)
    """

    def __init__(
        self,
        daily_tracker: DailyLossTracker | None = None,
    ) -> None:
        self._gate = RiskGate()
        self._sizer = PositionSizer()
        self._sltp = SLTPCalculator()
        self._fee_est = FeeSlippageEstimator()
        self._rr_calc = RiskRewardCalculator()
        self._ex_filter = ExchangeFilter()
        self._tracker = daily_tracker or DailyLossTracker(use_redis=False)

    def assess(self, context: dict[str, Any]) -> RiskAssessment:
        """Full risk assessment for a trade proposal.

        Args:
            context: Must include:
                symbol, direction, entry_price, atr, account_balance,
                risk_pct, spread_bps, signal_score, exchange_filters (dict)
                + all RiskGate context keys

        Returns:
            RiskAssessment with all computed values
        """
        symbol = context.get("symbol", "")
        direction = context.get("direction", "")

        # ── Step 1: Compute R/R if SL/TP hints provided ────────────
        entry = Decimal(str(context.get("entry_price", 0)))
        atr = Decimal(str(context.get("atr", 0)))

        sltp = None
        rr_ratio = None

        if entry > 0 and atr > 0:
            try:
                sltp = self._sltp.calculate(
                    entry_price=entry,
                    atr=atr,
                    direction=direction,
                    atr_multiplier=Decimal(str(context.get("atr_multiplier", "1.5"))),
                    risk_reward=Decimal(str(context.get("target_rr", "2.0"))),
                )
                rr_ratio = self._rr_calc.calculate(
                    entry=entry,
                    stop_loss=sltp["stop_loss"],
                    take_profit=sltp["take_profit"],
                )
                context["risk_reward_ratio"] = rr_ratio
            except (ValueError, Exception) as e:
                logger.warning("sltp_calculation_failed", error=str(e))

        # ── Step 2: Risk Gate check ─────────────────────────────────
        gate_result = self._gate.check(context)

        if not gate_result["allowed"]:
            for reason in gate_result["blocked_reasons"]:
                try:
                    RISK_REJECTIONS.labels(event_type="gate_block").inc()
                except Exception:
                    pass

            logger.warning(
                "risk_engine_blocked",
                symbol=symbol,
                reasons=gate_result["blocked_reasons"],
            )

            return RiskAssessment(
                allowed=False,
                blocked_reasons=gate_result["blocked_reasons"],
                risk_score=gate_result["risk_score"],
                stop_loss=sltp["stop_loss"] if sltp else None,
                take_profit=sltp["take_profit"] if sltp else None,
                risk_reward_ratio=rr_ratio,
                symbol=symbol,
                direction=direction,
            )

        # ── Step 3: Position sizing ─────────────────────────────────
        sizing = None
        if sltp:
            try:
                account_balance = Decimal(str(context.get("account_balance", 10000)))
                risk_pct = Decimal(str(context.get("risk_pct", "0.01")))

                sizing = self._sizer.calculate(
                    account_balance=account_balance,
                    risk_pct=risk_pct,
                    entry_price=entry,
                    stop_loss=sltp["stop_loss"],
                    direction=direction,
                )
            except (ValueError, Exception) as e:
                logger.error("position_sizing_failed", error=str(e))

        # ── Step 4: Apply exchange filters ──────────────────────────
        exchange_filters = context.get("exchange_filters", {})
        adj_quantity = sizing["quantity"] if sizing else None
        adj_entry = entry

        if sizing and exchange_filters:
            try:
                filtered = self._ex_filter.apply(
                    quantity=sizing["quantity"],
                    price=entry,
                    filters=exchange_filters,
                )
                adj_quantity = filtered["quantity"]
                adj_entry = filtered["price"]
            except (ValueError, Exception) as e:
                logger.warning("exchange_filter_failed", error=str(e))

        # ── Step 5: Cost estimation ─────────────────────────────────
        notional = adj_quantity * adj_entry if adj_quantity else None
        fee_result = None
        if notional:
            spread_bps = Decimal(str(context.get("spread_bps", "5")))
            fee_result = self._fee_est.estimate_round_trip(
                notional=notional,
                order_type=context.get("order_type", "LIMIT"),
                spread_bps=spread_bps,
            )

        # ── Step 6: Update Prometheus metrics ──────────────────────
        try:
            daily_loss_pct = float(context.get("daily_loss_pct", 0))
            DAILY_DRAWDOWN.set(daily_loss_pct)
        except Exception:
            pass

        logger.info(
            "risk_engine_assessment_complete",
            symbol=symbol,
            allowed=True,
            quantity=str(adj_quantity) if adj_quantity else None,
            stop_loss=str(sltp["stop_loss"]) if sltp else None,
            take_profit=str(sltp["take_profit"]) if sltp else None,
            risk_reward=str(rr_ratio) if rr_ratio else None,
        )

        return RiskAssessment(
            allowed=True,
            blocked_reasons=[],
            risk_score=gate_result["risk_score"],
            quantity=sizing["quantity"] if sizing else None,
            notional_value=notional,
            risk_amount=sizing["risk_amount"] if sizing else None,
            stop_loss=sltp["stop_loss"] if sltp else None,
            take_profit=sltp["take_profit"] if sltp else None,
            sl_distance=sltp["sl_distance"] if sltp else None,
            adjusted_quantity=adj_quantity,
            adjusted_entry=adj_entry,
            estimated_fee=fee_result["fee"] if fee_result else None,
            estimated_slippage=fee_result["slippage"] if fee_result else None,
            round_trip_cost=fee_result["round_trip_cost"] if fee_result else None,
            risk_reward_ratio=rr_ratio,
            was_quantity_capped=sizing.get("was_capped", False) if sizing else False,
            symbol=symbol,
            direction=direction,
        )
