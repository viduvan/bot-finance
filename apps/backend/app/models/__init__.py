"""SQLAlchemy models package.

Import all models here so Alembic can discover them for migrations.
"""

from app.models.user import User, ExchangeAccount  # noqa: F401
from app.models.market import MarketCandle, MarketSnapshot  # noqa: F401
from app.models.feature import TechnicalFeature  # noqa: F401
from app.models.agent import AgentWorkflow, AgentRun, AgentOutput  # noqa: F401
from app.models.proposal import TradeProposal, ProposalVersion  # noqa: F401
from app.models.approval import ApprovalToken, ProposalApproval  # noqa: F401
from app.models.order import Order, OrderFill  # noqa: F401
from app.models.position import Position, TradeResult  # noqa: F401
from app.models.risk import RiskEvent  # noqa: F401
from app.models.audit import AuditLog, SystemEvent  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.backtest import StrategyVersion, BacktestRun, BacktestTrade  # noqa: F401
