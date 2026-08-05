"""Proposal Repository — CRUD operations for trade proposals."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.approval import ProposalApproval
from app.models.proposal import ProposalVersion, TradeProposal

logger = structlog.get_logger(__name__)


def _sanitize_for_json(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types to safe equivalents."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_for_json(i) for i in obj]
    return obj


class ProposalRepository:
    """Data access layer for trade proposals, versions, and approvals."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, proposal_data: dict[str, Any]) -> TradeProposal:
        """Create a new proposal in DRAFT status."""
        proposal = TradeProposal(
            **{k: v for k, v in proposal_data.items() if hasattr(TradeProposal, k)}
        )
        self.db.add(proposal)
        await self.db.flush()

        # Record initial version
        await self._record_version(
            proposal=proposal,
            change_type="CREATED",
            changes=proposal_data,
            previous_values=None,
        )

        logger.info(
            "proposal_created",
            proposal_id=str(proposal.id),
            symbol=proposal.symbol,
            recommendation=proposal.recommendation,
        )
        return proposal

    async def get_by_id(self, proposal_id: str | UUID) -> TradeProposal | None:
        """Get a proposal by ID."""
        result = await self.db.execute(select(TradeProposal).where(TradeProposal.id == proposal_id))
        return result.scalar_one_or_none()

    async def list_active(self, symbol: str | None = None, limit: int = 20) -> list[TradeProposal]:
        """List active proposals (DRAFT, PENDING_REVIEW, RECONFIRM_REQUIRED)."""
        query = select(TradeProposal).where(
            TradeProposal.status.in_(["DRAFT", "PENDING_REVIEW", "RECONFIRM_REQUIRED"])
        )
        if symbol:
            query = query.where(TradeProposal.symbol == symbol)
        query = query.order_by(TradeProposal.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_all(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[TradeProposal]:
        """List proposals with optional filters."""
        query = select(TradeProposal)
        if symbol:
            query = query.where(TradeProposal.symbol == symbol)
        if status:
            query = query.where(TradeProposal.status == status)
        query = query.order_by(TradeProposal.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def transition_status(
        self,
        proposal: TradeProposal,
        new_status: str,
        change_type: str,
        changed_by: str | None = None,
        changed_fields: dict | None = None,
    ) -> TradeProposal:
        """Transition proposal to a new status via state machine."""
        old_status = proposal.status

        # Validate transition
        from app.proposals.state_machine import ProposalStateMachine

        ProposalStateMachine().transition(old_status, new_status)

        previous = {"status": old_status}
        proposal.status = new_status

        if changed_fields:
            for field, value in changed_fields.items():
                if hasattr(proposal, field):
                    previous[field] = getattr(proposal, field)
                    setattr(proposal, field, value)

        proposal.version = (proposal.version or 1) + 1

        await self._record_version(
            proposal=proposal,
            change_type=change_type,
            changes={"status": new_status, **(changed_fields or {})},
            previous_values=previous,
            changed_by=changed_by,
        )

        await self.db.flush()

        logger.info(
            "proposal_status_changed",
            proposal_id=str(proposal.id),
            from_status=old_status,
            to_status=new_status,
            change_type=change_type,
        )
        return proposal

    async def expire_pending_proposals(self) -> list[str]:
        """Expire all proposals past their expiration time. Returns list of expired IDs."""
        from app.proposals.expiration import ProposalExpirationService

        ProposalExpirationService()

        result = await self.db.execute(
            select(TradeProposal).where(
                TradeProposal.status.in_(["DRAFT", "PENDING_REVIEW", "RECONFIRM_REQUIRED"]),
                TradeProposal.expires_at < datetime.now(UTC),
            )
        )
        proposals = list(result.scalars().all())

        expired_ids = []
        for proposal in proposals:
            proposal.status = "EXPIRED"
            proposal.version = (proposal.version or 1) + 1
            await self._record_version(
                proposal=proposal,
                change_type="EXPIRED",
                changes={"status": "EXPIRED"},
                previous_values={"status": proposal.status},
            )
            expired_ids.append(str(proposal.id))

        if expired_ids:
            await self.db.flush()
            logger.info("proposals_expired", count=len(expired_ids))

        return expired_ids

    async def save_approval(
        self,
        proposal_id: str | UUID,
        user_id: str | UUID,
        decision: str,
        token_id: str | None = None,
        reason: str | None = None,
        edited_fields: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ProposalApproval:
        """Record a human decision on a proposal."""
        approval = ProposalApproval(
            proposal_id=proposal_id,
            user_id=user_id,
            decision=decision,
            token_id=token_id,
            reason=reason,
            edited_fields=edited_fields,
            ip_address=ip_address,
            user_agent=user_agent,
            decided_at=datetime.now(UTC),
        )
        self.db.add(approval)
        await self.db.flush()
        return approval

    async def _record_version(
        self,
        proposal: TradeProposal,
        change_type: str,
        changes: dict,
        previous_values: dict | None,
        changed_by: str | None = None,
    ) -> ProposalVersion:
        """Record a version snapshot for audit trail."""
        version = ProposalVersion(
            proposal_id=proposal.id,
            version=proposal.version or 1,
            changes=_sanitize_for_json(changes),
            changed_by=changed_by,
            change_type=change_type,
            previous_values=_sanitize_for_json(previous_values or {}),
        )
        self.db.add(version)
        await self.db.flush()
        return version
