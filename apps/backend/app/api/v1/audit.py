"""Audit log API endpoints — view audit trail."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencies import CurrentUser, DBSession
from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/audit/logs")
async def list_audit_logs(
    user: CurrentUser,
    db: DBSession,
    action: str | None = Query(default=None, description="Filter by action type"),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> dict:
    """List audit log entries (newest first). Admin only."""
    query = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)

    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    return {
        "count": len(logs),
        "logs": [
            {
                "id": log.id,
                "user_id": str(log.user_id) if log.user_id else None,
                "service": log.service,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": str(log.ip_address) if log.ip_address else None,
                "request_id": log.request_id,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
