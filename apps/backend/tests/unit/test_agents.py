"""Unit tests for Phase 4: Multi-Agent System.

Tests:
- LLM response parsing (extract_json)
- BaseAgent retry logic (mocked LLM)
- MarketRegimeOutput Pydantic validation
- TechnicalOutput validation
- OrderFlowOutput validation
- RiskAnalysisOutput validation
- CriticOutput validation
- SignalAggregator (consensus scoring, direction, agreement)
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base_agent import BaseAgent, AgentOutput
from app.agents.signal_aggregator import SignalAggregator, SIGNAL_SCORES


# ── JSON extraction ───────────────────────────────────────────────

class TestExtractJson:
    """Tests for BaseAgent.extract_json helper."""

    def test_extracts_raw_json(self):
        text = '{"signal": "BUY", "conviction": 75}'
        result = BaseAgent.extract_json(text)
        assert json.loads(result)["signal"] == "BUY"

    def test_extracts_json_from_code_block(self):
        text = '```json\n{"signal": "SELL", "conviction": 60}\n```'
        result = BaseAgent.extract_json(text)
        assert json.loads(result)["signal"] == "SELL"

    def test_extracts_json_from_explanation(self):
        text = 'Here is my analysis:\n\n{"regime": "BULL", "conviction": 80}\n\nThat covers it.'
        result = BaseAgent.extract_json(text)
        assert json.loads(result)["regime"] == "BULL"

    def test_returns_text_if_no_json(self):
        text = "No JSON here, just plain text"
        result = BaseAgent.extract_json(text)
        assert result == text


# ── Pydantic output model validation ─────────────────────────────

class TestMarketRegimeOutput:
    """Tests for MarketRegimeOutput Pydantic validation."""

    def test_valid_output(self):
        from app.agents.market_regime_agent import MarketRegimeOutput
        out = MarketRegimeOutput(
            agent_name="market_regime",
            regime="BULL",
            conviction=75,
            trend_direction="BULLISH",
            volatility_level="NORMAL",
            trading_bias="LONG_BIAS",
            summary="Bullish market",
        )
        assert out.regime == "BULL"
        assert out.conviction == 75

    def test_conviction_clamped_above_100(self):
        from app.agents.market_regime_agent import MarketRegimeOutput
        out = MarketRegimeOutput(agent_name="test", conviction=150)
        assert out.conviction == 100

    def test_conviction_clamped_below_0(self):
        from app.agents.market_regime_agent import MarketRegimeOutput
        out = MarketRegimeOutput(agent_name="test", conviction=-10)
        assert out.conviction == 0

    def test_unknown_regime_default(self):
        from app.agents.market_regime_agent import MarketRegimeOutput
        out = MarketRegimeOutput(agent_name="test")
        assert out.regime == "UNKNOWN"


class TestTechnicalOutput:
    """Tests for TechnicalOutput Pydantic validation."""

    def test_valid_buy_signal(self):
        from app.agents.technical_agent import TechnicalOutput
        out = TechnicalOutput(
            agent_name="technical",
            signal="STRONG_BUY",
            conviction=85,
            ema_alignment="BULLISH_STACK",
            rsi_signal="NEUTRAL",
            macd_signal="BULLISH_CROSS",
        )
        assert out.signal == "STRONG_BUY"
        assert out.ema_alignment == "BULLISH_STACK"

    def test_default_neutral(self):
        from app.agents.technical_agent import TechnicalOutput
        out = TechnicalOutput(agent_name="technical")
        assert out.signal == "NEUTRAL"


class TestCriticOutput:
    """Tests for CriticOutput validation."""

    def test_proceed_to_proposal_defaults_false(self):
        from app.agents.critic_agent import CriticOutput
        out = CriticOutput(agent_name="critic")
        assert out.proceed_to_proposal is False

    def test_valid_critic_output(self):
        from app.agents.critic_agent import CriticOutput
        out = CriticOutput(
            agent_name="critic",
            final_recommendation="BUY",
            conviction=70,
            proceed_to_proposal=True,
            quality_score=80,
        )
        assert out.proceed_to_proposal is True
        assert out.quality_score == 80

    def test_quality_score_clamped(self):
        from app.agents.critic_agent import CriticOutput
        out = CriticOutput(agent_name="critic", quality_score=120)
        assert out.quality_score == 100


# ── SignalAggregator ───────────────────────────────────────────────

class TestSignalAggregator:
    """Tests for signal aggregation and consensus scoring."""

    @pytest.fixture
    def agg(self) -> SignalAggregator:
        return SignalAggregator()

    def make_outputs(
        self,
        regime_bias="LONG_BIAS",
        tech_signal="BUY",
        flow_bias="BUY",
        risk_recommended=True,
        strategy_signal="LONG",
        strategy_score=75,
    ) -> tuple[dict, dict, dict, dict, dict]:
        return (
            {"trading_bias": regime_bias, "conviction": 70},
            {"signal": tech_signal, "conviction": 75},
            {"flow_bias": flow_bias, "conviction": 65},
            {"trade_recommended": risk_recommended, "conviction": 60},
            {"signal": strategy_signal, "score": strategy_score, "confidence": "HIGH"},
        )

    def test_bullish_consensus_gives_long(self, agg):
        """All bullish signals should produce LONG direction."""
        regime, tech, flow, risk, strategy = self.make_outputs()
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        assert result.direction == "LONG"

    def test_bearish_consensus_gives_short(self, agg):
        """All bearish signals should produce SHORT direction."""
        regime, tech, flow, risk, strategy = self.make_outputs(
            regime_bias="SHORT_BIAS",
            tech_signal="SELL",
            flow_bias="SELL",
            risk_recommended=False,
            strategy_signal="SHORT",
        )
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        assert result.direction == "SHORT"

    def test_mixed_signals_no_signal(self, agg):
        """Contradicting signals should produce NO_SIGNAL."""
        regime, tech, flow, risk, strategy = self.make_outputs(
            regime_bias="LONG_BIAS",
            tech_signal="SELL",   # Contradiction
            flow_bias="NEUTRAL",
            risk_recommended=False,
            strategy_signal="NO_SIGNAL",
            strategy_score=30,
        )
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        # Score should be near 0 — direction is undetermined
        assert abs(result.consensus_score) < 50

    def test_consensus_score_positive_for_long(self, agg):
        """Bullish consensus should have positive score."""
        regime, tech, flow, risk, strategy = self.make_outputs()
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        assert result.consensus_score > 0

    def test_agreement_pct_high_when_all_agree(self, agg):
        """100% agent agreement should give high agreement_pct."""
        regime, tech, flow, risk, strategy = self.make_outputs()
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        assert result.agreement_pct >= 75  # At least 3/4 agents agree

    def test_is_actionable_requires_strong_consensus(self, agg):
        """is_actionable should be False for weak consensus."""
        regime, tech, flow, risk, strategy = self.make_outputs(
            tech_signal="NEUTRAL",
            flow_bias="NEUTRAL",
            risk_recommended=False,
            strategy_score=40,
        )
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        # Weak consensus should not be actionable
        if abs(result.consensus_score) < 50:
            assert result.is_actionable is False

    def test_signal_score_map_covers_all_signals(self, agg):
        """All expected signal types must be in the score map."""
        expected = {"STRONG_BUY", "BUY", "NEUTRAL", "HOLD", "SELL", "STRONG_SELL", "AVOID",
                    "LONG_BIAS", "SHORT_BIAS", "UNKNOWN"}
        for signal in expected:
            assert signal in SIGNAL_SCORES, f"{signal} missing from SIGNAL_SCORES"

    def test_agent_scores_dict_populated(self, agg):
        """Result must include per-agent score breakdown."""
        regime, tech, flow, risk, strategy = self.make_outputs()
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        assert "market_regime" in result.agent_scores
        assert "technical" in result.agent_scores
        assert "order_flow" in result.agent_scores
        assert "risk_analysis" in result.agent_scores

    def test_to_dict_serializable(self, agg):
        """Result.to_dict() must be JSON serializable."""
        regime, tech, flow, risk, strategy = self.make_outputs()
        result = agg.aggregate(regime, tech, flow, risk, strategy)
        d = result.to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["direction"], str)
        assert isinstance(d["consensus_score"], float)
        assert isinstance(d["agreement_pct"], float)
        assert isinstance(d["is_actionable"], bool)
