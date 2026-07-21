"""Celery worker configuration and task definitions.

This module configures:
- Celery app with Redis broker
- Periodic tasks via Celery Beat
- Task routing and serialization
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import settings

# ── Celery App ───────────────────────────────────────────────────

celery_app = Celery(
    "acta",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,

    # Task execution
    task_track_started=True,
    task_time_limit=300,       # Hard kill after 5 minutes
    task_soft_time_limit=240,  # Soft timeout after 4 minutes
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)
    worker_prefetch_multiplier=1,    # Fair scheduling

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Retry policy
    task_default_retry_delay=10,
    task_max_retries=3,

    # Task routes (future use for scaling)
    task_routes={
        "app.scheduler.analysis_tasks.*": {"queue": "analysis"},
        "app.scheduler.expiration_tasks.*": {"queue": "maintenance"},
    },
)

# ── Periodic Tasks (Celery Beat) ─────────────────────────────────

celery_app.conf.beat_schedule = {
    # Check for expired proposals every minute
    "check-expired-proposals": {
        "task": "app.scheduler.expiration_tasks.check_expired_proposals",
        "schedule": 60.0,  # Every 60 seconds
    },
    # Check for expired approval tokens every 15 seconds
    "check-expired-tokens": {
        "task": "app.scheduler.expiration_tasks.check_expired_tokens",
        "schedule": 15.0,
    },
    # System health heartbeat
    "system-heartbeat": {
        "task": "app.scheduler.worker.system_heartbeat",
        "schedule": 60.0,
    },
}

# Conditionally add analysis schedule
if settings.analysis_schedule_enabled:
    celery_app.conf.beat_schedule["scheduled-analysis"] = {
        "task": "app.scheduler.analysis_tasks.run_scheduled_analysis",
        "schedule": settings.analysis_interval_minutes * 60,
    }


# ── Simple Tasks ─────────────────────────────────────────────────


@celery_app.task(name="app.scheduler.worker.system_heartbeat")
def system_heartbeat() -> dict:
    """Periodic heartbeat to verify worker is alive."""
    from datetime import UTC, datetime
    return {
        "status": "alive",
        "timestamp": datetime.now(UTC).isoformat(),
        "trading_mode": settings.trading_mode.value,
    }
