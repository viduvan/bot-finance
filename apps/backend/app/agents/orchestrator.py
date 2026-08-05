"""Analysis Orchestrator — coordinates the full multi-agent analysis workflow.

Workflow (timeout: 60s, max iterations: 2):
  1. Load features from DB
  2. Run rule-based strategy → strategy_signal
  3. Run Risk Engine pre-check
  4. Run agents concurrently (market_regime, technical, order_flow)
  5. Run risk_analysis agent (needs previous outputs)
  6. Aggregate signals
  7. Run critic agent (adversarial review)
  8. Persist analysis run to DB
  9. Return AnalysisResult

If critic says proceed_to_proposal=True → caller creates a proposal.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.critic_agent import CriticAgent, CriticOutput
from app.agents.market_regime_agent import MarketRegimeAgent, MarketRegimeOutput
from app.agents.order_flow_agent import OrderFlowAgent, OrderFlowOutput
from app.agents.risk_analysis_agent import RiskAnalysisAgent, RiskAnalysisOutput
from app.agents.signal_aggregator import AggregatedSignal, SignalAggregator
from app.agents.technical_agent import TechnicalAgent, TechnicalOutput
from app.config import settings
from app.core.metrics import AGENT_WORKFLOW_DURATION, AGENT_WORKFLOW_FAILURES
from app.features.engine import FeatureEngine
from app.risk.daily_tracker import DailyLossTracker
from app.risk.engine import RiskAssessment, RiskEngine
from app.strategies.registry import strategy_registry

logger = structlog.get_logger(__name__)


@dataclass
class AnalysisResult:
    """Complete output of the analysis orchestrator."""

    symbol: str
    started_at: datetime
    completed_at: datetime | None = None
    success: bool = False
    error: str | None = None

    # Agent outputs
    market_regime: MarketRegimeOutput | None = None
    technical: TechnicalOutput | None = None
    order_flow: OrderFlowOutput | None = None
    risk_analysis: RiskAnalysisOutput | None = None
    critic: CriticOutput | None = None

    # Aggregated results
    aggregated_signal: AggregatedSignal | None = None
    risk_assessment: RiskAssessment | None = None
    strategy_signal: dict = field(default_factory=dict)

    # Decision
    proceed_to_proposal: bool = False
    final_direction: str = "NO_SIGNAL"
    consensus_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict for DB storage."""
        return {
            "symbol": self.symbol,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "success": self.success,
            "error": self.error,
            "market_regime": self.market_regime.model_dump() if self.market_regime else None,
            "technical": self.technical.model_dump() if self.technical else None,
            "order_flow": self.order_flow.model_dump() if self.order_flow else None,
            "risk_analysis": self.risk_analysis.model_dump() if self.risk_analysis else None,
            "critic": self.critic.model_dump() if self.critic else None,
            "aggregated_signal": self.aggregated_signal.to_dict()
            if self.aggregated_signal
            else None,
            "risk_assessment": self.risk_assessment.to_dict() if self.risk_assessment else None,
            "strategy_signal": self.strategy_signal,
            "proceed_to_proposal": self.proceed_to_proposal,
            "final_direction": self.final_direction,
            "consensus_score": self.consensus_score,
        }


class AnalysisOrchestrator:
    """Orchestrates the full multi-agent analysis pipeline.

    Usage:
        orchestrator = AnalysisOrchestrator(db)
        result = await orchestrator.analyze(symbol="BTCUSDT")
    """

    def __init__(
        self,
        db: AsyncSession,
        daily_tracker: DailyLossTracker | None = None,
    ) -> None:
        self._db = db
        self._feature_engine = FeatureEngine(db)
        self._risk_engine = RiskEngine(daily_tracker=daily_tracker)
        self._aggregator = SignalAggregator()

        # Agents
        self._regime_agent = MarketRegimeAgent()
        self._tech_agent = TechnicalAgent()
        self._flow_agent = OrderFlowAgent()
        self._risk_agent = RiskAnalysisAgent()
        self._critic_agent = CriticAgent()

    async def analyze(self, symbol: str) -> AnalysisResult:
        """Run the full analysis pipeline for a symbol.

        Returns AnalysisResult regardless of success/failure.
        """
        started_at = datetime.now(UTC)
        result = AnalysisResult(symbol=symbol, started_at=started_at)

        try:
            result = await asyncio.wait_for(
                self._run_pipeline(symbol, result),
                timeout=settings.agent_timeout_seconds,
            )
        except TimeoutError:
            result.error = f"Analysis timed out after {settings.agent_timeout_seconds}s"
            logger.error("analysis_timeout", symbol=symbol)
            with contextlib.suppress(Exception):
                AGENT_WORKFLOW_FAILURES.labels(symbol=symbol, reason="timeout").inc()
        except Exception as e:
            result.error = str(e)
            logger.error("analysis_failed", symbol=symbol, error=str(e))
            with contextlib.suppress(Exception):
                AGENT_WORKFLOW_FAILURES.labels(symbol=symbol, reason="error").inc()

        result.completed_at = datetime.now(UTC)
        latency_s = (result.completed_at - result.started_at).total_seconds()

        with contextlib.suppress(Exception):
            AGENT_WORKFLOW_DURATION.labels(symbol=symbol).observe(latency_s)

        logger.info(
            "analysis_complete",
            symbol=symbol,
            success=result.success,
            proceed=result.proceed_to_proposal,
            direction=result.final_direction,
            latency_s=round(latency_s, 2),
        )

        return result

    async def _run_pipeline(self, symbol: str, result: AnalysisResult) -> AnalysisResult:
        """Internal pipeline execution."""

        # ── Step 1: Compute/load features ──────────────────────────
        logger.info("analysis_step_features", symbol=symbol)
        features = await self._feature_engine.compute_and_store(symbol)
        if not features:
            result.error = "No market data available"
            return result

        # ── Step 2: Rule-based strategy signal ─────────────────────
        logger.info("analysis_step_strategy", symbol=symbol)
        features_1h = {
            k.removeprefix("tf1h_"): v for k, v in features.items() if k.startswith("tf1h_")
        }
        features_4h = {
            k.removeprefix("tf4h_"): v for k, v in features.items() if k.startswith("tf4h_")
        }
        strategy_result = strategy_registry.evaluate(
            "ema_pullback", features, features_1h, features_4h
        )

        result.strategy_signal = {
            "signal": strategy_result.signal,
            "score": strategy_result.score,
            "confidence": strategy_result.confidence,
            "entry_zone_low": str(strategy_result.entry_zone_low)
            if strategy_result.entry_zone_low
            else None,
            "entry_zone_high": str(strategy_result.entry_zone_high)
            if strategy_result.entry_zone_high
            else None,
            "stop_loss_hint": str(strategy_result.stop_loss_hint)
            if strategy_result.stop_loss_hint
            else None,
            "take_profit_hint": str(strategy_result.take_profit_hint)
            if strategy_result.take_profit_hint
            else None,
            "reasons": strategy_result.reasons,
        }

        # ── Step 3: Risk Engine pre-check ──────────────────────────
        logger.info("analysis_step_risk_gate", symbol=symbol)
        atr = features.get("atr_14")
        close = features.get("close")

        risk_context = {
            "symbol": symbol,
            "direction": strategy_result.signal
            if strategy_result.signal != "NO_SIGNAL"
            else "LONG",
            "entry_price": float(close) if close else 50000,
            "atr": float(atr) if atr else 0,
            "atr_pct": float(features.get("atr_pct", 1.5) or 1.5),
            "account_balance": 10000,  # TODO: load from account service
            "risk_pct": settings.risk_per_trade_percent / 100,
            "signal_score": strategy_result.score,
            "spread_bps": float(features.get("ob_spread_bps", 5) or 5),
            "volume_relative": float(features.get("volume_relative", 1.0) or 1.0),
            "daily_loss_pct": 0,  # TODO: load from daily tracker
            "total_exposure_pct": 0,
            "open_positions_count": 0,
            "market_data_stale": False,
            "exchange_connected": True,
            "trading_mode": settings.trading_mode.value,
            "min_signal_score": 60,
            "min_risk_reward_ratio": settings.min_risk_reward_ratio,
            "max_spread_bps": settings.max_spread_bps,
            "max_daily_loss_pct": settings.max_daily_loss_percent,
            "max_open_positions": settings.max_open_positions,
            "max_total_exposure_pct": settings.max_total_exposure_percent,
            "target_rr": settings.min_risk_reward_ratio,
        }

        risk_assessment = self._risk_engine.assess(risk_context)
        result.risk_assessment = risk_assessment

        # ── Step 4: Run analysis agents concurrently ────────────────
        logger.info("analysis_step_agents", symbol=symbol)

        agent_context = {
            "symbol": symbol,
            "features": features,
            "strategy_signal": result.strategy_signal,
            "risk_assessment": risk_assessment.to_dict(),
        }

        # Run market_regime, technical, order_flow concurrently
        regime_task = asyncio.create_task(self._regime_agent.run(agent_context))
        tech_task = asyncio.create_task(self._tech_agent.run(agent_context))
        flow_task = asyncio.create_task(self._flow_agent.run(agent_context))

        regime_out, tech_out, flow_out = await asyncio.gather(
            regime_task,
            tech_task,
            flow_task,
            return_exceptions=True,
        )

        # Handle partial failures gracefully
        result.market_regime = regime_out if isinstance(regime_out, MarketRegimeOutput) else None
        result.technical = tech_out if isinstance(tech_out, TechnicalOutput) else None
        result.order_flow = flow_out if isinstance(flow_out, OrderFlowOutput) else None

        if isinstance(regime_out, Exception):
            logger.warning("market_regime_agent_failed", error=str(regime_out))
        if isinstance(tech_out, Exception):
            logger.warning("technical_agent_failed", error=str(tech_out))
        if isinstance(flow_out, Exception):
            logger.warning("order_flow_agent_failed", error=str(flow_out))

        # ── Step 5: Risk Analysis Agent (needs above outputs) ───────
        risk_agent_context = {
            **agent_context,
            "regime": regime_out.regime
            if isinstance(regime_out, MarketRegimeOutput)
            else "UNKNOWN",
        }

        try:
            risk_out = await self._risk_agent.run(risk_agent_context)
            result.risk_analysis = risk_out
        except Exception as e:
            logger.warning("risk_analysis_agent_failed", error=str(e))
            risk_out = None

        # ── Step 6: Signal aggregation ─────────────────────────────
        logger.info("analysis_step_aggregation", symbol=symbol)

        agg = self._aggregator.aggregate(
            regime_output=regime_out.model_dump()
            if isinstance(regime_out, MarketRegimeOutput)
            else {},
            technical_output=tech_out.model_dump() if isinstance(tech_out, TechnicalOutput) else {},
            order_flow_output=flow_out.model_dump()
            if isinstance(flow_out, OrderFlowOutput)
            else {},
            risk_output=risk_out.model_dump() if isinstance(risk_out, RiskAnalysisOutput) else {},
            strategy_signal=result.strategy_signal,
        )
        result.aggregated_signal = agg

        # ── Step 7: Critic Agent ────────────────────────────────────
        logger.info("analysis_step_critic", symbol=symbol)

        critic_context = {
            **agent_context,
            "market_regime_output": regime_out.model_dump()
            if isinstance(regime_out, MarketRegimeOutput)
            else {},
            "technical_output": tech_out.model_dump()
            if isinstance(tech_out, TechnicalOutput)
            else {},
            "order_flow_output": flow_out.model_dump()
            if isinstance(flow_out, OrderFlowOutput)
            else {},
            "risk_analysis_output": risk_out.model_dump()
            if isinstance(risk_out, RiskAnalysisOutput)
            else {},
        }

        try:
            critic_out = await self._critic_agent.run(critic_context)
            result.critic = critic_out
            result.proceed_to_proposal = critic_out.proceed_to_proposal
        except Exception as e:
            logger.warning("critic_agent_failed", error=str(e))
            # If critic fails, use aggregated signal conservatively
            result.proceed_to_proposal = agg.is_actionable and risk_assessment.allowed

        result.final_direction = agg.direction
        result.consensus_score = agg.consensus_score
        result.success = True

        return result
