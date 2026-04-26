"""Readiness Service - Evaluates story readiness."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    ConversationReadinessResult,
    ReadinessRule,
    ConversationFact,
    ConversationProtocolEntry,
)


class ReadinessService:
    """Service for evaluating story readiness."""

    @staticmethod
    async def get_active_rules(
        db: AsyncSession,
    ) -> list[ReadinessRule]:
        """Get all active readiness rules."""
        result = await db.execute(
            select(ReadinessRule).where(ReadinessRule.is_active == True)
        )
        return list(result.scalars().all())

    @staticmethod
    async def evaluate_readiness(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Evaluate readiness for a conversation."""
        # Get active rules
        rules = await ReadinessService.get_active_rules(db)

        # Get confirmed facts
        result = await db.execute(
            select(ConversationFact).where(
                ConversationFact.conversation_id == conversation_id,
                ConversationFact.org_id == org_id,
                ConversationFact.status == "confirmed",
                ConversationFact.deleted_at.is_(None),
            )
        )
        confirmed_facts = {f.category for f in result.scalars().all()}

        # Get all protocol entries
        result = await db.execute(
            select(ConversationProtocolEntry).where(
                ConversationProtocolEntry.conversation_id == conversation_id,
                ConversationProtocolEntry.org_id == org_id,
            )
        )
        entries = result.scalars().all()

        # Evaluate each rule
        findings = []
        total_score = 0
        max_score = 0
        missing_fields = []

        for rule in rules:
            max_score += rule.weight
            passed = False

            if rule.required_category:
                # Check if required category fact is confirmed
                if rule.required_category in confirmed_facts:
                    passed = True
                    total_score += rule.weight
                else:
                    missing_fields.append({
                        "field": rule.required_category,
                        "rule": rule.label,
                        "user_hint": "Als Information fehlt noch...",
                    })

            # Additional checks could go here

            findings.append({
                "rule_id": str(rule.id),
                "key": rule.key,
                "label": rule.label,
                "passed": passed,
                "is_mandatory": rule.is_blocking,
                "weight": rule.weight,
                "reviewer_hint": rule.label if passed else f"❌ {rule.label}",
            })

        # Determine status
        all_mandatory_passed = all(
            f["passed"] or not f["is_mandatory"]
            for f in findings
        )

        if total_score == max_score:
            status = "excellent"
            recommendation = "Die Story ist bereit für den nächsten Schritt."
        elif all_mandatory_passed and total_score >= max_score * 0.6:
            status = "ready"
            recommendation = "Die Story ist bereit, könnte aber noch verbessert werden."
        else:
            status = "not_ready"
            missing = ", ".join([m["field"] for m in missing_fields[:3]])
            recommendation = f"Fehlende Informationen: {missing}"

        return {
            "status": status,
            "score": total_score,
            "max_score": max_score,
            "percentage": int((total_score / max_score * 100)) if max_score > 0 else 0,
            "recommendation": recommendation,
            "findings": findings,
            "missing_fields": missing_fields,
            "all_mandatory_passed": all_mandatory_passed,
        }

    @staticmethod
    async def save_result(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        readiness_data: dict[str, Any],
    ) -> ConversationReadinessResult:
        """Save readiness result to database."""
        result = ConversationReadinessResult(
            conversation_id=conversation_id,
            org_id=org_id,
            status=readiness_data["status"],
            score=readiness_data["score"],
            recommendation=readiness_data["recommendation"],
            reason=readiness_data["recommendation"],
            missing_fields=[m["field"] for m in readiness_data["missing_fields"]],
            findings=[
                {
                    "rule_id": f["rule_id"],
                    "label": f["label"],
                    "passed": f["passed"],
                }
                for f in readiness_data["findings"]
            ],
            data_json={
                "percentage": readiness_data["percentage"],
                "all_mandatory_passed": readiness_data["all_mandatory_passed"],
            },
        )
        db.add(result)
        await db.flush()
        return result
