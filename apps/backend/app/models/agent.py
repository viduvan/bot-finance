"""Agent workflow, run, and output models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import JSON_TYPE, Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentWorkflow(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tracks one complete analysis workflow (all agents for one symbol)."""

    __tablename__ = "agent_workflows"

    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    config_snapshot: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_estimated_cost: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="workflow", lazy="selectin")


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Individual agent execution within a workflow."""

    __tablename__ = "agent_runs"

    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_workflows.id"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    workflow: Mapped[AgentWorkflow] = relationship(back_populates="agent_runs")
    outputs: Mapped[list[AgentOutput]] = relationship(back_populates="agent_run", lazy="selectin")


class AgentOutput(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Structured output from an agent run."""

    __tablename__ = "agent_outputs"

    agent_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    recommendation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    output_json: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    validation_errors: Mapped[dict] = mapped_column(JSON_TYPE, default=list)

    # Relationships
    agent_run: Mapped[AgentRun] = relationship(back_populates="outputs")
