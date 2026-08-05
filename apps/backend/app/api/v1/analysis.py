"""Analysis API endpoints — trigger and retrieve analysis results."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query

from app.dependencies import CurrentUser, DBSession

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/analysis/{symbol}/trigger")
async def trigger_analysis(
    symbol: str,
    user: CurrentUser,
) -> dict:
    """Manually trigger an analysis run for a symbol (async via Celery).

    Returns the Celery task ID — poll /analysis/task/{task_id} for result.
    """
    from app.scheduler.analysis_tasks import run_analysis_for_symbol

    task = run_analysis_for_symbol.apply_async(args=[symbol])
    return {
        "status": "queued",
        "symbol": symbol,
        "task_id": task.id,
        "message": f"Analysis for {symbol} queued. Check /api/v1/analysis/task/{task.id}",
    }


@router.post("/analysis/{symbol}/trigger-sync")
async def trigger_analysis_sync(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Synchronously run analysis and return result immediately.

    Use for development/testing. In production use /trigger (async).
    Timeout: 90 seconds.
    """
    from app.agents.orchestrator import AnalysisOrchestrator

    orchestrator = AnalysisOrchestrator(db)
    result = await orchestrator.analyze(symbol)
    return result.to_dict()


@router.get("/analysis/task/{task_id}")
async def get_analysis_task_status(
    task_id: str,
    user: CurrentUser,
) -> dict:
    """Get the status/result of a queued analysis task."""
    from app.scheduler.worker import celery_app

    task_result = celery_app.AsyncResult(task_id)

    if task_result.state == "PENDING":
        return {"status": "pending", "task_id": task_id}
    if task_result.state == "STARTED":
        return {"status": "running", "task_id": task_id}
    if task_result.state == "SUCCESS":
        return {"status": "success", "task_id": task_id, "result": task_result.result}
    if task_result.state == "FAILURE":
        return {"status": "failed", "task_id": task_id, "error": str(task_result.result)}
    return {"status": task_result.state, "task_id": task_id}


@router.get("/analysis/{symbol}/history")
async def get_analysis_history(
    symbol: str,
    user: CurrentUser,
    db: DBSession,
    limit: int = Query(default=10, le=50),
) -> dict:
    """Get recent analysis workflow history for a symbol."""
    from app.repositories.agent_repo import AgentWorkflowRepository

    repo = AgentWorkflowRepository(db)
    workflows = await repo.get_recent_workflows(symbol, limit)

    return {
        "symbol": symbol,
        "count": len(workflows),
        "workflows": [
            {
                "id": str(wf.id),
                "status": wf.status,
                "trigger_type": wf.trigger_type,
                "started_at": wf.started_at.isoformat() if wf.started_at else None,
                "completed_at": wf.completed_at.isoformat() if wf.completed_at else None,
                "total_latency_ms": wf.total_latency_ms,
                "total_input_tokens": wf.total_input_tokens,
                "total_output_tokens": wf.total_output_tokens,
                "error_message": wf.error_message,
            }
            for wf in workflows
        ],
    }
