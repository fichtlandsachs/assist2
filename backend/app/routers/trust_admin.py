# app/routers/trust_admin.py
"""
Admin Router: Trust Engine + Freigabecenter + Retrieval Test Lab.

Pflichtbereiche (spec §4):
  - Trust Profile Editor  (GET/PUT/POST /trust/profiles/*)
  - Trust Rules summary   (GET /trust/rules)
  - Freigabecenter        (GET/POST /admin/approvals/*)
  - Retrieval Test Lab    (POST /admin/retrieval-test)
  - Audit Log             (GET /admin/audit)

All mutating endpoints require org_admin or superadmin.
All actions are audit-logged.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.external_source import ExternalSource
from app.models.process_suggestion import ProcessMappingSuggestion, SuggestionStatus
from app.models.trust_profile import TrustProfile, TrustClass, SourceCategory
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.audit_service import log_trust_change, log_action
from app.services.trust_engine import compute_composite_score, default_profile_for_category

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin-trust"])


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _require_admin(user: User) -> User:
    """Raise 403 if not org_admin or superadmin."""
    from app.core.permissions import is_admin
    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


# ── Schemas ───────────────────────────────────────────────────────────────────

class TrustProfileRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_key: str = ""
    display_name: str = ""
    trust_class: str
    source_category: str
    authority_score: float
    standard_score: float
    context_score: float
    freshness_score: float
    governance_score: float
    traceability_score: float
    composite_score: float
    eligibility: dict
    admin_note: Optional[str] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class TrustProfileUpdate(BaseModel):
    trust_class: Optional[str] = None
    source_category: Optional[str] = None
    authority_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    standard_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    context_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    freshness_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    governance_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    traceability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    eligibility: Optional[dict] = None
    admin_note: Optional[str] = None

    @field_validator("trust_class")
    @classmethod
    def validate_trust_class(cls, v: str) -> str:
        if v not in TrustClass.__members__:
            raise ValueError(f"Invalid trust_class: {v}. Valid: {list(TrustClass.__members__)}")
        return v

    @field_validator("source_category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        if v not in SourceCategory.__members__:
            raise ValueError(f"Invalid source_category: {v}")
        return v


class TrustProfileCreate(TrustProfileUpdate):
    source_id: uuid.UUID
    trust_class: str = TrustClass.V3.value
    source_category: str = SourceCategory.internal_approved.value


class RetrievalTestRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=1000)
    org_id: uuid.UUID
    source_systems: Optional[list[str]] = None
    canonical_types: Optional[list[str]] = None


class RetrievalTestResult(BaseModel):
    query: str
    mode: str
    chunk_count: int
    primary_count: int
    has_conflicts: bool
    conflict_count: int
    guardrail_warnings: list[str]
    top_chunks: list[dict]
    conflicts: list[dict]


class ApprovalDecision(BaseModel):
    suggestion_id: uuid.UUID
    action: Literal["confirm", "reject", "reassign", "merge", "new_process"]
    admin_note: Optional[str] = None
    target_node_id: Optional[uuid.UUID] = None
    new_process_name: Optional[str] = None


# ── Trust Profile Endpoints ───────────────────────────────────────────────────

@router.get("/admin/trust/profiles", response_model=list[TrustProfileRead])
async def list_trust_profiles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List all trust profiles with their associated source info."""
    _require_admin(current_user)
    result = await db.execute(
        select(TrustProfile, ExternalSource)
        .join(ExternalSource, ExternalSource.id == TrustProfile.source_id)
        .offset(skip)
        .limit(limit)
    )
    rows = result.all()
    profiles = []
    for tp, src in rows:
        data = TrustProfileRead.model_validate(tp)
        data.source_key = src.source_key
        data.display_name = src.display_name
        profiles.append(data)
    return profiles


@router.get("/admin/trust/profiles/{source_id}", response_model=TrustProfileRead)
async def get_trust_profile(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    tp = await db.scalar(
        select(TrustProfile).where(TrustProfile.source_id == source_id)
    )
    if tp is None:
        raise HTTPException(status_code=404, detail="Trust profile not found")
    src = await db.get(ExternalSource, source_id)
    data = TrustProfileRead.model_validate(tp)
    if src:
        data.source_key = src.source_key
        data.display_name = src.display_name
    return data


@router.post("/admin/trust/profiles", response_model=TrustProfileRead, status_code=201)
async def create_trust_profile(
    payload: TrustProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create trust profile for a source. Uses category defaults for unset dimensions."""
    _require_admin(current_user)

    # Check source exists
    src = await db.get(ExternalSource, payload.source_id)
    if src is None:
        raise HTTPException(status_code=404, detail="ExternalSource not found")

    # Check not already exists
    existing = await db.scalar(
        select(TrustProfile).where(TrustProfile.source_id == payload.source_id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Trust profile already exists for this source")

    # Start from category defaults
    defaults = default_profile_for_category(payload.source_category or SourceCategory.internal_approved)
    update_data = payload.model_dump(exclude_none=True, exclude={"source_id"})
    merged = {**defaults, **update_data}

    tp = TrustProfile(
        source_id=payload.source_id,
        trust_class=merged.get("trust_class", TrustClass.V3.value),
        source_category=merged.get("source_category", SourceCategory.internal_approved.value),
        authority_score=merged.get("authority_score", 0.5),
        standard_score=merged.get("standard_score", 0.5),
        context_score=merged.get("context_score", 0.5),
        freshness_score=merged.get("freshness_score", 0.5),
        governance_score=merged.get("governance_score", 0.5),
        traceability_score=merged.get("traceability_score", 0.5),
        eligibility=merged.get("eligibility", {}),
        admin_note=payload.admin_note,
    )
    tp.composite_score = compute_composite_score({
        "authority_score":    tp.authority_score,
        "standard_score":     tp.standard_score,
        "context_score":      tp.context_score,
        "freshness_score":    tp.freshness_score,
        "governance_score":   tp.governance_score,
        "traceability_score": tp.traceability_score,
    })

    db.add(tp)
    await db.flush()

    # Determine org_id from source
    org_id = getattr(src, "org_id", None) or uuid.UUID(int=0)
    await log_trust_change(db, org_id, src.id, {}, tp.__dict__, actor_id=current_user.id, is_create=True)
    await db.commit()
    await db.refresh(tp)

    data = TrustProfileRead.model_validate(tp)
    data.source_key = src.source_key
    data.display_name = src.display_name
    return data


@router.put("/admin/trust/profiles/{source_id}", response_model=TrustProfileRead)
async def update_trust_profile(
    source_id: uuid.UUID,
    payload: TrustProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    tp = await db.scalar(
        select(TrustProfile).where(TrustProfile.source_id == source_id)
    )
    if tp is None:
        raise HTTPException(status_code=404, detail="Trust profile not found")

    old_snapshot = {
        "trust_class": tp.trust_class,
        "source_category": tp.source_category,
        "composite_score": tp.composite_score,
    }

    update_data = payload.model_dump(exclude_none=True)
    for field_name, val in update_data.items():
        setattr(tp, field_name, val)

    tp.composite_score = compute_composite_score({
        "authority_score":    tp.authority_score,
        "standard_score":     tp.standard_score,
        "context_score":      tp.context_score,
        "freshness_score":    tp.freshness_score,
        "governance_score":   tp.governance_score,
        "traceability_score": tp.traceability_score,
    })
    tp.reviewed_by = current_user.id
    tp.reviewed_at = datetime.now(timezone.utc)

    src = await db.get(ExternalSource, source_id)
    org_id = getattr(src, "org_id", None) or uuid.UUID(int=0)
    await log_trust_change(db, org_id, source_id, old_snapshot, {"trust_class": tp.trust_class}, actor_id=current_user.id)
    await db.commit()
    await db.refresh(tp)

    data = TrustProfileRead.model_validate(tp)
    if src:
        data.source_key = src.source_key
        data.display_name = src.display_name
    return data


@router.get("/admin/trust/rules")
async def get_trust_rules(
    current_user: User = Depends(get_current_user),
):
    """Return the hard-coded trust rules as a human-readable summary."""
    _require_admin(current_user)
    return {
        "scoring_weights": {
            "semantic":   0.35,
            "keyword":    0.15,
            "entity":     0.15,
            "trust":      0.20,
            "context":    0.10,
            "freshness":  0.05,
        },
        "hard_rules": [
            {
                "id": "HR-001",
                "rule": "Draft sources ALWAYS excluded in production mode",
                "applies_to": "internal_draft",
                "overridable": False,
            },
            {
                "id": "HR-002",
                "rule": "Community sources NEVER eligible for security or compliance queries",
                "applies_to": "community",
                "contexts": ["security", "compliance"],
                "overridable": False,
            },
            {
                "id": "HR-003",
                "rule": "Architecture queries require ≥2 sources with trust_class ≥ V3",
                "applies_to": "architecture",
                "overridable": False,
            },
            {
                "id": "HR-004",
                "rule": "Manufacturer source wins product standard conflicts",
                "applies_to": "conflict_resolution",
                "overridable": False,
            },
            {
                "id": "HR-005",
                "rule": "Internal approved source wins internal process conflicts",
                "applies_to": "conflict_resolution",
                "overridable": False,
            },
        ],
        "source_categories": [
            {"value": c.value, "description": CATEGORY_DESCRIPTIONS.get(c.value, "")}
            for c in SourceCategory
        ],
        "trust_classes": [
            {"value": tc.value, "description": TC_DESCRIPTIONS.get(tc.value, "")}
            for tc in TrustClass
        ],
    }


CATEGORY_DESCRIPTIONS = {
    "manufacturer":       "Hersteller-Dokumentation — führend für Produktstandards",
    "internal_approved":  "Freigegebene interne Dokumentation — führend für Prozesse",
    "internal_draft":     "Interner Entwurf — nicht produktiv verfügbar",
    "partner":            "Partner-Dokumentation — unterstützend",
    "community":          "Community — nur unterstützend, nicht für Security/Compliance",
    "standard_norm":      "Norm/Standard — methodisch stark, hohe Authority",
}

TC_DESCRIPTIONS = {
    "V5": "Verbindlich — höchste Autorität (Hersteller, Norm)",
    "V4": "Genehmigt offiziell",
    "V3": "Geprüft intern",
    "V2": "Entwurf / ungeprüft intern",
    "V1": "Community / nur unterstützend",
}


# ── Freigabecenter (Approval) Endpoints ──────────────────────────────────────

@router.get("/admin/approvals/suggestions")
async def list_pending_suggestions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: Optional[uuid.UUID] = Query(None),
    status_filter: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
):
    """List process mapping suggestions pending admin review."""
    _require_admin(current_user)

    stmt = select(ProcessMappingSuggestion)
    if status_filter != "all":
        stmt = stmt.where(ProcessMappingSuggestion.status == status_filter)
    if org_id:
        stmt = stmt.where(ProcessMappingSuggestion.org_id == org_id)
    stmt = stmt.order_by(ProcessMappingSuggestion.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    suggestions = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "org_id": str(s.org_id),
            "process_name": s.process_name,
            "detected_context": s.detected_context,
            "suggested_node_id": str(s.suggested_node_id) if s.suggested_node_id else None,
            "suggested_node_title": s.suggested_node_title,
            "confidence_score": s.confidence_score,
            "status": s.status,
            "admin_note": s.admin_note,
            "created_at": s.created_at.isoformat(),
        }
        for s in suggestions
    ]


@router.post("/admin/approvals/suggestions/decide")
async def decide_suggestion(
    payload: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Admin decision on a process mapping suggestion.

    Actions:
      confirm   → mark as confirmed (auto-assigns to suggested node)
      reject    → mark as rejected
      reassign  → assign to different node (target_node_id required)
      merge     → mark as merged with existing process
      new_process → create new process entry
    """
    _require_admin(current_user)

    sugg = await db.get(ProcessMappingSuggestion, payload.suggestion_id)
    if sugg is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    if sugg.status != SuggestionStatus.pending.value:
        raise HTTPException(status_code=409, detail=f"Suggestion already decided: {sugg.status}")

    action_map = {
        "confirm":     SuggestionStatus.confirmed.value,
        "reject":      SuggestionStatus.rejected.value,
        "reassign":    SuggestionStatus.reassigned.value,
        "merge":       SuggestionStatus.confirmed.value,
        "new_process": SuggestionStatus.confirmed.value,
    }
    new_status = action_map.get(payload.action)
    if not new_status:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")

    sugg.status = new_status
    sugg.admin_note = payload.admin_note
    sugg.reviewed_by = current_user.id
    sugg.reviewed_at = datetime.now(timezone.utc)

    if payload.action == "reassign" and payload.target_node_id:
        sugg.suggested_node_id = payload.target_node_id

    from app.services.audit_service import log_bcm_suggestion
    await log_bcm_suggestion(
        db,
        org_id=sugg.org_id,
        suggestion_id=sugg.id,
        process_name=sugg.process_name,
        action="bcm_suggestion_decided",
        actor_id=current_user.id,
        decision_data={"action": payload.action, "new_status": new_status},
    )
    await db.commit()
    return {"status": "ok", "new_status": new_status, "suggestion_id": str(sugg.id)}


# ── Retrieval Test Lab ────────────────────────────────────────────────────────

@router.post("/admin/retrieval-test", response_model=RetrievalTestResult)
async def run_retrieval_test(
    payload: RetrievalTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Execute a test retrieval for debugging/validation.
    Results are audit-logged and returned to the admin UI.
    """
    _require_admin(current_user)

    from app.services.hybrid_retrieval_service import hybrid_retrieve
    result = await hybrid_retrieve(
        query=payload.query,
        org_id=payload.org_id,
        db=db,
        source_systems=payload.source_systems,
        canonical_types=payload.canonical_types,
    )

    # Audit
    test_id = uuid.uuid4()
    from app.services.audit_service import log_retrieval_test
    await log_retrieval_test(
        db,
        org_id=payload.org_id,
        test_id=test_id,
        query=payload.query,
        result_mode=result.mode,
        chunk_count=len(result.chunks),
        warnings=result.guardrail_warnings,
        actor_id=current_user.id,
    )
    await db.commit()

    return RetrievalTestResult(
        query=payload.query,
        mode=result.mode,
        chunk_count=len(result.chunks),
        primary_count=result.primary_evidence_count(),
        has_conflicts=result.has_conflicts(),
        conflict_count=len(result.conflicts),
        guardrail_warnings=result.guardrail_warnings,
        top_chunks=[
            {
                "text_preview": c.text[:300],
                "source_url": c.source_url,
                "source_system": c.source_system,
                "chunk_type": c.chunk_type,
                "trust_class": c.trust_class,
                "trust_score": c.trust_score,
                "evidence_type": c.evidence_type,
                "final_score": round(c.final_score, 4),
            }
            for c in result.chunks[:5]
        ],
        conflicts=[
            {
                "type": cf.conflict_type,
                "system_a": cf.chunk_a_system,
                "system_b": cf.chunk_b_system,
                "winning_source": cf.winning_source,
                "resolution_rule": cf.resolution_rule,
                "excerpt_a": cf.excerpt_a[:150],
                "excerpt_b": cf.excerpt_b[:150],
            }
            for cf in result.conflicts
        ],
    )


# ── Audit Log Viewer ──────────────────────────────────────────────────────────

@router.get("/admin/audit")
async def get_audit_log(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_id: Optional[uuid.UUID] = Query(None),
    entity_type: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Return audit log entries. Append-only — no mutations here."""
    _require_admin(current_user)

    stmt = select(AuditLog)
    if org_id:
        stmt = stmt.where(AuditLog.org_id == org_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.occurred_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    entries = result.scalars().all()
    return {
        "total": len(entries),
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "org_id": str(e.org_id),
                "entity_type": e.entity_type,
                "entity_id": str(e.entity_id),
                "action": e.action,
                "actor_id": str(e.actor_id) if e.actor_id else None,
                "actor_type": e.actor_type,
                "diff": e.diff,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in entries
        ],
    }
