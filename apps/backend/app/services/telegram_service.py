"""Telegram bot service for sending notifications.

Telegram is used ONLY for notifications — no trading commands via Telegram.
Users must open the dashboard to approve proposals.
"""

from __future__ import annotations

from typing import Any

import structlog
import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

# Telegram Bot API base URL
_TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramService:
    """Sends notifications via Telegram Bot API.

    Uses httpx directly instead of python-telegram-bot for simplicity.
    The bot only sends messages — it never processes incoming commands.
    """

    def __init__(self) -> None:
        self.enabled = settings.telegram_enabled
        self.token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self._client: httpx.AsyncClient | None = None

    @property
    def base_url(self) -> str:
        return _TELEGRAM_API_BASE.format(token=self.token)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False,
    ) -> bool:
        """Send a text message to the configured chat.

        Returns True if sent successfully, False otherwise.
        Never raises exceptions — notifications should not break the main flow.
        """
        if not self.enabled:
            logger.debug("telegram_disabled", message_preview=text[:50])
            return False

        if not self.token or not self.chat_id:
            logger.warning("telegram_not_configured")
            return False

        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_notification": disable_notification,
                },
            )
            response.raise_for_status()
            logger.info("telegram_message_sent", chat_id=self.chat_id)
            return True
        except Exception as e:
            logger.error("telegram_send_failed", error=str(e))
            return False

    async def send_proposal_notification(
        self,
        symbol: str,
        recommendation: str,
        confidence: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_reward: float,
        expires_in_minutes: int,
    ) -> bool:
        """Send a formatted trade proposal notification."""
        emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "NO_TRADE": "⚪"}.get(
            recommendation, "⚪"
        )

        text = (
            f"{emoji} <b>New Trade Proposal</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Signal:</b> {recommendation}\n"
            f"<b>Confidence:</b> {confidence:.0%}\n"
            f"<b>Entry:</b> ${entry_price:,.2f}\n"
            f"<b>Stop Loss:</b> ${stop_loss:,.2f}\n"
            f"<b>Take Profit:</b> ${take_profit:,.2f}\n"
            f"<b>Risk/Reward:</b> 1:{risk_reward:.1f}\n"
            f"<b>Expires in:</b> {expires_in_minutes} minutes\n\n"
            f"⚠️ Open dashboard to review and approve."
        )
        return await self.send_message(text)

    async def send_order_notification(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        status: str,
        pnl: float | None = None,
    ) -> bool:
        """Send order execution notification."""
        emoji = "✅" if status == "FILLED" else "❌" if status == "FAILED" else "⏳"
        text = (
            f"{emoji} <b>Order {status}</b>\n\n"
            f"<b>Symbol:</b> {symbol}\n"
            f"<b>Side:</b> {side}\n"
            f"<b>Quantity:</b> {quantity}\n"
            f"<b>Price:</b> ${price:,.2f}\n"
        )
        if pnl is not None:
            pnl_emoji = "📈" if pnl >= 0 else "📉"
            text += f"<b>PnL:</b> {pnl_emoji} ${pnl:,.2f}\n"
        return await self.send_message(text)

    async def send_alert(self, title: str, message: str) -> bool:
        """Send a system alert notification."""
        text = f"🚨 <b>{title}</b>\n\n{message}"
        return await self.send_message(text)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Singleton instance
telegram_service = TelegramService()
