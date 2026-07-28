"""Notification API endpoints — list, mark read, unread count."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, func, update

from app.dependencies import CurrentUser, DBSession
from app.models.notification import Notification

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/notifications")
async def list_notifications(
    user: CurrentUser,
    db: DBSession,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, le=100),
) -> dict:
    """List notifications for the current user (newest first)."""
    query = select(Notification).order_by(Notification.created_at.desc()).limit(limit)
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712

    result = await db.execute(query)
    notifications = list(result.scalars().all())

    return {
        "count": len(notifications),
        "notifications": [
            {
                "id": str(n.id),
                "channel": n.channel,
                "event_type": n.event_type,
                "title": n.title,
                "body": n.body,
                "data": n.data,
                "is_read": n.is_read,
                "sent_at": n.sent_at.isoformat() if n.sent_at else None,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in notifications
        ],
    }


@router.get("/notifications/unread-count")
async def unread_count(
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get unread notification count."""
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.is_read == False  # noqa: E712
        )
    )
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post("/notifications/{notification_id}/read")
async def mark_read(
    notification_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Mark a notification as read."""
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    notif.is_read = True
    notif.read_at = datetime.now(UTC)
    await db.flush()

    return {"status": "ok", "id": notification_id}


@router.post("/notifications/read-all")
async def mark_all_read(
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Mark all notifications as read."""
    await db.execute(
        update(Notification)
        .where(Notification.is_read == False)  # noqa: E712
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.flush()
    return {"status": "ok"}
