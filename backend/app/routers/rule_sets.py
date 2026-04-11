from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.rule_set import (
    RuleSetCreate, RuleSetRead, RuleSetUpdate,
    RuleDefinitionCreate, RuleDefinitionRead, RuleDefinitionUpdate,
)
from app.services import rule_set_service

router = APIRouter(prefix="/api/v1/rule-sets", tags=["rule-sets"])


@router.get("", response_model=list[RuleSetRead])
async def list_rule_sets(
    org_id: uuid.UUID = Query(...),
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.list_rule_sets(db, org_id, status)


@router.post("", response_model=RuleSetRead, status_code=201)
async def create_rule_set(
    data: RuleSetCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.create_rule_set(db, org_id, data, current_user.id)


@router.get("/{rule_set_id}", response_model=RuleSetRead)
async def get_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.get_rule_set(db, rule_set_id, org_id)


@router.patch("/{rule_set_id}", response_model=RuleSetRead)
async def update_rule_set(
    rule_set_id: uuid.UUID,
    data: RuleSetUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.update_rule_set(db, rule_set_id, org_id, data)


@router.post("/{rule_set_id}/activate", response_model=RuleSetRead)
async def activate_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.activate_rule_set(db, rule_set_id, org_id)


@router.post("/{rule_set_id}/archive", response_model=RuleSetRead)
async def archive_rule_set(
    rule_set_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.archive_rule_set(db, rule_set_id, org_id)


@router.post("/{rule_set_id}/rules", response_model=RuleDefinitionRead, status_code=201)
async def add_rule(
    rule_set_id: uuid.UUID,
    data: RuleDefinitionCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.add_rule(db, rule_set_id, org_id, data)


@router.patch("/{rule_set_id}/rules/{rule_id}", response_model=RuleDefinitionRead)
async def update_rule(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: RuleDefinitionUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await rule_set_service.update_rule(db, rule_set_id, rule_id, org_id, data)


@router.delete("/{rule_set_id}/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await rule_set_service.delete_rule(db, rule_set_id, rule_id, org_id)
