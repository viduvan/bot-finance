"""Technical feature model for computed indicators."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import JSON_TYPE, Base, TimestampMixin


class TechnicalFeature(Base, TimestampMixin):
    """Computed technical indicators stored as versioned JSON."""

    __tablename__ = "technical_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    features: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
