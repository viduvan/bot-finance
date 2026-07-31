"""Audit log helper — fire-and-forget helper for recording audit events.

Usage:
    await record_audit(db, action="PROPOSAL_APPROVED", user_id=user.id,
                       resource_type="proposal", resource_id=str(proposal.id),
                       service="proposals", request=request)
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger(__name__)


async def record_audit(
    db: AsyncSession,
    action: str,
    service: str,
    user_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    """Append an audit log entry. Silently swallows errors to avoid breaking main flow."""
    try:
        ip: str | None = None
        if request:
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)

        entry = AuditLog(
            user_id=user_id,
            service=service,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip,
        )
        db.add(entry)
        await db.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("audit_log_failed", action=action, error=str(exc))
