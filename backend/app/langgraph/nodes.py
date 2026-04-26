"""LangGraph Nodes for Conversation Engine."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.langgraph.state import ConversationState
from app.services.conversation_service import ConversationService
from app.services.message_service import MessageService
from app.services.fact_service import FactService
from app.services.protocol_service import ProtocolService
from app.services.story_sizing_service import StorySizingService
from app.services.readiness_service import ReadinessService
from app.services.question_planner_service import QuestionPlannerService
from app.services.structure_service import StructureService
from app.services.observer_service import ObserverService
from app.services.audit_service import AuditService


async def load_context_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Load all context data for the conversation."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])

    errors = []

    try:
        # Load conversation
        conversation = await ConversationService.get_conversation(
            db, conversation_id, org_id
        )
        if not conversation:
            return {"errors": ["Conversation not found"]}

        # Load messages
        messages = await MessageService.get_messages(db, conversation_id, org_id, limit=50)

        # Load facts
        facts = await FactService.get_facts(db, conversation_id, org_id)

        # Load protocol
        protocol_data = await ProtocolService.get_protocol(db, conversation_id, org_id)

        # Determine if context exists
        has_context = any([
            conversation.linked_project_id,
            conversation.linked_epic_id,
            conversation.linked_process_id,
            conversation.linked_capability_id,
        ])

        return {
            "conversation": {
                "id": str(conversation.id),
                "title": conversation.title,
                "status": conversation.status,
                "current_mode": conversation.current_mode,
                "linked_project_id": str(conversation.linked_project_id) if conversation.linked_project_id else None,
                "linked_epic_id": str(conversation.linked_epic_id) if conversation.linked_epic_id else None,
                "linked_process_id": str(conversation.linked_process_id) if conversation.linked_process_id else None,
                "linked_capability_id": str(conversation.linked_capability_id) if conversation.linked_capability_id else None,
            },
            "messages": [
                {"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
            "facts": [
                {"id": str(f.id), "category": f.category, "value": f.value, "confidence": f.confidence, "status": f.status}
                for f in facts
            ],
            "protocol": {p["key"]: p for p in protocol_data},
            "has_context": has_context,
            "mode": conversation.current_mode,
            "errors": errors,
        }
    except Exception as e:
        return {"errors": [f"Error loading context: {str(e)}"]}


async def detect_initial_context_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Detect if we need to ask for context."""
    input_message = state.get("input_message", "")
    has_context = state.get("has_context", False)

    # Simple complexity detection based on message length
    complexity = "low"
    if len(input_message) > 500:
        complexity = "high"
    elif len(input_message) > 200:
        complexity = "medium"

    # If high complexity without context, we should ask
    should_ask = not has_context and complexity in ["medium", "high"]

    return {
        "complexity_level": complexity,
        "should_ask_for_context": should_ask,
    }


async def detect_intent_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Detect user intent from message."""
    input_message = state.get("input_message", "").lower()
    current_mode = state.get("mode", "exploration")

    # Intent detection patterns
    intent = "unknown"

    story_keywords = ["story", "user story", "erstelle story", "mach daraus eine story"]
    exploration_keywords = ["erkunden", "exploration", "brainstorm", "ideen"]
    review_keywords = ["review", "prüfen", "bewerten"]
    correction_keywords = ["korrigieren", "ändern", "falsch"]
    context_keywords = ["projekt", "epic", "prozess", "capability", "zugeordnet"]

    if any(kw in input_message for kw in story_keywords):
        intent = "story_creation_request"
    elif any(kw in input_message for kw in exploration_keywords):
        intent = "exploration_request"
    elif any(kw in input_message for kw in review_keywords):
        intent = "review_request"
    elif any(kw in input_message for kw in correction_keywords):
        intent = "correction_request"
    elif any(kw in input_message for kw in context_keywords):
        intent = "context_assignment"
    elif current_mode == "exploration":
        intent = "exploration_request"
    elif current_mode == "story":
        intent = "story_creation_request"

    return {"intent": intent}


async def detect_mode_switch_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Detect and handle mode switch requests."""
    intent = state.get("intent", "unknown")
    current_mode = state.get("mode", "exploration")
    previous_mode = current_mode

    new_mode = current_mode

    # Mode switch logic
    if intent == "story_creation_request" and current_mode == "exploration":
        new_mode = "story"
    elif intent == "exploration_request" and current_mode == "story":
        new_mode = "exploration"
    elif intent == "review_request":
        new_mode = "review"
    elif intent == "correction_request":
        new_mode = "correction"

    return {
        "mode": new_mode,
        "previous_mode": previous_mode if new_mode != current_mode else None,
    }


async def extract_facts_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Extract facts from user message."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    input_message = state.get("input_message", "")
    mode = state.get("mode", "exploration")

    errors = []
    extracted_facts = []

    try:
        # Get active signals
        signals = await FactService.get_active_signals(db)

        # Pattern matching
        matches = await FactService.match_patterns(input_message, signals)

        for match in matches:
            confidence = min(0.7 + match.get("confidence_boost", 0), 1.0)

            # Status based on mode
            status = "suggested" if mode == "exploration" else "detected"

            fact = await FactService.create_fact(
                db=db,
                conversation_id=conversation_id,
                org_id=org_id,
                category=match["category"],
                value=input_message[:200],
                confidence=confidence,
            )

            extracted_facts.append({
                "id": str(fact.id),
                "category": fact.category,
                "value": fact.value,
                "confidence": fact.confidence,
                "status": fact.status,
            })

    except Exception as e:
        errors.append(f"Fact extraction error: {str(e)}")

    return {
        "facts": state.get("facts", []) + extracted_facts,
        "newly_extracted_facts": extracted_facts,
        "errors": state.get("errors", []) + errors,
    }


async def map_protocol_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Map facts to protocol areas."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])

    errors = []
    newly_extracted = state.get("newly_extracted_facts", [])

    try:
        for fact_data in newly_extracted:
            # Find matching protocol area
            result = await db.execute(
                select(ProtocolService.get_protocol_areas(db, org_id))
            )

            # Map fact to protocol
            from app.models.conversation_engine import ConversationFact
            fact = await db.get(ConversationFact, uuid.UUID(fact_data["id"]))

            if fact:
                await ProtocolService.map_fact_to_protocol(
                    db, conversation_id, org_id, fact
                )

        # Reload protocol
        protocol_data = await ProtocolService.get_protocol(db, conversation_id, org_id)

    except Exception as e:
        errors.append(f"Protocol mapping error: {str(e)}")
        protocol_data = state.get("protocol", {})

    return {
        "protocol": {p["key"]: p for p in protocol_data} if isinstance(protocol_data, list) else protocol_data,
        "errors": state.get("errors", []) + errors,
    }


async def calculate_story_sizing_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Calculate story size."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    mode = state.get("mode", "exploration")

    # Only calculate in story or review mode
    if mode not in ["story", "review"]:
        return {
            "story_size_score": 0,
            "recommended_story_count": 1,
            "size_label": "XS",
            "sizing_recommendation": "",
        }

    try:
        sizing_data = await StorySizingService.calculate_size(
            db, conversation_id, org_id
        )

        return {
            "story_size_score": sizing_data["score"],
            "recommended_story_count": sizing_data["recommended_story_count"],
            "size_label": sizing_data["label"],
            "sizing_recommendation": sizing_data["recommendation"],
        }
    except Exception as e:
        return {
            "story_size_score": 0,
            "recommended_story_count": 1,
            "size_label": "XS",
            "sizing_recommendation": "",
            "errors": state.get("errors", []) + [f"Sizing error: {str(e)}"],
        }


async def evaluate_readiness_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Evaluate story readiness."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    mode = state.get("mode", "exploration")

    # Only evaluate in story or review mode
    if mode not in ["story", "review"]:
        return {
            "readiness_score": 0,
            "readiness_max_score": 100,
            "readiness_status": None,
            "readiness_recommendation": "",
            "missing_fields": [],
        }

    try:
        readiness_data = await ReadinessService.evaluate_readiness(
            db, conversation_id, org_id
        )

        return {
            "readiness_score": readiness_data["score"],
            "readiness_max_score": readiness_data["max_score"],
            "readiness_status": readiness_data["status"],
            "readiness_recommendation": readiness_data["recommendation"],
            "missing_fields": [m["field"] for m in readiness_data["missing_fields"]],
        }
    except Exception as e:
        return {
            "readiness_score": 0,
            "readiness_max_score": 100,
            "readiness_status": None,
            "readiness_recommendation": "",
            "missing_fields": [],
            "errors": state.get("errors", []) + [f"Readiness error: {str(e)}"],
        }


async def decide_structure_proposal_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Decide if structure proposal is needed."""
    previous_mode = state.get("previous_mode")
    current_mode = state.get("mode", "exploration")
    story_size_score = state.get("story_size_score", 0)
    user_provided_structure = state.get("user_provided_structure", False)

    should_propose = (
        previous_mode == "exploration"
        and current_mode == "story"
        and story_size_score > 60
        and not user_provided_structure
    )

    return {
        "structure_proposal_required": should_propose,
    }


async def generate_structure_proposal_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Generate structure proposal."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    user_id = uuid.UUID(state["user_id"])
    conversation_id = uuid.UUID(state["conversation_id"])

    try:
        proposal_data = await StructureService.analyze_and_propose(
            db, conversation_id, org_id, user_id
        )

        if "error" in proposal_data:
            return {
                "structure_proposal": None,
                "errors": state.get("errors", []) + [proposal_data["error"]],
            }

        return {
            "structure_proposal": {
                "proposal_id": proposal_data["proposal_id"],
                "recommended_type": proposal_data["recommended_type"],
                "story_count": proposal_data["story_count"],
                "size_score": proposal_data["size_score"],
                "size_label": proposal_data["size_label"],
                "reason": proposal_data["reason"],
                "items": proposal_data["items"],
            },
        }
    except Exception as e:
        return {
            "structure_proposal": None,
            "errors": state.get("errors", []) + [f"Structure proposal error: {str(e)}"],
        }


async def plan_questions_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Plan next questions."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])

    try:
        planned_questions = await QuestionPlannerService.plan_questions(
            db, conversation_id, org_id, max_questions=3
        )

        return {
            "next_questions": planned_questions,
            "max_questions_per_turn": 3,
        }
    except Exception as e:
        return {
            "next_questions": [],
            "errors": state.get("errors", []) + [f"Question planning error: {str(e)}"],
        }


async def generate_response_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Generate assistant response."""
    mode = state.get("mode", "exploration")
    intent = state.get("intent", "unknown")
    facts = state.get("facts", [])
    newly_extracted = state.get("newly_extracted_facts", [])
    protocol = state.get("protocol", {})
    sizing = {
        "score": state.get("story_size_score", 0),
        "label": state.get("size_label", "XS"),
        "recommendation": state.get("sizing_recommendation", ""),
        "count": state.get("recommended_story_count", 1),
    }
    readiness = {
        "status": state.get("readiness_status"),
        "score": state.get("readiness_score", 0),
        "recommendation": state.get("readiness_recommendation", ""),
    }
    questions = state.get("next_questions", [])
    structure_proposal = state.get("structure_proposal")
    errors = state.get("errors", [])

    parts = []
    facts_reused = []

    # Handle errors first
    if errors:
        parts.append("Entschuldigung, es ist ein Fehler aufgetreten. Lass uns neu beginnen.")

    # Exploration mode response
    elif mode == "exploration":
        if newly_extracted:
            categories = list(set(f["category"] for f in newly_extracted))
            if len(categories) == 1:
                parts.append(f"Ich habe erkannt: {newly_extracted[0]['value'][:100]}")
            else:
                parts.append(f"Ich habe {len(newly_extracted)} Informationen erkannt.")

        if questions:
            parts.append("\n**Nächste Fragen:**")
            for i, q in enumerate(questions[:2], 1):
                parts.append(f"{i}. {q['question']}")

    # Story mode response
    elif mode == "story":
        # Acknowledge facts
        if newly_extracted:
            parts.append(f"✓ {newly_extracted[0]['category']}: {newly_extracted[0]['value'][:80]}...")

        # Sizing info
        if sizing["score"] > 0:
            if sizing["score"] > 60:
                parts.append(f"📊 Story-Größe: {sizing['label']} (Score: {sizing['score']})")
                if sizing["count"] > 1:
                    parts.append(f"💡 Empfehlung: Aufteilung in {sizing['count']} Stories")
            else:
                parts.append(f"📊 Story-Größe: {sizing['label']} (gut proportioniert)")

        # Readiness info
        if readiness["status"]:
            emoji = {"excellent": "✅", "ready": "✓", "not_ready": "⏳"}.get(readiness["status"], "")
            parts.append(f"{emoji} Readiness: {readiness['score']}%")

        # Structure proposal
        if structure_proposal:
            parts.append(f"\n**Strukturvorschlag:**")
            parts.append(f"Typ: {structure_proposal['recommended_type']}")
            parts.append(f"Stories: {structure_proposal['story_count']}")
            parts.append("Soll ich diese Struktur übernehmen?")

        # Questions
        elif questions:
            parts.append("\n**Meine nächsten Fragen:**")
            for i, q in enumerate(questions[:2], 1):
                parts.append(f"{i}. {q['question']}")

    # Review mode
    elif mode == "review":
        if readiness["status"]:
            parts.append(f"**Review-Ergebnis:** {readiness['status']} ({readiness['score']}%)")
            if readiness["recommendation"]:
                parts.append(readiness["recommendation"])

    # Default fallback
    if not parts:
        parts.append("Ich verstehe. Erzählen Sie mir mehr.")

    response_text = "\n\n".join(parts)

    return {
        "response_text": response_text,
        "facts_reused_in_response": facts_reused,
    }


async def save_results_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Save all results to database."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    response_text = state.get("response_text", "")

    errors = []

    try:
        # Save assistant message
        from app.services.message_service import MessageService
        await MessageService.save_message(
            db=db,
            conversation_id=conversation_id,
            org_id=org_id,
            role="assistant",
            content=response_text,
        )

        # Update conversation state if mode changed
        previous_mode = state.get("previous_mode")
        if previous_mode:
            from app.services.conversation_service import ConversationService
            await ConversationService.switch_mode(
                db, conversation_id, org_id, state["mode"]
            )

        await db.commit()

    except Exception as e:
        errors.append(f"Save error: {str(e)}")

    return {"errors": state.get("errors", []) + errors}


async def observer_hook_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Observer hook for quality monitoring."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    observer_enabled = state.get("observer_enabled", False)

    if not observer_enabled:
        return {}

    try:
        findings = await ObserverService.create_findings(
            db, conversation_id, org_id
        )

        return {
            "audit_events": state.get("audit_events", []) + [
                {"type": "observer_findings_created", "count": len(findings)}
            ],
        }
    except Exception:
        # Observer errors should not break the flow
        return {}


async def audit_node(
    state: ConversationState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """Write audit log entries."""
    db = config["configurable"]["db"]
    org_id = uuid.UUID(state["org_id"])
    user_id = uuid.UUID(state["user_id"])
    conversation_id = uuid.UUID(state["conversation_id"])

    events = state.get("audit_events", [])

    # Add main events
    events.append({"type": "message_processed", "timestamp": datetime.now(timezone.utc).isoformat()})

    if state.get("newly_extracted_facts"):
        events.append({"type": "facts_extracted", "count": len(state["newly_extracted_facts"])})

    if state.get("story_size_score", 0) > 0:
        events.append({"type": "sizing_calculated", "score": state["story_size_score"]})

    if state.get("readiness_status"):
        events.append({"type": "readiness_evaluated", "status": state["readiness_status"]})

    if state.get("structure_proposal"):
        events.append({"type": "structure_proposal_created"})

    try:
        for event in events:
            await AuditService.log_action(
                db=db,
                org_id=org_id,
                conversation_id=conversation_id,
                actor_id=user_id,
                action=event["type"],
                entity_type="conversation",
                entity_id=conversation_id,
                after_state=event,
            )

        await db.commit()
    except Exception:
        # Audit errors should not break the flow
        pass

    return {}
