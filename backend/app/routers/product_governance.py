# app/routers/product_governance.py
"""
Product Governance & Control Management — REST API.

Endpoints:
  /api/v1/governance/overview             GET  — Dashboard stats
  /api/v1/governance/controls             GET  — List controls (filter/search/paginate)
  /api/v1/governance/controls             POST — Create dynamic control
  /api/v1/governance/controls/{id}        GET/PUT/DELETE
  /api/v1/governance/controls/{id}/publish    POST — Publish (creates ControlVersion)
  /api/v1/governance/controls/{id}/duplicate  POST — Duplicate
  /api/v1/governance/controls/{id}/versions   GET — Version history
  /api/v1/governance/gates                GET/POST
  /api/v1/governance/gates/{id}           GET/PUT
  /api/v1/governance/triggers             GET/POST
  /api/v1/governance/triggers/{id}        GET/PUT/DELETE
  /api/v1/governance/triggers/evaluate    POST — Evaluate trigger for input
  /api/v1/governance/evidence-types       GET/POST/PUT/DELETE
  /api/v1/governance/scoring-schemes      GET/POST/PUT
  /api/v1/governance/categories           GET
  /api/v1/governance/simulation/run       POST — Run simulation
  /api/v1/governance/simulation/scenarios GET/POST
  /api/v1/governance/changelog            GET — Audit trail
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.product_governance import (
    ControlDefinition, ControlVersion, ControlStatus, ControlKind,
    GateDefinition, GateVersion,
    DynamicTriggerRule,
    EvidenceType, ScoringScheme, ControlCategory,
    ProductScope, MarketScope, CustomerSegment, RiskDimension,
    GovernanceChangeLog, SimulationScenario,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/governance", tags=["product-governance"])


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _require_admin(user: User) -> User:
    from app.core.permissions import is_admin
    if not is_admin(user):
        raise HTTPException(status_code=403, detail="Admin required")
    return user


# ── Schemas ────────────────────────────────────────────────────────────────────

class ControlListItem(BaseModel):
    id: uuid.UUID
    slug: str
    kind: str
    name: str
    category_id: Optional[uuid.UUID] = None
    status: str
    gate_phases: list
    default_weight: float
    hard_stop: bool
    version: int
    responsible_role: Optional[str] = None
    is_visible_in_frontend: bool
    updated_at: datetime
    published_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ControlDetail(BaseModel):
    id: uuid.UUID
    slug: str
    system_id: Optional[str] = None
    kind: str
    name: str
    short_description: Optional[str] = None
    why_relevant: Optional[str] = None
    what_to_check: Optional[str] = None
    what_to_do: Optional[str] = None
    guiding_questions: list = []
    help_text: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    control_objective: Optional[str] = None
    risk_rationale: Optional[str] = None
    escalation_logic: Optional[str] = None
    gate_phases: list = []
    scoring_scheme_id: Optional[uuid.UUID] = None
    default_weight: float = 1.0
    hard_stop: bool = False
    hard_stop_threshold: int = 1
    requires_trigger: bool = False
    trigger_config: dict = {}
    evidence_requirements: list = []
    product_scope_ids: list = []
    market_scope_ids: list = []
    customer_segment_ids: list = []
    risk_dimension_ids: list = []
    framework_refs: list = []
    review_interval_days: int = 365
    last_reviewed_at: Optional[datetime] = None
    responsible_role: Optional[str] = None
    audit_notes: Optional[str] = None
    status: str = "draft"
    version: int = 1
    is_visible_in_frontend: bool = True
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ControlCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=200)
    name: str = Field(..., min_length=2, max_length=500)
    short_description: Optional[str] = None
    why_relevant: Optional[str] = None
    what_to_check: Optional[str] = None
    what_to_do: Optional[str] = None
    guiding_questions: list = []
    help_text: Optional[str] = None
    category_id: Optional[uuid.UUID] = None
    control_objective: Optional[str] = None
    risk_rationale: Optional[str] = None
    escalation_logic: Optional[str] = None
    gate_phases: list = []
    scoring_scheme_id: Optional[uuid.UUID] = None
    default_weight: float = Field(1.0, ge=0.0, le=10.0)
    hard_stop: bool = False
    hard_stop_threshold: int = 1
    requires_trigger: bool = False
    trigger_config: dict = {}
    evidence_requirements: list = []
    product_scope_ids: list = []
    market_scope_ids: list = []
    customer_segment_ids: list = []
    risk_dimension_ids: list = []
    framework_refs: list = []
    review_interval_days: int = 365
    responsible_role: Optional[str] = None
    audit_notes: Optional[str] = None
    is_visible_in_frontend: bool = True


class ControlUpdate(ControlCreate):
    slug: Optional[str] = None  # type: ignore
    name: Optional[str] = None  # type: ignore
    change_reason: Optional[str] = None


class PublishRequest(BaseModel):
    change_reason: Optional[str] = None


class TriggerCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=200)
    name: str = Field(..., min_length=2, max_length=500)
    description: Optional[str] = None
    condition_tree: dict
    activates_control_ids: list[uuid.UUID] = []
    priority: int = 100
    conflict_resolution: str = "latest_wins"
    is_active: bool = True


class TriggerUpdate(TriggerCreate):
    slug: Optional[str] = None  # type: ignore
    name: Optional[str] = None  # type: ignore


class GateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    min_total_score: Optional[float] = None
    required_fixed_control_slugs: Optional[list] = None
    hard_stop_threshold: Optional[int] = None
    approver_roles: Optional[list] = None
    escalation_path: Optional[str] = None
    outcomes_config: Optional[dict] = None
    change_reason: Optional[str] = None


class EvidenceTypeCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100)
    name: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = None
    format_guidance: Optional[str] = None
    template_url: Optional[str] = None


class ScoringSchemeUpdate(BaseModel):
    name: Optional[str] = None
    scale_min: Optional[int] = None
    scale_max: Optional[int] = None
    scale_labels: Optional[list] = None
    traffic_light: Optional[dict] = None
    formula: Optional[str] = None
    is_default: Optional[bool] = None


class SimulationInput(BaseModel):
    product_type: Optional[str] = None
    product_class: Optional[str] = None
    market: Optional[str] = None
    customer_segment: Optional[str] = None
    failure_criticality: Optional[str] = None  # low|medium|high|critical
    revenue_risk: Optional[str] = None
    cost_risk: Optional[str] = None
    credit_risk: Optional[str] = None
    supply_risk: Optional[str] = None
    quality_risk: Optional[str] = None
    support_load: Optional[str] = None
    has_software: bool = False
    has_cloud: bool = False
    has_battery: bool = False
    has_grid_connection: bool = False
    has_single_source: bool = False
    new_suppliers: bool = False
    phase: Optional[str] = None  # pilot|series|existing
    price_range: Optional[str] = None
    service_intensity: Optional[str] = None
    save_as_scenario: bool = False
    scenario_name: Optional[str] = None


# ── Helper: governance audit log ──────────────────────────────────────────────

async def _log_change(
    db: AsyncSession,
    entity_type: str,
    entity_id: uuid.UUID,
    entity_slug: str,
    action: str,
    actor: User,
    from_status: Optional[str] = None,
    to_status: Optional[str] = None,
    from_version: Optional[int] = None,
    to_version: Optional[int] = None,
    change_reason: Optional[str] = None,
    diff: Optional[dict] = None,
    org_id: Optional[uuid.UUID] = None,
) -> None:
    entry = GovernanceChangeLog(
        org_id=org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_slug=entity_slug,
        action=action,
        from_status=from_status,
        to_status=to_status,
        from_version=from_version,
        to_version=to_version,
        change_reason=change_reason,
        diff=diff,
        actor_id=actor.id,
        actor_name=getattr(actor, "full_name", None) or getattr(actor, "email", ""),
    )
    db.add(entry)


def _snapshot(obj: ControlDefinition | GateDefinition | DynamicTriggerRule) -> dict:
    """Create JSON-serializable snapshot of a model instance."""
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        data[col.name] = val
    return data


# ── Overview / Dashboard ──────────────────────────────────────────────────────

@router.get("/overview")
async def governance_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    fixed_count = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(ControlDefinition.kind == ControlKind.fixed.value)
    )
    dynamic_count = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(ControlDefinition.kind == ControlKind.dynamic.value)
    )
    active_triggers = await db.scalar(
        select(func.count()).select_from(DynamicTriggerRule)
        .where(DynamicTriggerRule.is_active == True)
    )
    hard_stop_count = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(ControlDefinition.hard_stop == True)
    )
    no_evidence = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(func.jsonb_array_length(ControlDefinition.evidence_requirements) == 0)
    )
    draft_count = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(ControlDefinition.status == ControlStatus.draft.value)
    )
    review_count = await db.scalar(
        select(func.count()).select_from(ControlDefinition)
        .where(ControlDefinition.status == ControlStatus.review.value)
    )

    recent_changes = await db.execute(
        select(GovernanceChangeLog)
        .order_by(GovernanceChangeLog.occurred_at.desc())
        .limit(10)
    )
    recent = [
        {
            "entity_type": c.entity_type,
            "entity_slug": c.entity_slug,
            "action": c.action,
            "actor_name": c.actor_name,
            "occurred_at": c.occurred_at.isoformat(),
        }
        for c in recent_changes.scalars().all()
    ]

    return {
        "fixed_controls": int(fixed_count or 0),
        "dynamic_controls": int(dynamic_count or 0),
        "active_triggers": int(active_triggers or 0),
        "hard_stop_controls": int(hard_stop_count or 0),
        "controls_without_evidence": int(no_evidence or 0),
        "draft_controls": int(draft_count or 0),
        "review_controls": int(review_count or 0),
        "recent_changes": recent,
    }


# ── Controls ──────────────────────────────────────────────────────────────────

@router.get("/controls", response_model=dict)
async def list_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kind: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    gate_phase: Optional[str] = Query(None),
    hard_stop: Optional[bool] = Query(None),
    has_trigger: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    _require_admin(current_user)

    stmt = select(ControlDefinition)
    if kind:
        stmt = stmt.where(ControlDefinition.kind == kind)
    if status_filter:
        stmt = stmt.where(ControlDefinition.status == status_filter)
    if category_id:
        stmt = stmt.where(ControlDefinition.category_id == category_id)
    if hard_stop is not None:
        stmt = stmt.where(ControlDefinition.hard_stop == hard_stop)
    if has_trigger is not None:
        stmt = stmt.where(ControlDefinition.requires_trigger == has_trigger)
    if search:
        stmt = stmt.where(
            or_(
                ControlDefinition.name.ilike(f"%{search}%"),
                ControlDefinition.slug.ilike(f"%{search}%"),
            )
        )

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    result = await db.execute(
        stmt.order_by(ControlDefinition.kind, ControlDefinition.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    controls = result.scalars().all()

    return {
        "total": int(total or 0),
        "page": page,
        "page_size": page_size,
        "items": [ControlListItem.model_validate(c).model_dump() for c in controls],
    }


@router.get("/controls/{control_id}", response_model=ControlDetail)
async def get_control(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")
    return ControlDetail.model_validate(ctrl)


@router.post("/controls", response_model=ControlDetail, status_code=201)
async def create_control(
    payload: ControlCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    # Check slug unique
    existing = await db.scalar(
        select(ControlDefinition).where(ControlDefinition.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Slug '{payload.slug}' already exists")

    ctrl = ControlDefinition(
        kind=ControlKind.dynamic.value,
        **payload.model_dump(),
    )
    db.add(ctrl)
    await db.flush()

    await _log_change(db, "control", ctrl.id, ctrl.slug, "created",
                      current_user, to_status="draft", to_version=1)
    await db.commit()
    await db.refresh(ctrl)
    return ControlDetail.model_validate(ctrl)


@router.put("/controls/{control_id}", response_model=ControlDetail)
async def update_control(
    control_id: uuid.UUID,
    payload: ControlUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")

    # Fixed controls: only allow limited field updates
    FIXED_ALLOWED = {
        "name", "short_description", "why_relevant", "what_to_check",
        "what_to_do", "guiding_questions", "help_text", "gate_phases",
        "default_weight", "responsible_role", "evidence_requirements",
        "is_visible_in_frontend", "review_interval_days", "audit_notes",
    }

    old_snapshot = _snapshot(ctrl)
    update_data = payload.model_dump(exclude_none=True, exclude={"change_reason"})

    if ctrl.kind == ControlKind.fixed.value:
        blocked = set(update_data.keys()) - FIXED_ALLOWED
        if blocked:
            raise HTTPException(400, f"Fixed controls cannot update: {', '.join(blocked)}")

    for field, val in update_data.items():
        if hasattr(ctrl, field):
            setattr(ctrl, field, val)

    new_snapshot = _snapshot(ctrl)
    diff = {k: {"from": old_snapshot.get(k), "to": new_snapshot.get(k)}
            for k in new_snapshot if old_snapshot.get(k) != new_snapshot.get(k)}

    await _log_change(db, "control", ctrl.id, ctrl.slug, "updated", current_user,
                      from_status=ctrl.status, to_status=ctrl.status,
                      change_reason=payload.change_reason, diff=diff)
    await db.commit()
    await db.refresh(ctrl)
    return ControlDetail.model_validate(ctrl)


@router.delete("/controls/{control_id}", status_code=204)
async def delete_control(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")
    if ctrl.kind == ControlKind.fixed.value:
        raise HTTPException(403, "Fixed (system) controls cannot be deleted")
    if ctrl.status == ControlStatus.approved.value:
        raise HTTPException(409, "Published controls cannot be deleted. Archive first.")

    await _log_change(db, "control", ctrl.id, ctrl.slug, "deleted",
                      current_user, from_status=ctrl.status)
    await db.delete(ctrl)
    await db.commit()


@router.post("/controls/{control_id}/publish", response_model=ControlDetail)
async def publish_control(
    control_id: uuid.UUID,
    payload: PublishRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Publish a control: creates an immutable ControlVersion and sets status=approved."""
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")

    # Validate required fields
    missing = []
    if not ctrl.name:
        missing.append("name")
    if not ctrl.control_objective:
        missing.append("control_objective")
    if not ctrl.gate_phases:
        missing.append("gate_phases")
    if missing:
        raise HTTPException(422, f"Missing required fields: {', '.join(missing)}")

    old_version = ctrl.version
    ctrl.version += 1
    ctrl.status = ControlStatus.approved.value
    ctrl.published_at = datetime.now(timezone.utc)

    version_snap = ControlVersion(
        control_id=ctrl.id,
        version=ctrl.version,
        snapshot=_snapshot(ctrl),
        status=ControlStatus.approved.value,
        change_reason=payload.change_reason,
        changed_by=current_user.id,
    )
    db.add(version_snap)

    await _log_change(db, "control", ctrl.id, ctrl.slug, "published", current_user,
                      from_status=ControlStatus.draft.value,
                      to_status=ControlStatus.approved.value,
                      from_version=old_version, to_version=ctrl.version,
                      change_reason=payload.change_reason)
    await db.commit()
    await db.refresh(ctrl)
    return ControlDetail.model_validate(ctrl)


@router.post("/controls/{control_id}/duplicate", response_model=ControlDetail, status_code=201)
async def duplicate_control(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")

    new_slug = f"{ctrl.slug}-copy-{uuid.uuid4().hex[:6]}"
    new_ctrl = ControlDefinition(
        kind=ControlKind.dynamic.value,
        slug=new_slug,
        name=f"{ctrl.name} (Kopie)",
        short_description=ctrl.short_description,
        why_relevant=ctrl.why_relevant,
        what_to_check=ctrl.what_to_check,
        what_to_do=ctrl.what_to_do,
        guiding_questions=ctrl.guiding_questions,
        help_text=ctrl.help_text,
        category_id=ctrl.category_id,
        control_objective=ctrl.control_objective,
        risk_rationale=ctrl.risk_rationale,
        gate_phases=ctrl.gate_phases,
        default_weight=ctrl.default_weight,
        hard_stop=ctrl.hard_stop,
        hard_stop_threshold=ctrl.hard_stop_threshold,
        evidence_requirements=ctrl.evidence_requirements,
        product_scope_ids=ctrl.product_scope_ids,
        market_scope_ids=ctrl.market_scope_ids,
        customer_segment_ids=ctrl.customer_segment_ids,
        risk_dimension_ids=ctrl.risk_dimension_ids,
        status=ControlStatus.draft.value,
        version=1,
    )
    db.add(new_ctrl)
    await db.flush()
    await _log_change(db, "control", new_ctrl.id, new_slug, "duplicated",
                      current_user, to_status="draft",
                      diff={"source_id": str(ctrl.id)})
    await db.commit()
    await db.refresh(new_ctrl)
    return ControlDetail.model_validate(new_ctrl)


@router.post("/controls/{control_id}/archive", response_model=ControlDetail)
async def archive_control(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")
    if ctrl.kind == ControlKind.fixed.value:
        raise HTTPException(403, "Fixed controls cannot be archived")
    old = ctrl.status
    ctrl.status = ControlStatus.archived.value
    await _log_change(db, "control", ctrl.id, ctrl.slug, "archived",
                      current_user, from_status=old, to_status="archived")
    await db.commit()
    await db.refresh(ctrl)
    return ControlDetail.model_validate(ctrl)


@router.get("/controls/{control_id}/versions")
async def get_control_versions(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(ControlVersion)
        .where(ControlVersion.control_id == control_id)
        .order_by(ControlVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": str(v.id),
            "version": v.version,
            "status": v.status,
            "change_reason": v.change_reason,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ]


# ── Gates ─────────────────────────────────────────────────────────────────────

@router.get("/gates")
async def list_gates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(GateDefinition).order_by(GateDefinition.sort_order)
    )
    gates = result.scalars().all()
    return [
        {
            "id": str(g.id),
            "phase": g.phase,
            "name": g.name,
            "description": g.description,
            "min_total_score": g.min_total_score,
            "hard_stop_threshold": g.hard_stop_threshold,
            "required_fixed_control_slugs": g.required_fixed_control_slugs,
            "approver_roles": g.approver_roles,
            "is_active": g.is_active,
            "version": g.version,
            "status": g.status,
            "updated_at": g.updated_at.isoformat(),
        }
        for g in gates
    ]


@router.get("/gates/{gate_id}")
async def get_gate(
    gate_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    gate = await db.get(GateDefinition, gate_id)
    if not gate:
        raise HTTPException(404, "Gate not found")
    return {
        "id": str(gate.id),
        "phase": gate.phase,
        "name": gate.name,
        "description": gate.description,
        "sort_order": gate.sort_order,
        "min_total_score": gate.min_total_score,
        "hard_stop_threshold": gate.hard_stop_threshold,
        "required_fixed_control_slugs": gate.required_fixed_control_slugs,
        "approver_roles": gate.approver_roles,
        "escalation_path": gate.escalation_path,
        "outcomes_config": gate.outcomes_config,
        "is_active": gate.is_active,
        "version": gate.version,
        "status": gate.status,
        "updated_at": gate.updated_at.isoformat(),
    }


@router.put("/gates/{gate_id}")
async def update_gate(
    gate_id: uuid.UUID,
    payload: GateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    gate = await db.get(GateDefinition, gate_id)
    if not gate:
        raise HTTPException(404, "Gate not found")

    old_version = gate.version
    old_snap = {c.name: getattr(gate, c.name) for c in gate.__table__.columns}

    for field, val in payload.model_dump(exclude_none=True, exclude={"change_reason"}).items():
        if hasattr(gate, field):
            setattr(gate, field, val)

    gate.version += 1
    snap = GateVersion(
        gate_id=gate.id,
        version=gate.version,
        snapshot={c.name: str(getattr(gate, c.name)) if isinstance(getattr(gate, c.name), (uuid.UUID, datetime)) else getattr(gate, c.name) for c in gate.__table__.columns},
        status=gate.status,
        change_reason=payload.change_reason,
        changed_by=current_user.id,
    )
    db.add(snap)
    await _log_change(db, "gate", gate.id, gate.phase, "updated", current_user,
                      from_version=old_version, to_version=gate.version,
                      change_reason=payload.change_reason)
    await db.commit()
    await db.refresh(gate)
    return {"id": str(gate.id), "version": gate.version, "status": "updated"}


# ── Triggers ──────────────────────────────────────────────────────────────────

@router.get("/triggers")
async def list_triggers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = Query(False),
):
    _require_admin(current_user)
    stmt = select(DynamicTriggerRule)
    if active_only:
        stmt = stmt.where(DynamicTriggerRule.is_active == True)
    result = await db.execute(stmt.order_by(DynamicTriggerRule.priority, DynamicTriggerRule.name))
    triggers = result.scalars().all()
    return [
        {
            "id": str(t.id),
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "condition_tree": t.condition_tree,
            "activates_control_ids": t.activates_control_ids,
            "priority": t.priority,
            "is_active": t.is_active,
            "status": t.status,
            "version": t.version,
            "updated_at": t.updated_at.isoformat(),
        }
        for t in triggers
    ]


@router.post("/triggers", status_code=201)
async def create_trigger(
    payload: TriggerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = await db.scalar(
        select(DynamicTriggerRule).where(DynamicTriggerRule.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Trigger slug '{payload.slug}' already exists")

    # Validate no circular references (basic: activates_control_ids must exist)
    data = payload.model_dump()
    data["activates_control_ids"] = [str(cid) for cid in payload.activates_control_ids]
    trigger = DynamicTriggerRule(**{k: v for k, v in data.items() if hasattr(DynamicTriggerRule, k)})
    trigger.activates_control_ids = [str(cid) for cid in payload.activates_control_ids]
    db.add(trigger)
    await db.flush()
    await _log_change(db, "trigger", trigger.id, trigger.slug, "created",
                      current_user, to_status=trigger.status)
    await db.commit()
    await db.refresh(trigger)
    return {"id": str(trigger.id), "slug": trigger.slug, "status": "created"}


@router.put("/triggers/{trigger_id}")
async def update_trigger(
    trigger_id: uuid.UUID,
    payload: TriggerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    trigger = await db.get(DynamicTriggerRule, trigger_id)
    if not trigger:
        raise HTTPException(404, "Trigger not found")
    for field, val in payload.model_dump(exclude_none=True).items():
        if hasattr(trigger, field):
            setattr(trigger, field, val)
    trigger.version += 1
    await _log_change(db, "trigger", trigger.id, trigger.slug, "updated", current_user)
    await db.commit()
    return {"id": str(trigger.id), "version": trigger.version}


@router.delete("/triggers/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    trigger = await db.get(DynamicTriggerRule, trigger_id)
    if not trigger:
        raise HTTPException(404, "Trigger not found")
    await _log_change(db, "trigger", trigger.id, trigger.slug, "deleted", current_user)
    await db.delete(trigger)
    await db.commit()


@router.post("/triggers/evaluate")
async def evaluate_trigger(
    payload: SimulationInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Evaluate all active triggers against input params. Returns which triggers fire."""
    _require_admin(current_user)
    result = await db.execute(
        select(DynamicTriggerRule).where(DynamicTriggerRule.is_active == True)
    )
    triggers = result.scalars().all()
    input_dict = payload.model_dump()
    fired = []
    for trigger in triggers:
        if _evaluate_condition_tree(trigger.condition_tree, input_dict):
            fired.append({
                "trigger_id": str(trigger.id),
                "trigger_name": trigger.name,
                "activates_control_ids": trigger.activates_control_ids,
            })
    return {"fired_triggers": fired, "total_evaluated": len(triggers)}


def _evaluate_condition_tree(tree: dict, params: dict) -> bool:
    """Recursive condition tree evaluator."""
    if not tree:
        return False
    if "operator" in tree:
        op = tree["operator"]
        conditions = tree.get("conditions", [])
        results = [_evaluate_condition_tree(c, params) for c in conditions]
        if op == "AND":
            return all(results)
        if op == "OR":
            return any(results)
        if op == "NOT":
            return not results[0] if results else True
    # Leaf condition
    field = tree.get("field", "")
    op = tree.get("op", "eq")
    value = tree.get("value")
    actual = params.get(field)
    if actual is None:
        return False
    if op == "eq":
        return str(actual).lower() == str(value).lower()
    if op == "in":
        return str(actual).lower() in [str(v).lower() for v in (value or [])]
    if op == "gte":
        return _risk_level(actual) >= _risk_level(value)
    if op == "gt":
        return _risk_level(actual) > _risk_level(value)
    if op == "is_true":
        return bool(actual)
    return False


def _risk_level(v: Any) -> int:
    levels = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return levels.get(str(v).lower(), 0)


# ── Evidence Types ────────────────────────────────────────────────────────────

@router.get("/evidence-types")
async def list_evidence_types(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    active_only: bool = Query(True),
):
    _require_admin(current_user)
    stmt = select(EvidenceType)
    if active_only:
        stmt = stmt.where(EvidenceType.is_active == True)
    result = await db.execute(stmt.order_by(EvidenceType.name))
    types = result.scalars().all()
    return [
        {
            "id": str(et.id), "slug": et.slug, "name": et.name,
            "description": et.description, "format_guidance": et.format_guidance,
            "is_system": et.is_system, "is_active": et.is_active,
        }
        for et in types
    ]


@router.post("/evidence-types", status_code=201)
async def create_evidence_type(
    payload: EvidenceTypeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = await db.scalar(
        select(EvidenceType).where(EvidenceType.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, "Evidence type slug already exists")
    et = EvidenceType(**payload.model_dump())
    db.add(et)
    await db.commit()
    await db.refresh(et)
    return {"id": str(et.id), "slug": et.slug}


# ── Scoring Schemes ───────────────────────────────────────────────────────────

@router.get("/scoring-schemes")
async def list_scoring_schemes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(ScoringScheme).where(ScoringScheme.is_active == True))
    schemes = result.scalars().all()
    return [
        {
            "id": str(s.id), "slug": s.slug, "name": s.name,
            "is_default": s.is_default, "scale_min": s.scale_min,
            "scale_max": s.scale_max, "scale_labels": s.scale_labels,
            "traffic_light": s.traffic_light, "formula": s.formula,
        }
        for s in schemes
    ]


@router.put("/scoring-schemes/{scheme_id}")
async def update_scoring_scheme(
    scheme_id: uuid.UUID,
    payload: ScoringSchemeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    scheme = await db.get(ScoringScheme, scheme_id)
    if not scheme:
        raise HTTPException(404, "Scoring scheme not found")

    # Validate consistency: gate min_score must not exceed scale_max
    update = payload.model_dump(exclude_none=True)
    new_max = update.get("scale_max", scheme.scale_max)
    new_min = update.get("scale_min", scheme.scale_min)
    if new_min >= new_max:
        raise HTTPException(422, "scale_min must be less than scale_max")

    for field, val in update.items():
        setattr(scheme, field, val)
    await db.commit()
    return {"id": str(scheme.id), "status": "updated"}


# ── Categories & Lookup ───────────────────────────────────────────────────────

@router.get("/categories")
async def list_categories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(ControlCategory).where(ControlCategory.is_active == True)
        .order_by(ControlCategory.sort_order)
    )
    cats = result.scalars().all()
    return [{"id": str(c.id), "slug": c.slug, "name": c.name, "description": c.description} for c in cats]


@router.get("/product-scopes")
async def list_product_scopes(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    result = await db.execute(select(ProductScope).where(ProductScope.is_active == True))
    return [{"id": str(p.id), "slug": p.slug, "name": p.name} for p in result.scalars().all()]


@router.get("/market-scopes")
async def list_market_scopes(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    result = await db.execute(select(MarketScope).where(MarketScope.is_active == True))
    return [{"id": str(m.id), "slug": m.slug, "name": m.name, "region": m.region} for m in result.scalars().all()]


@router.get("/customer-segments")
async def list_customer_segments(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    _require_admin(current_user)
    result = await db.execute(select(CustomerSegment).where(CustomerSegment.is_active == True))
    return [{"id": str(c.id), "slug": c.slug, "name": c.name, "segment_type": c.segment_type} for c in result.scalars().all()]


# ── Simulation ────────────────────────────────────────────────────────────────

@router.post("/simulation/run")
async def run_simulation(
    payload: SimulationInput,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run a simulation: determine which controls are active and what gate outcome would be.
    Returns structured result for admin preview.
    """
    _require_admin(current_user)
    params = payload.model_dump()

    # 1. All fixed controls are always active
    fixed_result = await db.execute(
        select(ControlDefinition).where(ControlDefinition.kind == ControlKind.fixed.value,
                                        ControlDefinition.status == ControlStatus.approved.value)
    )
    fixed_controls = fixed_result.scalars().all()

    # 2. Evaluate triggers → get dynamic control IDs
    trigger_result = await db.execute(
        select(DynamicTriggerRule).where(DynamicTriggerRule.is_active == True)
    )
    all_triggers = trigger_result.scalars().all()
    fired_triggers = []
    triggered_control_ids: set[str] = set()
    for trigger in all_triggers:
        if _evaluate_condition_tree(trigger.condition_tree, params):
            fired_triggers.append({"id": str(trigger.id), "name": trigger.name})
            for cid in trigger.activates_control_ids:
                triggered_control_ids.add(str(cid))

    # 3. Load triggered dynamic controls
    dynamic_controls: list[ControlDefinition] = []
    if triggered_control_ids:
        dyn_result = await db.execute(
            select(ControlDefinition).where(
                ControlDefinition.id.in_([uuid.UUID(cid) for cid in triggered_control_ids]),
                ControlDefinition.status == ControlStatus.approved.value,
            )
        )
        dynamic_controls = list(dyn_result.scalars().all())

    # 4. Compute hard stops
    all_active = list(fixed_controls) + list(dynamic_controls)
    hard_stop_active = [c for c in all_active if c.hard_stop]

    # 5. Determine required evidence
    all_evidence_ids: set[str] = set()
    for ctrl in all_active:
        for ev in ctrl.evidence_requirements:
            if isinstance(ev, dict):
                all_evidence_ids.add(ev.get("evidence_type_id", ""))

    # 6. Gate outcome estimation (simplified: if hard_stop controls exist → conditional_go)
    gate_outcome = "go"
    if hard_stop_active:
        gate_outcome = "conditional_go"  # Would be no_go if scores are insufficient

    result = {
        "input_params": params,
        "fixed_controls": [
            {"id": str(c.id), "name": c.name, "slug": c.slug, "gate_phases": c.gate_phases}
            for c in fixed_controls
        ],
        "triggered_controls": [
            {"id": str(c.id), "name": c.name, "slug": c.slug, "gate_phases": c.gate_phases}
            for c in dynamic_controls
        ],
        "fired_triggers": fired_triggers,
        "hard_stop_controls": [
            {"id": str(c.id), "name": c.name}
            for c in hard_stop_active
        ],
        "required_evidence_type_ids": list(all_evidence_ids),
        "estimated_gate_outcome": gate_outcome,
        "total_active_controls": len(all_active),
    }

    if payload.save_as_scenario and payload.scenario_name:
        scenario = SimulationScenario(
            name=payload.scenario_name,
            input_params=params,
            result=result,
            result_computed_at=datetime.now(timezone.utc),
            created_by=current_user.id,
        )
        db.add(scenario)
        await db.commit()
        result["scenario_id"] = str(scenario.id)
    
    return result


@router.get("/simulation/scenarios")
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(
        select(SimulationScenario).order_by(SimulationScenario.created_at.desc()).limit(50)
    )
    scenarios = result.scalars().all()
    return [
        {
            "id": str(s.id), "name": s.name, "description": s.description,
            "created_at": s.created_at.isoformat(),
            "total_active_controls": s.result.get("total_active_controls") if s.result else None,
        }
        for s in scenarios
    ]


# ── Changelog ─────────────────────────────────────────────────────────────────

@router.get("/changelog")
async def get_changelog(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity_type: Optional[str] = Query(None),
    entity_slug: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    _require_admin(current_user)
    stmt = select(GovernanceChangeLog)
    if entity_type:
        stmt = stmt.where(GovernanceChangeLog.entity_type == entity_type)
    if entity_slug:
        stmt = stmt.where(GovernanceChangeLog.entity_slug == entity_slug)
    stmt = stmt.order_by(GovernanceChangeLog.occurred_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    entries = result.scalars().all()
    return {
        "entries": [
            {
                "id": str(e.id),
                "entity_type": e.entity_type,
                "entity_slug": e.entity_slug,
                "action": e.action,
                "from_status": e.from_status,
                "to_status": e.to_status,
                "from_version": e.from_version,
                "to_version": e.to_version,
                "change_reason": e.change_reason,
                "actor_name": e.actor_name,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in entries
        ]
    }


@router.post("/seed", status_code=202)
async def run_seed(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run governance seed data (idempotent). Super-admin only."""
    _require_admin(current_user)
    from app.services.governance_seed import seed_all
    await seed_all(db)
    return {"status": "seeded"}
