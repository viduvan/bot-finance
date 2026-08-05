"""Execution API endpoints — execute approved proposals + view positions/trades."""

from __future__ import annotations

from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.dependencies import CurrentUser, DBSession

logger = structlog.get_logger(__name__)
router = APIRouter()


class ExecuteRequest(BaseModel):
    current_price: str  # Decimal-safe string


@router.post("/execution/{proposal_id}/execute")
async def execute_proposal(
    proposal_id: str,
    body: ExecuteRequest,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Execute an APPROVED proposal as a paper trade.

    Simulates fill, creates position, transitions proposal to EXECUTED.
    """
    from app.execution.service import PaperExecutionServiceAsync
    from app.repositories.proposal_repo import ProposalRepository

    repo = ProposalRepository(db)
    proposal = await repo.get_by_id(proposal_id)

    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    if proposal.status != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute proposal in status {proposal.status!r}. Must be APPROVED.",
        )

    proposal_dict = {
        "id": str(proposal.id),
        "symbol": proposal.symbol,
        "recommendation": proposal.recommendation,
        "status": proposal.status,
        "suggested_price": str(proposal.suggested_price) if proposal.suggested_price else None,
        "suggested_quantity": str(proposal.suggested_quantity)
        if proposal.suggested_quantity
        else None,
        "suggested_order_type": proposal.suggested_order_type,
        "stop_loss_price": str(proposal.stop_loss_price) if proposal.stop_loss_price else None,
        "environment": proposal.environment,
        "version": proposal.version,
    }

    try:
        svc = PaperExecutionServiceAsync(db)
        result = await svc.execute_and_persist(
            proposal_dict=proposal_dict,
            current_price=Decimal(body.current_price),
            user_id=str(user.id),
        )
        return {
            "status": "EXECUTED",
            "client_order_id": result["client_order_id"],
            "order_id": result.get("order_id"),
            "position_id": result.get("position_id"),
            "fill_price": str(result["fill_price"]),
            "fill_quantity": str(result["fill_quantity"]),
            "fee": str(result["fee"]),
            "side": result["side"],
            "environment": result["environment"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/positions")
async def list_positions(
    user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None, description="OPEN or CLOSED"),
    limit: int = Query(default=20, le=100),
) -> dict:
    """List paper trading positions."""
    from sqlalchemy import select

    from app.models.position import Position

    query = select(Position).where(Position.environment == "PAPER")
    if symbol:
        query = query.where(Position.symbol == symbol)
    if status:
        query = query.where(Position.status == status)
    query = query.order_by(Position.opened_at.desc()).limit(limit)

    result = await db.execute(query)
    positions = list(result.scalars().all())

    return {
        "count": len(positions),
        "positions": [_serialize_position(p) for p in positions],
    }


@router.get("/positions/{position_id}")
async def get_position(
    position_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get a specific position by ID."""
    from sqlalchemy import select

    from app.models.position import Position

    result = await db.execute(select(Position).where(Position.id == position_id))
    pos = result.scalar_one_or_none()

    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")
    return _serialize_position(pos)


@router.get("/trades")
async def list_trade_results(
    user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> dict:
    """List completed trade results (closed positions)."""
    from sqlalchemy import select

    from app.models.position import TradeResult

    query = select(TradeResult).where(TradeResult.environment == "PAPER")
    if symbol:
        query = query.where(TradeResult.symbol == symbol)
    query = query.order_by(TradeResult.closed_at.desc()).limit(limit)

    result = await db.execute(query)
    trades = list(result.scalars().all())

    return {
        "count": len(trades),
        "trades": [_serialize_trade(t) for t in trades],
    }


@router.get("/positions/summary/pnl")
async def get_pnl_summary(
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get aggregated P&L summary for paper trading."""
    from sqlalchemy import func, select

    from app.models.position import TradeResult

    result = await db.execute(
        select(
            func.count(TradeResult.id).label("total_trades"),
            func.sum(TradeResult.net_pnl).label("total_net_pnl"),
            func.sum(TradeResult.gross_pnl).label("total_gross_pnl"),
            func.sum(TradeResult.total_fee).label("total_fees"),
        ).where(TradeResult.environment == "PAPER")
    )
    row = result.one()

    total_trades = row.total_trades or 0
    total_net_pnl = row.total_net_pnl or Decimal("0")

    # Win count
    win_result = await db.execute(
        select(func.count(TradeResult.id)).where(
            TradeResult.environment == "PAPER",
            TradeResult.net_pnl > 0,
        )
    )
    winning_trades = win_result.scalar() or 0
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

    return {
        "total_trades": total_trades,
        "winning_trades": winning_trades,
        "losing_trades": total_trades - winning_trades,
        "win_rate": round(win_rate, 2),
        "total_net_pnl": str(total_net_pnl),
        "total_gross_pnl": str(row.total_gross_pnl or 0),
        "total_fees_paid": str(row.total_fees or 0),
        "environment": "PAPER",
    }


def _serialize_position(pos) -> dict:
    return {
        "id": str(pos.id),
        "symbol": pos.symbol,
        "side": pos.side,
        "entry_price": str(pos.entry_price),
        "quantity": str(pos.quantity),
        "current_price": str(pos.current_price) if pos.current_price else None,
        "unrealized_pnl": str(pos.unrealized_pnl) if pos.unrealized_pnl else "0",
        "total_fee": str(pos.total_fee),
        "environment": pos.environment,
        "status": pos.status,
        "opened_at": pos.opened_at.isoformat() if pos.opened_at else None,
        "closed_at": pos.closed_at.isoformat() if pos.closed_at else None,
    }


def _serialize_trade(trade) -> dict:
    return {
        "id": str(trade.id),
        "symbol": trade.symbol,
        "side": trade.side,
        "entry_price": str(trade.entry_price),
        "exit_price": str(trade.exit_price),
        "quantity": str(trade.quantity),
        "gross_pnl": str(trade.gross_pnl),
        "total_fee": str(trade.total_fee),
        "net_pnl": str(trade.net_pnl),
        "return_percent": str(trade.return_percent) if trade.return_percent else None,
        "holding_time_seconds": trade.holding_time_seconds,
        "close_reason": trade.close_reason,
        "environment": trade.environment,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
    }
