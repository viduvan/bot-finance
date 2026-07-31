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
    include=[
        "app.scheduler.analysis_tasks",
        "app.scheduler.expiration_tasks",
    ],
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
    task_time_limit=450,       # Hard kill after 7.5 minutes
    task_soft_time_limit=400,  # Soft timeout after 6.6 minutes
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)
    worker_prefetch_multiplier=1,    # Fair scheduling

    # Result backend
    result_expires=3600,  # Results expire after 1 hour

    # Retry policy
    task_default_retry_delay=10,
    task_max_retries=3,

    # Task routes — all tasks use default 'celery' queue for single-worker setup
    # task_routes kept empty to avoid routing to non-existent queues
    task_routes={},
)

# ── Periodic Tasks (Celery Beat) ─────────────────────────────────

celery_app.conf.beat_schedule = {
    # Check for expired proposals every minute
    "check-expired-proposals": {
        "task": "app.scheduler.expiration_tasks.check_expired_proposals",
        "schedule": 60.0,
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
    # ── Market Data Tasks ────────────────────────────────────────
    # Sync candles every 15 minutes
    "sync-candles-15m": {
        "task": "market.sync_candles",
        "schedule": 15 * 60,  # 15 minutes
        "kwargs": {"timeframe": "15m"},
    },
    # Sync 1h candles every hour
    "sync-candles-1h": {
        "task": "market.sync_candles",
        "schedule": 60 * 60,  # 1 hour
        "kwargs": {"timeframe": "1h"},
    },
    # Sync 4h candles every 4 hours
    "sync-candles-4h": {
        "task": "market.sync_candles",
        "schedule": 4 * 60 * 60,  # 4 hours
        "kwargs": {"timeframe": "4h"},
    },
    # Refresh market snapshots every 60 seconds
    "refresh-snapshots": {
        "task": "market.refresh_snapshots",
        "schedule": 60.0,
    },
    # Backfill data gaps every hour
    "backfill-gaps": {
        "task": "market.backfill_gaps",
        "schedule": 60 * 60,  # 1 hour
    },
    # Clean up old data daily at 03:00 UTC
    "cleanup-old-data": {
        "task": "market.cleanup_old_data",
        "schedule": crontab(hour=3, minute=0),
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
