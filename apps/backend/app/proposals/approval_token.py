"""Approval Token Manager — one-time-use HMAC-signed tokens for trade approval.

Security guarantees:
- Each token is HMAC-signed with server secret (SHA-256)
- Token is tied to: proposal_id + user_id + payload_hash + expiry
- payload_hash covers price, quantity, stop_loss — any change invalidates token
- One-time use: token is consumed on successful validation
- Short TTL (default: 30 seconds from config)
- Constant-time comparison to prevent timing attacks
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_used_tokens: set[str] = set()  # In-memory; production uses Redis


class ApprovalTokenManager:
    """Issues and validates one-time approval tokens.

    Uses HMAC-SHA256 signed tokens (JWT-style but custom to avoid library deps).
    Token format: "{payload_b64}.{signature}"
    """

    def __init__(self, secret: str | None = None) -> None:
        self._secret = (secret or settings.approval_token_secret).encode()

    def issue(
        self,
        proposal: dict[str, Any],
        user_id: str,
        ttl_seconds: int | None = None,
    ) -> str:
        """Issue a new approval token.

        Args:
            proposal: Proposal dict (must include id, suggested_price, quantity, etc.)
            user_id: ID of the user who will use this token
            ttl_seconds: Token lifetime in seconds (default from config)

        Returns:
            Signed token string
        """
        ttl = ttl_seconds if ttl_seconds is not None else settings.approval_token_expiration_seconds
        expires_at = time.time() + ttl

        payload_hash = self._compute_payload_hash(proposal)

        claims = {
            "proposal_id": str(proposal["id"]),
            "user_id": str(user_id),
            "payload_hash": payload_hash,
            "expires_at": expires_at,
            "issued_at": time.time(),
        }

        claims_json = json.dumps(claims, sort_keys=True)
        claims_b64 = claims_json.encode().hex()
        signature = self._sign(claims_b64)

        token = f"{claims_b64}.{signature}"
        logger.info(
            "approval_token_issued",
            proposal_id=claims["proposal_id"],
            user_id=user_id,
            expires_in_seconds=ttl,
        )
        return token

    def validate(
        self,
        token: str,
        proposal: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Validate an approval token.

        Returns:
            dict: {"valid": bool, "reason": str, "claims": dict | None}
        """
        try:
            claims_b64, signature = token.rsplit(".", 1)
        except ValueError:
            return {"valid": False, "reason": "malformed token", "claims": None}

        # Signature check (constant-time)
        expected_sig = self._sign(claims_b64)
        if not hmac.compare_digest(signature, expected_sig):
            return {"valid": False, "reason": "invalid signature", "claims": None}

        # Decode claims
        try:
            claims = json.loads(bytes.fromhex(claims_b64).decode())
        except Exception:
            return {"valid": False, "reason": "malformed token payload", "claims": None}

        # Check expiry
        if time.time() > claims["expires_at"]:
            return {"valid": False, "reason": "token expired", "claims": claims}

        # Check user
        if claims["user_id"] != str(user_id):
            return {"valid": False, "reason": "user_id mismatch", "claims": claims}

        # Check proposal not changed
        current_payload_hash = self._compute_payload_hash(proposal)
        if claims["payload_hash"] != current_payload_hash:
            return {
                "valid": False,
                "reason": "proposal payload changed since token was issued — reconfirm required",
                "claims": claims,
            }

        # Check one-time use
        token_fingerprint = self._fingerprint(token)
        if token_fingerprint in _used_tokens:
            return {"valid": False, "reason": "token already consumed", "claims": claims}

        return {"valid": True, "reason": "ok", "claims": claims}

    def consume(self, token: str) -> None:
        """Mark token as used (one-time-use enforcement)."""
        _used_tokens.add(self._fingerprint(token))
        logger.info("approval_token_consumed")

    def decode(self, token: str) -> dict[str, Any]:
        """Decode token payload without validating signature (for inspection)."""
        try:
            claims_b64 = token.split(".")[0]
            return json.loads(bytes.fromhex(claims_b64).decode())
        except Exception as e:
            raise ValueError(f"Cannot decode token: {e}") from e

    def _sign(self, data: str) -> str:
        """Compute HMAC-SHA256 signature."""
        return hmac.new(self._secret, data.encode(), hashlib.sha256).hexdigest()

    def _compute_payload_hash(self, proposal: dict[str, Any]) -> str:
        """Compute a hash of the security-critical proposal fields.

        Any change to price, quantity, or SL invalidates outstanding tokens.
        """
        critical_fields = {
            "id": str(proposal.get("id", "")),
            "suggested_price": str(proposal.get("suggested_price", "")),
            "suggested_quantity": str(proposal.get("suggested_quantity", "")),
            "stop_loss_price": str(proposal.get("stop_loss_price", "")),
            "version": str(proposal.get("version", 1)),
        }
        payload_json = json.dumps(critical_fields, sort_keys=True)
        return hashlib.sha256(payload_json.encode()).hexdigest()

    def _fingerprint(self, token: str) -> str:
        """Compute a fingerprint for one-time-use tracking."""
        return hashlib.sha256(token.encode()).hexdigest()
