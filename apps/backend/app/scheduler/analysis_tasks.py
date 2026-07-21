"""Scheduled analysis tasks."""

from __future__ import annotations

from app.scheduler.worker import celery_app


@celery_app.task(name="app.scheduler.analysis_tasks.run_scheduled_analysis")
def run_scheduled_analysis() -> dict:
    """Run scheduled multi-agent analysis for all configured symbols.

    This task is triggered by Celery Beat at the configured interval
    (default: every 15 minutes).

    Implementation will be completed in Phase 4 (Multi-Agent).
    """
    # TODO: Phase 4 - Trigger analysis workflow for each symbol
    from app.config import settings
    return {
        "triggered": True,
        "symbols": settings.trading_symbols,
        "trading_mode": settings.trading_mode.value,
    }
