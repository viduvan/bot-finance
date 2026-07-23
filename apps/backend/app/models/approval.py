"""Approval token and proposal approval models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, INET_TYPE, JSON_TYPE, TimestampMixin, UUIDPrimaryKeyMixin


class ApprovalToken(Base, UUIDPrimaryKeyMixin):
    """One-time-use approval token for executing a trade.

    Security invariants:
    - Linked to exactly one proposal
    - Linked to exactly one user
    - Can only be used once (used_at is set on use)
    - Short expiration (default 30 seconds)
    - Does NOT contain any API secrets
    - Signed by server secret (HMAC)
    - Invalidated if proposal is modified after token creation
    """

    __tablename__ = "approval_tokens"

    proposal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    approved_payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    invalidation_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)


class ProposalApproval(Base, UUIDPrimaryKeyMixin):
    """Records human decisions on proposals (approve, reject, edit)."""

    __tablename__ = "proposal_approvals"

    proposal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    token_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("approval_tokens.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    edited_fields: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(INET_TYPE, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
