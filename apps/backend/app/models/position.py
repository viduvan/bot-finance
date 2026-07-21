"""Position and trade result models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Position(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Open or closed position tracker."""

    __tablename__ = "positions"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False, default="LONG")
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    current_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    total_fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="PAPER")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TradeResult(Base, UUIDPrimaryKeyMixin):
    """Completed trade performance record."""

    __tablename__ = "trade_results"

    position_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("positions.id"), nullable=False
    )
    proposal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    gross_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    total_slippage: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    net_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    return_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    holding_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="PAPER")
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
