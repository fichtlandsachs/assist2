# app/routers/conversation_engine.py
"""Conversation Engine API — session management, chat turns, facts, sizing, readiness."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.conversation_engine import (
    ConversationFact,
    ConversationSession,
    DialogProfile,
    PromptTemplate,
    ConversationRule,
)
from app.models.user import User
from app.services.conversation_engine_service import (
    FACT_CATEGORIES,
    ExtractedFact,
    compute_sizing,
    evaluate_readiness,
    extract_facts,
    plan_questions,
    seed_conversation_engine,
)
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation", tags=["conversation-engine"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    organization_id: uuid.UUID
    mode: str = "exploration_mode"
    project_id: Optional[uuid.UUID] = None
    epic_id: Optional[uuid.UUID] = None
    profile_key: Optional[str] = None


class SessionRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    mode: str
    status: str
    protocol_json: dict
    sizing_json: dict
    readiness_json: dict
    messages: list
    facts: list
    asked_question_keys: list
    story_id: Optional[uuid.UUID]
    epic_id: Optional[uuid.UUID]
    project_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatTurnRequest(BaseModel):
    message: str
    stream: bool = True


class FactPatch(BaseModel):
    status: Optional[str] = None  # confirmed | rejected
    value: Optional[str] = None
    confidence: Optional[float] = None


class ModeSwitchRequest(BaseModel):
    mode: str


class LinkArtefactsRequest(BaseModel):
    story_id: Optional[uuid.UUID] = None
    epic_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_session(session_id: uuid.UUID, db: AsyncSession, user: User) -> ConversationSession:
    session = await db.get(ConversationSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session nicht gefunden")
    return session


def _facts_to_summary(facts: list[ConversationFact]) -> str:
    if not facts:
        return "Noch keine Facts extrahiert."
    lines = []
    by_cat: dict[str, list[str]] = {}
    for f in facts:
        if f.status != "rejected":
            by_cat.setdefault(f.category, []).append(f.value[:120])
    for cat, vals in by_cat.items():
        lines.append(f"[{cat}]")
        for v in vals[:3]:
            lines.append(f"  • {v}")
    return "\n".join(lines)


def _build_protocol(facts: list[ConversationFact]) -> dict:
    """Build the living protocol from current facts."""
    protocol: dict[str, Any] = {
        "context": [],
        "user_groups": [],
        "problem": [],
        "benefit": [],
        "scope": [],
        "out_of_scope": [],
        "acceptance_criteria": [],
        "risks": [],
        "compliance": [],
        "dependencies": [],
        "evidence": [],
        "open_questions": [],
    }
    cat_map = {
        "context": "context",
        "user_group": "user_groups",
        "problem": "problem",
        "benefit": "benefit",
        "scope": "scope",
        "out_of_scope": "out_of_scope",
        "acceptance_criterion": "acceptance_criteria",
        "risk": "risks",
        "compliance": "compliance",
        "dependency": "dependencies",
        "evidence": "evidence",
        "open_question": "open_questions",
    }
    for f in facts:
        if f.status == "rejected":
            continue
        key = cat_map.get(f.category)
        if key:
            protocol[key].append({
                "id": str(f.id),
                "value": f.value,
                "confidence": f.confidence,
                "status": f.status,
            })
    return protocol


async def _get_system_prompt(mode: str, context_text: str, db: AsyncSession) -> str:
    key = f"ce_system_{mode}"
    result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.key == key,
            PromptTemplate.is_active == True,
        ).order_by(PromptTemplate.version.desc())
    )
    tpl = result.scalars().first()
    if tpl:
        return tpl.prompt_text.replace("{context}", context_text)
    # Fallback
    return (
        f"Du bist Karl, ein freundlicher Agile Coach. Modus: {mode}\n\n"
        f"Kontext:\n{context_text}"
    )


async def _get_max_questions(db: AsyncSession) -> int:
    result = await db.execute(
        select(ConversationRule).where(
            ConversationRule.key == "rule_max_questions",
            ConversationRule.is_active == True,
        )
    )
    rule = result.scalars().first()
    if rule:
        return int(rule.value_json.get("max", 2))
    return 2


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/seed")
async def seed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Seed built-in Conversation Engine configuration."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403)
    counts = await seed_conversation_engine(db)
    return {"seeded": counts}


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    """Create a new Conversation Engine session."""
    profile_id = None
    if body.profile_key:
        p_result = await db.execute(
            select(DialogProfile).where(DialogProfile.key == body.profile_key)
        )
        profile = p_result.scalars().first()
        if profile:
            profile_id = profile.id
    else:
        # Use default profile
        p_result = await db.execute(
            select(DialogProfile).where(
                DialogProfile.is_default == True,
                DialogProfile.is_active == True,
            )
        )
        profile = p_result.scalars().first()
        if profile:
            profile_id = profile.id

    session = ConversationSession(
        organization_id=body.organization_id,
        created_by_id=current_user.id,
        profile_id=profile_id,
        mode=body.mode,
        project_id=body.project_id,
        epic_id=body.epic_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_read(session, [])


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionRead:
    session = await _get_session(session_id, db, current_user)
    facts_result = await db.execute(
        select(ConversationFact).where(ConversationFact.session_id == session_id)
        .order_by(ConversationFact.created_at)
    )
    facts = facts_result.scalars().all()
    return _session_to_read(session, list(facts))


@router.get("/sessions")
async def list_sessions(
    organization_id: uuid.UUID = Query(...),
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(
        select(ConversationSession)
        .where(ConversationSession.organization_id == organization_id)
        .order_by(ConversationSession.updated_at.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "mode": s.mode,
            "status": s.status,
            "story_id": str(s.story_id) if s.story_id else None,
            "epic_id": str(s.epic_id) if s.epic_id else None,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.post("/sessions/{session_id}/chat")
async def chat_turn(
    session_id: uuid.UUID,
    body: ChatTurnRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Process one chat turn: extract facts, plan questions, stream reply."""
    session = await _get_session(session_id, db, current_user)
    settings = get_settings()

    facts_result = await db.execute(
        select(ConversationFact).where(ConversationFact.session_id == session_id)
    )
    facts = list(facts_result.scalars().all())
    turn_index = len(session.messages)

    # Persist user message immediately
    messages = list(session.messages or [])
    messages.append({
        "role": "user",
        "content": body.message,
        "ts": datetime.now(timezone.utc).isoformat(),
        "turn": turn_index,
    })
    session.messages = messages
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    async def event_stream() -> AsyncIterator[str]:
        nonlocal facts

        # 1. Extract facts from this turn
        new_facts = await extract_facts(body.message, facts, db)
        saved_facts: list[ConversationFact] = []
        for ef in new_facts:
            cf = ConversationFact(
                session_id=session_id,
                category=ef.category,
                value=ef.value,
                confidence=ef.confidence,
                status="detected",
                source_turn=turn_index,
                source_quote=ef.source_quote[:300] if ef.source_quote else None,
            )
            db.add(cf)
            saved_facts.append(cf)
        if saved_facts:
            await db.commit()
            facts = facts + saved_facts

        # 2. Update sizing + readiness (non-blocking)
        sizing = await compute_sizing(facts, db)
        readiness = await evaluate_readiness(facts, db)
        protocol = _build_protocol(facts)

        session.sizing_json = {
            "score": sizing.score,
            "size_label": sizing.size_label,
            "stories_suggested": sizing.stories_suggested,
            "recommendation": sizing.recommendation,
            "breakdown": sizing.breakdown,
        }
        session.readiness_json = {
            "status": readiness.status,
            "score": readiness.score,
            "missing": readiness.missing,
            "blockers": readiness.blockers,
        }
        session.protocol_json = protocol

        # 3. Plan next questions (story_mode only)
        question_texts: list[str] = []
        if session.mode == "story_mode":
            max_q = await _get_max_questions(db)
            next_questions = await plan_questions(session, facts, db, max_q)
            question_texts = [q.question_text for q in next_questions]
            # Mark as asked
            asked = list(session.asked_question_keys or [])
            for q in next_questions:
                if q.key not in asked:
                    asked.append(q.key)
            session.asked_question_keys = asked

        await db.commit()

        # 4. Build system prompt with full context
        fact_reuse_hints = ""
        if facts:
            confirmed = [f for f in facts if f.status in ("confirmed", "detected") and f.confidence >= 0.5]
            if confirmed:
                fact_reuse_hints = "\n\nBereits bekannte Informationen (NICHT nochmal fragen):\n" + "\n".join(
                    f"• [{f.category}] {f.value[:100]}"
                    for f in confirmed[:8]
                )

        context_text = (
            f"Modus: {session.mode}\n"
            f"Story-Gr\u00f6\u00dfe: {sizing.size_label} (Score: {sizing.score}/10, Empfehlung: {sizing.recommendation})\n"
            f"Readiness: {readiness.status} ({readiness.score}%)\n"
            f"{fact_reuse_hints}"
        )
        system_prompt = await _get_system_prompt(session.mode, context_text, db)

        # Add question injection for story_mode
        question_injection = ""
        if question_texts:
            question_injection = (
                "\n\nDie n\u00e4chsten wichtigen Informationen die fehlen:\n"
                + "\n".join(f"- {q}" for q in question_texts)
                + "\n\nW\u00e4hle daraus maximal 1-2 die am besten zum Gespr\u00e4chsfluss passen. Stelle sie als nat\u00fcrliche Fragen, nicht als Liste."
            )

        # Send sizing/readiness update as SSE metadata before streaming text
        meta_event = json.dumps({
            "type": "meta",
            "sizing": session.sizing_json,
            "readiness": session.readiness_json,
            "protocol": session.protocol_json,
            "new_facts": [
                {"category": f.category, "value": f.value[:100], "confidence": f.confidence}
                for f in saved_facts
            ],
        })
        yield f"data: [META]{meta_event}\n\n"

        # 5. Stream LLM response
        history_msgs = [
            {"role": m["role"], "content": m["content"]}
            for m in (session.messages or [])[:-1]  # exclude current user msg
        ][-10:]  # last 10 turns

        llm_messages = [
            {"role": "system", "content": system_prompt + question_injection}
        ] + history_msgs + [
            {"role": "user", "content": body.message}
        ]

        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{settings.LITELLM_URL}/v1",
        )

        full_response = ""
        try:
            stream = await oai.chat.completions.create(
                model="ionos-quality",
                max_tokens=800,
                messages=llm_messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if not delta:
                    continue
                full_response += delta
                yield f"data: {delta.replace(chr(10), chr(10) + 'data: ')}\n\n"
        except Exception as exc:
            logger.error("CE LLM stream error: %s", exc)
            yield "data: [Entschuldigung, es gab einen Fehler. Bitte nochmal versuchen.]\n\n"
            return

        # 6. Persist assistant message
        msgs = list(session.messages or [])
        msgs.append({
            "role": "assistant",
            "content": full_response,
            "ts": datetime.now(timezone.utc).isoformat(),
            "turn": turn_index,
        })
        session.messages = msgs
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions/{session_id}/facts")
async def list_facts(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    result = await db.execute(
        select(ConversationFact).where(ConversationFact.session_id == session_id)
        .order_by(ConversationFact.created_at)
    )
    return [_fact_to_dict(f) for f in result.scalars().all()]


@router.patch("/sessions/{session_id}/facts/{fact_id}")
async def patch_fact(
    session_id: uuid.UUID,
    fact_id: uuid.UUID,
    body: FactPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Confirm, reject or correct a fact."""
    fact = await db.get(ConversationFact, fact_id)
    if not fact or fact.session_id != session_id:
        raise HTTPException(status_code=404)
    if body.status:
        fact.status = body.status
    if body.value:
        fact.value = body.value
    if body.confidence is not None:
        fact.confidence = body.confidence
    fact.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _fact_to_dict(fact)


@router.post("/sessions/{session_id}/switch-mode")
async def switch_mode(
    session_id: uuid.UUID,
    body: ModeSwitchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    valid_modes = {"exploration_mode", "story_mode", "review_mode", "correction_mode"}
    if body.mode not in valid_modes:
        raise HTTPException(status_code=422, detail=f"Invalid mode. Valid: {valid_modes}")
    session = await _get_session(session_id, db, current_user)
    session.mode = body.mode
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"mode": session.mode, "session_id": str(session_id)}


@router.post("/sessions/{session_id}/link")
async def link_artefacts(
    session_id: uuid.UUID,
    body: LinkArtefactsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Link a session to a story, epic or project."""
    session = await _get_session(session_id, db, current_user)
    if body.story_id is not None:
        session.story_id = body.story_id
    if body.epic_id is not None:
        session.epic_id = body.epic_id
    if body.project_id is not None:
        session.project_id = body.project_id
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {
        "story_id": str(session.story_id) if session.story_id else None,
        "epic_id": str(session.epic_id) if session.epic_id else None,
        "project_id": str(session.project_id) if session.project_id else None,
    }


@router.get("/sessions/{session_id}/sizing")
async def get_sizing(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = await _get_session(session_id, db, current_user)
    if not session.sizing_json:
        facts_result = await db.execute(
            select(ConversationFact).where(ConversationFact.session_id == session_id)
        )
        facts = list(facts_result.scalars().all())
        sizing = await compute_sizing(facts, db)
        return {
            "score": sizing.score,
            "size_label": sizing.size_label,
            "stories_suggested": sizing.stories_suggested,
            "recommendation": sizing.recommendation,
            "breakdown": sizing.breakdown,
        }
    return session.sizing_json


@router.get("/sessions/{session_id}/readiness")
async def get_readiness(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = await _get_session(session_id, db, current_user)
    if not session.readiness_json:
        facts_result = await db.execute(
            select(ConversationFact).where(ConversationFact.session_id == session_id)
        )
        facts = list(facts_result.scalars().all())
        readiness = await evaluate_readiness(facts, db)
        return {
            "status": readiness.status,
            "score": readiness.score,
            "missing": readiness.missing,
            "blockers": readiness.blockers,
        }
    return session.readiness_json


@router.post("/sessions/{session_id}/close")
async def close_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = await _get_session(session_id, db, current_user)
    session.status = "closed"
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "closed"}


# ── Serializers ───────────────────────────────────────────────────────────────

def _fact_to_dict(f: ConversationFact) -> dict:
    return {
        "id": str(f.id),
        "session_id": str(f.session_id),
        "category": f.category,
        "value": f.value,
        "confidence": f.confidence,
        "status": f.status,
        "source_turn": f.source_turn,
        "source_quote": f.source_quote,
        "created_at": f.created_at.isoformat(),
    }


def _session_to_read(session: ConversationSession, facts: list[ConversationFact]) -> SessionRead:
    return SessionRead(
        id=session.id,
        organization_id=session.organization_id,
        mode=session.mode,
        status=session.status,
        protocol_json=session.protocol_json or {},
        sizing_json=session.sizing_json or {},
        readiness_json=session.readiness_json or {},
        messages=session.messages or [],
        facts=[_fact_to_dict(f) for f in facts],
        asked_question_keys=session.asked_question_keys or [],
        story_id=session.story_id,
        epic_id=session.epic_id,
        project_id=session.project_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
