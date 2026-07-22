"""Paper Execution Service — orchestrates APPROVED proposal → simulated fill → position.

Execution flow:
  1. Validate proposal is APPROVED
  2. Determine side (BUY→LONG, SELL→SHORT)
  3. Generate unique client_order_id
  4. Simulate fill via PaperFillSimulator
  5. Create position via PaperPositionManager
  6. Record daily loss (for risk gate integration)
  7. Return execution result dict

This service is synchronous (no DB) for unit testing.
The async DB-persisting version lives in PaperExecutionServiceAsync.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import structlog

from app.core.constants import CLIENT_ORDER_ID_PREFIX
from app.execution.paper_fill import PaperFillSimulator
from app.execution.position_manager import PaperPositionManager

logger = structlog.get_logger(__name__)

RECOMMENDATION_TO_SIDE = {
    "BUY": "LONG",
    "LONG": "LONG",
    "SELL": "SHORT",
    "SHORT": "SHORT",
}


class PaperExecutionService:
    """Synchronous paper execution service for unit testing.

    For production (DB persistence), use PaperExecutionServiceAsync.
    """

    def __init__(self) -> None:
        self._fill_sim = PaperFillSimulator()
        self._position_mgr = PaperPositionManager()

    def execute(
        self,
        proposal: dict[str, Any],
        current_price: Decimal,
    ) -> dict[str, Any]:
        """Execute a paper trade from an APPROVED proposal.

        Args:
            proposal: Proposal dict (must be status='APPROVED')
            current_price: Current market price for fill simulation

        Returns:
            dict: client_order_id, fill_price, fill_quantity, position, environment, etc.

        Raises:
            ValueError: If proposal is not APPROVED
        """
        status = proposal.get("status", "")
        if status != "APPROVED":
            raise ValueError(
                f"Cannot execute proposal in status {status!r} — must be APPROVED"
            )

        symbol = proposal["symbol"]
        recommendation = proposal.get("recommendation", "BUY")
        order_type = proposal.get("suggested_order_type", "MARKET")
        order_price = Decimal(str(proposal["suggested_price"])) if proposal.get("suggested_price") else None
        quantity = Decimal(str(proposal["suggested_quantity"]))
        environment = proposal.get("environment", "PAPER")
        side_position = RECOMMENDATION_TO_SIDE.get(recommendation, "LONG")
        side_order = "BUY" if side_position == "LONG" else "SELL"

        # Generate unique client order ID
        short_id = str(proposal.get("id", uuid.uuid4()))[:8]
        client_order_id = f"{CLIENT_ORDER_ID_PREFIX}-{short_id}-{uuid.uuid4().hex[:6].upper()}"

        # Simulate fill
        fill = self._fill_sim.simulate_fill(
            order_type=order_type,
            order_price=order_price,
            current_price=current_price,
            quantity=quantity,
            side=side_order,
        )

        # Determine effective fill price (LIMIT unfilled → use current for paper)
        if not fill["filled"] and order_type == "LIMIT":
            # Paper trading: force fill at limit price for simplicity
            fill["filled"] = True
            fill["fill_price"] = order_price or current_price
            fill["fill_quantity"] = quantity
            fill["fee"] = (fill["fill_price"] * quantity * Decimal("0.001")).quantize(Decimal("0.00100000"))
            fill["notional"] = fill["fill_price"] * quantity

        fill_price = fill["fill_price"]
        fee = fill["fee"]

        # Open position
        position = self._position_mgr.open_position(
            symbol=symbol,
            side=side_position,
            entry_price=fill_price,
            quantity=quantity,
            fee=fee,
            environment=environment,
        )

        logger.info(
            "paper_execution_complete",
            symbol=symbol,
            side=side_position,
            fill_price=str(fill_price),
            quantity=str(quantity),
            fee=str(fee),
            client_order_id=client_order_id,
            environment=environment,
        )

        return {
            "client_order_id": client_order_id,
            "symbol": symbol,
            "side": side_order,
            "order_type": order_type,
            "fill_price": fill_price,
            "fill_quantity": quantity,
            "fee": fee,
            "notional": fill["notional"],
            "slippage": fill.get("slippage_amount", Decimal("0")),
            "position": position,
            "environment": environment,
            "proposal_id": proposal.get("id"),
        }


class PaperExecutionServiceAsync:
    """Async paper execution service with DB persistence.

    Used in the API and Celery tasks.
    """

    def __init__(self, db, daily_tracker=None) -> None:
        self._db = db
        self._sync_svc = PaperExecutionService()
        self._daily_tracker = daily_tracker

    async def execute_and_persist(
        self,
        proposal_dict: dict[str, Any],
        current_price: Decimal,
        user_id: str,
    ) -> dict[str, Any]:
        """Execute proposal and persist order + position to DB.

        Args:
            proposal_dict: Proposal as serialized dict
            current_price: Current market price
            user_id: Who triggered execution

        Returns:
            Execution result with DB IDs
        """
        from datetime import UTC, datetime
        from app.models.order import Order, OrderFill
        from app.models.position import Position, TradeResult
        from app.repositories.proposal_repo import ProposalRepository

        # Execute (synchronous logic)
        result = self._sync_svc.execute(
            proposal=proposal_dict,
            current_price=current_price,
        )
        position_data = result["position"]
        now = datetime.now(UTC)

        # Persist Order
        order = Order(
            proposal_id=proposal_dict["id"],
            client_order_id=result["client_order_id"],
            symbol=result["symbol"],
            side=result["side"],
            order_type=result["order_type"],
            price=result["fill_price"],
            quantity=result["fill_quantity"],
            filled_quantity=result["fill_quantity"],
            average_fill_price=result["fill_price"],
            status="FILLED",
            environment=result["environment"],
            submitted_at=now,
            filled_at=now,
        )
        self._db.add(order)
        await self._db.flush()

        # Persist OrderFill
        fill_record = OrderFill(
            order_id=order.id,
            fill_price=result["fill_price"],
            fill_quantity=result["fill_quantity"],
            fee=result["fee"],
            fee_asset="USDT",
            is_maker=result["order_type"] == "LIMIT",
            timestamp=now,
            created_at=now,
        )
        self._db.add(fill_record)

        # Persist Position
        pos = Position(
            symbol=position_data["symbol"],
            side=position_data["side"],
            entry_price=position_data["entry_price"],
            quantity=position_data["quantity"],
            current_price=position_data["current_price"],
            unrealized_pnl=Decimal("0"),
            total_fee=position_data["total_fee"],
            environment=position_data["environment"],
            status="OPEN",
            opened_at=position_data["opened_at"],
        )
        self._db.add(pos)
        await self._db.flush()

        # Transition proposal to EXECUTED
        repo = ProposalRepository(self._db)
        proposal_obj = await repo.get_by_id(proposal_dict["id"])
        if proposal_obj:
            await repo.transition_status(
                proposal=proposal_obj,
                new_status="EXECUTED",
                change_type="ORDER_FILLED",
                changed_by=user_id,
            )

        await self._db.commit()

        # Record in daily loss tracker (for risk gate)
        if self._daily_tracker:
            self._daily_tracker.record_trade_result(
                symbol=result["symbol"],
                pnl=Decimal("0"),  # PnL is 0 at open; tracked at close
                balance=Decimal("10000"),
            )

        # Send Telegram notification
        await self._notify_order_filled(result)

        result["order_id"] = str(order.id)
        result["position_id"] = str(pos.id)
        return result

    async def _notify_order_filled(self, result: dict) -> None:
        """Send Telegram notification when order is filled."""
        from app.config import settings
        if not settings.telegram_enabled:
            return

        symbol = result["symbol"]
        side = result["side"]
        price = result["fill_price"]
        qty = result["fill_quantity"]

        message = (
            f"✅ *Order Filled (PAPER)*\n"
            f"Symbol: `{symbol}`\n"
            f"Side: *{side}*\n"
            f"Price: `{price}`\n"
            f"Quantity: `{qty}`\n"
            f"Fee: `{result['fee']}`"
        )

        try:
            import httpx
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(url, json={
                    "chat_id": settings.telegram_chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                })
        except Exception as e:
            logger.warning("telegram_fill_notification_failed", error=str(e))
