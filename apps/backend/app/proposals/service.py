"""Proposal Service — orchestrates the full proposal lifecycle.

Handles:
- Creating proposals from analysis results
- Submitting for review
- Approving (with token issuance + price drift check)
- Rejecting
- Editing (triggers RECONFIRM_REQUIRED)
- Cancelling
- Re-triggering analysis (reanalyze)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import PROPOSALS_ACTIVE, PROPOSALS_APPROVED, PROPOSALS_CREATED, PROPOSALS_REJECTED
from app.proposals.approval_token import ApprovalTokenManager
from app.proposals.builder import ProposalBuilder
from app.proposals.price_drift import PriceDriftGuard
from app.repositories.proposal_repo import ProposalRepository

logger = structlog.get_logger(__name__)

_token_manager = ApprovalTokenManager()
_drift_guard = PriceDriftGuard()
_builder = ProposalBuilder()


class ProposalService:
    """Orchestrates all proposal lifecycle operations."""

    def __init__(self, db: AsyncSession) -> None:
        self._repo = ProposalRepository(db)
        self._db = db

    async def create_from_analysis(
        self,
        analysis_result: dict[str, Any],
        current_price: Decimal,
        created_by: str | None = None,
    ) -> dict:
        """Build and persist a proposal from an analysis result.

        Returns the created proposal as dict.
        """
        proposal_data = _builder.build(
            analysis_result=analysis_result,
            current_price=current_price,
            created_by=created_by,
        )

        proposal = await self._repo.create(proposal_data)

        # Immediately promote to PENDING_REVIEW
        proposal = await self._repo.transition_status(
            proposal=proposal,
            new_status="PENDING_REVIEW",
            change_type="SUBMITTED_FOR_REVIEW",
            changed_by="system",
        )

        await self._db.commit()

        try:
            PROPOSALS_CREATED.labels(
                symbol=proposal.symbol,
                recommendation=proposal.recommendation,
            ).inc()
            PROPOSALS_ACTIVE.inc()
        except Exception:
            pass

        logger.info(
            "proposal_created_and_submitted",
            proposal_id=str(proposal.id),
            symbol=proposal.symbol,
        )

        return self._proposal_to_dict(proposal)

    async def issue_approval_token(
        self,
        proposal_id: str,
        user_id: str,
    ) -> dict:
        """Issue a one-time approval token for a PENDING_REVIEW proposal."""
        proposal = await self._repo.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status != "PENDING_REVIEW":
            raise ValueError(
                f"Cannot issue token: proposal status is {proposal.status!r}, must be PENDING_REVIEW"
            )

        proposal_dict = self._proposal_to_dict(proposal)
        token = _token_manager.issue(proposal=proposal_dict, user_id=user_id)

        return {
            "token": token,
            "proposal_id": proposal_id,
            "expires_in_seconds": 30,
        }

    async def approve(
        self,
        proposal_id: str,
        user_id: str,
        token: str,
        current_price: Decimal,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """Approve a proposal for execution.

        Validates: token, user, price drift.
        On price drift: transitions to RECONFIRM_REQUIRED instead of APPROVED.
        """
        proposal = await self._repo.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status not in ("PENDING_REVIEW", "RECONFIRM_REQUIRED"):
            raise ValueError(f"Cannot approve proposal in status {proposal.status!r}")

        # Validate token
        proposal_dict = self._proposal_to_dict(proposal)
        validation = _token_manager.validate(
            token=token,
            proposal=proposal_dict,
            user_id=user_id,
        )

        if not validation["valid"]:
            raise ValueError(f"Token validation failed: {validation['reason']}")

        # Check price drift
        approved_price = proposal.suggested_price or proposal.current_price
        if approved_price:
            drift = _drift_guard.check(
                approved_price=Decimal(str(approved_price)),
                current_price=current_price,
            )
            if drift["requires_reconfirm"]:
                proposal = await self._repo.transition_status(
                    proposal=proposal,
                    new_status="RECONFIRM_REQUIRED",
                    change_type="PRICE_DRIFT_DETECTED",
                    changed_by=user_id,
                    changed_fields={"current_price": current_price},
                )
                await self._db.commit()

                return {
                    "status": "RECONFIRM_REQUIRED",
                    "reason": f"Price drifted {drift['drift_bps']:.1f} bps from approved price. Please re-confirm.",
                    "drift_bps": drift["drift_bps"],
                    "approved_price": str(approved_price),
                    "current_price": str(current_price),
                }

        # Consume token (one-time use)
        _token_manager.consume(token)

        # Approve
        proposal = await self._repo.transition_status(
            proposal=proposal,
            new_status="APPROVED",
            change_type="APPROVED_BY_HUMAN",
            changed_by=user_id,
        )

        await self._repo.save_approval(
            proposal_id=proposal_id,
            user_id=user_id,
            decision="APPROVED",
            reason="Human approved",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        await self._db.commit()

        try:
            PROPOSALS_APPROVED.labels(symbol=proposal.symbol).inc()
        except Exception:
            pass

        # Broadcast real-time event
        try:
            from app.api.websocket.connection_manager import event_manager
            await event_manager.broadcast("proposal_update", {
                "proposal_id": proposal_id,
                "symbol": proposal.symbol,
                "new_status": "APPROVED",
                "message": "Proposal approved",
            })
        except Exception:
            pass

        logger.info("proposal_approved", proposal_id=proposal_id, user_id=user_id)
        return {"status": "APPROVED", "proposal_id": proposal_id}

    async def reject(
        self,
        proposal_id: str,
        user_id: str,
        reason: str = "",
        ip_address: str | None = None,
    ) -> dict:
        """Reject a proposal."""
        proposal = await self._repo.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        proposal = await self._repo.transition_status(
            proposal=proposal,
            new_status="REJECTED",
            change_type="REJECTED_BY_HUMAN",
            changed_by=user_id,
        )

        await self._repo.save_approval(
            proposal_id=proposal_id,
            user_id=user_id,
            decision="REJECTED",
            reason=reason,
            ip_address=ip_address,
        )

        await self._db.commit()

        try:
            PROPOSALS_REJECTED.labels(symbol=proposal.symbol).inc()
            PROPOSALS_ACTIVE.dec()
        except Exception:
            pass

        # Broadcast real-time event
        try:
            from app.api.websocket.connection_manager import event_manager
            await event_manager.broadcast("proposal_update", {
                "proposal_id": proposal_id,
                "symbol": proposal.symbol,
                "new_status": "REJECTED",
                "message": reason or "Proposal rejected",
            })
        except Exception:
            pass

        logger.info("proposal_rejected", proposal_id=proposal_id, reason=reason)
        return {"status": "REJECTED", "proposal_id": proposal_id}

    async def edit(
        self,
        proposal_id: str,
        user_id: str,
        edited_fields: dict[str, Any],
    ) -> dict:
        """Edit a proposal (triggers RECONFIRM_REQUIRED for security-critical fields).

        Security-critical fields (suggested_price, suggested_quantity, stop_loss_price)
        automatically invalidate outstanding tokens and require re-confirmation.
        """
        proposal = await self._repo.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        if proposal.status not in ("PENDING_REVIEW", "RECONFIRM_REQUIRED"):
            raise ValueError(f"Cannot edit proposal in status {proposal.status!r}")

        SECURITY_CRITICAL_FIELDS = {"suggested_price", "suggested_quantity", "stop_loss_price"}
        has_critical_change = bool(SECURITY_CRITICAL_FIELDS & set(edited_fields.keys()))

        new_status = "RECONFIRM_REQUIRED" if has_critical_change else proposal.status

        proposal = await self._repo.transition_status(
            proposal=proposal,
            new_status=new_status,
            change_type="EDITED_BY_HUMAN",
            changed_by=user_id,
            changed_fields=edited_fields,
        )

        await self._repo.save_approval(
            proposal_id=proposal_id,
            user_id=user_id,
            decision="EDITED",
            edited_fields=edited_fields,
        )

        await self._db.commit()

        return {
            "status": proposal.status,
            "proposal_id": proposal_id,
            "reconfirm_required": has_critical_change,
        }

    async def cancel(self, proposal_id: str, user_id: str) -> dict:
        """Cancel a proposal."""
        proposal = await self._repo.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        proposal = await self._repo.transition_status(
            proposal=proposal,
            new_status="CANCELLED",
            change_type="CANCELLED_BY_HUMAN",
            changed_by=user_id,
        )

        await self._db.commit()

        try:
            PROPOSALS_ACTIVE.dec()
        except Exception:
            pass

        return {"status": "CANCELLED", "proposal_id": proposal_id}

    def _proposal_to_dict(self, proposal) -> dict:
        """Convert proposal ORM object to dict for token/API use."""
        return {
            "id": str(proposal.id),
            "symbol": proposal.symbol,
            "recommendation": proposal.recommendation,
            "status": proposal.status,
            "suggested_price": str(proposal.suggested_price) if proposal.suggested_price else None,
            "suggested_quantity": str(proposal.suggested_quantity) if proposal.suggested_quantity else None,
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
        }
