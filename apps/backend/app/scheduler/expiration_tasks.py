"""Expiration check tasks for proposals and approval tokens."""

from __future__ import annotations

from app.scheduler.worker import celery_app


@celery_app.task(name="app.scheduler.expiration_tasks.check_expired_proposals")
def check_expired_proposals() -> dict:
    """Check and expire proposals that have passed their expiration time.

    Proposals in WAITING_FOR_HUMAN status that have expired are
    transitioned to EXPIRED status. This runs every 60 seconds.

    Implementation will be completed in Phase 5 (Proposal Workflow).
    """
    # TODO: Phase 5 - Query proposals where expires_at < now() and status = WAITING_FOR_HUMAN
    return {"checked": True, "expired_count": 0}


@celery_app.task(name="app.scheduler.expiration_tasks.check_expired_tokens")
def check_expired_tokens() -> dict:
    """Check and invalidate expired approval tokens.

    Tokens with expires_at < now() and status = ACTIVE are
    transitioned to EXPIRED. This runs every 15 seconds.

    Implementation will be completed in Phase 5 (Proposal Workflow).
    """
    # TODO: Phase 5 - Query tokens where expires_at < now() and status = ACTIVE
    return {"checked": True, "expired_count": 0}
