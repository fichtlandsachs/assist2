"""Question Planner Service - Plans next questions based on missing information."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    QuestionBlock,
    ConversationState,
    ConversationFact,
)


class QuestionPlannerService:
    """Service for planning conversation questions."""

    # Required categories in priority order
    REQUIRED_CATEGORIES = [
        "target_user",
        "problem",
        "desired_outcome",
        "business_value",
        "scope",
        "acceptance_criteria",
    ]

    @staticmethod
    async def get_active_question_blocks(
        db: AsyncSession,
    ) -> list[QuestionBlock]:
        """Get all active question blocks."""
        result = await db.execute(
            select(QuestionBlock)
            .where(QuestionBlock.is_active == True)
            .order_by(QuestionBlock.priority)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_asked_questions(
        db: AsyncSession,
        conversation_id: uuid.UUID,
    ) -> set[str]:
        """Get set of already asked question keys."""
        result = await db.execute(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation_id
            )
        )
        state = result.scalar_one_or_none()

        if state and state.next_questions:
            return set(state.next_questions)
        return set()

    @staticmethod
    async def identify_missing_categories(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[str]:
        """Identify which required categories are missing."""
        # Get confirmed facts
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.org_id == org_id,
                ConversationFact.status.in_(["detected", "confirmed"]),
                ConversationFact.deleted_at.is_(None),
            )
        )
        existing_categories = {f.category for f in result.scalars().all()}

        # Find missing required categories
        missing = [
            cat for cat in QuestionPlannerService.REQUIRED_CATEGORIES
            if cat not in existing_categories
        ]

        return missing

    @staticmethod
    async def plan_questions(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        max_questions: int = 3,
    ) -> list[dict[str, Any]]:
        """Plan next questions for the conversation."""
        # Get missing categories
        missing_categories = await QuestionPlannerService.identify_missing_categories(
            db, conversation_id, org_id
        )

        if not missing_categories:
            return []

        # Get question blocks for missing categories
        blocks = await QuestionPlannerService.get_active_question_blocks(db)

        planned_questions = []
        for category in missing_categories[:max_questions]:
            # Find question block for this category
            matching_blocks = [
                b for b in blocks
                if b.category == category and b.is_required
            ]

            if matching_blocks:
                block = matching_blocks[0]
                planned_questions.append({
                    "category": block.category,
                    "question": block.question_text,
                    "label": block.label,
                    "priority": block.priority,
                    "follow_up": block.follow_up_text,
                    "reason": f"Fehlende Information: {block.category}",
                })

        return planned_questions

    @staticmethod
    async def update_state_questions(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        questions: list[dict[str, Any]],
    ) -> None:
        """Update state with planned questions."""
        result = await db.execute(
            select(ConversationState).where(
                ConversationState.conversation_id == conversation_id
            )
        )
        state = result.scalar_one_or_none()

        if state:
            # Track which question categories are being asked
            asked_categories = [q["category"] for q in questions]
            current_next = state.next_questions or []
            state.next_questions = current_next + asked_categories
            await db.flush()
