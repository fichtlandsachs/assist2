# app/routers/compliance_chat.py
"""
Compliance Chat API.

  POST /api/v1/compliance/chat/sessions
       Get or create a compliance chat session for an assessment.

  GET  /api/v1/compliance/chat/sessions/{session_id}
       Get session state (next question, progress, gap summary).

  POST /api/v1/compliance/chat/sessions/{session_id}/turn
       Submit a user message; receive assistant reply + gap update.

  POST /api/v1/compliance/chat/sessions/{session_id}/apply-mappings
       Commit all pending high-confidence score mappings to assessment items.

  GET  /api/v1/compliance/chat/sessions/{session_id}/turns
       Full turn history (for rendering the chat).

  GET  /api/v1/compliance/chat/questions/{control_id}
       Get the ControlChatQuestion config for a single control.

  PUT  /api/v1/compliance/chat/questions/{control_id}
       Update the ControlChatQuestion config (admin only).

  POST /api/v1/compliance/chat/seed-questions
       Seed default ControlChatQuestion for all controls without one.

  GET  /api/v1/compliance/chat/questions
       List all ControlChatQuestion configs.
"""
from __future__ import annotations

import uuid
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.compliance_assessment import ComplianceAssessment
from app.models.control_chat_config import (
    ComplianceChatSession, ComplianceChatTurn, ComplianceChatMapping,
    ControlChatQuestion, SessionStatus,
)
from app.models.product_governance import ControlDefinition
from app.services.compliance_chat_service import (
    get_or_create_session, process_user_turn, apply_pending_mappings,
    get_next_question, seed_chat_questions,
)

router = APIRouter(prefix="/compliance/chat", tags=["compliance-chat"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SessionCreateRequest(BaseModel):
    assessment_id: uuid.UUID


class TurnRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


class ChatQuestionUpdate(BaseModel):
    primary_question: Optional[str] = None
    answer_type: Optional[str] = None
    answer_options: Optional[List[Any]] = None
    alternative_questions: Optional[List[Any]] = None
    followup_questions: Optional[List[Any]] = None
    completion_conditions: Optional[List[Any]] = None
    score_mapping_rules: Optional[List[Any]] = None
    forbidden_terms: Optional[List[Any]] = None
    hint_text: Optional[str] = None
    question_priority: Optional[int] = None
    always_ask: Optional[bool] = None
    skippable: Optional[bool] = None
    gap_label_template: Optional[str] = None
    risk_label_template: Optional[str] = None
    is_active: Optional[bool] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _session_dict(s: ComplianceChatSession, next_q: dict | None = None) -> dict:
    return {
        "id": str(s.id),
        "assessment_id": str(s.assessment_id),
        "status": s.status,
        "context_params": s.context_params,
        "addressed_count": len(s.addressed_control_ids or []),
        "pending_count": len(s.pending_control_ids or []),
        "turn_count": s.turn_count,
        "conversation_summary": s.conversation_summary,
        "next_question": next_q or s.next_question,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def _cq_dict(cq: ControlChatQuestion) -> dict:
    return {
        "id": str(cq.id),
        "control_id": str(cq.control_id),
        "primary_question": cq.primary_question,
        "answer_type": cq.answer_type,
        "answer_options": cq.answer_options,
        "alternative_questions": cq.alternative_questions,
        "followup_questions": cq.followup_questions,
        "completion_conditions": cq.completion_conditions,
        "score_mapping_rules": cq.score_mapping_rules,
        "forbidden_terms": cq.forbidden_terms,
        "hint_text": cq.hint_text,
        "question_priority": cq.question_priority,
        "always_ask": cq.always_ask,
        "skippable": cq.skippable,
        "gap_label_template": cq.gap_label_template,
        "risk_label_template": cq.risk_label_template,
        "is_active": cq.is_active,
        "updated_at": cq.updated_at.isoformat(),
    }


# ── Session endpoints ─────────────────────────────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.get(ComplianceAssessment, payload.assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    session = await get_or_create_session(db, assessment, current_user)
    await db.commit()
    await db.refresh(session)
    return _session_dict(session)


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(ComplianceChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    assessment = await db.get(ComplianceAssessment, session.assessment_id)
    next_q = await get_next_question(db, session, assessment)
    return _session_dict(session, next_q)


@router.post("/sessions/{session_id}/turn")
async def submit_turn(
    session_id: uuid.UUID,
    payload: TurnRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(ComplianceChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != SessionStatus.active.value:
        raise HTTPException(400, "Session is not active")

    assessment = await db.get(ComplianceAssessment, session.assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    result = await process_user_turn(db, session, assessment, payload.message, current_user)
    await db.commit()

    return result


@router.post("/sessions/{session_id}/apply-mappings")
async def apply_mappings(
    session_id: uuid.UUID,
    min_confidence: float = Query(0.6, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = await db.get(ComplianceChatSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    assessment = await db.get(ComplianceAssessment, session.assessment_id)
    count = await apply_pending_mappings(db, session, assessment, current_user, min_confidence)
    await db.commit()

    return {"applied": count, "session_id": str(session_id)}


@router.get("/sessions/{session_id}/turns")
async def get_turns(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ComplianceChatTurn)
        .where(ComplianceChatTurn.session_id == session_id)
        .order_by(ComplianceChatTurn.turn_index)
    )
    turns = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "role": t.role,
            "content": t.content,
            "turn_index": t.turn_index,
            "control_ids": t.control_ids,
            "extracted_params": t.extracted_params,
            "created_at": t.created_at.isoformat(),
        }
        for t in turns
    ]


# ── Chat Question config endpoints ────────────────────────────────────────────

@router.get("/questions")
async def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import func as sqlfunc
    total = await db.scalar(select(sqlfunc.count()).select_from(ControlChatQuestion))
    result = await db.execute(
        select(ControlChatQuestion)
        .order_by(ControlChatQuestion.question_priority)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    # Enrich with control name
    enriched = []
    for cq in items:
        ctrl = await db.get(ControlDefinition, cq.control_id)
        d = _cq_dict(cq)
        d["control_name"] = ctrl.name if ctrl else "–"
        d["control_slug"] = ctrl.slug if ctrl else "–"
        enriched.append(d)

    return {"total": int(total or 0), "page": page, "page_size": page_size, "items": enriched}


@router.get("/questions/{control_id}")
async def get_question(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cq = await db.scalar(
        select(ControlChatQuestion).where(ControlChatQuestion.control_id == control_id)
    )
    if not cq:
        raise HTTPException(404, "No chat question config for this control")
    return _cq_dict(cq)


@router.put("/questions/{control_id}")
async def update_question(
    control_id: uuid.UUID,
    payload: ChatQuestionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cq = await db.scalar(
        select(ControlChatQuestion).where(ControlChatQuestion.control_id == control_id)
    )
    if not cq:
        raise HTTPException(404, "No chat question config for this control")

    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(cq, field, val)
    cq.last_edited_by = current_user.id

    await db.commit()
    return _cq_dict(cq)


@router.post("/seed-questions", status_code=201)
async def run_seed_questions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    created = await seed_chat_questions(db)
    await db.commit()
    return {"created": created, "status": "ok"}
