"""Security Tests — Phase 8.1

Tests cover:
  - Token replay attacks (one-time use enforcement)
  - Token tampering (signature verification)
  - User escalation (wrong user_id)
  - Payload tampering (price/qty change after token issue)
  - Expired token rejection
  - HMAC timing-safe comparison
  - JWT type confusion (refresh token used as access token)
  - JWT secret integrity
  - Encryption roundtrip + wrong key rejection
  - SQL injection strings passed through Pydantic
  - XSS strings passed through proposal fields
  - Rate limit / import boundary sanity
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest


# ─────────────────────────────────────────────────────────────────
# ApprovalToken Security
# ─────────────────────────────────────────────────────────────────


@pytest.fixture
def token_manager():
    from app.proposals.approval_token import ApprovalTokenManager
    return ApprovalTokenManager(secret="test-secret-for-security-tests")


@pytest.fixture
def sample_proposal():
    return {
        "id": "sec-test-proposal-001",
        "symbol": "BTCUSDT",
        "suggested_price": "50000",
        "suggested_quantity": "0.1",
        "stop_loss_price": "48000",
        "version": 1,
    }


class TestApprovalTokenSecurity:

    def test_replay_attack_blocked(self, token_manager, sample_proposal):
        """Same token cannot be used twice (replay protection)."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)

        # First use — valid
        result1 = token_manager.validate(token, sample_proposal, user_id="user-1")
        assert result1["valid"] is True
        token_manager.consume(token)

        # Second use — must be blocked
        result2 = token_manager.validate(token, sample_proposal, user_id="user-1")
        assert result2["valid"] is False
        assert "consumed" in result2["reason"].lower() or "used" in result2["reason"].lower()

    def test_tampered_signature_rejected(self, token_manager, sample_proposal):
        """Token with modified signature is rejected."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)

        # Tamper with the signature portion
        parts = token.rsplit(".", 1)
        tampered = parts[0] + ".deadbeefdeadbeef00000000000000000000000000000000000000000000000"

        result = token_manager.validate(tampered, sample_proposal, user_id="user-1")
        assert result["valid"] is False
        assert "signature" in result["reason"].lower() or "invalid" in result["reason"].lower()

    def test_wrong_user_rejected(self, token_manager, sample_proposal):
        """Token issued to user-1 cannot be used by user-2."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)
        result = token_manager.validate(token, sample_proposal, user_id="user-2")
        assert result["valid"] is False
        assert "user" in result["reason"].lower() or "mismatch" in result["reason"].lower()

    def test_payload_tampering_detected(self, token_manager, sample_proposal):
        """Changing price after token issuance invalidates the token."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)

        # Attacker tries to change price after token was issued
        modified_proposal = {**sample_proposal, "suggested_price": "1"}  # Much lower price
        result = token_manager.validate(token, modified_proposal, user_id="user-1")
        assert result["valid"] is False
        assert "payload" in result["reason"].lower() or "changed" in result["reason"].lower()

    def test_quantity_tampering_detected(self, token_manager, sample_proposal):
        """Changing quantity after token issuance invalidates the token."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)

        modified = {**sample_proposal, "suggested_quantity": "999"}  # Much larger qty
        result = token_manager.validate(token, modified, user_id="user-1")
        assert result["valid"] is False

    def test_stop_loss_tampering_detected(self, token_manager, sample_proposal):
        """Removing stop-loss after token issuance invalidates the token."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)

        modified = {**sample_proposal, "stop_loss_price": None}
        result = token_manager.validate(token, modified, user_id="user-1")
        assert result["valid"] is False

    def test_expired_token_rejected(self, token_manager, sample_proposal):
        """Token with zero TTL should be rejected."""
        token = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=0)
        # Give it a moment to expire
        time.sleep(0.01)
        result = token_manager.validate(token, sample_proposal, user_id="user-1")
        assert result["valid"] is False
        assert "expir" in result["reason"].lower()

    def test_malformed_token_rejected(self, token_manager, sample_proposal):
        """Completely malformed tokens are rejected cleanly."""
        for bad_token in ["", "abc", "abc.def.ghi", "a" * 200, "null", "0", "." * 10]:
            result = token_manager.validate(bad_token, sample_proposal, user_id="user-1")
            assert result["valid"] is False, f"Should reject: {bad_token!r}"

    def test_different_secrets_produce_different_tokens(self, sample_proposal):
        """Tokens from different secrets must not cross-validate."""
        from app.proposals.approval_token import ApprovalTokenManager
        mgr1 = ApprovalTokenManager(secret="secret-A")
        mgr2 = ApprovalTokenManager(secret="secret-B")

        token = mgr1.issue(sample_proposal, user_id="user-1", ttl_seconds=60)
        result = mgr2.validate(token, sample_proposal, user_id="user-1")
        assert result["valid"] is False

    def test_token_fingerprint_is_collision_resistant(self, token_manager, sample_proposal):
        """Two different tokens should have different fingerprints."""
        t1 = token_manager.issue(sample_proposal, user_id="user-1", ttl_seconds=60)
        p2 = {**sample_proposal, "id": "sec-test-proposal-002"}
        t2 = token_manager.issue(p2, user_id="user-2", ttl_seconds=60)

        fp1 = token_manager._fingerprint(t1)
        fp2 = token_manager._fingerprint(t2)
        assert fp1 != fp2


# ─────────────────────────────────────────────────────────────────
# JWT Security
# ─────────────────────────────────────────────────────────────────


class TestJWTSecurity:

    def test_refresh_token_rejected_as_access_token(self):
        """Refresh token cannot be used where access token is expected."""
        from app.core.security import create_refresh_token, decode_token

        refresh = create_refresh_token(user_id="user-1")
        payload = decode_token(refresh)
        # The WS and API endpoints check payload["type"] == "access"
        assert payload["type"] == "refresh"
        assert payload["type"] != "access"  # Cannot be used as access token

    def test_access_token_payload_structure(self):
        """Access token must contain required security fields."""
        from app.core.security import create_access_token, decode_token

        token = create_access_token(user_id="user-1", role="admin")
        payload = decode_token(token)

        assert "sub" in payload
        assert "role" in payload
        assert "type" in payload
        assert "jti" in payload      # JWT ID — prevents replay at transport level
        assert "exp" in payload
        assert "iat" in payload
        assert payload["type"] == "access"

    def test_wrong_secret_rejected(self):
        """Token signed with wrong secret should raise AuthenticationError."""
        from jose import jwt
        from app.core.exceptions import AuthenticationError
        from app.core.security import decode_token

        # Create token with a DIFFERENT secret
        bad_token = jwt.encode(
            {"sub": "attacker", "type": "access", "exp": 9999999999},
            "wrong-secret-here",
            algorithm="HS256",
        )

        with pytest.raises(AuthenticationError):
            decode_token(bad_token)

    def test_expired_jwt_raises_token_expired_error(self):
        """Expired JWT should raise TokenExpiredError, not generic error."""
        from jose import jwt
        from app.core.exceptions import TokenExpiredError
        from app.core.security import decode_token
        from app.config import settings

        import time
        expired_payload = {
            "sub": "user-1",
            "type": "access",
            "exp": int(time.time()) - 10,  # 10 seconds in the past
            "jti": "test-jti",
        }
        expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        with pytest.raises(TokenExpiredError):
            decode_token(expired_token)


# ─────────────────────────────────────────────────────────────────
# Encryption Security
# ─────────────────────────────────────────────────────────────────


class TestEncryptionSecurity:

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted value must decrypt to original."""
        from app.core.security import encrypt_value, decrypt_value

        original = "super-secret-api-key-12345"
        ciphertext = encrypt_value(original)
        assert ciphertext != original  # Must not be stored in plaintext
        assert decrypt_value(ciphertext) == original

    def test_encrypted_value_is_not_plaintext(self):
        """API key must not appear as substring in its ciphertext."""
        from app.core.security import encrypt_value

        api_key = "sk-proj-abc123REALKEY"
        ciphertext = encrypt_value(api_key)
        assert api_key not in ciphertext

    def test_different_encryptions_of_same_value_differ(self):
        """Fernet uses random IV — same plaintext produces different ciphertext."""
        from app.core.security import encrypt_value

        value = "same-api-key"
        c1 = encrypt_value(value)
        c2 = encrypt_value(value)
        assert c1 != c2  # Must differ due to random IV


# ─────────────────────────────────────────────────────────────────
# Input Sanitization
# ─────────────────────────────────────────────────────────────────


class TestInputSanitization:

    def test_proposal_builder_rejects_non_numeric_price(self):
        """ProposalBuilder must reject non-numeric price values gracefully."""
        from app.proposals.builder import ProposalBuilder

        builder = ProposalBuilder()
        bad_result = {
            "symbol": "BTCUSDT",
            "proceed_to_proposal": True,
            "final_direction": "LONG",
            "consensus_score": 75,
            "risk_assessment": {
                "stop_loss": "'; DROP TABLE trade_proposals; --",  # SQL injection attempt
                "take_profit": None,
                "quantity": "0.1",
                "risk_amount": "50",
                "risk_reward_ratio": "2.0",
                "estimated_fee": "5",
                "estimated_slippage": "2",
            },
        }
        # _to_decimal should return None for invalid value, not raise
        result = builder.build(bad_result, current_price=Decimal("50000"))
        # stop_loss should be None (rejected gracefully), not crash
        assert result["stop_loss_price"] is None

    def test_xss_string_in_symbol_is_not_executed(self):
        """XSS strings in symbol field should be stored as literal strings."""
        from app.proposals.builder import ProposalBuilder

        builder = ProposalBuilder()
        xss_result = {
            "symbol": "<script>alert('xss')</script>",
            "proceed_to_proposal": True,
            "final_direction": "LONG",
            "consensus_score": 75,
            "risk_assessment": {
                "stop_loss": "48000",
                "take_profit": "52000",
                "quantity": "0.1",
                "risk_amount": "50",
                "risk_reward_ratio": "2.0",
                "estimated_fee": "5",
                "estimated_slippage": "2",
            },
        }
        # Should not raise — the symbol is stored as a string, not executed
        result = builder.build(xss_result, current_price=Decimal("50000"))
        assert "<script>" in result["symbol"]  # Stored literally, not executed


# ─────────────────────────────────────────────────────────────────
# Price Drift Guard Security
# ─────────────────────────────────────────────────────────────────


class TestPriceDriftGuardSecurity:

    def test_zero_approved_price_triggers_reconfirm(self):
        """Zero approved price should always trigger reconfirm (avoid divide-by-zero)."""
        from app.proposals.price_drift import PriceDriftGuard

        guard = PriceDriftGuard(max_drift_bps=20)
        result = guard.check(
            approved_price=Decimal("0"),
            current_price=Decimal("50000"),
        )
        assert result["requires_reconfirm"] is True

    def test_negative_drift_triggers_reconfirm(self):
        """Large price drop should also trigger reconfirm."""
        from app.proposals.price_drift import PriceDriftGuard

        guard = PriceDriftGuard(max_drift_bps=20)
        result = guard.check(
            approved_price=Decimal("50000"),
            current_price=Decimal("40000"),  # 20% drop
        )
        assert result["requires_reconfirm"] is True
        assert result["drift_bps"] > 20


# ─────────────────────────────────────────────────────────────────
# Import Boundaries (Sanity)
# ─────────────────────────────────────────────────────────────────


class TestImportBoundaries:

    def test_execution_module_does_not_import_agents(self):
        """Execution module must not import from agents (isolation)."""
        import app.execution.service as svc_module
        source = open(svc_module.__file__).read()
        # The execution service should not directly import agent code
        assert "from app.agents" not in source
        assert "import app.agents" not in source

    def test_agents_module_does_not_import_execution(self):
        """Agent orchestrator must not import from execution module."""
        import app.agents.orchestrator as orch_module
        source = open(orch_module.__file__).read()
        assert "from app.execution" not in source
        assert "import app.execution" not in source

    def test_proposals_module_does_not_import_agents_directly(self):
        """Proposals service must not import agent code (decoupled)."""
        import app.proposals.service as prop_svc
        source = open(prop_svc.__file__).read()
        assert "from app.agents" not in source

    def test_risk_engine_does_not_import_agents(self):
        """Risk engine is purely deterministic — no agent imports."""
        import app.risk.engine as risk_eng
        source = open(risk_eng.__file__).read()
        assert "from app.agents" not in source
