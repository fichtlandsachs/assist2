"""Observer Service - Conversation quality monitoring and improvement suggestions."""
from __future__ import annotations

import uuid
from typing import Any, Optional
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationObserverFinding,
    ConversationObserverProposalNew,
    ConversationObserverValidation,
    ConversationMessage,
    Conversation,
)


class ObserverService:
    """Service for conversation quality observation."""

    @staticmethod
    async def analyze_conversation(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[dict[str, Any]]:
        """Analyze conversation and generate findings."""
        findings = []

        # Get messages
        result = await db.execute(
            select(ConversationMessage).where(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.org_id == org_id,
            ).order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()

        if not messages:
            return findings

        # Check for unmapped answers
        for msg in messages:
            if msg.role == "user" and len(msg.content) > 200:
                # Long user message without clear fact mapping
                findings.append({
                    "type": "unmapped_content",
                    "severity": "medium",
                    "message_id": msg.id,
                    "reason": "Lange Antwort ohne klare Fakt-Extraktion",
                    "suggested_improvement": "Pattern-Matching verbessern",
                })

        # Check for repeated questions (assistant)
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        if len(assistant_msgs) > 5:
            # Many messages without user progress
            findings.append({
                "type": "too_many_questions",
                "severity": "low",
                "reason": "Viele Fragen ohne ausreichenden Fortschritt",
                "suggested_improvement": "Frageanzahl reduzieren",
            })

        return findings

    @staticmethod
    async def create_findings(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> list[ConversationObserverFinding]:
        """Create findings from analysis."""
        findings_data = await ObserverService.analyze_conversation(
            db, conversation_id, org_id
        )

        created = []
        for data in findings_data:
            finding = ConversationObserverFinding(
                org_id=org_id,
                conversation_id=conversation_id,
                message_id=data.get("message_id"),
                type=data["type"],
                severity=data["severity"],
                reason=data["reason"],
                suggested_improvement=data.get("suggested_improvement"),
                status="open",
            )
            db.add(finding)
            created.append(finding)

        await db.flush()
        return created

    @staticmethod
    async def get_findings(
        db: AsyncSession,
        org_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[ConversationObserverFinding]:
        """Get observer findings."""
        query = select(ConversationObserverFinding).where(
            ConversationObserverFinding.org_id == org_id,
        )

        if status:
            query = query.where(ConversationObserverFinding.status == status)

        result = await db.execute(
            query.order_by(ConversationObserverFinding.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_proposal_from_finding(
        db: AsyncSession,
        finding_id: uuid.UUID,
        org_id: uuid.UUID,
        proposal_type: str,
        title: str,
        description: str,
        proposed_change: dict,
    ) -> Optional[ConversationObserverProposalNew]:
        """Create an improvement proposal from a finding."""
        # Verify finding exists
        result = await db.execute(
            select(ConversationObserverFinding).where(
                ConversationObserverFinding.id == finding_id,
                ConversationObserverFinding.org_id == org_id,
            )
        )
        finding = result.scalar_one_or_none()

        if not finding:
            return None

        proposal = ConversationObserverProposalNew(
            org_id=org_id,
            finding_id=finding_id,
            proposal_type=proposal_type,
            title=title,
            description=description,
            proposed_change=proposed_change,
            expected_impact="Verbesserte Fact-Erkennung",
            status="draft",
        )
        db.add(proposal)
        await db.flush()

        return proposal

    @staticmethod
    async def approve_proposal(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Approve a proposal and activate it."""
        result = await db.execute(
            select(ConversationObserverProposalNew).where(
                ConversationObserverProposalNew.id == proposal_id,
                ConversationObserverProposalNew.org_id == org_id,
            )
        )
        proposal = result.scalar_one_or_none()

        if not proposal:
            return False

        proposal.status = "approved"
        proposal.reviewed_by = user_id
        proposal.reviewed_at = datetime.now(timezone.utc)
        proposal.activated_at = datetime.now(timezone.utc)

        await db.flush()
        return True

    @staticmethod
    async def rollback_proposal(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Rollback an approved proposal."""
        result = await db.execute(
            select(ConversationObserverProposalNew).where(
                ConversationObserverProposalNew.id == proposal_id,
                ConversationObserverProposalNew.org_id == org_id,
            )
        )
        proposal = result.scalar_one_or_none()

        if not proposal:
            return False

        proposal.status = "rolled_back"
        proposal.rolled_back_at = datetime.now(timezone.utc)

        await db.flush()
        return True

    @staticmethod
    async def get_proposals(
        db: AsyncSession,
        org_id: uuid.UUID,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[ConversationObserverProposalNew]:
        """Get observer proposals."""
        query = select(ConversationObserverProposalNew).where(
            ConversationObserverProposalNew.org_id == org_id,
        )

        if status:
            query = query.where(ConversationObserverProposalNew.status == status)

        result = await db.execute(
            query.order_by(ConversationObserverProposalNew.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def start_validation(
        db: AsyncSession,
        proposal_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> ConversationObserverValidation:
        """Start A/B validation for a proposal."""
        validation = ConversationObserverValidation(
            proposal_id=proposal_id,
            org_id=org_id,
            baseline_start=datetime.now(timezone.utc),
            status="running",
        )
        db.add(validation)
        await db.flush()
        return validation
