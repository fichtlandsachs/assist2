"""Story Sizing Service - Calculates story size based on rules."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationStorySizingResult,
    StorySizingRule,
    ConversationFact,
)


class StorySizingService:
    """Service for calculating story size and recommendations."""

    # Size thresholds
    SIZE_LABELS = {
        (0, 25): "XS",
        (25, 50): "S",
        (50, 75): "M",
        (75, 100): "L",
        (100, float('inf')): "XL",
    }

    @staticmethod
    async def get_active_rules(
        db: AsyncSession,
    ) -> list[StorySizingRule]:
        """Get all active sizing rules."""
        result = await db.execute(
            select(StorySizingRule).where(StorySizingRule.is_active == True)
        )
        return list(result.scalars().all())

    @staticmethod
    def get_size_label(score: int) -> str:
        """Get size label for a score."""
        for (min_val, max_val), label in StorySizingService.SIZE_LABELS.items():
            if min_val <= score < max_val:
                return label
        return "XL"

    @staticmethod
    async def calculate_size(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Calculate story size for a conversation."""
        # Get active rules
        rules = await StorySizingService.get_active_rules(db)

        # Get facts for this conversation
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.org_id == org_id,
                ConversationFact.status.in_(["detected", "confirmed"]),
                ConversationFact.deleted_at.is_(None),
            )
        )
        facts = result.scalars().all()

        # Analyze facts
        detected_functions = set()
        detected_systems = set()
        detected_user_groups = set()
        acceptance_criteria_count = 0

        for fact in facts:
            if fact.category == "acceptance_criteria":
                acceptance_criteria_count += 1
            elif fact.category == "target_user":
                detected_user_groups.add(fact.normalized_value or fact.value)
            # Functions and systems would be extracted from fact content

        # Calculate score based on rules
        total_score = 0
        triggered_rules = []

        for rule in rules:
            triggered = False
            rule_score = 0

            if rule.dimension == "user_groups" and len(detected_user_groups) >= 2:
                triggered = True
                rule_score = rule.weight
            elif rule.dimension == "functions" and len(detected_functions) >= 2:
                triggered = True
                rule_score = rule.weight
            elif rule.dimension == "systems" and len(detected_systems) >= 2:
                triggered = True
                rule_score = rule.weight
            elif rule.dimension == "acceptance_criteria" and acceptance_criteria_count >= 7:
                triggered = True
                rule_score = rule.weight

            if triggered:
                total_score += rule_score
                triggered_rules.append({
                    "rule_id": str(rule.id),
                    "key": rule.key,
                    "label": rule.label,
                    "weight": rule.weight,
                })

        # Cap score at 150
        total_score = min(total_score, 150)

        # Determine size label
        size_label = StorySizingService.get_size_label(total_score)

        # Recommend story count
        recommended_count = 1
        if total_score > 80:
            recommended_count = 3
        elif total_score > 50:
            recommended_count = 2

        # Build recommendation text
        if recommended_count > 1:
            recommendation = (
                f"Die Story ist mit einem Score von {total_score} ({size_label}) "
                f"relativ groß. Ich empfehle eine Aufteilung in {recommended_count} Stories."
            )
        else:
            recommendation = (
                f"Die Story hat einen Score von {total_score} ({size_label}) "
                f"und ist gut proportioniert."
            )

        return {
            "score": total_score,
            "label": size_label,
            "recommended_story_count": recommended_count,
            "recommendation": recommendation,
            "triggered_rules": triggered_rules,
            "detected_data": {
                "user_groups_count": len(detected_user_groups),
                "functions_count": len(detected_functions),
                "systems_count": len(detected_systems),
                "acceptance_criteria_count": acceptance_criteria_count,
            },
        }

    @staticmethod
    async def save_result(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        sizing_data: dict[str, Any],
    ) -> ConversationStorySizingResult:
        """Save sizing result to database."""
        result = ConversationStorySizingResult(
            conversation_id=conversation_id,
            org_id=org_id,
            size_score=sizing_data["score"],
            size_label=sizing_data["label"],
            recommended_story_count=sizing_data["recommended_story_count"],
            recommendation=sizing_data["recommendation"],
            detected_user_groups=[],
            detected_functions=[],
            detected_systems=[],
            detected_subtopics=[],
            reason=sizing_data["recommendation"],
            data_json={
                "triggered_rules": sizing_data["triggered_rules"],
                "detected_data": sizing_data["detected_data"],
            },
        )
        db.add(result)
        await db.flush()
        return result
