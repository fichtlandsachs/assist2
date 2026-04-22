# app/routers/capabilities.py
"""Capability map endpoints: CRUD, tree, import, org init status."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.capability_node import CapabilityNode, ALLOWED_ASSIGNMENT_LEVELS, EXCEPTION_ALLOWED_LEVELS
from app.models.artifact_assignment import ArtifactAssignment
from app.schemas.capability import (
    CapabilityNodeCreate,
    CapabilityNodeRead,
    CapabilityNodeUpdate,
    ArtifactAssignmentCreate,
    ArtifactAssignmentRead,
    ImportValidationResult,
    OrgInitStatusRead,
    OrgInitAdvance,
)
from app.services import capability_service as svc
from app.services.capability_import_service import (
    parse_excel,
    get_demo_nodes,
    get_template_nodes,
    list_templates,
)

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


async def _get_org(db: AsyncSession, org_id: uuid.UUID) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


def _validate_assignment_level(
    artifact_type: str,
    node_type: str,
    is_exception: bool,
    exception_reason: str | None,
) -> None:
    from app.models.capability_node import NodeType
    try:
        nt = NodeType(node_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown node_type: {node_type}")

    allowed = ALLOWED_ASSIGNMENT_LEVELS.get(artifact_type, [])
    exception_levels = EXCEPTION_ALLOWED_LEVELS.get(artifact_type, [])

    if nt in allowed:
        return
    if is_exception and nt in exception_levels:
        if not exception_reason:
            raise HTTPException(
                status_code=422,
                detail=f"assignment_exception_reason required when assigning {artifact_type} to {node_type}",
            )
        return
    raise HTTPException(
        status_code=422,
        detail=(
            f"Cannot assign {artifact_type} to {node_type}. "
            f"Allowed: {[n.value for n in allowed]}."
        ),
    )


# ── Org initialization status ─────────────────────────────────────────────────

@router.get("/orgs/{org_id}/init-status", response_model=OrgInitStatusRead)
async def get_init_status(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OrgInitStatusRead:
    org = await _get_org(db, org_id)
    return OrgInitStatusRead.model_validate(org)


@router.patch("/orgs/{org_id}/init-status", response_model=OrgInitStatusRead)
async def advance_init_status(
    org_id: uuid.UUID,
    data: OrgInitAdvance,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrgInitStatusRead:
    org = await _get_org(db, org_id)
    updated = await svc.advance_org_init_status(db, org, data, current_user.id)
    return OrgInitStatusRead.model_validate(updated)


# ── Tree ──────────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/tree")
async def get_tree(
    org_id: uuid.UUID,
    with_counts: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    if with_counts:
        return await svc.get_capability_tree_with_counts(db, org_id)
    return await svc.get_capability_tree(db, org_id)


# ── Nodes CRUD ────────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/nodes", response_model=list[CapabilityNodeRead])
async def list_nodes(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[CapabilityNodeRead]:
    result = await db.execute(
        select(CapabilityNode).where(CapabilityNode.org_id == org_id)
        .order_by(CapabilityNode.node_type, CapabilityNode.sort_order)
    )
    return [CapabilityNodeRead.model_validate(n) for n in result.scalars().all()]


@router.post("/orgs/{org_id}/nodes", response_model=CapabilityNodeRead, status_code=201)
async def create_node(
    org_id: uuid.UUID,
    data: CapabilityNodeCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CapabilityNodeRead:
    node = await svc.create_node(db, org_id, data)
    return CapabilityNodeRead.model_validate(node)


@router.patch("/orgs/{org_id}/nodes/{node_id}", response_model=CapabilityNodeRead)
async def update_node(
    org_id: uuid.UUID,
    node_id: uuid.UUID,
    data: CapabilityNodeUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> CapabilityNodeRead:
    node = await svc.get_node(db, org_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    updated = await svc.update_node(db, node, data)
    return CapabilityNodeRead.model_validate(updated)


@router.delete("/orgs/{org_id}/nodes/{node_id}", status_code=204)
async def delete_node(
    org_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    node = await svc.get_node(db, org_id, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    await db.delete(node)
    await db.commit()


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/import/excel", response_model=ImportValidationResult)
async def import_excel(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    content = await file.read()
    result = parse_excel(content)
    if not dry_run and result.is_valid:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        org = await _get_org(db, org_id)
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="excel"), current_user.id
        )
    return result


@router.get("/orgs/{org_id}/import/templates")
async def list_import_templates(_user: User = Depends(get_current_user)) -> list[dict]:
    return list_templates()


@router.post("/orgs/{org_id}/import/template/{template_key}", response_model=ImportValidationResult)
async def apply_template(
    org_id: uuid.UUID,
    template_key: str,
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    try:
        nodes = get_template_nodes(template_key)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    result = ImportValidationResult(
        is_valid=True, error_count=0, warning_count=0,
        capability_count=sum(1 for n in nodes if n["node_type"] == "capability"),
        level_1_count=sum(1 for n in nodes if n["node_type"] == "level_1"),
        level_2_count=sum(1 for n in nodes if n["node_type"] == "level_2"),
        level_3_count=sum(1 for n in nodes if n["node_type"] == "level_3"),
        issues=[],
        nodes=nodes,
    )
    if not dry_run:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        org = await _get_org(db, org_id)
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="template"), current_user.id
        )
    return result


@router.post("/orgs/{org_id}/import/demo", response_model=ImportValidationResult)
async def apply_demo(
    org_id: uuid.UUID,
    dry_run: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportValidationResult:
    nodes = get_demo_nodes()
    result = ImportValidationResult(
        is_valid=True, error_count=0, warning_count=0,
        capability_count=sum(1 for n in nodes if n["node_type"] == "capability"),
        level_1_count=sum(1 for n in nodes if n["node_type"] == "level_1"),
        level_2_count=sum(1 for n in nodes if n["node_type"] == "level_2"),
        level_3_count=sum(1 for n in nodes if n["node_type"] == "level_3"),
        issues=[],
        nodes=nodes,
    )
    if not dry_run:
        await svc.delete_org_nodes(db, org_id)
        await svc.bulk_create_nodes(db, org_id, result.nodes)
        org = await _get_org(db, org_id)
        await svc.advance_org_init_status(
            db, org, OrgInitAdvance(status="capability_setup_validated", source="demo"), current_user.id
        )
    return result


# ── Assignments ───────────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/assignments", response_model=ArtifactAssignmentRead, status_code=201)
async def create_assignment(
    org_id: uuid.UUID,
    data: ArtifactAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ArtifactAssignmentRead:
    node = await svc.get_node(db, org_id, data.node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Capability node not found in this org")
    _validate_assignment_level(
        data.artifact_type, node.node_type,
        data.assignment_is_exception, data.assignment_exception_reason,
    )
    assignment = ArtifactAssignment(
        org_id=org_id,
        artifact_type=data.artifact_type,
        artifact_id=data.artifact_id,
        node_id=data.node_id,
        relation_type=data.relation_type,
        assignment_is_exception=data.assignment_is_exception,
        assignment_exception_reason=data.assignment_exception_reason,
        created_by_id=current_user.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return ArtifactAssignmentRead.model_validate(assignment)


@router.get("/orgs/{org_id}/assignments", response_model=list[ArtifactAssignmentRead])
async def list_assignments(
    org_id: uuid.UUID,
    artifact_type: str | None = Query(None),
    artifact_id: uuid.UUID | None = Query(None),
    node_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ArtifactAssignmentRead]:
    stmt = select(ArtifactAssignment).where(ArtifactAssignment.org_id == org_id)
    if artifact_type:
        stmt = stmt.where(ArtifactAssignment.artifact_type == artifact_type)
    if artifact_id:
        stmt = stmt.where(ArtifactAssignment.artifact_id == artifact_id)
    if node_id:
        stmt = stmt.where(ArtifactAssignment.node_id == node_id)
    result = await db.execute(stmt)
    return [ArtifactAssignmentRead.model_validate(a) for a in result.scalars().all()]


@router.delete("/orgs/{org_id}/assignments/{assignment_id}", status_code=204)
async def delete_assignment(
    org_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> None:
    result = await db.execute(
        select(ArtifactAssignment).where(
            ArtifactAssignment.org_id == org_id,
            ArtifactAssignment.id == assignment_id,
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await db.delete(obj)
    await db.commit()
