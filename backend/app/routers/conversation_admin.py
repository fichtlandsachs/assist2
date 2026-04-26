"""Conversation Admin API Router - Superadmin configuration endpoints."""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.conversation_engine import (
    DialogProfile,
    QuestionBlock,
    AnswerSignal,
    PromptTemplate,
    ConversationRule,
    StorySizingRule,
    ReadinessRule,
    ConversationProtocolArea,
)
from app.routers.superadmin import require_superuser
from app.models.user import User

router = APIRouter(
    prefix="/api/v1/superadmin/conversation-engine",
    tags=["conversation-admin"],
    dependencies=[Depends(require_superuser)],
)


# ── Dialog Profiles ───────────────────────────────────────────────────────────

@router.get("/profiles")
async def list_profiles(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all dialog profiles."""
    result = await db.execute(select(DialogProfile))
    profiles = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "key": p.key,
            "name": p.name,
            "description": p.description,
            "mode": p.mode,
            "tone": p.tone,
            "isDefault": p.is_default,
            "isActive": p.is_active,
            "configJson": p.config_json,
            "version": p.version,
        }
        for p in profiles
    ]


@router.post("/profiles")
async def create_profile(
    data: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create a new dialog profile."""
    profile = DialogProfile(
        key=data["key"],
        name=data["name"],
        description=data.get("description"),
        mode=data.get("mode", "story_mode"),
        tone=data.get("tone", "friendly"),
        is_default=data.get("is_default", False),
        is_active=data.get("is_active", True),
        config_json=data.get("config_json", {}),
    )
    db.add(profile)
    await db.flush()

    return {
        "id": str(profile.id),
        "key": profile.key,
        "name": profile.name,
    }


@router.patch("/profiles/{profile_id}")
async def update_profile(
    profile_id: uuid.UUID,
    data: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Update a dialog profile."""
    result = await db.execute(
        select(DialogProfile).where(DialogProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    for field in ["name", "description", "mode", "tone", "is_default", "is_active", "config_json"]:
        if field in data:
            setattr(profile, field, data[field])

    await db.flush()
    return {"id": str(profile.id), "message": "Updated"}


# ── Question Blocks ────────────────────────────────────────────────────────────

@router.get("/question-blocks")
async def list_question_blocks(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """List all question blocks."""
    query = select(QuestionBlock)
    if category:
        query = query.where(QuestionBlock.category == category)

    result = await db.execute(query)
    blocks = result.scalars().all()

    return [
        {
            "id": str(b.id),
            "key": b.key,
            "category": b.category,
            "label": b.label,
            "questionText": b.question_text,
            "priority": b.priority,
            "isRequired": b.is_required,
            "isActive": b.is_active,
        }
        for b in blocks
    ]


@router.post("/question-blocks")
async def create_question_block(
    data: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create a new question block."""
    block = QuestionBlock(
        key=data["key"],
        category=data["category"],
        label=data["label"],
        question_text=data["question_text"],
        follow_up_text=data.get("follow_up_text"),
        priority=data.get("priority", 5),
        is_required=data.get("is_required", False),
        is_active=data.get("is_active", True),
    )
    db.add(block)
    await db.flush()

    return {"id": str(block.id), "key": block.key}


# ── Answer Signals ───────────────────────────────────────────────────────────

@router.get("/answer-signals")
async def list_answer_signals(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all answer signals."""
    result = await db.execute(select(AnswerSignal))
    signals = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "key": s.key,
            "factCategory": s.fact_category,
            "patternType": s.pattern_type,
            "pattern": s.pattern,
            "confidenceBoost": s.confidence_boost,
            "isActive": s.is_active,
        }
        for s in signals
    ]


@router.post("/answer-signals")
async def create_answer_signal(
    data: dict[str, Any],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Create a new answer signal."""
    signal = AnswerSignal(
        key=data["key"],
        fact_category=data["fact_category"],
        pattern_type=data.get("pattern_type", "keyword"),
        pattern=data["pattern"],
        confidence_boost=data.get("confidence_boost", 0.1),
        is_active=data.get("is_active", True),
    )
    db.add(signal)
    await db.flush()

    return {"id": str(signal.id), "key": signal.key}


# ── Conversation Rules ────────────────────────────────────────────────────────

@router.get("/rules")
async def list_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, list[dict[str, Any]]]:
    """List all conversation rules (conversation, sizing, readiness)."""
    # Get all rule types
    conv_result = await db.execute(select(ConversationRule))
    sizing_result = await db.execute(select(StorySizingRule))
    readiness_result = await db.execute(select(ReadinessRule))

    return {
        "conversationRules": [
            {
                "id": str(r.id),
                "key": r.key,
                "ruleType": r.rule_type,
                "label": r.label,
                "isActive": r.is_active,
            }
            for r in conv_result.scalars().all()
        ],
        "sizingRules": [
            {
                "id": str(r.id),
                "key": r.key,
                "label": r.label,
                "dimension": r.dimension,
                "weight": r.weight,
                "isActive": r.is_active,
            }
            for r in sizing_result.scalars().all()
        ],
        "readinessRules": [
            {
                "id": str(r.id),
                "key": r.key,
                "label": r.label,
                "requiredCategory": r.required_category,
                "isBlocking": r.is_blocking,
                "weight": r.weight,
                "isActive": r.is_active,
            }
            for r in readiness_result.scalars().all()
        ],
    }


# ── Protocol Areas ───────────────────────────────────────────────────────────

@router.get("/protocol-areas")
async def list_protocol_areas(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all protocol areas."""
    result = await db.execute(
        select(ConversationProtocolArea).where(
            ConversationProtocolArea.org_id.is_(None)
        ).order_by(ConversationProtocolArea.sort_order)
    )
    areas = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "key": a.key,
            "displayName": a.display_name,
            "description": a.description,
            "helpText": a.help_text,
            "sortOrder": a.sort_order,
            "isRequired": a.is_required,
            "isActive": a.is_active,
        }
        for a in areas
    ]


# ── Config Summary ────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """Get complete configuration summary."""
    profiles_result = await db.execute(select(DialogProfile))
    blocks_result = await db.execute(select(QuestionBlock))
    signals_result = await db.execute(select(AnswerSignal))
    areas_result = await db.execute(
        select(ConversationProtocolArea).where(
            ConversationProtocolArea.org_id.is_(None)
        )
    )

    return {
        "profiles": len(profiles_result.scalars().all()),
        "questionBlocks": len(blocks_result.scalars().all()),
        "answerSignals": len(signals_result.scalars().all()),
        "protocolAreas": len(areas_result.scalars().all()),
    }
