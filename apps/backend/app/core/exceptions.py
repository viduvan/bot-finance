"""Custom exception hierarchy for ACTA.

All exceptions inherit from ACTAError for consistent error handling.
Each exception carries a machine-readable error code for API responses.
"""

from __future__ import annotations


class ACTAError(Exception):
    """Base exception for all ACTA errors."""

    def __init__(self, message: str, error_code: str = "INTERNAL_ERROR") -> None:
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


# ── Authentication & Authorization ───────────────────────────────


class AuthenticationError(ACTAError):
    """Invalid credentials or expired token."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "AUTH_FAILED")


class AuthorizationError(ACTAError):
    """User lacks required permissions."""

    def __init__(self, message: str = "Insufficient permissions") -> None:
        super().__init__(message, "FORBIDDEN")


class MFARequiredError(ACTAError):
    """Multi-factor authentication required."""

    def __init__(self, message: str = "MFA verification required") -> None:
        super().__init__(message, "MFA_REQUIRED")


class MFAInvalidError(ACTAError):
    """Invalid MFA code."""

    def __init__(self, message: str = "Invalid MFA code") -> None:
        super().__init__(message, "MFA_INVALID")


class TokenExpiredError(ACTAError):
    """JWT or approval token has expired."""

    def __init__(self, message: str = "Token expired") -> None:
        super().__init__(message, "TOKEN_EXPIRED")


# ── Proposal & Approval ─────────────────────────────────────────


class InvalidStateTransitionError(ACTAError):
    """Attempted invalid proposal state transition."""

    def __init__(self, from_state: str, to_state: str) -> None:
        message = f"Invalid state transition: {from_state} → {to_state}"
        super().__init__(message, "INVALID_STATE_TRANSITION")


class ProposalExpiredError(ACTAError):
    """Proposal has expired and cannot be acted upon."""

    def __init__(self, proposal_id: str) -> None:
        super().__init__(f"Proposal {proposal_id} has expired", "PROPOSAL_EXPIRED")


class ProposalNotFoundError(ACTAError):
    """Proposal not found."""

    def __init__(self, proposal_id: str) -> None:
        super().__init__(f"Proposal {proposal_id} not found", "PROPOSAL_NOT_FOUND")


class ApprovalTokenInvalidError(ACTAError):
    """Approval token is invalid, used, or expired."""

    def __init__(self, reason: str = "Token is invalid") -> None:
        super().__init__(f"Approval token invalid: {reason}", "APPROVAL_TOKEN_INVALID")


class ApprovalTokenUsedError(ACTAError):
    """Approval token has already been used (one-time use enforced)."""

    def __init__(self) -> None:
        super().__init__("Approval token has already been used", "APPROVAL_TOKEN_USED")


# ── Risk ─────────────────────────────────────────────────────────


class RiskRejectionError(ACTAError):
    """Risk engine rejected the proposal."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        message = f"Risk check failed: {'; '.join(reasons)}"
        super().__init__(message, "RISK_REJECTED")


class DailyLossExceededError(RiskRejectionError):
    """Daily loss limit has been exceeded."""

    def __init__(self, current_loss: float, limit: float) -> None:
        super().__init__([f"Daily loss {current_loss:.2f}% exceeds limit {limit:.2f}%"])


class InsufficientBalanceError(ACTAError):
    """Not enough balance to execute the order."""

    def __init__(self, required: float, available: float) -> None:
        super().__init__(
            f"Insufficient balance: required {required}, available {available}",
            "INSUFFICIENT_BALANCE",
        )


class PriceDriftError(ACTAError):
    """Price has drifted beyond acceptable threshold since approval."""

    def __init__(self, drift_bps: float, max_bps: float) -> None:
        super().__init__(
            f"Price drift {drift_bps:.1f} bps exceeds maximum {max_bps:.1f} bps",
            "PRICE_DRIFT",
        )


# ── Execution ────────────────────────────────────────────────────


class ExecutionDeniedError(ACTAError):
    """Execution service refused to process the order."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Execution denied: {reason}", "EXECUTION_DENIED")


class DuplicateOrderError(ACTAError):
    """Attempted to create a duplicate order (idempotency violation)."""

    def __init__(self, client_order_id: str) -> None:
        super().__init__(
            f"Duplicate order detected: {client_order_id}",
            "DUPLICATE_ORDER",
        )


class OrderNotFoundError(ACTAError):
    """Order not found."""

    def __init__(self, order_id: str) -> None:
        super().__init__(f"Order {order_id} not found", "ORDER_NOT_FOUND")


# ── Market Data ──────────────────────────────────────────────────


class StaleDataError(ACTAError):
    """Market data is too old to be trusted."""

    def __init__(self, staleness_seconds: float) -> None:
        super().__init__(
            f"Market data is stale: {staleness_seconds:.0f}s old",
            "STALE_DATA",
        )


class BinanceConnectionError(ACTAError):
    """Failed to connect to Binance."""

    def __init__(self, detail: str = "Connection failed") -> None:
        super().__init__(f"Binance connection error: {detail}", "BINANCE_ERROR")


# ── Agent ────────────────────────────────────────────────────────


class AgentTimeoutError(ACTAError):
    """Agent workflow exceeded maximum time limit."""

    def __init__(self, agent_name: str, timeout: int) -> None:
        super().__init__(
            f"Agent '{agent_name}' timed out after {timeout}s",
            "AGENT_TIMEOUT",
        )


class AgentOutputValidationError(ACTAError):
    """Agent produced invalid structured output."""

    def __init__(self, agent_name: str, errors: list[str]) -> None:
        self.validation_errors = errors
        super().__init__(
            f"Agent '{agent_name}' output validation failed: {'; '.join(errors)}",
            "AGENT_OUTPUT_INVALID",
        )


class LLMUnavailableError(ACTAError):
    """All LLM providers are unavailable."""

    def __init__(self) -> None:
        super().__init__(
            "All LLM providers unavailable. Result: NO_TRADE",
            "LLM_UNAVAILABLE",
        )


# ── Configuration ────────────────────────────────────────────────


class ConfigurationError(ACTAError):
    """Invalid configuration detected."""

    def __init__(self, detail: str) -> None:
        super().__init__(f"Configuration error: {detail}", "CONFIG_ERROR")


# ── General ──────────────────────────────────────────────────────


class NotFoundError(ACTAError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(f"{resource} '{identifier}' not found", "NOT_FOUND")


class ConflictError(ACTAError):
    """Resource conflict (duplicate, version mismatch, etc)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "CONFLICT")


class RateLimitError(ACTAError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, "RATE_LIMITED")


class ExternalServiceError(ACTAError):
    """External service (Binance, News API) is unavailable."""

    def __init__(self, service: str, detail: str) -> None:
        super().__init__(f"{service} service error: {detail}", "EXTERNAL_SERVICE_ERROR")
