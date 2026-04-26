"""Protocol Service - Manages conversation protocol entries."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationProtocolArea,
    ConversationProtocolEntry,
    ConversationFact,
)


class ProtocolService:
    """Service for managing conversation protocol."""

    @staticmethod
    async def get_protocol_areas(
        db: AsyncSession,
        org_id: Optional[uuid.UUID] = None,
        is_active: bool = True,
    ) -> list[ConversationProtocolArea]:
        """Get protocol areas for an org or global."""
        query = select(ConversationProtocolArea).where(
            ConversationProtocolArea.is_active == is_active,
        )

        if org_id:
            # Get org-specific and global areas
            query = query.where(
                (ConversationProtocolArea.org_id == org_id) |
                (ConversationProtocolArea.org_id.is_(None))
            )
        else:
            # Only global areas
            query = query.where(ConversationProtocolArea.org_id.is_(None))

        result = await db.execute(
            query.order_by(ConversationProtocolArea.sort_order)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_protocol_entry(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        protocol_area_id: uuid.UUID,
        fact_id: Optional[uuid.UUID] = None,
        value: Optional[str] = None,
        confidence: Optional[float] = None,
        status: str = "suggested",
    ) -> ConversationProtocolEntry:
        """Create a protocol entry."""
        entry = ConversationProtocolEntry(
            conversation_id=conversation_id,
            org_id=org_id,
            protocol_area_id=protocol_area_id,
            fact_id=fact_id,
            value=value,
            confidence=confidence,
            status=status,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def get_protocol(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[dict]:
        """Get full protocol for a conversation."""
        # Get all areas
        areas = await ProtocolService.get_protocol_areas(db, org_id)

        # Get entries for this conversation
        result = await db.execute(
            select(ConversationProtocolEntry)
            .where(
                ConversationProtocolEntry.conversation_id == conversation_id,
                ConversationProtocolEntry.org_id == org_id,
            )
            .order_by(ConversationProtocolEntry.created_at.desc())
        )
        entries = result.scalars().all()

        # Build protocol structure
        protocol = []
        for area in areas:
            area_entries = [
                {
                    "id": str(e.id),
                    "value": e.value,
                    "status": e.status,
                    "confidence": e.confidence,
                    "fact_id": str(e.fact_id) if e.fact_id else None,
                    "created_at": e.created_at.isoformat(),
                }
                for e in entries
                if e.protocol_area_id == area.id
            ]

            # Determine area status
            if area_entries:
                if any(e["status"] == "confirmed" for e in area_entries):
                    area_status = "confirmed"
                elif any(e["status"] == "suggested" for e in area_entries):
                    area_status = "suggested"
                else:
                    area_status = "empty"
            else:
                area_status = "empty"

            protocol.append({
                "area_id": str(area.id),
                "key": area.key,
                "display_name": area.display_name,
                "description": area.description,
                "help_text": area.help_text,
                "is_required": area.is_required,
                "sort_order": area.sort_order,
                "status": area_status,
                "entries": area_entries,
            })

        return protocol

    @staticmethod
    async def update_entry_status(
        db: AsyncSession,
        entry_id: uuid.UUID,
        status: str,
    ) -> Optional[ConversationProtocolEntry]:
        """Update protocol entry status."""
        result = await db.execute(
            select(ConversationProtocolEntry).where(
                ConversationProtocolEntry.id == entry_id
            )
        )
        entry = result.scalar_one_or_none()

        if entry:
            entry.status = status
            entry.updated_at = datetime.now(timezone.utc)
            await db.flush()

        return entry

    @staticmethod
    async def map_fact_to_protocol(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        fact: ConversationFact,
    ) -> Optional[ConversationProtocolEntry]:
        """Map a fact to the appropriate protocol area."""
        # Find matching protocol area by category
        result = await db.execute(
            select(ConversationProtocolArea).where(
                ConversationProtocolArea.key == fact.category,
                (ConversationProtocolArea.org_id == org_id) |
                (ConversationProtocolArea.org_id.is_(None)),
                ConversationProtocolArea.is_active == True,
            )
        )
        area = result.scalar_one_or_none()

        if not area:
            return None

        # Create or update protocol entry
        existing = await db.execute(
            select(ConversationProtocolEntry).where(
                ConversationProtocolEntry.conversation_id == conversation_id,
                ConversationProtocolEntry.protocol_area_id == area.id,
                ConversationProtocolEntry.fact_id == fact.id,
            )
        )

        if existing.scalar_one_or_none():
            return None  # Already mapped

        entry = await ProtocolService.create_protocol_entry(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            protocol_area_id=area.id,
            fact_id=fact.id,
            value=fact.value,
            confidence=fact.confidence,
            status="suggested",
        )

        return entry
