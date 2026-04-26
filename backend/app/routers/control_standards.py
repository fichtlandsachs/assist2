# app/routers/control_standards.py
"""
Control Standards & Grouped Controls API.

  GET  /api/v1/governance/standards               List all standards
  POST /api/v1/governance/standards               Create standard
  PUT  /api/v1/governance/standards/{id}          Update standard
  POST /api/v1/governance/standards/seed          Seed default standards + mappings

  GET  /api/v1/governance/controls/grouped        Grouped controls (primary query)
       ?view=standard|category|gate
       &standard_id=...  (optional filter)
       &category_id=...
       &kind=fixed|dynamic
       &hard_stop_only=true
       &active_only=true
       &draft_only=true
       &no_evidence_only=true
       &multi_standard_only=true
       &search=...

  GET  /api/v1/governance/controls/{id}/standards  Standards mapped to a control
  POST /api/v1/governance/controls/{id}/standards  Add standard mapping
  DELETE /api/v1/governance/controls/{id}/standards/{std_id}  Remove mapping

  POST /api/v1/governance/controls/{id}/family    Set control_family
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.control_standards import StandardDefinition, ControlStandardMapping
from app.models.product_governance import (
    ControlDefinition, ControlCategory, ControlStatus, ControlKind,
)
from app.services.standards_seed import seed_standards, seed_control_mappings

router = APIRouter(prefix="/governance", tags=["control-standards"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class StandardCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=100)
    name: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    standard_type: str = "external"
    color: Optional[str] = None
    display_order: int = 50


class StandardUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    description: Optional[str] = None
    standard_type: Optional[str] = None
    color: Optional[str] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class MappingCreate(BaseModel):
    standard_id: uuid.UUID
    section_ref: Optional[str] = None
    section_label: Optional[str] = None
    is_primary: bool = False
    display_order: int = 50


class FamilyUpdate(BaseModel):
    control_family: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _std_dict(s: StandardDefinition) -> dict:
    return {
        "id": str(s.id),
        "slug": s.slug,
        "name": s.name,
        "short_name": s.short_name or s.slug,
        "description": s.description,
        "standard_type": s.standard_type,
        "color": s.color,
        "is_active": s.is_active,
        "display_order": s.display_order,
    }


def _ctrl_dict(ctrl: ControlDefinition, std_badges: list[dict]) -> dict:
    return {
        "id": str(ctrl.id),
        "slug": ctrl.slug,
        "name": ctrl.name,
        "short_description": ctrl.short_description,
        "kind": ctrl.kind,
        "status": ctrl.status,
        "version": ctrl.version,
        "hard_stop": ctrl.hard_stop,
        "gate_phases": ctrl.gate_phases,
        "control_family": ctrl.control_family,
        "responsible_role": ctrl.responsible_role,
        "evidence_requirements": ctrl.evidence_requirements,
        "updated_at": ctrl.updated_at.isoformat(),
        "standards": std_badges,
    }


async def _get_std_badges(db: AsyncSession, ctrl_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(ControlStandardMapping, StandardDefinition)
        .join(StandardDefinition, ControlStandardMapping.standard_id == StandardDefinition.id)
        .where(ControlStandardMapping.control_id == ctrl_id)
        .order_by(ControlStandardMapping.is_primary.desc(), StandardDefinition.display_order)
    )
    return [
        {
            "standard_id": str(m.id),
            "standard_slug": s.slug,
            "standard_name": s.short_name or s.name,
            "section_ref": m.section_ref,
            "is_primary": m.is_primary,
            "color": s.color,
        }
        for m, s in result.fetchall()
    ]


def _count_controls(controls: list[ControlDefinition]) -> dict:
    return {
        "total": len(controls),
        "active": sum(1 for c in controls if c.status == ControlStatus.approved.value),
        "hard_stops": sum(1 for c in controls if c.hard_stop),
        "drafts": sum(1 for c in controls if c.status == ControlStatus.draft.value),
        "no_evidence": sum(1 for c in controls if not c.evidence_requirements),
    }


# ── Standards CRUD ────────────────────────────────────────────────────────────

@router.get("/standards")
async def list_standards(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StandardDefinition)
        .order_by(StandardDefinition.display_order, StandardDefinition.name)
    )
    standards = result.scalars().all()

    # Enrich each standard with control count
    out = []
    for s in standards:
        ctrl_count = await db.scalar(
            select(func.count(ControlStandardMapping.id)).where(
                ControlStandardMapping.standard_id == s.id
            )
        )
        d = _std_dict(s)
        d["control_count"] = int(ctrl_count or 0)
        out.append(d)
    return out


@router.post("/standards", status_code=201)
async def create_standard(
    payload: StandardCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = await db.scalar(
        select(StandardDefinition).where(StandardDefinition.slug == payload.slug)
    )
    if existing:
        raise HTTPException(409, f"Standard with slug '{payload.slug}' already exists")
    obj = StandardDefinition(**payload.model_dump())
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    return _std_dict(obj)


@router.put("/standards/{standard_id}")
async def update_standard(
    standard_id: uuid.UUID,
    payload: StandardUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    obj = await db.get(StandardDefinition, standard_id)
    if not obj:
        raise HTTPException(404, "Standard not found")
    for k, v in payload.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    await db.commit()
    return _std_dict(obj)


@router.post("/standards/seed")
async def seed_standards_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    std_map = await seed_standards(db)
    mapped = await seed_control_mappings(db)
    await db.commit()
    return {
        "standards_created": len([v for v in std_map.values() if v]),
        "mappings_created": mapped,
        "status": "ok",
    }


# ── Grouped Controls ──────────────────────────────────────────────────────────

@router.get("/controls-grouped")
async def get_grouped_controls(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    view: str = Query("standard", pattern="^(standard|category|gate)$"),
    standard_id: Optional[uuid.UUID] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    kind: Optional[str] = Query(None),
    hard_stop_only: bool = Query(False),
    active_only: bool = Query(False),
    draft_only: bool = Query(False),
    no_evidence_only: bool = Query(False),
    multi_standard_only: bool = Query(False),
    search: Optional[str] = Query(None),
):
    """
    Returns controls grouped by the requested view.

    Standard-view:  [{standard, categories: [{category, families: [{family, controls}]}]}]
    Category-view:  [{category, families: [{family, controls}]}]
    Gate-view:      [{gate, controls}]
    """
    # Build base control query
    stmt = select(ControlDefinition)

    if kind:
        stmt = stmt.where(ControlDefinition.kind == kind)
    if hard_stop_only:
        stmt = stmt.where(ControlDefinition.hard_stop == True)
    if active_only:
        stmt = stmt.where(ControlDefinition.status == ControlStatus.approved.value)
    if draft_only:
        stmt = stmt.where(ControlDefinition.status == ControlStatus.draft.value)
    if no_evidence_only:
        stmt = stmt.where(func.jsonb_array_length(ControlDefinition.evidence_requirements) == 0)
    if search:
        stmt = stmt.where(
            or_(
                ControlDefinition.name.ilike(f"%{search}%"),
                ControlDefinition.slug.ilike(f"%{search}%"),
                ControlDefinition.short_description.ilike(f"%{search}%"),
            )
        )
    if category_id:
        stmt = stmt.where(ControlDefinition.category_id == category_id)

    result = await db.execute(stmt.order_by(ControlDefinition.name))
    all_controls = result.scalars().all()

    # Filter by standard_id (via mapping table)
    if standard_id or multi_standard_only:
        ctrl_std_result = await db.execute(
            select(ControlStandardMapping.control_id, func.count(ControlStandardMapping.id).label("cnt"))
            .group_by(ControlStandardMapping.control_id)
        )
        ctrl_std_counts = {str(r[0]): r[1] for r in ctrl_std_result.fetchall()}

        if standard_id:
            mapped_result = await db.execute(
                select(ControlStandardMapping.control_id).where(
                    ControlStandardMapping.standard_id == standard_id
                )
            )
            allowed_ids = {str(r[0]) for r in mapped_result.fetchall()}
            all_controls = [c for c in all_controls if str(c.id) in allowed_ids]
        if multi_standard_only:
            all_controls = [c for c in all_controls if ctrl_std_counts.get(str(c.id), 0) > 1]

    # Collect control std badges + category names in bulk
    cat_result = await db.execute(select(ControlCategory))
    cat_map: dict[str, str] = {str(c.id): c.name for c in cat_result.scalars().all()}

    # Standard badges per control (batch load)
    all_ctrl_ids = [c.id for c in all_controls]
    mapping_result = await db.execute(
        select(ControlStandardMapping, StandardDefinition)
        .join(StandardDefinition, ControlStandardMapping.standard_id == StandardDefinition.id)
        .where(ControlStandardMapping.control_id.in_(all_ctrl_ids))
        .order_by(ControlStandardMapping.is_primary.desc(), StandardDefinition.display_order)
    )
    ctrl_to_badges: dict[str, list[dict]] = {}
    ctrl_to_std_ids: dict[str, list[str]] = {}
    for m, s in mapping_result.fetchall():
        cid = str(m.control_id)
        badge = {
            "standard_id": str(s.id),
            "standard_slug": s.slug,
            "standard_name": s.short_name or s.name,
            "section_ref": m.section_ref,
            "is_primary": m.is_primary,
            "color": s.color or "slate",
        }
        ctrl_to_badges.setdefault(cid, []).append(badge)
        ctrl_to_std_ids.setdefault(cid, []).append(str(s.id))

    def ctrl_item(c: ControlDefinition) -> dict:
        return _ctrl_dict(c, ctrl_to_badges.get(str(c.id), []))

    # ── Standard view ─────────────────────────────────────────────────────────
    if view == "standard":
        std_result = await db.execute(
            select(StandardDefinition)
            .where(StandardDefinition.is_active == True)
            .order_by(StandardDefinition.display_order)
        )
        standards = std_result.scalars().all()

        if standard_id:
            standards = [s for s in standards if s.id == standard_id]

        output = []
        for std in standards:
            sid = str(std.id)
            std_controls = [c for c in all_controls if sid in ctrl_to_std_ids.get(str(c.id), [])]
            if not std_controls:
                continue

            # Group by category
            cat_groups: dict[str, list[ControlDefinition]] = {}
            for c in std_controls:
                cat_name = cat_map.get(str(c.category_id), "Sonstige") if c.category_id else "Sonstige"
                cat_groups.setdefault(cat_name, []).append(c)

            cat_output = []
            for cat_name, cat_controls in sorted(cat_groups.items()):
                # Group by control family within category
                family_groups: dict[str, list[ControlDefinition]] = {}
                for c in cat_controls:
                    fam = c.control_family or "Weitere Controls"
                    family_groups.setdefault(fam, []).append(c)

                families = [
                    {
                        "family": fam,
                        "counts": _count_controls(fam_controls),
                        "controls": [ctrl_item(c) for c in fam_controls],
                    }
                    for fam, fam_controls in sorted(family_groups.items())
                ]
                cat_output.append({
                    "category": cat_name,
                    "counts": _count_controls(cat_controls),
                    "families": families,
                })

            output.append({
                "standard_id": sid,
                "standard_slug": std.slug,
                "standard_name": std.name,
                "standard_short": std.short_name or std.slug,
                "standard_color": std.color or "slate",
                "standard_type": std.standard_type,
                "counts": _count_controls(std_controls),
                "categories": cat_output,
            })

        return {"view": "standard", "groups": output}

    # ── Category view ─────────────────────────────────────────────────────────
    if view == "category":
        cat_groups: dict[str, list[ControlDefinition]] = {}
        for c in all_controls:
            cat_name = cat_map.get(str(c.category_id), "Sonstige") if c.category_id else "Sonstige"
            cat_groups.setdefault(cat_name, []).append(c)

        output = []
        for cat_name, cat_controls in sorted(cat_groups.items()):
            family_groups: dict[str, list[ControlDefinition]] = {}
            for c in cat_controls:
                fam = c.control_family or "Weitere Controls"
                family_groups.setdefault(fam, []).append(c)

            families = [
                {
                    "family": fam,
                    "counts": _count_controls(fam_controls),
                    "controls": [ctrl_item(c) for c in fam_controls],
                }
                for fam, fam_controls in sorted(family_groups.items())
            ]
            output.append({
                "category": cat_name,
                "counts": _count_controls(cat_controls),
                "families": families,
            })

        return {"view": "category", "groups": output}

    # ── Gate view ─────────────────────────────────────────────────────────────
    if view == "gate":
        gate_groups: dict[str, list[ControlDefinition]] = {}
        for c in all_controls:
            gates = c.gate_phases or ["Kein Gate"]
            for g in gates:
                gate_groups.setdefault(g, []).append(c)

        output = [
            {
                "gate": gate,
                "counts": _count_controls(controls),
                "controls": [ctrl_item(c) for c in sorted(controls, key=lambda x: x.name)],
            }
            for gate, controls in sorted(gate_groups.items())
        ]
        return {"view": "gate", "groups": output}

    raise HTTPException(400, "Invalid view")


# ── Control ↔ Standard mapping management ─────────────────────────────────────

@router.get("/controls/{control_id}/standards")
async def get_control_standards(
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ControlStandardMapping, StandardDefinition)
        .join(StandardDefinition, ControlStandardMapping.standard_id == StandardDefinition.id)
        .where(ControlStandardMapping.control_id == control_id)
        .order_by(ControlStandardMapping.is_primary.desc(), StandardDefinition.display_order)
    )
    return [
        {
            "mapping_id": str(m.id),
            "standard_id": str(s.id),
            "standard_slug": s.slug,
            "standard_name": s.name,
            "standard_short": s.short_name or s.slug,
            "section_ref": m.section_ref,
            "section_label": m.section_label,
            "is_primary": m.is_primary,
            "display_order": m.display_order,
            "color": s.color,
        }
        for m, s in result.fetchall()
    ]


@router.post("/controls/{control_id}/standards", status_code=201)
async def add_control_standard(
    control_id: uuid.UUID,
    payload: MappingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")
    std = await db.get(StandardDefinition, payload.standard_id)
    if not std:
        raise HTTPException(404, "Standard not found")

    existing = await db.scalar(
        select(ControlStandardMapping).where(
            and_(
                ControlStandardMapping.control_id == control_id,
                ControlStandardMapping.standard_id == payload.standard_id,
            )
        )
    )
    if existing:
        raise HTTPException(409, "Mapping already exists")

    m = ControlStandardMapping(
        control_id=control_id,
        standard_id=payload.standard_id,
        section_ref=payload.section_ref,
        section_label=payload.section_label,
        is_primary=payload.is_primary,
        display_order=payload.display_order,
    )
    db.add(m)
    await db.commit()
    return {"mapping_id": str(m.id), "status": "created"}


@router.delete("/controls/{control_id}/standards/{standard_id}", status_code=204)
async def remove_control_standard(
    control_id: uuid.UUID,
    standard_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    m = await db.scalar(
        select(ControlStandardMapping).where(
            and_(
                ControlStandardMapping.control_id == control_id,
                ControlStandardMapping.standard_id == standard_id,
            )
        )
    )
    if not m:
        raise HTTPException(404, "Mapping not found")
    await db.delete(m)
    await db.commit()


@router.post("/controls/{control_id}/family")
async def set_control_family(
    control_id: uuid.UUID,
    payload: FamilyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ctrl = await db.get(ControlDefinition, control_id)
    if not ctrl:
        raise HTTPException(404, "Control not found")
    ctrl.control_family = payload.control_family
    await db.commit()
    return {"slug": ctrl.slug, "control_family": ctrl.control_family}
