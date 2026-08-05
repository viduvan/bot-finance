"""Risk event model."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import JSON_TYPE, Base, TimestampMixin, UUIDPrimaryKeyMixin


class RiskEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Records risk gate decisions (allow/deny) for auditability."""

    __tablename__ = "risk_events"

    proposal_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    risk_metrics: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
