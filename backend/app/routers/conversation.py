"""Conversation API Router - Core conversation endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.conversation import (
    ConversationStartRequest,
    ConversationStartResponse,
    ConversationResponse,
    MessageRequest,
    ProcessMessageResponse,
    ProtocolResponse,
    ModeSwitchRequest,
    ModeSwitchResponse,
)
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.protocol_service import ProtocolService
from app.services.orchestrator_service import OrchestratorService
from app.services.fact_pipeline import FactPipeline

router = APIRouter(prefix="/api/v1/conversation", tags=["conversation"])


async def _get_org_id_for_user(db: AsyncSession, user: User) -> uuid.UUID | None:
    """Get the organization ID for a user from their memberships."""
    from sqlalchemy import select
    from app.models.membership import Membership

    result = await db.execute(
        select(Membership.organization_id)
        .where(Membership.user_id == user.id)
        .where(Membership.status == "active")
        .limit(1)
    )
    org_id = result.scalar_one_or_none()
    return org_id


@router.post("/start", response_model=ConversationStartResponse)
async def start_conversation(
    request: ConversationStartRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationStartResponse:
    """Start a new conversation."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    conversation = await ConversationService.start_conversation(
        db=db,
        org_id=org_id,
        user_id=current_user.id,
        request=request,
    )

    return ConversationStartResponse(
        conversationId=str(conversation.id),
        title=conversation.title or "New Conversation",
        mode=conversation.current_mode,
        status=conversation.status,
        createdAt=conversation.created_at,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConversationResponse:
    """Get conversation details."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    conversation = await ConversationService.get_conversation(
        db, conversation_id, org_id
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title,
        status=conversation.status,
        currentMode=conversation.current_mode,
        orgId=str(conversation.org_id),
        userId=str(conversation.user_id),
        createdAt=conversation.created_at,
        updatedAt=conversation.updated_at,
    )


@router.post("/{conversation_id}/message", response_model=ProcessMessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    request: MessageRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProcessMessageResponse:
    """Send a message to the conversation."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    # Verify conversation exists and belongs to user
    conversation = await ConversationService.get_conversation(
        db, conversation_id, org_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # First, save the user message
    message = await MessageService.save_message(
        db=db,
        conversation_id=conversation_id,
        org_id=org_id,
        role="user",
        content=request.message,
    )

    # Process through Fact Pipeline
    pipeline_result = await FactPipeline.process_message(
        db=db,
        message_text=request.message,
        message_id=message.id,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=current_user.id,
        mode=conversation.current_mode,
    )

    # Process through orchestrator for response generation
    result = await OrchestratorService.process_message(
        db=db,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=current_user.id,
        message_text=request.message,
    )

    # Add fact extraction results to response
    result["factsExtracted"] = [
        {
            "factId": str(f.id),
            "category": f.category,
            "value": f.value,
            "confidence": f.confidence,
            "status": f.status,
        }
        for f in pipeline_result.facts_extracted
    ]
    result["factsUpdated"] = [
        {
            "factId": str(f.id),
            "category": f.category,
            "value": f.value,
            "confidence": f.confidence,
            "status": f.status,
        }
        for f in pipeline_result.facts_updated
    ]
    result["conflicts"] = pipeline_result.conflicts
    result["unmapped"] = pipeline_result.unmapped

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return ProcessMessageResponse(**result)


@router.get("/{conversation_id}/protocol", response_model=list[ProtocolResponse])
async def get_protocol(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ProtocolResponse]:
    """Get conversation protocol."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    # Verify conversation exists
    conversation = await ConversationService.get_conversation(
        db, conversation_id, org_id
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    protocol_data = await ProtocolService.get_protocol(
        db, conversation_id, org_id
    )

    return [
        ProtocolResponse(
            areaId=p["area_id"],
            key=p["key"],
            displayName=p["display_name"],
            description=p.get("description"),
            helpText=p.get("help_text"),
            isRequired=p["is_required"],
            sortOrder=p["sort_order"],
            status=p["status"],
            entries=p["entries"],
        )
        for p in protocol_data
    ]


@router.post("/{conversation_id}/switch-mode", response_model=ModeSwitchResponse)
async def switch_mode(
    conversation_id: uuid.UUID,
    request: ModeSwitchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ModeSwitchResponse:
    """Switch conversation mode."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    result = await OrchestratorService.switch_mode(
        db=db,
        conversation_id=conversation_id,
        org_id=org_id,
        user_id=current_user.id,
        new_mode=request.mode,
    )

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return ModeSwitchResponse(**result)


@router.get("/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Get conversation messages."""
    org_id = await _get_org_id_for_user(db, current_user)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active organization",
        )

    messages = await MessageService.get_messages(
        db, conversation_id, org_id, limit, offset
    )

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "createdAt": m.created_at,
        }
        for m in messages
    ]
