"""Fact Deduplicator - Detects and handles duplicate facts."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationFact
from app.services.fact_normalizer import FactNormalizer


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    existing_fact: Optional[ConversationFact]
    should_update: bool
    action: str  # "create", "update", "skip"
    reason: str


class FactDeduplicator:
    """Detects and handles duplicate facts within a conversation."""

    SIMILARITY_THRESHOLD = 0.8

    @staticmethod
    async def find_similar_facts(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        category: str,
        normalized_value: str,
        exclude_fact_id: Optional[uuid.UUID] = None,
    ) -> list[ConversationFact]:
        """Find existing facts that might be duplicates."""
        query = select(ConversationFact).where(
            ConversationFact.conversation_id == conversation_id,
            ConversationFact.category == category,
            ConversationFact.deleted_at.is_(None),
        )

        if exclude_fact_id:
            query = query.where(ConversationFact.id != exclude_fact_id)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def calculate_similarity(
        value1: str,
        value2: str,
        category: str,
    ) -> float:
        """Calculate similarity between two fact values."""
        return FactNormalizer.calculate_similarity(value1, value2, category)

    @staticmethod
    async def check_duplicate(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        category: str,
        value: str,
        normalized_value: str,
        confidence: float,
        exclude_fact_id: Optional[uuid.UUID] = None,
    ) -> DeduplicationResult:
        """Check if a fact would be a duplicate."""
        existing_facts = await FactDeduplicator.find_similar_facts(
            db, conversation_id, category, normalized_value, exclude_fact_id
        )

        if not existing_facts:
            return DeduplicationResult(
                is_duplicate=False,
                existing_fact=None,
                should_update=False,
                action="create",
                reason="No existing facts in this category",
            )

        # Find most similar fact
        best_match = None
        best_similarity = 0.0

        for fact in existing_facts:
            similarity = FactDeduplicator.calculate_similarity(
                value, fact.value, category
            )
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = fact

        # Check if it's a duplicate based on similarity
        if best_similarity >= FactDeduplicator.SIMILARITY_THRESHOLD:
            # Check if new confidence is higher
            should_update = confidence > best_match.confidence

            return DeduplicationResult(
                is_duplicate=True,
                existing_fact=best_match,
                should_update=should_update,
                action="update" if should_update else "skip",
                reason=f"Duplicate detected (similarity: {best_similarity:.2f})" +
                       (", new confidence higher" if should_update else ", keeping existing"),
            )

        # Similar but not duplicate - might be a conflict
        if best_similarity >= 0.5:
            return DeduplicationResult(
                is_duplicate=False,
                existing_fact=best_match,
                should_update=False,
                action="create",
                reason=f"Similar but distinct (similarity: {best_similarity:.2f}), potential conflict",
            )

        return DeduplicationResult(
            is_duplicate=False,
            existing_fact=None,
            should_update=False,
            action="create",
            reason="Different fact in same category",
        )

    @staticmethod
    async def handle_duplicate(
        db: AsyncSession,
        candidate: "CandidateFact",
        dedup_result: DeduplicationResult,
    ) -> Optional[ConversationFact]:
        """Handle a fact based on deduplication result."""
        from datetime import datetime, timezone

        if dedup_result.action == "skip":
            # Don't create, just return existing
            return dedup_result.existing_fact

        if dedup_result.action == "update":
            # Update existing fact with new evidence
            existing = dedup_result.existing_fact
            existing.confidence = candidate.confidence
            existing.value = candidate.value  # Keep latest formulation
            existing.normalized_value = candidate.normalized_value

            # Append to used_in if message_id not already there
            if candidate.source_message_id:
                current_used = existing.used_in or []
                if str(candidate.source_message_id) not in current_used:
                    current_used.append(str(candidate.source_message_id))
                    existing.used_in = current_used

            existing.updated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing

        if dedup_result.action == "create":
            # Create new fact
            fact = ConversationFact(
                conversation_id=candidate.source_message_id,  # Will be updated
                org_id=candidate.source_message_id,  # Will be updated
                category=candidate.category,
                value=candidate.value,
                normalized_value=candidate.normalized_value,
                confidence=candidate.confidence,
                source_message_id=candidate.source_message_id,
                status="detected",  # Will be updated by status assignment
                used_in=[str(candidate.source_message_id)] if candidate.source_message_id else [],
            )
            db.add(fact)
            await db.flush()
            return fact

        return None

    @staticmethod
    async def detect_conflicts(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        new_fact: ConversationFact,
    ) -> list[ConversationFact]:
        """Detect conflicting facts with the new fact."""
        # Find facts in same category with different normalized value
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.category == new_fact.category,
                ConversationFact.id != new_fact.id,
                ConversationFact.deleted_at.is_(None),
                ConversationFact.status.in_(["detected", "suggested", "confirmed"]),
            )
        )
        existing = list(result.scalars().all())

        conflicts = []
        for fact in existing:
            # Check if values are different but similar (potential conflict)
            similarity = FactDeduplicator.calculate_similarity(
                new_fact.value, fact.value, new_fact.category
            )
            if 0.3 <= similarity < 0.8:
                conflicts.append(fact)

        return conflicts
