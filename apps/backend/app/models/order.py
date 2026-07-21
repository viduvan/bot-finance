"""Order and order fill models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Actual or paper order submitted to exchange."""

    __tablename__ = "orders"

    proposal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False, index=True
    )
    approval_token_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_tokens.id"), nullable=True
    )
    client_order_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    exchange_order_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0)
    average_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    environment: Mapped[str] = mapped_column(String(10), nullable=False, default="PAPER")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    fills: Mapped[list[OrderFill]] = relationship(back_populates="order", lazy="selectin")


class OrderFill(Base, UUIDPrimaryKeyMixin):
    """Individual fill execution within an order."""

    __tablename__ = "order_fills"

    order_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, index=True
    )
    exchange_fill_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fill_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fill_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    fee_asset: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_maker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    order: Mapped[Order] = relationship(back_populates="fills")
