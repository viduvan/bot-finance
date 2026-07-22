"""Agent workflow repository — persists analysis results to DB."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentOutput, AgentRun, AgentWorkflow

logger = structlog.get_logger(__name__)


class AgentWorkflowRepository:
    """CRUD operations for agent workflow + run + output records."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_workflow(
        self,
        symbol: str,
        trigger_type: str = "SCHEDULED",
        config_snapshot: dict | None = None,
    ) -> AgentWorkflow:
        """Create a new workflow record."""
        wf = AgentWorkflow(
            symbol=symbol,
            trigger_type=trigger_type,
            status="RUNNING",
            started_at=datetime.now(UTC),
            config_snapshot=config_snapshot or {},
        )
        self.db.add(wf)
        await self.db.flush()
        return wf

    async def complete_workflow(
        self,
        workflow: AgentWorkflow,
        success: bool,
        analysis_result_dict: dict,
        error_message: str | None = None,
    ) -> AgentWorkflow:
        """Mark a workflow as complete and store aggregated results."""
        workflow.status = "SUCCESS" if success else "FAILED"
        workflow.completed_at = datetime.now(UTC)
        workflow.error_message = error_message

        # Aggregate token/cost stats from all agent runs
        total_input = 0
        total_output = 0

        for agent_name in ["market_regime", "technical", "order_flow", "risk_analysis", "critic"]:
            agent_out = analysis_result_dict.get(agent_name) or {}
            if isinstance(agent_out, dict):
                total_input += agent_out.get("input_tokens", 0)
                total_output += agent_out.get("output_tokens", 0)

        workflow.total_input_tokens = total_input
        workflow.total_output_tokens = total_output

        if workflow.started_at and workflow.completed_at:
            delta = workflow.completed_at - workflow.started_at
            workflow.total_latency_ms = int(delta.total_seconds() * 1000)

        await self.db.flush()
        return workflow

    async def save_agent_run(
        self,
        workflow_id: str,
        agent_name: str,
        output_dict: dict,
        status: str = "SUCCESS",
        error: str | None = None,
    ) -> AgentRun:
        """Save an individual agent run result."""
        run = AgentRun(
            workflow_id=workflow_id,
            agent_name=agent_name,
            model_name=output_dict.get("model"),
            status=status,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            latency_ms=int(output_dict.get("latency_ms", 0)),
            input_tokens=output_dict.get("input_tokens"),
            output_tokens=output_dict.get("output_tokens"),
            retry_count=output_dict.get("parse_retries", 0),
            error_message=error,
        )
        self.db.add(run)
        await self.db.flush()

        # Save output
        recommendation = (
            output_dict.get("signal")
            or output_dict.get("regime")
            or output_dict.get("flow_bias")
            or output_dict.get("risk_rating")
            or output_dict.get("final_recommendation")
        )
        conviction = output_dict.get("conviction", 0)

        agent_output = AgentOutput(
            agent_run_id=run.id,
            recommendation=str(recommendation) if recommendation else None,
            confidence=conviction / 100 if conviction else None,
            output_json=output_dict,
            validation_status="VALID",
        )
        self.db.add(agent_output)
        await self.db.flush()

        return run

    async def get_recent_workflows(
        self, symbol: str, limit: int = 10
    ) -> list[AgentWorkflow]:
        """Get recent analysis workflows for a symbol."""
        result = await self.db.execute(
            select(AgentWorkflow)
            .where(AgentWorkflow.symbol == symbol)
            .order_by(AgentWorkflow.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
