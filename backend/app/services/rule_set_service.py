from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.rule_set import RuleSet
from app.models.rule_definition import RuleDefinition
from app.schemas.rule_set import RuleSetCreate, RuleSetUpdate, RuleDefinitionCreate, RuleDefinitionUpdate


async def create_rule_set(
    db: AsyncSession,
    org_id: uuid.UUID,
    data: RuleSetCreate,
    created_by: uuid.UUID,
) -> RuleSet:
    existing = await db.execute(
        select(RuleSet).where(
            RuleSet.org_id == org_id,
            RuleSet.name == data.name,
            RuleSet.status != "archived",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Rule set with this name already exists")

    rs = RuleSet(
        org_id=org_id,
        name=data.name,
        description=data.description,
        version=1,
        status="draft",
        created_by=created_by,
    )
    db.add(rs)
    await db.commit()
    await db.refresh(rs)
    # Re-fetch with relationship loaded (refresh doesn't load relationships)
    return await get_rule_set(db, rs.id, org_id)


async def get_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    result = await db.execute(
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.id == rule_set_id, RuleSet.org_id == org_id)
    )
    rs = result.scalar_one_or_none()
    if rs is None:
        raise HTTPException(status_code=404, detail="Rule set not found")
    return rs


async def list_rule_sets(
    db: AsyncSession, org_id: uuid.UUID, status: Optional[str] = None
) -> list[RuleSet]:
    stmt = (
        select(RuleSet)
        .options(selectinload(RuleSet.rules))
        .where(RuleSet.org_id == org_id)
        .order_by(RuleSet.created_at.desc())
    )
    if status:
        stmt = stmt.where(RuleSet.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID, data: RuleSetUpdate
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen and cannot be modified")
    if data.name is not None:
        rs.name = data.name
    if data.description is not None:
        rs.description = data.description
    await db.commit()
    return await get_rule_set(db, rule_set_id, org_id)


async def activate_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.status == "active":
        raise HTTPException(status_code=409, detail="Rule set is already active")
    if rs.status == "archived":
        raise HTTPException(status_code=409, detail="Cannot activate an archived rule set")
    now = datetime.now(timezone.utc)
    rs.status = "active"
    rs.frozen_at = now
    rs.activated_at = now
    await db.commit()
    return await get_rule_set(db, rule_set_id, org_id)


async def archive_rule_set(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID
) -> RuleSet:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.status == "archived":
        raise HTTPException(status_code=409, detail="Already archived")
    rs.status = "archived"
    rs.archived_at = datetime.now(timezone.utc)
    await db.commit()
    return await get_rule_set(db, rule_set_id, org_id)


async def add_rule(
    db: AsyncSession, rule_set_id: uuid.UUID, org_id: uuid.UUID, data: RuleDefinitionCreate
) -> RuleDefinition:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot add rules")
    rule = RuleDefinition(
        rule_set_id=rule_set_id,
        name=data.name,
        description=data.description,
        rule_type=data.rule_type,
        dimension=data.dimension,
        weight=data.weight,
        parameters=data.parameters,
        prompt_template=data.prompt_template,
        order_index=data.order_index,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


async def update_rule(
    db: AsyncSession,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    org_id: uuid.UUID,
    data: RuleDefinitionUpdate,
) -> RuleDefinition:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot modify rules")
    result = await db.execute(
        select(RuleDefinition).where(
            RuleDefinition.id == rule_id,
            RuleDefinition.rule_set_id == rule_set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(
    db: AsyncSession, rule_set_id: uuid.UUID, rule_id: uuid.UUID, org_id: uuid.UUID
) -> None:
    rs = await get_rule_set(db, rule_set_id, org_id)
    if rs.is_frozen:
        raise HTTPException(status_code=409, detail="Rule set is frozen — cannot delete rules")
    result = await db.execute(
        select(RuleDefinition).where(
            RuleDefinition.id == rule_id,
            RuleDefinition.rule_set_id == rule_set_id,
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    await db.delete(rule)
    await db.commit()
