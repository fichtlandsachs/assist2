# app/routers/controls.py
"""CRUD endpoints for compliance controls and their capability-node assignments."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.control import Control, ControlCapabilityAssignment
from app.schemas.control import (
    ControlCreate,
    ControlRead,
    ControlUpdate,
    ControlCapabilityAssignmentCreate,
    ControlCapabilityAssignmentRead,
    ControlCapabilityAssignmentUpdate,
)
from app.services import control_service as svc

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_control(
    db: AsyncSession, org_id: uuid.UUID, control_id: uuid.UUID
) -> Control:
    result = await db.execute(
        select(Control).where(
            and_(Control.id == control_id, Control.org_id == org_id)
        )
    )
    ctrl = result.scalar_one_or_none()
    if not ctrl:
        raise HTTPException(status_code=404, detail="Control not found")
    return ctrl


# ─── Control CRUD ─────────────────────────────────────────────────────────────

@router.get("/api/v1/controls/orgs/{org_id}", response_model=list[ControlRead])
async def list_controls(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ControlRead]:
    result = await db.execute(
        select(Control).where(Control.org_id == org_id).order_by(Control.created_at.desc())
    )
    return [ControlRead.model_validate(c) for c in result.scalars().all()]


@router.post(
    "/api/v1/controls/orgs/{org_id}",
    response_model=ControlRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_control(
    org_id: uuid.UUID,
    data: ControlCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ControlRead:
    ctrl = Control(
        org_id=org_id,
        title=data.title,
        description=data.description,
        control_type=data.control_type,
        implementation_status=data.implementation_status,
        owner_id=data.owner_id,
        review_interval_days=data.review_interval_days,
        framework_refs=data.framework_refs or [],
    )
    db.add(ctrl)
    await db.commit()
    await db.refresh(ctrl)
    return ControlRead.model_validate(ctrl)


@router.get("/api/v1/controls/orgs/{org_id}/{control_id}", response_model=ControlRead)
async def get_control(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ControlRead:
    ctrl = await _get_control(db, org_id, control_id)
    return ControlRead.model_validate(ctrl)


@router.patch("/api/v1/controls/orgs/{org_id}/{control_id}", response_model=ControlRead)
async def update_control(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    data: ControlUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ControlRead:
    ctrl = await _get_control(db, org_id, control_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ctrl, field, value)
    ctrl.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(ctrl)
    return ControlRead.model_validate(ctrl)


@router.delete(
    "/api/v1/controls/orgs/{org_id}/{control_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_control(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    ctrl = await _get_control(db, org_id, control_id)
    await db.delete(ctrl)
    await db.commit()
    return Response(status_code=204)


# ─── Capability Assignments ───────────────────────────────────────────────────

@router.post(
    "/api/v1/controls/orgs/{org_id}/{control_id}/capabilities",
    response_model=list[ControlCapabilityAssignmentRead],
    status_code=status.HTTP_201_CREATED,
)
async def assign_control_to_capability(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    data: ControlCapabilityAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ControlCapabilityAssignmentRead]:
    # Verify control belongs to org
    await _get_control(db, org_id, control_id)

    assignments = await svc.assign_control_to_capability(
        db=db,
        org_id=org_id,
        control_id=control_id,
        capability_node_id=data.capability_node_id,
        maturity_level=data.maturity_level,
        effectiveness=data.effectiveness,
        coverage_note=data.coverage_note,
        gap_description=data.gap_description,
        assessor_id=data.assessor_id,
        propagate_to_children=data.propagate_to_children,
    )
    return [ControlCapabilityAssignmentRead.model_validate(a) for a in assignments]


@router.get(
    "/api/v1/controls/orgs/{org_id}/{control_id}/capabilities",
    response_model=list[ControlCapabilityAssignmentRead],
)
async def list_control_capability_assignments(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[ControlCapabilityAssignmentRead]:
    await _get_control(db, org_id, control_id)
    result = await db.execute(
        select(ControlCapabilityAssignment).where(
            and_(
                ControlCapabilityAssignment.control_id == control_id,
                ControlCapabilityAssignment.org_id == org_id,
            )
        )
    )
    return [ControlCapabilityAssignmentRead.model_validate(a) for a in result.scalars().all()]


@router.patch(
    "/api/v1/controls/orgs/{org_id}/{control_id}/capabilities/{node_id}",
    response_model=ControlCapabilityAssignmentRead,
)
async def update_control_capability_assignment(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    node_id: uuid.UUID,
    data: ControlCapabilityAssignmentUpdate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ControlCapabilityAssignmentRead:
    await _get_control(db, org_id, control_id)
    result = await db.execute(
        select(ControlCapabilityAssignment).where(
            and_(
                ControlCapabilityAssignment.control_id == control_id,
                ControlCapabilityAssignment.capability_node_id == node_id,
                ControlCapabilityAssignment.org_id == org_id,
            )
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(assignment, field, value)
    assignment.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(assignment)
    return ControlCapabilityAssignmentRead.model_validate(assignment)


@router.delete(
    "/api/v1/controls/orgs/{org_id}/{control_id}/capabilities/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_control_from_capability(
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    node_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    await _get_control(db, org_id, control_id)
    await svc.remove_control_from_capability(db, org_id, control_id, node_id)
    return Response(status_code=204)
