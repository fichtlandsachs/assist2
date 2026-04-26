"""Fact Reuse Detector - Detects reusable facts to avoid duplicate questions."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationFact


@dataclass
class ReuseCheckResult:
    """Result of fact reuse check."""
    has_usable_fact: bool
    existing_fact: Optional[ConversationFact]
    confidence_sufficient: bool
    needs_confirmation: bool
    can_reuse: bool
    message: str


class FactReuseDetector:
    """Detects when facts can be reused instead of asking again."""

    # Confidence thresholds
    MIN_CONFIDENCE_FOR_REUSE = 0.75
    MIN_CONFIDENCE_FOR_CONFIRMED = 0.85

    @staticmethod
    async def find_fact_for_category(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        category: str,
    ) -> Optional[ConversationFact]:
        """Find the best fact for a given category."""
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.category == category,
                ConversationFact.deleted_at.is_(None),
                ConversationFact.status.in_(["detected", "suggested", "confirmed"]),
            ).order_by(ConversationFact.confidence.desc())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def check_reusable_facts(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        categories: list[str],
    ) -> dict[str, ReuseCheckResult]:
        """Check which categories have reusable facts."""
        results = {}

        for category in categories:
            fact = await FactReuseDetector.find_fact_for_category(
                db, conversation_id, category
            )

            if fact:
                # Check confidence
                confidence_sufficient = fact.confidence >= FactReuseDetector.MIN_CONFIDENCE_FOR_REUSE
                needs_confirmation = fact.confidence < FactReuseDetector.MIN_CONFIDENCE_FOR_CONFIRMED
                can_reuse = fact.status == "confirmed" or (
                    fact.status in ["detected", "suggested"] and confidence_sufficient
                )

                # Generate message
                if can_reuse:
                    if fact.status == "confirmed":
                        message = f"Du hattest bereits gesagt, dass {fact.normalized_value or fact.value}."
                    else:
                        message = f"Ich habe mir gemerkt, dass {fact.normalized_value or fact.value} (vorläufig)."
                else:
                    message = f"Ich habe einen Hinweis auf {fact.normalized_value or fact.value}, aber die Confidence ist noch niedrig."

                results[category] = ReuseCheckResult(
                    has_usable_fact=True,
                    existing_fact=fact,
                    confidence_sufficient=confidence_sufficient,
                    needs_confirmation=needs_confirmation,
                    can_reuse=can_reuse,
                    message=message,
                )
            else:
                results[category] = ReuseCheckResult(
                    has_usable_fact=False,
                    existing_fact=None,
                    confidence_sufficient=False,
                    needs_confirmation=True,
                    can_reuse=False,
                    message="",
                )

        return results

    @staticmethod
    def should_ask_for_category(
        reuse_result: ReuseCheckResult,
        category: str,
    ) -> bool:
        """Determine if we should ask for this category."""
        if not reuse_result.has_usable_fact:
            return True

        if reuse_result.can_reuse:
            return False

        # Has fact but not confident enough
        return reuse_result.needs_confirmation

    @staticmethod
    async def get_reuse_message(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        category: str,
    ) -> Optional[str]:
        """Get the reuse message for a category if applicable."""
        fact = await FactReuseDetector.find_fact_for_category(
            db, conversation_id, category
        )

        if not fact:
            return None

        # Only return message if we can reuse
        if fact.status == "confirmed":
            return f"Du hattest bereits gesagt, dass {fact.normalized_value or fact.value}."

        if fact.confidence >= FactReuseDetector.MIN_CONFIDENCE_FOR_REUSE:
            return f"Ich habe mir gemerkt, dass {fact.normalized_value or fact.value}. Ich übernehme das vorläufig."

        return None

    @staticmethod
    async def get_categories_to_ask(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        required_categories: list[str],
    ) -> list[str]:
        """Get list of categories that still need to be asked."""
        categories_to_ask = []

        reuse_results = await FactReuseDetector.check_reusable_facts(
            db, conversation_id, required_categories
        )

        for category, result in reuse_results.items():
            if FactReuseDetector.should_ask_for_category(result, category):
                categories_to_ask.append(category)

        return categories_to_ask

    @staticmethod
    async def mark_fact_used(
        db: AsyncSession,
        fact_id: uuid.UUID,
        context: str,
    ) -> None:
        """Mark a fact as used in a specific context."""
        from datetime import datetime, timezone

        fact = await db.get(ConversationFact, fact_id)
        if fact:
            current_used = fact.used_in or []
            if context not in current_used:
                current_used.append(context)
                fact.used_in = current_used
                fact.updated_at = datetime.now(timezone.utc)
                await db.flush()
