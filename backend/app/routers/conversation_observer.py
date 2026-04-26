"""Conversation Observer API Router - Observer findings and proposals."""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.routers.superadmin import require_superuser
from app.schemas.conversation import (
    ObserverFindingResponse,
    ObserverProposalResponse,
    ObserverProposalCreateRequest,
)
from app.services.observer_service import ObserverService

router = APIRouter(
    prefix="/api/v1/superadmin/conversation/observer",
    tags=["conversation-observer"],
)


# ── Findings ───────────────────────────────────────────────────────────────────

@router.get("/findings", response_model=list[ObserverFindingResponse])
async def list_findings(
    status: Optional[str] = None,
    limit: int = 50,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> list[ObserverFindingResponse]:
    """List observer findings."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    findings = await ObserverService.get_findings(
        db, current_user.active_org_id, status, limit
    )

    return [
        ObserverFindingResponse(
            id=str(f.id),
            type=f.type,
            severity=f.severity,
            reason=f.reason,
            suggestedImprovement=f.suggested_improvement,
            status=f.status,
            createdAt=f.created_at,
        )
        for f in findings
    ]


@router.post("/findings/analyze/{conversation_id}")
async def analyze_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> dict[str, Any]:
    """Analyze a conversation and create findings."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    findings = await ObserverService.create_findings(
        db, conversation_id, current_user.active_org_id
    )

    return {
        "findingsCreated": len(findings),
        "findings": [
            {
                "id": str(f.id),
                "type": f.type,
                "severity": f.severity,
                "reason": f.reason,
            }
            for f in findings
        ],
    }


# ── Proposals ───────────────────────────────────────────────────────────────────

@router.get("/proposals", response_model=list[ObserverProposalResponse])
async def list_proposals(
    status: Optional[str] = None,
    limit: int = 50,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> list[ObserverProposalResponse]:
    """List observer proposals."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    proposals = await ObserverService.get_proposals(
        db, current_user.active_org_id, status, limit
    )

    return [
        ObserverProposalResponse(
            id=str(p.id),
            findingId=str(p.finding_id) if p.finding_id else None,
            proposalType=p.proposal_type,
            title=p.title,
            description=p.description,
            expectedImpact=p.expected_impact,
            status=p.status,
            createdAt=p.created_at,
            reviewedAt=p.reviewed_at,
        )
        for p in proposals
    ]


@router.post("/proposals", response_model=ObserverProposalResponse)
async def create_proposal(
    request: ObserverProposalCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> ObserverProposalResponse:
    """Create an improvement proposal."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    proposal = await ObserverService.create_proposal_from_finding(
        db=db,
        finding_id=uuid.UUID(request.findingId),
        org_id=current_user.active_org_id,
        proposal_type=request.proposalType,
        title=request.title,
        description=request.description,
        proposed_change=request.proposedChange,
    )

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Finding not found",
        )

    return ObserverProposalResponse(
        id=str(proposal.id),
        findingId=str(proposal.finding_id) if proposal.finding_id else None,
        proposalType=proposal.proposal_type,
        title=proposal.title,
        description=proposal.description,
        expectedImpact=proposal.expected_impact,
        status=proposal.status,
        createdAt=proposal.created_at,
        reviewedAt=proposal.reviewed_at,
    )


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> dict[str, Any]:
    """Approve and activate a proposal."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    success = await ObserverService.approve_proposal(
        db, proposal_id, current_user.active_org_id, current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    return {"success": True, "message": "Proposal approved and activated"}


@router.post("/proposals/{proposal_id}/rollback")
async def rollback_proposal(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> dict[str, Any]:
    """Rollback an activated proposal."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    success = await ObserverService.rollback_proposal(
        db, proposal_id, current_user.active_org_id, current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    return {"success": True, "message": "Proposal rolled back"}


# ── Validation ───────────────────────────────────────────────────────────────────

@router.post("/proposals/{proposal_id}/validation/start")
async def start_validation(
    proposal_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> dict[str, Any]:
    """Start A/B validation for a proposal."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    validation = await ObserverService.start_validation(
        db, proposal_id, current_user.active_org_id
    )

    return {
        "validationId": str(validation.id),
        "proposalId": str(validation.proposal_id),
        "status": validation.status,
        "baselineStart": validation.baseline_start,
    }


@router.get("/validation")
async def list_validations(
    status: Optional[str] = None,
    limit: int = 50,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(require_superuser)] = None,
) -> list[dict[str, Any]]:
    """List validation runs."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    from sqlalchemy import select
    from app.models.conversation_engine import ConversationObserverValidation

    query = select(ConversationObserverValidation).where(
        ConversationObserverValidation.org_id == current_user.active_org_id
    )

    if status:
        query = query.where(ConversationObserverValidation.status == status)

    result = await db.execute(
        query.order_by(ConversationObserverValidation.created_at.desc()).limit(limit)
    )
    validations = result.scalars().all()

    return [
        {
            "id": str(v.id),
            "proposalId": str(v.proposal_id),
            "status": v.status,
            "metricsBefore": v.metrics_before,
            "metricsAfter": v.metrics_after,
            "successRate": v.success_rate,
            "recommendation": v.recommendation,
            "createdAt": v.created_at,
            "completedAt": v.completed_at,
        }
        for v in validations
    ]
