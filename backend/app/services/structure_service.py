"""Structure Service - Proposes story structure from exploration."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationStructureProposal,
    Conversation,
    ConversationState,
)
from app.services.story_sizing_service import StorySizingService


class StructureService:
    """Service for proposing story structures."""

    @staticmethod
    async def analyze_and_propose(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Analyze conversation and propose structure."""
        # Get conversation and state
        result = await db.execute(
            select(Conversation, ConversationState)
            .join(ConversationState, Conversation.id == ConversationState.conversation_id)
            .where(
                Conversation.id == conversation_id,
                Conversation.org_id == org_id,
            )
        )
        row = result.one_or_none()

        if not row:
            return {"error": "Conversation not found"}

        conversation, state = row

        # Calculate sizing
        sizing = await StorySizingService.calculate_size(db, conversation_id, org_id)

        # Determine proposal
        recommended_type = "story"
        story_count = 1

        if sizing["score"] > 80:
            recommended_type = "epic"
            story_count = sizing["recommended_story_count"]

        # Build items
        items = []
        if story_count > 1:
            for i in range(story_count):
                items.append({
                    "type": "story",
                    "title": f"Story {i + 1}",
                    "description": f"Teil {i + 1} der Epic",
                })
        else:
            items.append({
                "type": "story",
                "title": conversation.title or "User Story",
                "description": "Hauptstory",
            })

        # Create proposal
        proposal = ConversationStructureProposal(
            conversation_id=conversation_id,
            org_id=org_id,
            source_mode=conversation.current_mode,
            target_mode="story",
            recommended_artifact_type=recommended_type,
            story_size_score=sizing["score"],
            recommended_story_count=story_count,
            reason=sizing["recommendation"],
            items=items,
            created_by=user_id,
            status="draft",
        )
        db.add(proposal)
        await db.flush()

        return {
            "proposal_id": str(proposal.id),
            "recommended_type": recommended_type,
            "story_count": story_count,
            "size_score": sizing["score"],
            "size_label": sizing["label"],
            "reason": sizing["recommendation"],
            "items": items,
        }

    @staticmethod
    async def accept_proposal(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Accept a structure proposal."""
        result = await db.execute(
            select(ConversationStructureProposal).where(
                ConversationStructureProposal.id == proposal_id,
                ConversationStructureProposal.org_id == org_id,
            )
        )
        proposal = result.scalar_one_or_none()

        if not proposal:
            return False

        proposal.status = "accepted"
        proposal.accepted_by = user_id
        from datetime import datetime, timezone
        proposal.accepted_at = datetime.now(timezone.utc)
        proposal.updated_at = datetime.now(timezone.utc)

        await db.flush()
        return True
