"""Proposal State Machine — strict transition enforcement.

States:
  DRAFT → PENDING_REVIEW
  PENDING_REVIEW → APPROVED | REJECTED | RECONFIRM_REQUIRED | CANCELLED
  RECONFIRM_REQUIRED → PENDING_REVIEW | REJECTED
  APPROVED → EXECUTED | CANCELLED
  EXECUTED → (terminal)
  REJECTED → (terminal)
  EXPIRED → (terminal)
  CANCELLED → (terminal)
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Terminal states: no further transitions allowed
TERMINAL_STATES = frozenset({"EXECUTED", "REJECTED", "EXPIRED", "CANCELLED"})

# Allowed transitions: {from_state: {valid_to_states}}
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PENDING_REVIEW"}),
    "PENDING_REVIEW": frozenset({"APPROVED", "REJECTED", "RECONFIRM_REQUIRED", "CANCELLED"}),
    "RECONFIRM_REQUIRED": frozenset({"PENDING_REVIEW", "REJECTED", "CANCELLED"}),
    "APPROVED": frozenset({"EXECUTED", "CANCELLED"}),
    "EXECUTED": frozenset(),
    "REJECTED": frozenset(),
    "EXPIRED": frozenset(),
    "CANCELLED": frozenset(),
}


class ProposalStateMachine:
    """Enforces valid state transitions for trade proposals.

    All state changes must go through this machine.
    Invalid transitions raise ValueError — never silently ignored.
    """

    def can_transition(self, from_state: str, to_state: str) -> bool:
        """Check if transition is valid without performing it."""
        allowed = ALLOWED_TRANSITIONS.get(from_state, frozenset())
        return to_state in allowed

    def transition(self, from_state: str, to_state: str) -> str:
        """Perform a state transition.

        Args:
            from_state: Current state of the proposal
            to_state: Target state

        Returns:
            to_state (the new state)

        Raises:
            ValueError: If the transition is not allowed
        """
        if not self.can_transition(from_state, to_state):
            allowed = ALLOWED_TRANSITIONS.get(from_state, frozenset())
            raise ValueError(
                f"Invalid state transition: {from_state!r} → {to_state!r}. "
                f"Allowed from {from_state!r}: {sorted(allowed) or '(none — terminal state)'}"
            )

        logger.info(
            "proposal_state_transition",
            from_state=from_state,
            to_state=to_state,
        )
        return to_state

    def get_allowed_transitions(self, from_state: str) -> list[str]:
        """Get list of valid target states from current state."""
        return sorted(ALLOWED_TRANSITIONS.get(from_state, frozenset()))

    def is_terminal(self, state: str) -> bool:
        """Return True if state is terminal (no further transitions)."""
        return state in TERMINAL_STATES
