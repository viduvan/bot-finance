"""Proposal Expiration Service — detect and process expired proposals.

Proposals expire if not actioned within their TTL (default 10 minutes).
Terminal states (EXECUTED, REJECTED, EXPIRED, CANCELLED) cannot be expired.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from app.proposals.state_machine import TERMINAL_STATES

logger = structlog.get_logger(__name__)

# States that can be expired (active states only)
EXPIRABLE_STATES = frozenset({"PENDING_REVIEW", "RECONFIRM_REQUIRED", "DRAFT"})


class ProposalExpirationService:
    """Detects expired proposals and processes expiration logic."""

    def is_expired(self, proposal: dict) -> bool:
        """Check if a proposal has passed its expiration time.

        Args:
            proposal: Dict with 'expires_at' (datetime) and 'status' fields

        Returns:
            True if the proposal is past expiry AND in an expirable state
        """
        status = proposal.get("status", "")

        # Terminal states are never re-expired
        if status in TERMINAL_STATES:
            return False

        # Only expirable states can expire
        if status not in EXPIRABLE_STATES:
            return False

        expires_at = proposal.get("expires_at")
        if expires_at is None:
            return False

        now = datetime.now(UTC)
        if isinstance(expires_at, str):
            from datetime import datetime as dt
            expires_at = dt.fromisoformat(expires_at)

        # Ensure timezone-aware comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        return now > expires_at

    def seconds_until_expiry(self, proposal: dict) -> float:
        """Return seconds remaining until expiry. Returns 0 if already expired."""
        expires_at = proposal.get("expires_at")
        if expires_at is None:
            return 0.0

        now = datetime.now(UTC)
        if isinstance(expires_at, str):
            from datetime import datetime as dt
            expires_at = dt.fromisoformat(expires_at)

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        remaining = (expires_at - now).total_seconds()
        return max(0.0, remaining)

    def get_expiry_summary(self, proposal: dict) -> dict:
        """Get human-readable expiry status for a proposal."""
        expired = self.is_expired(proposal)
        seconds_left = self.seconds_until_expiry(proposal)

        return {
            "is_expired": expired,
            "seconds_until_expiry": round(seconds_left),
            "expires_at": str(proposal.get("expires_at", "")),
            "status": proposal.get("status", ""),
        }
