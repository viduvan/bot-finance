"""Trade proposal and version models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TradeProposal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Central output of the system: a trade proposal awaiting human decision."""

    __tablename__ = "trade_proposals"

    workflow_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_workflows.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(10), nullable=False, default="SPOT")
    recommendation: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT", index=True)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    entry_zone_min: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    entry_zone_max: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    suggested_order_type: Mapped[str] = mapped_column(String(20), default="LIMIT")
    suggested_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    suggested_quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    take_profit_prices: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    estimated_risk_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    estimated_profit_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    risk_reward_ratio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    estimated_fee: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    estimated_slippage: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    agent_consensus: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    supporting_reasons: Mapped[dict] = mapped_column(JSONB, default=list)
    risk_warnings: Mapped[dict] = mapped_column(JSONB, default=list)
    critic_objections: Mapped[dict] = mapped_column(JSONB, default=list)
    market_snapshot_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="PAPER")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    versions: Mapped[list[ProposalVersion]] = relationship(
        back_populates="proposal", lazy="selectin"
    )


class ProposalVersion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Records every change to a proposal for audit trail."""

    __tablename__ = "proposal_versions"

    proposal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False)
    changed_by: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    previous_values: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    proposal: Mapped[TradeProposal] = relationship(back_populates="versions")
