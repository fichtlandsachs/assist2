"""Orchestrator Service - Central coordinator for conversation flow."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.fact_service import FactService
from app.services.protocol_service import ProtocolService
from app.services.question_planner_service import QuestionPlannerService
from app.services.story_sizing_service import StorySizingService
from app.services.readiness_service import ReadinessService
from app.services.audit_service import AuditService


class OrchestratorService:
    """Central orchestrator for conversation processing."""

    @staticmethod
    async def process_message(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        message_text: str,
    ) -> dict[str, Any]:
        """
        Process a user message through the complete conversation flow.
        
        Flow:
        1. Save user message
        2. Extract facts
        3. Update protocol
        4. Calculate story sizing
        5. Evaluate readiness
        6. Plan next questions
        7. Generate response
        8. Save response
        9. Audit log
        """
        # 1. Save user message
        user_message = await MessageService.save_message(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            role="user",
            content=message_text,
        )

        # 2. Extract facts
        extracted_facts = await FactService.extract_facts_from_text(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            text=message_text,
            source_message_id=user_message.id,
        )

        # 3. Update protocol with new facts
        for fact in extracted_facts:
            await ProtocolService.map_fact_to_protocol(
                db=db,
                conversation_id=conversation_id,
                org_id=org_id,
                fact=fact,
            )

        # Get conversation state
        conversation, state = await ConversationService.get_conversation_with_state(
            db, conversation_id, org_id
        )

        if not conversation:
            return {"error": "Conversation not found"}

        # 4. Calculate story sizing (only in story mode)
        sizing_data = None
        if conversation.current_mode == "story":
            sizing_data = await StorySizingService.calculate_size(
                db, conversation_id, org_id
            )
            await StorySizingService.save_result(
                db, conversation_id, org_id, sizing_data
            )

        # 5. Evaluate readiness (only in story mode)
        readiness_data = None
        if conversation.current_mode == "story":
            readiness_data = await ReadinessService.evaluate_readiness(
                db, conversation_id, org_id
            )
            await ReadinessService.save_result(
                db, conversation_id, org_id, readiness_data
            )

        # 6. Plan next questions
        planned_questions = await QuestionPlannerService.plan_questions(
            db, conversation_id, org_id, max_questions=3
        )
        await QuestionPlannerService.update_state_questions(
            db, conversation_id, planned_questions
        )

        # 7. Generate response
        response_text = await OrchestratorService._generate_response(
            extracted_facts=extracted_facts,
            sizing_data=sizing_data,
            readiness_data=readiness_data,
            planned_questions=planned_questions,
            mode=conversation.current_mode,
        )

        # 8. Save assistant response
        assistant_message = await MessageService.save_message(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            role="assistant",
            content=response_text,
        )

        # 9. Audit log
        await AuditService.log_action(
            db=db,
            org_id=org_id,
            conversation_id=conversation_id,
            actor_id=user_id,
            action="message_processed",
            entity_type="conversation_message",
            entity_id=user_message.id,
            after_state={
                "facts_extracted": len(extracted_facts),
                "questions_planned": len(planned_questions),
                "mode": conversation.current_mode,
            },
        )

        await db.commit()

        # Build response
        protocol = await ProtocolService.get_protocol(
            db, conversation_id, org_id
        )

        return {
            "response": response_text,
            "mode": conversation.current_mode,
            "facts_extracted": [
                {
                    "id": str(f.id),
                    "category": f.category,
                    "value": f.value,
                    "confidence": f.confidence,
                }
                for f in extracted_facts
            ],
            "protocol_updates": protocol,
            "story_sizing": sizing_data,
            "readiness": readiness_data,
            "next_questions": planned_questions,
        }

    @staticmethod
    async def _generate_response(
        extracted_facts: list,
        sizing_data: Optional[dict],
        readiness_data: Optional[dict],
        planned_questions: list[dict],
        mode: str,
    ) -> str:
        """Generate assistant response text."""
        parts = []

        # Acknowledge extracted facts
        if extracted_facts:
            categories = set(f.category for f in extracted_facts)
            if len(categories) == 1:
                parts.append(f"Ich habe erkannt: {extracted_facts[0].value}")
            else:
                parts.append(f"Ich habe {len(extracted_facts)} Informationen erkannt.")

        # Add sizing feedback (only in story mode)
        if sizing_data and mode == "story":
            if sizing_data["score"] > 50:
                parts.append(f"📊 Story-Größe: {sizing_data['label']} (Score: {sizing_data['score']})")
                if sizing_data["recommended_story_count"] > 1:
                    parts.append(f"💡 Empfehlung: Aufteilung in {sizing_data['recommended_story_count']} Stories")

        # Add readiness feedback (only in story mode)
        if readiness_data and mode == "story":
            status_emoji = {"excellent": "✅", "ready": "✓", "not_ready": "⏳"}
            emoji = status_emoji.get(readiness_data["status"], "")
            parts.append(f"{emoji} Readiness: {readiness_data['percentage']}%")

        # Add questions
        if planned_questions:
            parts.append("\n**Meine nächsten Fragen:**")
            for i, q in enumerate(planned_questions[:2], 1):
                parts.append(f"{i}. {q['question']}")

        return "\n\n".join(parts) if parts else "Ich verstehe. Erzählen Sie mir mehr."

    @staticmethod
    async def switch_mode(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        new_mode: str,
    ) -> dict[str, Any]:
        """Switch conversation mode with proper handling."""
        # Validate mode
        if new_mode not in ["exploration", "story", "review"]:
            return {"error": f"Invalid mode: {new_mode}"}

        # Perform mode switch
        state = await ConversationService.switch_mode(
            db, conversation_id, org_id, new_mode
        )

        if not state:
            return {"error": "Failed to switch mode"}

        # Create system message about mode switch
        mode_descriptions = {
            "exploration": "Wir erkunden nun frei das Thema.",
            "story": "Wir arbeiten jetzt strukturiert an einer User Story.",
            "review": "Wir prüfen nun eine bestehende Story.",
        }

        system_message = await MessageService.save_message(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            role="system",
            content=f"Mode switched to: {new_mode}",
        )

        # Audit log
        await AuditService.log_action(
            db=db,
            org_id=org_id,
            conversation_id=conversation_id,
            actor_id=user_id,
            action="mode_switched",
            entity_type="conversation",
            entity_id=conversation_id,
            after_state={"new_mode": new_mode},
        )

        await db.commit()

        return {
            "success": True,
            "mode": new_mode,
            "message": mode_descriptions.get(new_mode, ""),
            "system_message_id": str(system_message.id),
        }
