"""User and ExchangeAccount models."""

from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """System user with authentication credentials."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="TRADER")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    exchange_accounts: Mapped[list[ExchangeAccount]] = relationship(
        back_populates="user", lazy="selectin"
    )


class ExchangeAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Encrypted Binance API credentials.

    - Read-only and trading keys are stored separately.
    - All secrets are AES-256 encrypted at rest.
    - Agent Service only accesses read-only keys.
    """

    __tablename__ = "exchange_accounts"

    user_id: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, default="BINANCE")
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    encrypted_read_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_read_api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_trade_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_trade_api_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONB, default=list)
    ip_whitelist: Mapped[dict] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user: Mapped[User] = relationship(back_populates="exchange_accounts")
