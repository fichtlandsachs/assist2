"""Message Service - Handles conversation messages and token tracking."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationMessage


class MessageService:
    """Service for managing conversation messages."""

    @staticmethod
    async def save_message(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        role: str,
        content: str,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        token_input: int = 0,
        token_output: int = 0,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ConversationMessage:
        """Save a message to the conversation."""
        message = ConversationMessage(
            conversation_id=conversation_id,
            org_id=org_id,
            role=role,
            content=content,
            intent=intent,
            confidence=confidence,
            token_input=token_input,
            token_output=token_output,
            token_total=token_input + token_output,
            model_name=model_name,
            provider=provider,
        )
        db.add(message)
        await db.flush()
        return message

    @staticmethod
    async def get_messages(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ConversationMessage]:
        """Get messages for a conversation."""
        result = await db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.org_id == org_id,
            )
            .order_by(ConversationMessage.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_message_count(
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> int:
        """Get total message count for conversation."""
        from sqlalchemy import func
        result = await db.execute(
            select(func.count(ConversationMessage.id))
            .where(ConversationMessage.conversation_id == conversation_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_total_tokens(
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> dict[str, int]:
        """Get total tokens used in conversation."""
        from sqlalchemy import func
        result = await db.execute(
            select(
                func.sum(ConversationMessage.token_input),
                func.sum(ConversationMessage.token_output),
                func.sum(ConversationMessage.token_total),
            )
            .where(ConversationMessage.conversation_id == conversation_id)
        )
        row = result.one()
        return {
            "input": row[0] or 0,
            "output": row[1] or 0,
            "total": row[2] or 0,
        }
