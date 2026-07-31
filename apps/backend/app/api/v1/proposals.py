"""Proposal API endpoints — full CRUD + approval flow."""

from __future__ import annotations

from decimal import Decimal

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.core.audit_helper import record_audit
from app.dependencies import CurrentUser, DBSession

logger = structlog.get_logger(__name__)
router = APIRouter()


# ── Request/Response Schemas ─────────────────────────────────────


class ApproveRequest(BaseModel):
    token: str
    current_price: str = Field(..., description="Current market price as string (Decimal-safe)")


class RejectRequest(BaseModel):
    reason: str = ""


class EditRequest(BaseModel):
    suggested_price: str | None = None
    suggested_quantity: str | None = None
    stop_loss_price: str | None = None
    reason: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("/proposals")
async def list_proposals(
    user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
) -> dict:
    """List proposals with optional filters."""
    from app.repositories.proposal_repo import ProposalRepository
    repo = ProposalRepository(db)
    proposals = await repo.list_all(symbol=symbol, status=status, limit=limit)
    return {
        "count": len(proposals),
        "proposals": [_serialize(p) for p in proposals],
    }


@router.get("/proposals/active")
async def list_active_proposals(
    user: CurrentUser,
    db: DBSession,
    symbol: str | None = Query(default=None),
) -> dict:
    """List active proposals (DRAFT, PENDING_REVIEW, RECONFIRM_REQUIRED)."""
    from app.repositories.proposal_repo import ProposalRepository
    repo = ProposalRepository(db)
    proposals = await repo.list_active(symbol=symbol)
    return {
        "count": len(proposals),
        "proposals": [_serialize(p) for p in proposals],
    }


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Get a specific proposal by ID."""
    from app.repositories.proposal_repo import ProposalRepository
    repo = ProposalRepository(db)
    proposal = await repo.get_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")
    return _serialize(proposal)


@router.post("/proposals/{proposal_id}/approval-token")
async def issue_approval_token(
    proposal_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Issue a one-time approval token for a PENDING_REVIEW proposal.

    Token expires in 30 seconds and ties to the current proposal price/qty.
    """
    from app.proposals.service import ProposalService
    svc = ProposalService(db)
    try:
        result = await svc.issue_approval_token(
            proposal_id=proposal_id,
            user_id=str(user.id),
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    body: ApproveRequest,
    user: CurrentUser,
    db: DBSession,
    request: Request,
) -> dict:
    """Approve a proposal for execution.

    Requires:
    - Valid approval token (issued via /approval-token, expires in 30s)
    - Current market price for drift check
    """
    from app.proposals.service import ProposalService
    svc = ProposalService(db)

    try:
        result = await svc.approve(
            proposal_id=proposal_id,
            user_id=str(user.id),
            token=body.token,
            current_price=Decimal(body.current_price),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        await record_audit(
            db, action="PROPOSAL_APPROVED", service="proposals",
            user_id=str(user.id),
            resource_type="proposal", resource_id=proposal_id,
            details={"current_price": body.current_price},
            request=request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    body: RejectRequest,
    user: CurrentUser,
    db: DBSession,
    request: Request,
) -> dict:
    """Reject a proposal."""
    from app.proposals.service import ProposalService
    svc = ProposalService(db)
    try:
        result = await svc.reject(
            proposal_id=proposal_id,
            user_id=str(user.id),
            reason=body.reason,
            ip_address=request.client.host if request.client else None,
        )
        await record_audit(
            db, action="PROPOSAL_REJECTED", service="proposals",
            user_id=str(user.id),
            resource_type="proposal", resource_id=proposal_id,
            details={"reason": body.reason},
            request=request,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/proposals/{proposal_id}/edit")
async def edit_proposal(
    proposal_id: str,
    body: EditRequest,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Edit a proposal.

    Modifying price, quantity, or stop-loss will:
    1. Require re-confirmation (RECONFIRM_REQUIRED state)
    2. Invalidate any outstanding approval tokens
    """
    from app.proposals.service import ProposalService
    svc = ProposalService(db)

    # Only include non-None fields
    edited = {
        k: v for k, v in {
            "suggested_price": Decimal(body.suggested_price) if body.suggested_price else None,
            "suggested_quantity": Decimal(body.suggested_quantity) if body.suggested_quantity else None,
            "stop_loss_price": Decimal(body.stop_loss_price) if body.stop_loss_price else None,
        }.items() if v is not None
    }

    if not edited:
        raise HTTPException(status_code=400, detail="No valid fields to edit")

    try:
        return await svc.edit(
            proposal_id=proposal_id,
            user_id=str(user.id),
            edited_fields=edited,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_proposal(
    proposal_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Cancel a proposal."""
    from app.proposals.service import ProposalService
    svc = ProposalService(db)
    try:
        return await svc.cancel(proposal_id=proposal_id, user_id=str(user.id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/reanalyze")
async def reanalyze_proposal(
    proposal_id: str,
    user: CurrentUser,
    db: DBSession,
) -> dict:
    """Trigger a fresh analysis for a proposal's symbol (async via Celery)."""
    from app.repositories.proposal_repo import ProposalRepository
    from app.scheduler.analysis_tasks import run_analysis_for_symbol

    repo = ProposalRepository(db)
    proposal = await repo.get_by_id(proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

    task = run_analysis_for_symbol.apply_async(args=[proposal.symbol])
    return {
        "message": f"Re-analysis queued for {proposal.symbol}",
        "task_id": task.id,
        "symbol": proposal.symbol,
    }


def _serialize(proposal) -> dict:
    """Serialize a TradeProposal ORM object to API response dict."""
    from app.proposals.expiration import ProposalExpirationService
    svc = ProposalExpirationService()
    p_dict = {
        "id": str(proposal.id),
        "symbol": proposal.symbol,
        "market": proposal.market,
        "recommendation": proposal.recommendation,
        "status": proposal.status,
        "current_price": str(proposal.current_price) if proposal.current_price else None,
        "suggested_price": str(proposal.suggested_price) if proposal.suggested_price else None,
        "suggested_quantity": str(proposal.suggested_quantity) if proposal.suggested_quantity else None,
        "suggested_order_type": proposal.suggested_order_type,
        "stop_loss_price": str(proposal.stop_loss_price) if proposal.stop_loss_price else None,
        "take_profit_prices": proposal.take_profit_prices,
        "risk_reward_ratio": str(proposal.risk_reward_ratio) if proposal.risk_reward_ratio else None,
        "estimated_fee": str(proposal.estimated_fee) if proposal.estimated_fee else None,
        "confidence": str(proposal.confidence) if proposal.confidence else None,
        "agent_consensus": proposal.agent_consensus,
        "supporting_reasons": proposal.supporting_reasons,
        "risk_warnings": proposal.risk_warnings,
        "critic_objections": proposal.critic_objections,
        "environment": proposal.environment,
        "version": proposal.version,
        "expires_at": proposal.expires_at.isoformat() if proposal.expires_at else None,
        "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
        "updated_at": proposal.updated_at.isoformat() if proposal.updated_at else None,
    }

    # Add expiry info
    p_dict["seconds_until_expiry"] = svc.seconds_until_expiry(
        {"expires_at": proposal.expires_at, "status": proposal.status}
    )
    return p_dict
