"""Orders API endpoints — view orders and fills."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DBSession
from app.models.order import Order

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/orders")
async def list_orders(
    user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> dict:
    """List orders with their fills (newest first)."""
    query = (
        select(Order)
        .options(selectinload(Order.fills))
        .order_by(Order.created_at.desc())
        .limit(limit)
    )

    if symbol:
        query = query.where(Order.symbol == symbol)
    if status:
        query = query.where(Order.status == status)

    result = await db.execute(query)
    orders = list(result.scalars().unique().all())

    return {
        "count": len(orders),
        "orders": [_serialize_order(o) for o in orders],
    }


@router.get("/orders/{order_id}")
async def get_order(
    order_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get a specific order with fills."""
    result = await db.execute(
        select(Order).options(selectinload(Order.fills)).where(Order.id == order_id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")
    return _serialize_order(order)


def _serialize_order(order: Order) -> dict:
    return {
        "id": str(order.id),
        "proposal_id": str(order.proposal_id),
        "client_order_id": order.client_order_id,
        "exchange_order_id": order.exchange_order_id,
        "symbol": order.symbol,
        "side": order.side,
        "order_type": order.order_type,
        "price": str(order.price) if order.price else None,
        "quantity": str(order.quantity),
        "filled_quantity": str(order.filled_quantity),
        "average_fill_price": str(order.average_fill_price) if order.average_fill_price else None,
        "status": order.status,
        "environment": order.environment,
        "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
        "filled_at": order.filled_at.isoformat() if order.filled_at else None,
        "canceled_at": order.canceled_at.isoformat() if order.canceled_at else None,
        "error_message": order.error_message,
        "fills": [
            {
                "id": str(f.id),
                "fill_price": str(f.fill_price),
                "fill_quantity": str(f.fill_quantity),
                "fee": str(f.fee),
                "fee_asset": f.fee_asset,
                "is_maker": f.is_maker,
                "timestamp": f.timestamp.isoformat() if f.timestamp else None,
            }
            for f in order.fills
        ],
        "created_at": order.created_at.isoformat() if order.created_at else None,
    }
