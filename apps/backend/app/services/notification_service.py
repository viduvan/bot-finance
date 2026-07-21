"""Notification service: dispatches notifications to multiple channels.

Supports: Dashboard (DB), Telegram.
Each notification is stored in the database for dashboard display,
and optionally forwarded to Telegram.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import NotificationChannel, NotificationEventType
from app.models.notification import Notification
from app.services.telegram_service import telegram_service

logger = structlog.get_logger(__name__)


class NotificationService:
    """Multi-channel notification dispatcher."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def notify(
        self,
        event_type: NotificationEventType,
        title: str,
        body: str | None = None,
        data: dict | None = None,
        user_id: str | None = None,
        send_telegram: bool = True,
    ) -> None:
        """Send notification to dashboard and optionally Telegram.

        Always saves to DB (for dashboard). Optionally sends to Telegram.
        Never raises exceptions — notification failures are logged but don't
        break the main application flow.
        """
        try:
            # Save to database (for dashboard display)
            notification = Notification(
                user_id=user_id,
                channel=NotificationChannel.DASHBOARD.value,
                event_type=event_type.value,
                title=title,
                body=body,
                data=data or {},
                is_read=False,
                sent_at=datetime.now(UTC),
            )
            self.db.add(notification)
            await self.db.flush()

            logger.info(
                "notification_saved",
                event_type=event_type.value,
                title=title,
            )

            # Send to Telegram if enabled
            if send_telegram:
                telegram_text = f"<b>{title}</b>"
                if body:
                    telegram_text += f"\n\n{body}"
                await telegram_service.send_message(telegram_text)

        except Exception as e:
            logger.error(
                "notification_failed",
                event_type=event_type.value,
                error=str(e),
            )

    # ── Convenience Methods ──────────────────────────────────

    async def notify_new_proposal(
        self,
        symbol: str,
        recommendation: str,
        confidence: float,
        proposal_id: str,
    ) -> None:
        """Notify about a new trade proposal."""
        await self.notify(
            event_type=NotificationEventType.NEW_PROPOSAL,
            title=f"New {recommendation} proposal for {symbol}",
            body=f"Confidence: {confidence:.0%}. Open dashboard to review.",
            data={"proposal_id": proposal_id, "symbol": symbol},
        )

    async def notify_proposal_expiring(
        self, symbol: str, proposal_id: str, minutes_left: int
    ) -> None:
        """Warn that a proposal is about to expire."""
        await self.notify(
            event_type=NotificationEventType.PROPOSAL_EXPIRING,
            title=f"⏰ Proposal expiring in {minutes_left}min",
            body=f"{symbol} proposal will expire soon.",
            data={"proposal_id": proposal_id},
        )

    async def notify_order_filled(
        self, symbol: str, side: str, quantity: float, price: float, pnl: float | None = None
    ) -> None:
        """Notify about a filled order."""
        body = f"{side} {quantity} {symbol} at ${price:,.2f}"
        if pnl is not None:
            body += f" | PnL: ${pnl:,.2f}"
        await self.notify(
            event_type=NotificationEventType.ORDER_FILLED,
            title=f"Order Filled: {symbol}",
            body=body,
        )

    async def notify_risk_limit(self, reason: str) -> None:
        """Notify about a risk limit being exceeded."""
        await self.notify(
            event_type=NotificationEventType.RISK_LIMIT_EXCEEDED,
            title="⚠️ Risk Limit Exceeded",
            body=reason,
        )

    async def notify_system_error(self, service: str, message: str) -> None:
        """Notify about a system error."""
        await self.notify(
            event_type=NotificationEventType.SYSTEM_ERROR,
            title=f"🚨 System Error: {service}",
            body=message,
        )

    async def notify_binance_disconnected(self) -> None:
        """Notify about Binance WebSocket disconnection."""
        await self.notify(
            event_type=NotificationEventType.BINANCE_DISCONNECTED,
            title="🔴 Binance WebSocket Disconnected",
            body="Market data may be stale. Reconnecting...",
        )
