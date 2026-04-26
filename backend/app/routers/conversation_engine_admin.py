# app/routers/conversation_engine_admin.py
"""Superadmin API for Conversation Engine configuration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.conversation_engine import (
    AnswerSignal,
    ConversationFact,
    ConversationRule,
    ConversationSession,
    DialogProfile,
    ObserverProposal,
    PromptTemplate,
    QuestionBlock,
    ReadinessRule,
    StorySizingRule,
)
from app.models.user import User
from app.routers.superadmin import require_superuser

router = APIRouter(prefix="/superadmin/conversation-engine", tags=["conversation-engine-admin"])


# ── Dialog Profiles ───────────────────────────────────────────────────────────

class DialogProfileWrite(BaseModel):
    key: str
    name: str
    description: Optional[str] = None
    mode: str = "story_mode"
    tone: str = "friendly"
    is_default: bool = False
    is_active: bool = True
    config_json: dict = {}


@router.get("/profiles")
async def list_profiles(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(DialogProfile).order_by(DialogProfile.name))
    return [_profile_dict(p) for p in r.scalars().all()]


@router.post("/profiles", status_code=status.HTTP_201_CREATED)
async def create_profile(body: DialogProfileWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    if body.is_default:
        await db.execute(select(DialogProfile))  # clear others? kept as is; UI handles
    p = DialogProfile(**body.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _profile_dict(p)


@router.patch("/profiles/{profile_id}")
async def patch_profile(profile_id: uuid.UUID, body: DialogProfileWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    p = await db.get(DialogProfile, profile_id)
    if not p:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    p.version += 1
    p.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _profile_dict(p)


# ── Question Blocks ───────────────────────────────────────────────────────────

class QuestionBlockWrite(BaseModel):
    key: str
    category: str
    label: str
    question_text: str
    follow_up_text: Optional[str] = None
    priority: int = 5
    is_required: bool = False
    is_active: bool = True
    condition_json: dict = {}


@router.get("/question-blocks")
async def list_question_blocks(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(QuestionBlock).order_by(QuestionBlock.priority, QuestionBlock.category))
    return [_qblock_dict(b) for b in r.scalars().all()]


@router.post("/question-blocks", status_code=status.HTTP_201_CREATED)
async def create_question_block(body: QuestionBlockWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    b = QuestionBlock(**body.model_dump())
    db.add(b)
    await db.commit()
    await db.refresh(b)
    return _qblock_dict(b)


@router.patch("/question-blocks/{block_id}")
async def patch_question_block(block_id: uuid.UUID, body: QuestionBlockWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    b = await db.get(QuestionBlock, block_id)
    if not b:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    b.version += 1
    b.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _qblock_dict(b)


@router.delete("/question-blocks/{block_id}")
async def delete_question_block(block_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    b = await db.get(QuestionBlock, block_id)
    if not b:
        raise HTTPException(404)
    b.is_active = False
    await db.commit()
    return {"status": "deactivated"}


# ── Answer Signals ────────────────────────────────────────────────────────────

class AnswerSignalWrite(BaseModel):
    key: str
    fact_category: str
    pattern_type: str = "keyword"
    pattern: str
    confidence_boost: float = 0.1
    is_active: bool = True


@router.get("/answer-signals")
async def list_signals(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(AnswerSignal).order_by(AnswerSignal.fact_category))
    return [_signal_dict(s) for s in r.scalars().all()]


@router.post("/answer-signals", status_code=status.HTTP_201_CREATED)
async def create_signal(body: AnswerSignalWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    s = AnswerSignal(**body.model_dump())
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _signal_dict(s)


@router.patch("/answer-signals/{signal_id}")
async def patch_signal(signal_id: uuid.UUID, body: AnswerSignalWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    s = await db.get(AnswerSignal, signal_id)
    if not s:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _signal_dict(s)


# ── Prompt Templates ──────────────────────────────────────────────────────────

class PromptTemplateWrite(BaseModel):
    key: str
    mode: str
    phase: str
    prompt_text: str
    is_active: bool = True


@router.get("/prompt-templates")
async def list_templates(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(
        select(PromptTemplate).order_by(PromptTemplate.key, desc(PromptTemplate.version))
    )
    return [_template_dict(t) for t in r.scalars().all()]


@router.post("/prompt-templates", status_code=status.HTTP_201_CREATED)
async def create_template(body: PromptTemplateWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    # Auto-increment version
    existing = await db.execute(
        select(PromptTemplate).where(PromptTemplate.key == body.key).order_by(desc(PromptTemplate.version))
    )
    latest = existing.scalars().first()
    next_version = (latest.version + 1) if latest else 1
    t = PromptTemplate(**body.model_dump(), version=next_version)
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return _template_dict(t)


# ── Conversation Rules ────────────────────────────────────────────────────────

class ConversationRuleWrite(BaseModel):
    key: str
    rule_type: str
    label: str
    value_json: dict = {}
    is_active: bool = True


@router.get("/rules")
async def list_rules(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(ConversationRule).order_by(ConversationRule.rule_type))
    return [_rule_dict(r_) for r_ in r.scalars().all()]


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(body: ConversationRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = ConversationRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _rule_dict(rule)


@router.patch("/rules/{rule_id}")
async def patch_rule(rule_id: uuid.UUID, body: ConversationRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = await db.get(ConversationRule, rule_id)
    if not rule:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    rule.version += 1
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _rule_dict(rule)


# ── Sizing Rules ──────────────────────────────────────────────────────────────

class SizingRuleWrite(BaseModel):
    key: str
    label: str
    dimension: str
    weight: float = 1.0
    thresholds_json: dict = {}
    is_active: bool = True


@router.get("/sizing-rules")
async def list_sizing_rules(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(StorySizingRule).order_by(StorySizingRule.dimension))
    return [_sizing_dict(s) for s in r.scalars().all()]


@router.post("/sizing-rules", status_code=status.HTTP_201_CREATED)
async def create_sizing_rule(body: SizingRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = StorySizingRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _sizing_dict(rule)


@router.patch("/sizing-rules/{rule_id}")
async def patch_sizing_rule(rule_id: uuid.UUID, body: SizingRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = await db.get(StorySizingRule, rule_id)
    if not rule:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    rule.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _sizing_dict(rule)


# ── Readiness Rules ───────────────────────────────────────────────────────────

class ReadinessRuleWrite(BaseModel):
    key: str
    label: str
    required_category: str
    min_confidence: float = 0.6
    is_blocking: bool = True
    weight: float = 1.0
    is_active: bool = True


@router.get("/readiness-rules")
async def list_readiness_rules(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(ReadinessRule).order_by(ReadinessRule.required_category))
    return [_readiness_dict(r_) for r_ in r.scalars().all()]


@router.post("/readiness-rules", status_code=status.HTTP_201_CREATED)
async def create_readiness_rule(body: ReadinessRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = ReadinessRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return _readiness_dict(rule)


@router.patch("/readiness-rules/{rule_id}")
async def patch_readiness_rule(rule_id: uuid.UUID, body: ReadinessRuleWrite, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    rule = await db.get(ReadinessRule, rule_id)
    if not rule:
        raise HTTPException(404)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(rule, k, v)
    await db.commit()
    return _readiness_dict(rule)


# ── Observer Proposals ────────────────────────────────────────────────────────

@router.get("/observer-proposals")
async def list_proposals(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> list[dict]:
    r = await db.execute(select(ObserverProposal).order_by(desc(ObserverProposal.created_at)))
    return [_proposal_dict(p) for p in r.scalars().all()]


@router.post("/observer-proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_superuser),
) -> dict:
    p = await db.get(ObserverProposal, proposal_id)
    if not p:
        raise HTTPException(404)
    if p.status not in ("draft",):
        raise HTTPException(422, detail="Nur draft-Proposals k\u00f6nnen genehmigt werden")
    p.status = "approved"
    p.approved_by_id = admin.id
    p.approved_at = datetime.now(timezone.utc)
    p.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _proposal_dict(p)


@router.post("/observer-proposals/{proposal_id}/validate")
async def start_validation(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    p = await db.get(ObserverProposal, proposal_id)
    if not p:
        raise HTTPException(404)
    if p.status != "approved":
        raise HTTPException(422, detail="Nur approved-Proposals k\u00f6nnen validiert werden")
    p.status = "active_validation"
    p.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _proposal_dict(p)


@router.post("/observer-proposals/{proposal_id}/rollback")
async def rollback_proposal(proposal_id: uuid.UUID, db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    p = await db.get(ObserverProposal, proposal_id)
    if not p:
        raise HTTPException(404)
    p.status = "rollback"
    p.validation_result = "rollback"
    p.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return _proposal_dict(p)


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics/overview")
async def analytics_overview(db: AsyncSession = Depends(get_db), _: User = Depends(require_superuser)) -> dict:
    from sqlalchemy import func, text
    sessions_r = await db.execute(select(func.count()).select_from(ConversationSession))
    facts_r = await db.execute(select(func.count()).select_from(ConversationFact))
    confirmed_r = await db.execute(
        select(func.count()).select_from(ConversationFact).where(ConversationFact.status == "confirmed")
    )
    proposals_r = await db.execute(
        select(func.count()).select_from(ObserverProposal).where(ObserverProposal.status == "draft")
    )
    return {
        "total_sessions": sessions_r.scalar() or 0,
        "total_facts": facts_r.scalar() or 0,
        "confirmed_facts": confirmed_r.scalar() or 0,
        "pending_proposals": proposals_r.scalar() or 0,
    }


# ── Serializers ───────────────────────────────────────────────────────────────

def _profile_dict(p: DialogProfile) -> dict:
    return {"id": str(p.id), "key": p.key, "name": p.name, "description": p.description,
            "mode": p.mode, "tone": p.tone, "is_default": p.is_default, "is_active": p.is_active,
            "config_json": p.config_json, "version": p.version}


def _qblock_dict(b: QuestionBlock) -> dict:
    return {"id": str(b.id), "key": b.key, "category": b.category, "label": b.label,
            "question_text": b.question_text, "follow_up_text": b.follow_up_text,
            "priority": b.priority, "is_required": b.is_required, "is_active": b.is_active,
            "condition_json": b.condition_json, "version": b.version}


def _signal_dict(s: AnswerSignal) -> dict:
    return {"id": str(s.id), "key": s.key, "fact_category": s.fact_category,
            "pattern_type": s.pattern_type, "pattern": s.pattern,
            "confidence_boost": s.confidence_boost, "is_active": s.is_active}


def _template_dict(t: PromptTemplate) -> dict:
    return {"id": str(t.id), "key": t.key, "mode": t.mode, "phase": t.phase,
            "prompt_text": t.prompt_text, "is_active": t.is_active, "version": t.version}


def _rule_dict(r: ConversationRule) -> dict:
    return {"id": str(r.id), "key": r.key, "rule_type": r.rule_type, "label": r.label,
            "value_json": r.value_json, "is_active": r.is_active, "version": r.version}


def _sizing_dict(s: StorySizingRule) -> dict:
    return {"id": str(s.id), "key": s.key, "label": s.label, "dimension": s.dimension,
            "weight": s.weight, "thresholds_json": s.thresholds_json, "is_active": s.is_active}


def _readiness_dict(r: ReadinessRule) -> dict:
    return {"id": str(r.id), "key": r.key, "label": r.label, "required_category": r.required_category,
            "min_confidence": r.min_confidence, "is_blocking": r.is_blocking,
            "weight": r.weight, "is_active": r.is_active}


def _proposal_dict(p: ObserverProposal) -> dict:
    return {"id": str(p.id), "proposal_type": p.proposal_type, "title": p.title,
            "description": p.description, "rationale": p.rationale,
            "suggested_config": p.suggested_config, "status": p.status,
            "metrics_before": p.metrics_before, "metrics_after": p.metrics_after,
            "validation_result": p.validation_result,
            "approved_by_id": str(p.approved_by_id) if p.approved_by_id else None,
            "approved_at": p.approved_at.isoformat() if p.approved_at else None,
            "created_at": p.created_at.isoformat()}
