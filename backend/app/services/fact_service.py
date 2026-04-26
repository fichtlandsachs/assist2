"""Fact Service - Handles fact extraction and management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationFact,
    AnswerSignal,
)


class FactService:
    """Service for extracting and managing facts."""

    @staticmethod
    async def create_fact(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        category: str,
        value: str,
        confidence: float = 0.7,
        source_message_id: Optional[uuid.UUID] = None,
        normalized_value: Optional[str] = None,
    ) -> ConversationFact:
        """Create a new fact."""
        fact = ConversationFact(
            conversation_id=conversation_id,
            org_id=org_id,
            category=category,
            value=value,
            normalized_value=normalized_value or value.lower().strip(),
            confidence=confidence,
            source_message_id=source_message_id,
            status="detected",
        )
        db.add(fact)
        await db.flush()
        return fact

    @staticmethod
    async def get_facts(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[ConversationFact]:
        """Get facts for a conversation."""
        query = select(ConversationFact).where(
            ConversationFact.conversation_id == conversation_id,
            ConversationFact.org_id == org_id,
            ConversationFact.deleted_at.is_(None),
        )

        if category:
            query = query.where(ConversationFact.category == category)
        if status:
            query = query.where(ConversationFact.status == status)

        result = await db.execute(query.order_by(ConversationFact.created_at.desc()))
        return list(result.scalars().all())

    @staticmethod
    async def confirm_fact(
        db: AsyncSession,
        fact_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Optional[ConversationFact]:
        """Confirm a fact."""
        result = await db.execute(
            select(ConversationFact).where(ConversationFact.id == fact_id)
        )
        fact = result.scalar_one_or_none()

        if fact:
            fact.status = "confirmed"
            fact.confirmed_by = user_id
            fact.confirmed_at = datetime.now(timezone.utc)
            fact.updated_at = datetime.now(timezone.utc)
            await db.flush()

        return fact

    @staticmethod
    async def reject_fact(
        db: AsyncSession,
        fact_id: uuid.UUID,
    ) -> Optional[ConversationFact]:
        """Reject a fact."""
        result = await db.execute(
            select(ConversationFact).where(ConversationFact.id == fact_id)
        )
        fact = result.scalar_one_or_none()

        if fact:
            fact.status = "rejected"
            fact.updated_at = datetime.now(timezone.utc)
            await db.flush()

        return fact

    @staticmethod
    async def get_active_signals(
        db: AsyncSession,
    ) -> list[AnswerSignal]:
        """Get all active answer signals for pattern matching."""
        result = await db.execute(
            select(AnswerSignal).where(AnswerSignal.is_active == True)
        )
        return list(result.scalars().all())

    @staticmethod
    async def match_patterns(
        text: str,
        signals: list[AnswerSignal],
    ) -> list[dict]:
        """Match text against answer signal patterns."""
        import re

        matches = []
        text_lower = text.lower()

        for signal in signals:
            if signal.pattern_type == "keyword":
                # Simple keyword matching
                keywords = signal.pattern.split("|")
                for keyword in keywords:
                    if keyword.lower().strip() in text_lower:
                        matches.append({
                            "signal_id": signal.id,
                            "category": signal.fact_category,
                            "matched_keyword": keyword.strip(),
                            "confidence_boost": signal.confidence_boost,
                        })
                        break
            elif signal.pattern_type == "regex":
                # Regex pattern matching
                try:
                    if re.search(signal.pattern, text, re.IGNORECASE):
                        matches.append({
                            "signal_id": signal.id,
                            "category": signal.fact_category,
                            "matched_pattern": signal.pattern,
                            "confidence_boost": signal.confidence_boost,
                        })
                except re.error:
                    continue

        return matches

    @staticmethod
    async def extract_facts_from_text(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        text: str,
        source_message_id: Optional[uuid.UUID] = None,
    ) -> list[ConversationFact]:
        """Extract facts from text using pattern matching."""
        signals = await FactService.get_active_signals(db)
        matches = await FactService.match_patterns(text, signals)

        created_facts = []
        for match in matches:
            # Check if similar fact already exists
            existing = await db.execute(
                select(ConversationFact).where(
                    ConversationFact.conversation_id == conversation_id,
                    ConversationFact.category == match["category"],
                    ConversationFact.status.in_(["detected", "confirmed"]),
                )
            )

            if existing.scalar_one_or_none():
                continue  # Skip if already exists

            fact = await FactService.create_fact(
                db=db,
                conversation_id=conversation_id,
                org_id=org_id,
                category=match["category"],
                value=text[:200],  # Truncate for storage
                confidence=min(0.7 + match.get("confidence_boost", 0), 1.0),
                source_message_id=source_message_id,
            )
            created_facts.append(fact)

        return created_facts
