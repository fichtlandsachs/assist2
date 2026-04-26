"""Protocol Mapper - Maps facts to protocol areas and calculates status."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationFact, ConversationProtocolArea


@dataclass
class ProtocolEntry:
    """A protocol entry for display."""
    fact_id: str
    value: str
    confidence: float
    status: str
    source_message_id: Optional[str]


@dataclass
class ProtocolArea:
    """A protocol area with its status."""
    area_key: str
    display_name: str
    description: Optional[str]
    help_text: Optional[str]
    is_required: bool
    sort_order: int
    status: str  # empty, incomplete, complete_candidate, needs_review
    facts_count: int
    entries: list[ProtocolEntry]


class ProtocolMapper:
    """Maps facts to protocol areas and calculates completion status."""

    # Category to protocol area mapping
    CATEGORY_TO_AREA = {
        "target_user": "target_user",
        "target_users": "target_user",
        "problem": "problem",
        "desired_outcome": "desired_outcome",
        "business_value": "business_value",
        "scope": "scope",
        "out_of_scope": "out_of_scope",
        "acceptance_criteria": "acceptance_criteria",
        "acceptance_criterion": "acceptance_criteria",
        "dependency": "dependencies",
        "dependencies": "dependencies",
        "risk": "risks",
        "risks": "risks",
        "evidence": "evidence",
        "affected_system": "affected_systems",
        "affected_systems": "affected_systems",
        "business_capability": "business_capabilities",
        "business_capabilities": "business_capabilities",
        "process_context": "process_context",
        "project_context": "project_context",
        "epic_context": "epic_context",
    }

    # Status thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.60

    @staticmethod
    def get_protocol_area_key(category: str) -> str:
        """Get protocol area key from fact category."""
        return ProtocolMapper.CATEGORY_TO_AREA.get(category, category)

    @staticmethod
    async def load_protocol_areas(
        db: AsyncSession,
        org_id: Optional[uuid.UUID] = None,
    ) -> list[ConversationProtocolArea]:
        """Load all active protocol areas."""
        query = select(ConversationProtocolArea).where(
            ConversationProtocolArea.is_active == True
        )

        if org_id:
            query = query.where(
                (ConversationProtocolArea.org_id == org_id) |
                (ConversationProtocolArea.org_id.is_(None))
            )

        query = query.order_by(ConversationProtocolArea.sort_order)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def calculate_fact_status(confidence: float) -> str:
        """Calculate status for a single fact."""
        if confidence >= ProtocolMapper.HIGH_CONFIDENCE_THRESHOLD:
            return "suggested"
        return "detected"

    @staticmethod
    def calculate_area_status(
        entries: list[ProtocolEntry],
        is_required: bool,
    ) -> str:
        """Calculate overall status for a protocol area."""
        if not entries:
            return "empty" if is_required else "complete"

        # Check for conflicts
        has_conflict = any(e.status == "needs_review" for e in entries)
        if has_conflict:
            return "needs_review"

        # Check for high confidence entries
        high_confidence = [e for e in entries if e.confidence >= ProtocolMapper.HIGH_CONFIDENCE_THRESHOLD]
        if high_confidence:
            return "complete_candidate"

        # Check for medium confidence
        medium_confidence = [e for e in entries if e.confidence >= ProtocolMapper.MEDIUM_CONFIDENCE_THRESHOLD]
        if medium_confidence:
            return "incomplete"

        # Low confidence only
        return "incomplete"

    @staticmethod
    async def map_facts_to_protocol(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: Optional[uuid.UUID] = None,
    ) -> list[ProtocolArea]:
        """Map all facts to protocol areas."""
        # Load protocol areas
        areas = await ProtocolMapper.load_protocol_areas(db, org_id)

        # Load facts
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.deleted_at.is_(None),
                ConversationFact.status.in_(["detected", "suggested", "confirmed"]),
            )
        )
        facts = list(result.scalars().all())

        # Group facts by protocol area
        area_facts: dict[str, list[ConversationFact]] = {}
        for fact in facts:
            area_key = ProtocolMapper.get_protocol_area_key(fact.category)
            if area_key not in area_facts:
                area_facts[area_key] = []
            area_facts[area_key].append(fact)

        # Build protocol areas
        protocol = []
        for area in areas:
            area_key = area.key
            facts_in_area = area_facts.get(area_key, [])

            entries = [
                ProtocolEntry(
                    fact_id=str(fact.id),
                    value=fact.value,
                    confidence=fact.confidence,
                    status=fact.status,
                    source_message_id=str(fact.source_message_id) if fact.source_message_id else None,
                )
                for fact in facts_in_area
            ]

            status = ProtocolMapper.calculate_area_status(entries, area.is_required)

            protocol.append(ProtocolArea(
                area_key=area_key,
                display_name=area.display_name,
                description=area.description,
                help_text=area.help_text,
                is_required=area.is_required,
                sort_order=area.sort_order,
                status=status,
                facts_count=len(entries),
                entries=entries,
            ))

        return protocol

    @staticmethod
    async def update_protocol_entry_status(
        db: AsyncSession,
        fact: ConversationFact,
    ) -> None:
        """Update status when a fact changes."""
        # The status is calculated dynamically in map_facts_to_protocol
        # This method can be used for side effects if needed
        pass

    @staticmethod
    def get_protocol_completion_summary(
        protocol: list[ProtocolArea],
    ) -> dict:
        """Get a summary of protocol completion."""
        total = len(protocol)
        required = len([a for a in protocol if a.is_required])

        empty = len([a for a in protocol if a.status == "empty"])
        incomplete = len([a for a in protocol if a.status == "incomplete"])
        complete = len([a for a in protocol if a.status in ["complete_candidate", "complete"]])
        needs_review = len([a for a in protocol if a.status == "needs_review"])

        required_empty = len([a for a in protocol if a.is_required and a.status == "empty"])
        required_complete = len([a for a in protocol if a.is_required and a.status in ["complete_candidate", "complete"]])

        return {
            "total_areas": total,
            "required_areas": required,
            "empty_areas": empty,
            "incomplete_areas": incomplete,
            "complete_areas": complete,
            "needs_review_areas": needs_review,
            "required_empty": required_empty,
            "required_complete": required_complete,
            "completion_percentage": (required_complete / required * 100) if required > 0 else 0,
        }
