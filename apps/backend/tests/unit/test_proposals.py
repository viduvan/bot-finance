"""Phase 5: Proposal + Approval System Tests (TDD — written BEFORE implementation).

Tests cover:
- ProposalBuilder: build proposal from analysis result
- ProposalStateMachine: all state transitions + invalid transitions
- ApprovalTokenManager: issue, validate, invalidate tokens
- ProposalRepository: CRUD operations
- PriceDriftGuard: detect price drift requiring re-confirmation
- ProposalExpirationService: expiry detection
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# State Machine
# ─────────────────────────────────────────────────────────────────────────────


class TestProposalStateMachine:
    """Tests for the strict proposal state machine.

    Valid transitions:
        DRAFT → PENDING_REVIEW
        PENDING_REVIEW → APPROVED
        PENDING_REVIEW → REJECTED
        PENDING_REVIEW → RECONFIRM_REQUIRED  (price drift / edit)
        RECONFIRM_REQUIRED → PENDING_REVIEW  (user re-confirms)
        RECONFIRM_REQUIRED → REJECTED
        APPROVED → EXECUTED
        APPROVED → CANCELLED
        PENDING_REVIEW → CANCELLED
        Any → EXPIRED  (only via expiration service)
    """

    @pytest.fixture
    def sm(self):
        from app.proposals.state_machine import ProposalStateMachine

        return ProposalStateMachine()

    def test_draft_to_pending_review(self, sm):
        """DRAFT → PENDING_REVIEW is valid."""
        assert sm.can_transition("DRAFT", "PENDING_REVIEW") is True

    def test_pending_review_to_approved(self, sm):
        """PENDING_REVIEW → APPROVED is valid."""
        assert sm.can_transition("PENDING_REVIEW", "APPROVED") is True

    def test_pending_review_to_rejected(self, sm):
        """PENDING_REVIEW → REJECTED is valid."""
        assert sm.can_transition("PENDING_REVIEW", "REJECTED") is True

    def test_pending_review_to_reconfirm(self, sm):
        """PENDING_REVIEW → RECONFIRM_REQUIRED is valid."""
        assert sm.can_transition("PENDING_REVIEW", "RECONFIRM_REQUIRED") is True

    def test_reconfirm_to_pending_review(self, sm):
        """RECONFIRM_REQUIRED → PENDING_REVIEW is valid (user reconfirms)."""
        assert sm.can_transition("RECONFIRM_REQUIRED", "PENDING_REVIEW") is True

    def test_approved_to_executed(self, sm):
        """APPROVED → EXECUTED is valid."""
        assert sm.can_transition("APPROVED", "EXECUTED") is True

    def test_approved_to_cancelled(self, sm):
        """APPROVED → CANCELLED is valid."""
        assert sm.can_transition("APPROVED", "CANCELLED") is True

    def test_executed_is_terminal(self, sm):
        """EXECUTED state cannot transition to anything."""
        for target in ["APPROVED", "PENDING_REVIEW", "DRAFT", "CANCELLED"]:
            assert sm.can_transition("EXECUTED", target) is False

    def test_rejected_is_terminal(self, sm):
        """REJECTED state cannot transition to anything."""
        assert sm.can_transition("REJECTED", "APPROVED") is False
        assert sm.can_transition("REJECTED", "PENDING_REVIEW") is False

    def test_expired_is_terminal(self, sm):
        """EXPIRED state cannot transition to anything."""
        assert sm.can_transition("EXPIRED", "APPROVED") is False

    def test_invalid_transition_raises(self, sm):
        """Invalid transition should raise ValueError."""
        with pytest.raises(ValueError, match="transition|state"):
            sm.transition("EXECUTED", "PENDING_REVIEW")

    def test_valid_transition_returns_new_state(self, sm):
        """Valid transition should return the new state string."""
        new_state = sm.transition("DRAFT", "PENDING_REVIEW")
        assert new_state == "PENDING_REVIEW"

    def test_draft_to_approved_invalid(self, sm):
        """DRAFT → APPROVED skipping review is NOT allowed."""
        assert sm.can_transition("DRAFT", "APPROVED") is False

    def test_get_allowed_transitions(self, sm):
        """get_allowed_transitions() returns list of valid next states."""
        allowed = sm.get_allowed_transitions("PENDING_REVIEW")
        assert "APPROVED" in allowed
        assert "REJECTED" in allowed
        assert "RECONFIRM_REQUIRED" in allowed
        assert "DRAFT" not in allowed


# ─────────────────────────────────────────────────────────────────────────────
# ApprovalTokenManager
# ─────────────────────────────────────────────────────────────────────────────


class TestApprovalTokenManager:
    """Tests for one-time approval token lifecycle."""

    @pytest.fixture
    def manager(self):
        from app.proposals.approval_token import ApprovalTokenManager

        return ApprovalTokenManager(secret="test-secret-32-bytes-for-hmac!!")

    def make_proposal(self, price="50000") -> dict:
        return {
            "id": "prop-123",
            "symbol": "BTCUSDT",
            "suggested_price": price,
            "suggested_quantity": "0.1",
            "stop_loss_price": "49000",
            "version": 1,
        }

    def test_issue_token_returns_string(self, manager):
        """Issued token should be a non-empty string."""
        token = manager.issue(proposal=self.make_proposal(), user_id="user-1")
        assert isinstance(token, str)
        assert len(token) > 20

    def test_issued_token_is_valid(self, manager):
        """A freshly issued token should be valid."""
        proposal = self.make_proposal()
        token = manager.issue(proposal=proposal, user_id="user-1")
        result = manager.validate(token=token, proposal=proposal, user_id="user-1")
        assert result["valid"] is True

    def test_token_invalid_wrong_user(self, manager):
        """Token issued for user-1 should fail for user-2."""
        proposal = self.make_proposal()
        token = manager.issue(proposal=proposal, user_id="user-1")
        result = manager.validate(token=token, proposal=proposal, user_id="user-2")
        assert result["valid"] is False
        assert "user" in result["reason"].lower()

    def test_token_invalid_after_use(self, manager):
        """Token should be invalid after being consumed."""
        proposal = self.make_proposal()
        token = manager.issue(proposal=proposal, user_id="user-1")
        manager.consume(token)  # Mark as used
        result = manager.validate(token=token, proposal=proposal, user_id="user-1")
        assert result["valid"] is False
        assert "used" in result["reason"].lower() or "consumed" in result["reason"].lower()

    def test_token_expires(self, manager):
        """Token should be invalid after expiry time."""
        # Issue with very short TTL (0 seconds = already expired)
        proposal = self.make_proposal()
        token = manager.issue(proposal=proposal, user_id="user-1", ttl_seconds=-1)
        result = manager.validate(token=token, proposal=proposal, user_id="user-1")
        assert result["valid"] is False
        assert "expir" in result["reason"].lower()

    def test_token_invalid_if_proposal_changed(self, manager):
        """Token should be invalid if proposal price changes after issuance."""
        original = self.make_proposal(price="50000")
        token = manager.issue(proposal=original, user_id="user-1")

        # Proposal price changed
        modified = self.make_proposal(price="51000")
        result = manager.validate(token=token, proposal=modified, user_id="user-1")
        assert result["valid"] is False
        assert (
            "payload" in result["reason"].lower()
            or "mismatch" in result["reason"].lower()
            or "changed" in result["reason"].lower()
        )

    def test_different_proposals_get_different_tokens(self, manager):
        """Two proposals should produce different tokens."""
        p1 = self.make_proposal(price="50000")
        p2 = self.make_proposal(price="51000")
        t1 = manager.issue(proposal=p1, user_id="user-1")
        t2 = manager.issue(proposal=p2, user_id="user-1")
        assert t1 != t2

    def test_token_has_payload_hash(self, manager):
        """Token validation must include proposal payload hash."""
        proposal = self.make_proposal()
        token = manager.issue(proposal=proposal, user_id="user-1")
        data = manager.decode(token)
        assert "payload_hash" in data
        assert "user_id" in data
        assert "proposal_id" in data


# ─────────────────────────────────────────────────────────────────────────────
# ProposalBuilder
# ─────────────────────────────────────────────────────────────────────────────


class TestProposalBuilder:
    """Tests for building proposals from analysis results."""

    @pytest.fixture
    def builder(self):
        from app.proposals.builder import ProposalBuilder

        return ProposalBuilder()

    def make_analysis_result(self, direction="LONG", score=75, proceed=True) -> dict:
        return {
            "symbol": "BTCUSDT",
            "final_direction": direction,
            "consensus_score": score,
            "proceed_to_proposal": proceed,
            "strategy_signal": {
                "signal": direction,
                "score": score,
                "entry_zone_low": "49500",
                "entry_zone_high": "50000",
                "stop_loss_hint": "48000",
                "take_profit_hint": "52000",
            },
            "risk_assessment": {
                "allowed": True,
                "stop_loss": "48000",
                "take_profit": "52000",
                "quantity": "0.05",
                "notional_value": "2500",
                "risk_amount": "100",
                "risk_reward_ratio": "2.5",
                "estimated_fee": "2.5",
                "estimated_slippage": "1.25",
                "risk_score": 30,
                "was_quantity_capped": False,
                "blocked_reasons": [],
            },
            "market_regime": {"regime": "BULL", "conviction": 70},
            "technical": {"signal": "BUY", "conviction": 75},
            "order_flow": {"flow_bias": "BUY", "conviction": 65},
            "risk_analysis": {"risk_rating": "MEDIUM", "summary": "Acceptable risk"},
            "critic": {
                "final_recommendation": "BUY",
                "proceed_to_proposal": True,
                "contradictions_found": [],
                "summary": "Strong confluence",
            },
        }

    def test_build_returns_proposal_dict(self, builder):
        """build() should return a dict with required fields."""
        analysis = self.make_analysis_result()
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert "symbol" in proposal
        assert "recommendation" in proposal
        assert "suggested_price" in proposal
        assert "stop_loss_price" in proposal

    def test_build_long_signal(self, builder):
        """LONG signal should map to BUY recommendation."""
        analysis = self.make_analysis_result(direction="LONG")
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert proposal["recommendation"] in ("BUY", "LONG")

    def test_build_short_signal(self, builder):
        """SHORT signal should map to SELL recommendation."""
        analysis = self.make_analysis_result(direction="SHORT")
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("50250"))
        assert proposal["recommendation"] in ("SELL", "SHORT")

    def test_build_populates_risk_fields(self, builder):
        """Proposal must include SL, TP, R/R, fees from risk assessment."""
        analysis = self.make_analysis_result()
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert "stop_loss_price" in proposal
        assert "take_profit_prices" in proposal
        assert "risk_reward_ratio" in proposal
        assert "estimated_fee" in proposal

    def test_build_sets_draft_status(self, builder):
        """New proposal should start in DRAFT status."""
        analysis = self.make_analysis_result()
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert proposal["status"] == "DRAFT"

    def test_build_sets_expiry(self, builder):
        """Proposal must have an expiration timestamp."""
        analysis = self.make_analysis_result()
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert "expires_at" in proposal
        # Expiry should be in the future
        assert proposal["expires_at"] > datetime.now(UTC)

    def test_build_raises_if_no_proceed(self, builder):
        """Should raise ValueError if proceed_to_proposal is False."""
        analysis = self.make_analysis_result(proceed=False)
        with pytest.raises(ValueError, match="proceed"):
            builder.build(analysis_result=analysis, current_price=Decimal("49750"))

    def test_build_includes_agent_consensus(self, builder):
        """Proposal should include agent consensus snapshot."""
        analysis = self.make_analysis_result()
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert "agent_consensus" in proposal
        assert isinstance(proposal["agent_consensus"], dict)

    def test_build_confidence_from_score(self, builder):
        """Confidence should be derived from consensus_score."""
        analysis = self.make_analysis_result(score=80)
        proposal = builder.build(analysis_result=analysis, current_price=Decimal("49750"))
        assert "confidence" in proposal
        assert 0 < float(proposal["confidence"]) <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# PriceDriftGuard
# ─────────────────────────────────────────────────────────────────────────────


class TestPriceDriftGuard:
    """Tests for price drift detection requiring re-confirmation."""

    @pytest.fixture
    def guard(self):
        from app.proposals.price_drift import PriceDriftGuard

        return PriceDriftGuard(max_drift_bps=20)  # 20 bps = 0.2%

    def test_no_drift_within_threshold(self, guard):
        """Price within threshold should NOT trigger reconfirmation."""
        # 0.1% drift — within 20 bps threshold
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("50050"),  # +0.1%
        )
        assert result["requires_reconfirm"] is False

    def test_drift_above_threshold_triggers_reconfirm(self, guard):
        """Price drift above threshold MUST trigger reconfirmation."""
        # 0.5% drift — above 20 bps threshold
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("50250"),  # +0.5%
        )
        assert result["requires_reconfirm"] is True

    def test_negative_drift_above_threshold(self, guard):
        """Downward drift above threshold also triggers reconfirmation."""
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("49700"),  # -0.6%
        )
        assert result["requires_reconfirm"] is True

    def test_result_includes_drift_bps(self, guard):
        """Result should include the actual drift in basis points."""
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("50100"),
        )
        assert "drift_bps" in result
        assert abs(result["drift_bps"] - 20) < 1  # ~20 bps

    def test_zero_drift_no_reconfirm(self, guard):
        """Identical price should not require reconfirmation."""
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("50000"),
        )
        assert result["requires_reconfirm"] is False
        assert result["drift_bps"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# ProposalExpirationService
# ─────────────────────────────────────────────────────────────────────────────


class TestProposalExpirationService:
    """Tests for proposal expiration detection."""

    @pytest.fixture
    def svc(self):
        from app.proposals.expiration import ProposalExpirationService

        return ProposalExpirationService()

    def make_proposal(self, expires_delta_seconds: int) -> dict:
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_delta_seconds)
        return {"id": "prop-1", "expires_at": expires_at, "status": "PENDING_REVIEW"}

    def test_expired_proposal_detected(self, svc):
        """Proposal past expiration time should be detected as expired."""
        proposal = self.make_proposal(expires_delta_seconds=-10)
        assert svc.is_expired(proposal) is True

    def test_active_proposal_not_expired(self, svc):
        """Proposal with future expiration should not be expired."""
        proposal = self.make_proposal(expires_delta_seconds=300)
        assert svc.is_expired(proposal) is False

    def test_seconds_until_expiry_positive(self, svc):
        """seconds_until_expiry() should be positive for active proposals."""
        proposal = self.make_proposal(expires_delta_seconds=120)
        assert svc.seconds_until_expiry(proposal) > 0

    def test_seconds_until_expiry_zero_for_expired(self, svc):
        """seconds_until_expiry() should return 0 for expired proposals."""
        proposal = self.make_proposal(expires_delta_seconds=-60)
        assert svc.seconds_until_expiry(proposal) == 0

    def test_already_rejected_not_expired(self, svc):
        """REJECTED proposals should not be re-expired."""
        proposal = self.make_proposal(expires_delta_seconds=-10)
        proposal["status"] = "REJECTED"
        assert svc.is_expired(proposal) is False

    def test_executed_not_expired(self, svc):
        """EXECUTED proposals should not be re-expired."""
        proposal = self.make_proposal(expires_delta_seconds=-10)
        proposal["status"] = "EXECUTED"
        assert svc.is_expired(proposal) is False
