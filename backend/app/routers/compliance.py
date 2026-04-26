# app/routers/compliance.py
"""
Compliance Assessment API.

  POST /api/v1/compliance/assessments
       Create or retrieve assessment for an object.

  GET  /api/v1/compliance/assessments/{id}
       Full assessment with summary.

  GET  /api/v1/compliance/assessments/by-object
       Look up by object_type + object_id.

  POST /api/v1/compliance/assessments/{id}/refresh
       Re-evaluate triggers, sync items, recompute scores.

  GET  /api/v1/compliance/assessments/{id}/items
       Paginated, filtered list of assessment items.

  GET  /api/v1/compliance/assessments/{id}/items/{item_id}
       Single item with full detail (evidence, actions, score history).

  POST /api/v1/compliance/assessments/{id}/items/{item_id}/score
       Submit or update a score for an item.

  POST /api/v1/compliance/assessments/{id}/items/{item_id}/evidence
       Add an evidence link to an item.

  DELETE /api/v1/compliance/assessments/{id}/items/{item_id}/evidence/{ev_id}
       Remove an evidence link.

  POST /api/v1/compliance/assessments/{id}/items/{item_id}/actions
       Create an action/Maßnahme.

  PUT  /api/v1/compliance/assessments/{id}/items/{item_id}/actions/{action_id}
       Update action status/owner/due_date.

  GET  /api/v1/compliance/assessments/{id}/snapshots
       List status snapshots.

  POST /api/v1/compliance/assessments/{id}/snapshots
       Create a new snapshot (e.g. before gate decision).

  GET  /api/v1/compliance/assessments/{id}/gate-readiness
       Gate-by-gate readiness with blocking detail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.compliance_assessment import (
    ComplianceAssessment, ComplianceAssessmentItem, ComplianceScoreEntry,
    ComplianceEvidenceLink, ComplianceAction, ComplianceStatusSnapshot,
    ItemStatus, ActivationSource, TrafficLight,
)
from app.services.compliance_service import (
    get_or_create_assessment, refresh_assessment,
    score_item, compute_assessment_summary, create_snapshot,
    derive_traffic_light, derive_item_status, derive_blocks_gate,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AssessmentCreateRequest(BaseModel):
    org_id: uuid.UUID
    object_type: str = Field(..., description="project | product | custom")
    object_id: uuid.UUID
    object_name: str
    context_params: dict = {}


class ScoreRequest(BaseModel):
    score: int = Field(..., ge=0, le=3)
    rationale: Optional[str] = None
    residual_risk: Optional[str] = None


class EvidenceLinkCreate(BaseModel):
    evidence_type_slug: Optional[str] = None
    evidence_type_name: Optional[str] = None
    file_name: Optional[str] = None
    file_url: Optional[str] = None
    external_ref: Optional[str] = None
    description: Optional[str] = None
    is_mandatory: bool = False


class ActionCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    priority: str = "medium"
    owner_name: Optional[str] = None
    due_date: Optional[datetime] = None


class ActionUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    owner_name: Optional[str] = None
    due_date: Optional[datetime] = None
    escalation_note: Optional[str] = None


class SnapshotCreate(BaseModel):
    trigger_reason: str = "manual"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _item_summary(item: ComplianceAssessmentItem) -> dict:
    return {
        "id": str(item.id),
        "control_id": str(item.control_id),
        "control_slug": item.control_slug,
        "control_name": item.control_name,
        "control_kind": item.control_kind,
        "category_name": item.category_name,
        "gate_phases": item.gate_phases,
        "hard_stop": item.hard_stop,
        "activation_source": item.activation_source,
        "activating_trigger_name": item.activating_trigger_name,
        "score": item.score,
        "status": item.status,
        "traffic_light": item.traffic_light,
        "blocks_gate": item.blocks_gate,
        "responsible_role": item.responsible_role,
        "assessed_by_name": item.assessed_by_name,
        "assessed_at": item.assessed_at.isoformat() if item.assessed_at else None,
        "evidence_status": item.evidence_status,
        "approval_status": item.approval_status,
        "updated_at": item.updated_at.isoformat(),
    }


def _item_detail(item: ComplianceAssessmentItem) -> dict:
    base = _item_summary(item)
    base.update({
        "control_objective": item.control_objective,
        "why_relevant": item.why_relevant,
        "what_to_check": item.what_to_check,
        "guiding_questions": item.guiding_questions,
        "required_evidence_types": item.required_evidence_types,
        "control_version": item.control_version,
        "activating_trigger_id": str(item.activating_trigger_id) if item.activating_trigger_id else None,
        "activating_gate": item.activating_gate,
        "rationale": item.rationale,
        "residual_risk": item.residual_risk,
        "evidence_comment": item.evidence_comment,
        "hard_stop_threshold": item.hard_stop_threshold,
        "default_weight": item.default_weight,
        "approved_by": str(item.approved_by) if item.approved_by else None,
        "approved_at": item.approved_at.isoformat() if item.approved_at else None,
        "evidence_links": [
            {
                "id": str(ev.id),
                "evidence_type_slug": ev.evidence_type_slug,
                "evidence_type_name": ev.evidence_type_name,
                "file_name": ev.file_name,
                "file_url": ev.file_url,
                "external_ref": ev.external_ref,
                "description": ev.description,
                "is_mandatory": ev.is_mandatory,
                "uploaded_at": ev.uploaded_at.isoformat(),
            }
            for ev in (item.evidence_links or [])
        ],
        "actions": [
            {
                "id": str(a.id),
                "title": a.title,
                "description": a.description,
                "status": a.status,
                "priority": a.priority,
                "owner_name": a.owner_name,
                "due_date": a.due_date.isoformat() if a.due_date else None,
                "escalation_note": a.escalation_note,
                "created_at": a.created_at.isoformat(),
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in (item.actions or [])
        ],
        "score_history": [
            {
                "id": str(e.id),
                "from_score": e.from_score,
                "to_score": e.to_score,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "rationale": e.rationale,
                "gate_impact": e.gate_impact,
                "changed_by_name": e.changed_by_name,
                "created_at": e.created_at.isoformat(),
            }
            for e in (item.score_history or [])
        ],
    })
    return base


def _assessment_summary(a: ComplianceAssessment) -> dict:
    return {
        "id": str(a.id),
        "org_id": str(a.org_id),
        "object_type": a.object_type,
        "object_id": str(a.object_id),
        "object_name": a.object_name,
        "context_params": a.context_params,
        "total_controls": a.total_controls,
        "fulfilled_controls": a.fulfilled_controls,
        "deviation_controls": a.deviation_controls,
        "not_assessed_controls": a.not_assessed_controls,
        "hard_stop_total": a.hard_stop_total,
        "hard_stop_critical": a.hard_stop_critical,
        "overall_score": a.overall_score,
        "traffic_light": a.traffic_light,
        "compliance_status": a.compliance_status,
        "gate_readiness": a.gate_readiness,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
        "last_refreshed_at": a.last_refreshed_at.isoformat() if a.last_refreshed_at else None,
    }


# ── Assessment endpoints ──────────────────────────────────────────────────────

@router.get("/assessments")
async def list_assessments(
    org_id: Optional[uuid.UUID] = None,
    object_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(ComplianceAssessment)
    if org_id:
        stmt = stmt.where(ComplianceAssessment.org_id == org_id)
    if object_type:
        stmt = stmt.where(ComplianceAssessment.object_type == object_type)
    result = await db.execute(stmt.order_by(ComplianceAssessment.updated_at.desc()).limit(200))
    assessments = result.scalars().all()
    return [_assessment_summary(a) for a in assessments]


@router.post("/assessments", status_code=201)
async def create_assessment(
    payload: AssessmentCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await get_or_create_assessment(
        db,
        org_id=payload.org_id,
        object_type=payload.object_type,
        object_id=payload.object_id,
        object_name=payload.object_name,
        context_params=payload.context_params,
        created_by=current_user.id,
    )
    await db.commit()
    await db.refresh(assessment)
    return _assessment_summary(assessment)


@router.get("/assessments/by-object")
async def get_assessment_by_object(
    object_type: str = Query(...),
    object_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.scalar(
        select(ComplianceAssessment).where(
            and_(
                ComplianceAssessment.object_type == object_type,
                ComplianceAssessment.object_id == object_id,
            )
        )
    )
    if not assessment:
        raise HTTPException(404, "No assessment found for this object")
    return _assessment_summary(assessment)


@router.get("/assessments/{assessment_id}")
async def get_assessment(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.get(ComplianceAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    return _assessment_summary(assessment)


@router.post("/assessments/{assessment_id}/refresh")
async def refresh_assessment_endpoint(
    assessment_id: uuid.UUID,
    context_params: Optional[dict] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.get(ComplianceAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    await refresh_assessment(db, assessment, context_params)
    await db.commit()
    await db.refresh(assessment)
    return _assessment_summary(assessment)


# ── Items ─────────────────────────────────────────────────────────────────────

@router.get("/assessments/{assessment_id}/items")
async def list_items(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # Filters
    gate_phase: Optional[str] = Query(None),
    control_kind: Optional[str] = Query(None),
    activation_source: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    hard_stop_only: bool = Query(False),
    blocks_gate_only: bool = Query(False),
    no_evidence_only: bool = Query(False),
    has_actions: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stmt = select(ComplianceAssessmentItem).where(
        ComplianceAssessmentItem.assessment_id == assessment_id
    )

    if control_kind:
        stmt = stmt.where(ComplianceAssessmentItem.control_kind == control_kind)
    if activation_source:
        stmt = stmt.where(ComplianceAssessmentItem.activation_source == activation_source)
    if status_filter:
        stmt = stmt.where(ComplianceAssessmentItem.status == status_filter)
    if hard_stop_only:
        stmt = stmt.where(ComplianceAssessmentItem.hard_stop == True)
    if blocks_gate_only:
        stmt = stmt.where(ComplianceAssessmentItem.blocks_gate == True)
    if no_evidence_only:
        stmt = stmt.where(ComplianceAssessmentItem.evidence_status == "missing")
    if search:
        stmt = stmt.where(
            or_(
                ComplianceAssessmentItem.control_name.ilike(f"%{search}%"),
                ComplianceAssessmentItem.control_slug.ilike(f"%{search}%"),
            )
        )

    from sqlalchemy import func as sqlfunc
    total_stmt = select(sqlfunc.count()).select_from(stmt.subquery())
    total = await db.scalar(total_stmt)

    result = await db.execute(
        stmt.order_by(
            ComplianceAssessmentItem.hard_stop.desc(),
            ComplianceAssessmentItem.score.asc(),
            ComplianceAssessmentItem.control_name,
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    # Post-filter by gate_phase (JSON array filter in Python)
    if gate_phase:
        items = [i for i in items if gate_phase in i.gate_phases]

    return {
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "items": [_item_summary(i) for i in items],
    }


@router.get("/assessments/{assessment_id}/items/{item_id}")
async def get_item(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(ComplianceAssessmentItem)
        .options(
            selectinload(ComplianceAssessmentItem.evidence_links),
            selectinload(ComplianceAssessmentItem.actions),
            selectinload(ComplianceAssessmentItem.score_history),
        )
        .where(
            and_(
                ComplianceAssessmentItem.assessment_id == assessment_id,
                ComplianceAssessmentItem.id == item_id,
            )
        )
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Item not found")
    return _item_detail(item)


@router.post("/assessments/{assessment_id}/items/{item_id}/score")
async def submit_score(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await db.scalar(
        select(ComplianceAssessmentItem).where(
            and_(
                ComplianceAssessmentItem.assessment_id == assessment_id,
                ComplianceAssessmentItem.id == item_id,
            )
        )
    )
    if not item:
        raise HTTPException(404, "Item not found")

    await score_item(db, item, payload.score, payload.rationale, payload.residual_risk, current_user)

    # Recompute assessment summary
    assessment = await db.get(ComplianceAssessment, assessment_id)
    if assessment:
        await compute_assessment_summary(db, assessment)

    await db.commit()
    return {"status": "scored", "score": item.score, "traffic_light": item.traffic_light,
            "blocks_gate": item.blocks_gate, "status_label": item.status}


# ── Evidence ──────────────────────────────────────────────────────────────────

@router.post("/assessments/{assessment_id}/items/{item_id}/evidence", status_code=201)
async def add_evidence(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: EvidenceLinkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await db.scalar(
        select(ComplianceAssessmentItem).where(
            and_(
                ComplianceAssessmentItem.assessment_id == assessment_id,
                ComplianceAssessmentItem.id == item_id,
            )
        )
    )
    if not item:
        raise HTTPException(404, "Item not found")

    ev = ComplianceEvidenceLink(
        item_id=item_id,
        uploaded_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(ev)

    # Recalculate evidence_status
    item.evidence_status = _recalculate_evidence_status(item)
    await db.commit()
    await db.refresh(ev)
    return {"id": str(ev.id), "status": "added"}


@router.delete("/assessments/{assessment_id}/items/{item_id}/evidence/{ev_id}", status_code=204)
async def remove_evidence(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    ev_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ev = await db.get(ComplianceEvidenceLink, ev_id)
    if not ev or ev.item_id != item_id:
        raise HTTPException(404, "Evidence link not found")
    await db.delete(ev)
    await db.commit()


def _recalculate_evidence_status(item: ComplianceAssessmentItem) -> str:
    required = [e for e in (item.required_evidence_types or []) if isinstance(e, dict) and e.get("requirement") == "mandatory"]
    if not required:
        return "complete"
    linked_types = {ev.evidence_type_slug for ev in (item.evidence_links or [])}
    required_slugs = {e.get("evidence_type_id", "") for e in required}
    if required_slugs.issubset(linked_types):
        return "complete"
    if linked_types:
        return "partial"
    return "missing"


# ── Actions / Maßnahmen ───────────────────────────────────────────────────────

@router.post("/assessments/{assessment_id}/items/{item_id}/actions", status_code=201)
async def create_action(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ActionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = await db.scalar(
        select(ComplianceAssessmentItem).where(
            and_(
                ComplianceAssessmentItem.assessment_id == assessment_id,
                ComplianceAssessmentItem.id == item_id,
            )
        )
    )
    if not item:
        raise HTTPException(404, "Item not found")

    action = ComplianceAction(
        item_id=item_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        owner_name=payload.owner_name,
        due_date=payload.due_date,
        created_by=current_user.id,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return {"id": str(action.id), "status": "created"}


@router.put("/assessments/{assessment_id}/items/{item_id}/actions/{action_id}")
async def update_action(
    assessment_id: uuid.UUID,
    item_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: ActionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = await db.get(ComplianceAction, action_id)
    if not action or action.item_id != item_id:
        raise HTTPException(404, "Action not found")

    for field, val in payload.model_dump(exclude_none=True).items():
        setattr(action, field, val)

    if payload.status == "done" and not action.completed_at:
        action.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"id": str(action.id), "status": action.status}


# ── Snapshots ─────────────────────────────────────────────────────────────────

@router.get("/assessments/{assessment_id}/snapshots")
async def list_snapshots(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ComplianceStatusSnapshot)
        .where(ComplianceStatusSnapshot.assessment_id == assessment_id)
        .order_by(ComplianceStatusSnapshot.created_at.desc())
        .limit(50)
    )
    snaps = result.scalars().all()
    return [
        {
            "id": str(s.id),
            "trigger_reason": s.trigger_reason,
            "compliance_status": s.compliance_status,
            "overall_score": s.overall_score,
            "traffic_light": s.traffic_light,
            "gate_readiness": s.gate_readiness,
            "summary": s.summary,
            "created_at": s.created_at.isoformat(),
        }
        for s in snaps
    ]


@router.post("/assessments/{assessment_id}/snapshots", status_code=201)
async def take_snapshot(
    assessment_id: uuid.UUID,
    payload: SnapshotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.get(ComplianceAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")
    snap = await create_snapshot(db, assessment, payload.trigger_reason, current_user)
    await db.commit()
    return {"id": str(snap.id), "status": "snapshot_created"}


# ── Gate readiness ────────────────────────────────────────────────────────────

@router.get("/assessments/{assessment_id}/gate-readiness")
async def gate_readiness(
    assessment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    assessment = await db.get(ComplianceAssessment, assessment_id)
    if not assessment:
        raise HTTPException(404, "Assessment not found")

    # Detailed blocking list per gate
    items_result = await db.execute(
        select(ComplianceAssessmentItem).where(
            ComplianceAssessmentItem.assessment_id == assessment_id,
            ComplianceAssessmentItem.blocks_gate == True,
        )
    )
    blocking = items_result.scalars().all()
    blocking_by_gate: dict[str, list] = {}
    for item in blocking:
        for gate in item.gate_phases:
            blocking_by_gate.setdefault(gate, []).append({
                "control_name": item.control_name,
                "score": item.score,
                "hard_stop": item.hard_stop,
                "status": item.status,
            })

    return {
        "assessment_id": str(assessment_id),
        "gate_readiness": assessment.gate_readiness,
        "blocking_detail": blocking_by_gate,
        "overall_compliance": assessment.compliance_status,
        "traffic_light": assessment.traffic_light,
        "overall_score": assessment.overall_score,
    }
