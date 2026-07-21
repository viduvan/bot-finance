"""Centralized enumerations for the entire ACTA system.

All enums are string-based for JSON serialization and database storage.
"""

from __future__ import annotations

from enum import Enum


# ── User & Auth ──────────────────────────────────────────────────


class UserRole(str, Enum):
    """User roles for RBAC authorization."""

    ADMIN = "ADMIN"
    TRADER = "TRADER"
    VIEWER = "VIEWER"
    AGENT_SERVICE = "AGENT_SERVICE"
    EXECUTION_SERVICE = "EXECUTION_SERVICE"


class Permission(str, Enum):
    """Granular permissions for authorization."""

    VIEW_MARKET = "VIEW_MARKET"
    VIEW_PROPOSAL = "VIEW_PROPOSAL"
    EDIT_PROPOSAL = "EDIT_PROPOSAL"
    APPROVE_PROPOSAL = "APPROVE_PROPOSAL"
    REJECT_PROPOSAL = "REJECT_PROPOSAL"
    EXECUTE_APPROVED_ORDER = "EXECUTE_APPROVED_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    VIEW_ANALYTICS = "VIEW_ANALYTICS"
    MANAGE_CONFIG = "MANAGE_CONFIG"
    TRIGGER_ANALYSIS = "TRIGGER_ANALYSIS"


# Role → permissions mapping
ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: set(Permission),  # All permissions
    UserRole.TRADER: {
        Permission.VIEW_MARKET,
        Permission.VIEW_PROPOSAL,
        Permission.EDIT_PROPOSAL,
        Permission.APPROVE_PROPOSAL,
        Permission.REJECT_PROPOSAL,
        Permission.CANCEL_ORDER,
        Permission.VIEW_ANALYTICS,
        Permission.TRIGGER_ANALYSIS,
    },
    UserRole.VIEWER: {
        Permission.VIEW_MARKET,
        Permission.VIEW_PROPOSAL,
        Permission.VIEW_ANALYTICS,
    },
    UserRole.AGENT_SERVICE: {
        Permission.VIEW_MARKET,
        Permission.TRIGGER_ANALYSIS,
    },
    UserRole.EXECUTION_SERVICE: {
        Permission.EXECUTE_APPROVED_ORDER,
        Permission.VIEW_MARKET,
    },
}


# ── Trading ──────────────────────────────────────────────────────


class TradingEnvironment(str, Enum):
    """Trading environment type."""

    PAPER = "PAPER"
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"


class OrderSide(str, Enum):
    """Order direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    LIMIT = "LIMIT"
    MARKET = "MARKET"


class OrderStatus(str, Enum):
    """Exchange order status."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


# ── Proposals ────────────────────────────────────────────────────


class Recommendation(str, Enum):
    """Trading recommendation from signal aggregator."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    NO_TRADE = "NO_TRADE"


class ProposalStatus(str, Enum):
    """Trade proposal lifecycle status.

    State machine transitions are enforced in proposals/state_machine.py
    """

    DRAFT = "DRAFT"
    ANALYZING = "ANALYZING"
    RISK_REJECTED = "RISK_REJECTED"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    EDITED_BY_HUMAN = "EDITED_BY_HUMAN"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECONFIRM_REQUIRED = "RECONFIRM_REQUIRED"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    EXECUTED = "EXECUTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"


class ApprovalDecision(str, Enum):
    """Human decision on a proposal."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"


class ApprovalTokenStatus(str, Enum):
    """Approval token lifecycle."""

    ACTIVE = "ACTIVE"
    USED = "USED"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


# ── Agents ───────────────────────────────────────────────────────


class AgentName(str, Enum):
    """Multi-agent system agent identifiers."""

    MARKET_REGIME = "market_regime"
    TECHNICAL = "technical"
    ORDER_FLOW = "order_flow"
    RISK_ANALYSIS = "risk_analysis"
    CRITIC = "critic"


class AgentWorkflowStatus(str, Enum):
    """Agent workflow execution status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class AgentRunStatus(str, Enum):
    """Individual agent run status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    SKIPPED = "SKIPPED"


class MarketRegime(str, Enum):
    """Market regime classifications."""

    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    MEAN_REVERSION = "MEAN_REVERSION"


class CriticVerdict(str, Enum):
    """Critic agent verdict on a proposal."""

    PROCEED = "PROCEED"
    CAUTION = "CAUTION"
    REJECT = "REJECT"


class LiquidityStatus(str, Enum):
    """Order book liquidity assessment."""

    NORMAL = "NORMAL"
    LOW = "LOW"
    VERY_LOW = "VERY_LOW"
    HIGH = "HIGH"


# ── Risk ─────────────────────────────────────────────────────────


class RiskDecision(str, Enum):
    """Risk gate decision."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class RiskLevel(str, Enum):
    """Risk classification level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskEventType(str, Enum):
    """Types of risk events."""

    DAILY_LOSS_EXCEEDED = "DAILY_LOSS_EXCEEDED"
    MAX_DRAWDOWN_EXCEEDED = "MAX_DRAWDOWN_EXCEEDED"
    POSITION_SIZE_INVALID = "POSITION_SIZE_INVALID"
    BALANCE_INSUFFICIENT = "BALANCE_INSUFFICIENT"
    RISK_REWARD_BELOW_MIN = "RISK_REWARD_BELOW_MIN"
    SPREAD_ABOVE_MAX = "SPREAD_ABOVE_MAX"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"
    DATA_STALE = "DATA_STALE"
    DUPLICATE_PROPOSAL = "DUPLICATE_PROPOSAL"
    EXPOSURE_TOO_HIGH = "EXPOSURE_TOO_HIGH"
    STOP_LOSS_INVALID = "STOP_LOSS_INVALID"
    TAKE_PROFIT_INVALID = "TAKE_PROFIT_INVALID"
    PRICE_DRIFT_TOO_LARGE = "PRICE_DRIFT_TOO_LARGE"
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    TRADING_MODE_DISABLED = "TRADING_MODE_DISABLED"


# ── Market Data ──────────────────────────────────────────────────


class Timeframe(str, Enum):
    """Supported candlestick timeframes."""

    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


class DataSource(str, Enum):
    """Market data source."""

    BINANCE = "BINANCE"
    BINANCE_TESTNET = "BINANCE_TESTNET"


# ── Notifications ────────────────────────────────────────────────


class NotificationChannel(str, Enum):
    """Notification delivery channel."""

    DASHBOARD = "DASHBOARD"
    TELEGRAM = "TELEGRAM"
    EMAIL = "EMAIL"


class NotificationEventType(str, Enum):
    """Notification event types."""

    NEW_PROPOSAL = "NEW_PROPOSAL"
    PROPOSAL_EXPIRING = "PROPOSAL_EXPIRING"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_PARTIALLY_FILLED = "ORDER_PARTIALLY_FILLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    RISK_LIMIT_EXCEEDED = "RISK_LIMIT_EXCEEDED"
    DAILY_LOSS_REACHED = "DAILY_LOSS_REACHED"
    BINANCE_DISCONNECTED = "BINANCE_DISCONNECTED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


# ── Audit ────────────────────────────────────────────────────────


class AuditAction(str, Enum):
    """Auditable actions (append-only log)."""

    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    USER_LOGIN_FAILED = "USER_LOGIN_FAILED"
    MFA_SETUP = "MFA_SETUP"
    MFA_VERIFIED = "MFA_VERIFIED"
    PROPOSAL_CREATED = "PROPOSAL_CREATED"
    PROPOSAL_EDITED = "PROPOSAL_EDITED"
    PROPOSAL_APPROVED = "PROPOSAL_APPROVED"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"
    PROPOSAL_EXPIRED = "PROPOSAL_EXPIRED"
    APPROVAL_TOKEN_ISSUED = "APPROVAL_TOKEN_ISSUED"
    APPROVAL_TOKEN_USED = "APPROVAL_TOKEN_USED"
    APPROVAL_TOKEN_EXPIRED = "APPROVAL_TOKEN_EXPIRED"
    APPROVAL_TOKEN_INVALIDATED = "APPROVAL_TOKEN_INVALIDATED"
    EXECUTION_REQUESTED = "EXECUTION_REQUESTED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_FAILED = "ORDER_FAILED"
    ORDER_CANCELED = "ORDER_CANCELED"
    RISK_REJECTION = "RISK_REJECTION"
    CONFIG_CHANGED = "CONFIG_CHANGED"
    ANALYSIS_TRIGGERED = "ANALYSIS_TRIGGERED"


# ── Backtest ─────────────────────────────────────────────────────


class BacktestStatus(str, Enum):
    """Backtest execution status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PositionStatus(str, Enum):
    """Position tracking status."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LIQUIDATED = "LIQUIDATED"


class CloseReason(str, Enum):
    """Reason for closing a position."""

    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    MANUAL = "MANUAL"
    EXPIRED = "EXPIRED"
    SIGNAL = "SIGNAL"


# ── LLM ──────────────────────────────────────────────────────────


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OLLAMA = "ollama"
    GEMINI = "gemini"
    OPENAI = "openai"


# ── Analysis Trigger ─────────────────────────────────────────────


class AnalysisTriggerType(str, Enum):
    """What triggered the analysis workflow."""

    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    EVENT = "EVENT"
