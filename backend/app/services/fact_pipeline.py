"""Fact Pipeline - Orchestrates the complete fact extraction and processing pipeline."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationFact
from app.services.fact_extractor import CandidateFact, FactExtractor
from app.services.fact_normalizer import FactNormalizer
from app.services.fact_deduplicator import DeduplicationResult, FactDeduplicator
from app.services.protocol_mapper import ProtocolArea, ProtocolMapper
from app.services.audit_service import AuditService


@dataclass
class FactPipelineResult:
    """Complete result of fact pipeline execution."""
    facts_extracted: list[ConversationFact]
    facts_updated: list[ConversationFact]
    conflicts: list[dict]
    protocol: list[ProtocolArea]
    unmapped: bool


class FactPipeline:
    """Orchestrates fact extraction, normalization, deduplication, and protocol mapping."""

    @staticmethod
    async def process_message(
        db: AsyncSession,
        message_text: str,
        message_id: uuid.UUID,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        mode: str,
    ) -> FactPipelineResult:
        """Process a user message through the complete pipeline."""
        # Load existing facts for deduplication and conflict detection
        existing_facts = await FactExtractor.load_existing_facts(
            db, conversation_id, org_id
        )

        # 1. Extract candidates
        candidates = await FactExtractor.extract_facts(
            db=db,
            message_text=message_text,
            message_id=message_id,
            conversation_id=conversation_id,
            org_id=org_id,
            mode=mode,
            existing_facts=existing_facts,
        )

        if not candidates:
            # No facts detected - unmapped answer
            await AuditService.log_action(
                db=db,
                org_id=org_id,
                action="unmapped_answer_detected",
                entity_type="conversation_message",
                entity_id=message_id,
                actor_id=user_id,
                after_state={"message_preview": message_text[:100]},
            )

            # Load protocol for response
            protocol = await ProtocolMapper.map_facts_to_protocol(
                db, conversation_id, org_id
            )

            return FactPipelineResult(
                facts_extracted=[],
                facts_updated=[],
                conflicts=[],
                protocol=protocol,
                unmapped=True,
            )

        # 2. Normalize and process each candidate
        facts_extracted = []
        facts_updated = []
        conflicts = []

        for candidate in candidates:
            # Normalize value
            candidate.normalized_value = FactNormalizer.normalize(
                candidate.value, candidate.category
            )

            # Apply confidence adjustments
            entities = FactExtractor.detect_entities(message_text)
            candidate.confidence = FactExtractor.apply_confidence_adjustments(
                candidate, existing_facts, entities
            )

            # Assign status based on mode and confidence
            status = FactExtractor.assign_status(candidate.confidence, mode)

            # Check for duplicates
            dedup_result = await FactDeduplicator.check_duplicate(
                db=db,
                conversation_id=conversation_id,
                category=candidate.category,
                value=candidate.value,
                normalized_value=candidate.normalized_value,
                confidence=candidate.confidence,
            )

            if dedup_result.action == "skip":
                # Log deduplication
                await AuditService.log_action(
                    db=db,
                    org_id=org_id,
                    action="fact_deduplicated",
                    entity_type="conversation_fact",
                    entity_id=dedup_result.existing_fact.id if dedup_result.existing_fact else None,
                    actor_id=user_id,
                    after_state={
                        "reason": dedup_result.reason,
                        "category": candidate.category,
                    },
                )
                continue

            # Handle duplicate or create new
            if dedup_result.action == "update":
                # Update existing fact
                existing = dedup_result.existing_fact
                old_state = {
                    "confidence": existing.confidence,
                    "value": existing.value,
                }

                # Update with new evidence
                existing.confidence = candidate.confidence
                existing.value = candidate.value
                existing.normalized_value = candidate.normalized_value
                existing.status = status

                # Track usage
                current_used = existing.used_in or []
                if str(message_id) not in current_used:
                    current_used.append(str(message_id))
                    existing.used_in = current_used

                await db.flush()
                facts_updated.append(existing)

                # Log update
                await AuditService.log_action(
                    db=db,
                    org_id=org_id,
                    action="fact_updated",
                    entity_type="conversation_fact",
                    entity_id=existing.id,
                    actor_id=user_id,
                    before_state=old_state,
                    after_state={
                        "confidence": existing.confidence,
                        "value": existing.value,
                    },
                )

                fact = existing

            else:  # create
                # Create new fact
                fact = ConversationFact(
                    conversation_id=conversation_id,
                    org_id=org_id,
                    source_message_id=message_id,
                    category=candidate.category,
                    value=candidate.value,
                    normalized_value=candidate.normalized_value,
                    confidence=candidate.confidence,
                    status=status,
                    used_in=[str(message_id)] if message_id else [],
                )
                db.add(fact)
                await db.flush()
                facts_extracted.append(fact)

                # Log creation
                await AuditService.log_action(
                    db=db,
                    org_id=org_id,
                    action="fact_created",
                    entity_type="conversation_fact",
                    entity_id=fact.id,
                    actor_id=user_id,
                    after_state={
                        "category": fact.category,
                        "value": fact.value,
                        "confidence": fact.confidence,
                        "status": fact.status,
                    },
                )

            # Check for conflicts
            if dedup_result.is_duplicate == False and dedup_result.existing_fact:
                # Similar but distinct - potential conflict
                conflict_fact = dedup_result.existing_fact
                conflicts.append({
                    "existing_fact_id": str(conflict_fact.id),
                    "existing_value": conflict_fact.value,
                    "new_fact_id": str(fact.id),
                    "new_value": fact.value,
                    "category": fact.category,
                    "message": (
                        f"Du hattest zuvor {conflict_fact.normalized_value or conflict_fact.value} "
                        f"als {fact.category} genannt. Jetzt klingt es nach "
                        f"{fact.normalized_value or fact.value}. "
                        f"Soll ich beide berücksichtigen oder eine Zuordnung korrigieren?"
                    ),
                })

                # Mark both as needs_review
                fact.status = "needs_review"
                conflict_fact.status = "needs_review"

                # Log conflict
                await AuditService.log_action(
                    db=db,
                    org_id=org_id,
                    action="fact_conflict_detected",
                    entity_type="conversation_fact",
                    entity_id=fact.id,
                    actor_id=user_id,
                    after_state={
                        "conflicting_fact_id": str(conflict_fact.id),
                        "category": fact.category,
                    },
                )

        # 3. Map to protocol
        protocol = await ProtocolMapper.map_facts_to_protocol(
            db, conversation_id, org_id
        )

        # Log protocol updates
        for area in protocol:
            if area.entries:
                await AuditService.log_action(
                    db=db,
                    org_id=org_id,
                    action="protocol_entry_updated",
                    entity_type="conversation_protocol_area",
                    entity_id=None,
                    actor_id=user_id,
                    after_state={
                        "area_key": area.area_key,
                        "facts_count": area.facts_count,
                        "status": area.status,
                    },
                )

        return FactPipelineResult(
            facts_extracted=facts_extracted,
            facts_updated=facts_updated,
            conflicts=conflicts,
            protocol=protocol,
            unmapped=False,
        )


# Add helper method to FactExtractor
async def load_existing_facts(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    org_id: uuid.UUID,
) -> list[ConversationFact]:
    """Load existing facts for a conversation."""
    from sqlalchemy import select

    result = await db.execute(
        select(ConversationFact).where(
            ConversationFact.conversation_id == conversation_id,
            ConversationFact.org_id == org_id,
            ConversationFact.deleted_at.is_(None),
            ConversationFact.status.in_(["detected", "suggested", "confirmed"]),
        )
    )
    return list(result.scalars().all())


# Monkey-patch helper
FactExtractor.load_existing_facts = load_existing_facts
