"""Story API Router - Story generation and evaluation endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.conversation import (
    StructureProposalResponse,
    StructureProposalAcceptRequest,
    EvaluateReadinessResponse,
)
from app.services.conversation_service import ConversationService
from app.services.structure_service import StructureService
from app.services.readiness_service import ReadinessService

router = APIRouter(prefix="/api/v1/conversation/{conversation_id}/story", tags=["story"])


@router.post("/structure-proposal", response_model=StructureProposalResponse)
async def create_structure_proposal(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StructureProposalResponse:
    """Create a structure proposal for the conversation."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    # Verify conversation exists
    conversation = await ConversationService.get_conversation(
        db, conversation_id, current_user.active_org_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    result = await StructureService.analyze_and_propose(
        db=db,
        conversation_id=conversation_id,
        org_id=current_user.active_org_id,
        user_id=current_user.id,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return StructureProposalResponse(**result)


@router.post("/structure-proposal/accept")
async def accept_structure_proposal(
    conversation_id: uuid.UUID,
    request: StructureProposalAcceptRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Accept a structure proposal."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    success = await StructureService.accept_proposal(
        db=db,
        proposal_id=uuid.UUID(request.proposalId),
        org_id=current_user.active_org_id,
        user_id=current_user.id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Proposal not found",
        )

    return {"success": True, "message": "Proposal accepted"}


@router.post("/generate")
async def generate_story(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Generate a story from the conversation."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    # Get protocol for story generation
    from app.services.protocol_service import ProtocolService
    from app.services.fact_service import FactService

    protocol = await ProtocolService.get_protocol(
        db, conversation_id, current_user.active_org_id
    )

    # Build story from protocol entries
    story_data = {
        "storyTitle": "User Story",
        "storyDescription": "",
        "acceptanceCriteria": [],
        "userGroup": None,
        "businessValue": None,
    }

    for area in protocol:
        if area["entries"]:
            entry = area["entries"][0]  # Take first entry

            if area["key"] == "target_user":
                story_data["userGroup"] = entry["value"]
            elif area["key"] == "desired_outcome":
                story_data["storyDescription"] = entry["value"]
            elif area["key"] == "acceptance_criteria":
                story_data["acceptanceCriteria"].append(entry["value"])
            elif area["key"] == "business_value":
                story_data["businessValue"] = entry["value"]

    # Build title
    if story_data["userGroup"]:
        story_data["storyTitle"] = f"{story_data['userGroup']}: {story_data['storyDescription'][:50]}"
    else:
        story_data["storyTitle"] = story_data["storyDescription"][:50] or "User Story"

    return story_data


@router.get("/readiness", response_model=EvaluateReadinessResponse)
async def evaluate_readiness(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EvaluateReadinessResponse:
    """Evaluate story readiness."""
    if not current_user.active_org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    # Verify conversation exists
    conversation = await ConversationService.get_conversation(
        db, conversation_id, current_user.active_org_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Evaluate readiness
    readiness_data = await ReadinessService.evaluate_readiness(
        db, conversation_id, current_user.active_org_id
    )

    return EvaluateReadinessResponse(
        status=readiness_data["status"],
        score=readiness_data["score"],
        maxScore=readiness_data["max_score"],
        percentage=readiness_data["percentage"],
        recommendation=readiness_data["recommendation"],
        findings=readiness_data["findings"],
        missingFields=readiness_data["missing_fields"],
    )
