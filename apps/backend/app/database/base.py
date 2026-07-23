"""SQLAlchemy base model with common columns."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, String, DateTime, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Cross-dialect types (PostgreSQL native in production, String/JSON in SQLite tests)
JSON_TYPE = JSONB().with_variant(JSON(), "sqlite")
INET_TYPE = INET().with_variant(String(45), "sqlite")


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDPrimaryKeyMixin:
    """Mixin that adds a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
