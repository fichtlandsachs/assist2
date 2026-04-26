"""Conversation Service - Core conversation management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    Conversation,
    ConversationState,
    ConversationProtocolArea,
)
from app.schemas.conversation import ConversationStartRequest, ConversationResponse


class ConversationService:
    """Service for managing conversation lifecycle."""

    @staticmethod
    async def start_conversation(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConversationStartRequest,
    ) -> Conversation:
        """Start a new conversation."""
        # Create conversation
        conversation = Conversation(
            org_id=org_id,
            user_id=user_id,
            title=request.title or "New Conversation",
            status="active",
            current_mode=request.mode or "exploration",
        )
        db.add(conversation)
        await db.flush()

        # Create initial state
        state = ConversationState(
            conversation_id=conversation.id,
            org_id=org_id,
            mode=request.mode or "exploration",
            context_status="unassigned",
        )
        db.add(state)
        await db.commit()

        return conversation

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> Optional[Conversation]:
        """Get conversation by ID with org validation."""
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.org_id == org_id,
                Conversation.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_conversation_with_state(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> tuple[Optional[Conversation], Optional[ConversationState]]:
        """Get conversation and its state."""
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.org_id == org_id,
                Conversation.deleted_at.is_(None),
            )
        )
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            return None, None

        state_result = await db.execute(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation_id,
            )
        )
        state = state_result.scalar_one_or_none()

        return conversation, state

    @staticmethod
    async def switch_mode(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        new_mode: str,
    ) -> Optional[ConversationState]:
        """Switch conversation mode."""
        # Validate conversation exists and belongs to org
        conversation = await ConversationService.get_conversation(
            db, conversation_id, org_id
        )
        if not conversation:
            return None

        # Update conversation mode
        conversation.current_mode = new_mode
        conversation.updated_at = datetime.now(timezone.utc)

        # Update or create state
        result = await db.execute(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation_id,
            )
        )
        state = result.scalar_one_or_none()

        if state:
            state.mode = new_mode
            state.updated_at = datetime.now(timezone.utc)
        else:
            state = ConversationState(
                conversation_id=conversation_id,
                org_id=org_id,
                mode=new_mode,
            )
            db.add(state)

        await db.commit()
        return state

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Conversation]:
        """List conversations for org/user."""
        query = select(Conversation).where(
            Conversation.org_id == org_id,
            Conversation.deleted_at.is_(None),
        )

        if user_id:
            query = query.where(Conversation.user_id == user_id)
        if status:
            query = query.where(Conversation.status == status)

        query = query.order_by(Conversation.created_at.desc()).limit(limit).offset(offset)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def close_conversation(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> bool:
        """Close/archived a conversation."""
        conversation = await ConversationService.get_conversation(
            db, conversation_id, org_id
        )
        if not conversation:
            return False

        conversation.status = "closed"
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True
