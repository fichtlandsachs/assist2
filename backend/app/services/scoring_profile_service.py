from __future__ import annotations
import uuid
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scoring_profile import ScoringProfile
from app.schemas.scoring_profile import ScoringProfileCreate, ScoringProfileUpdate


async def create_scoring_profile(
    db: AsyncSession,
    org_id: uuid.UUID,
    data: ScoringProfileCreate,
    created_by: uuid.UUID,
) -> ScoringProfile:
    profile = ScoringProfile(
        org_id=org_id,
        rule_set_id=data.rule_set_id,
        name=data.name,
        version=1,
        dimension_weights=data.dimension_weights,
        pass_threshold=data.pass_threshold,
        warn_threshold=data.warn_threshold,
        auto_approve_threshold=data.auto_approve_threshold,
        require_review_below=data.require_review_below,
        is_default=data.is_default,
        created_by=created_by,
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_scoring_profile(
    db: AsyncSession, profile_id: uuid.UUID, org_id: uuid.UUID
) -> ScoringProfile:
    result = await db.execute(
        select(ScoringProfile).where(
            ScoringProfile.id == profile_id, ScoringProfile.org_id == org_id
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Scoring profile not found")
    return profile


async def list_scoring_profiles(
    db: AsyncSession, org_id: uuid.UUID, rule_set_id: Optional[uuid.UUID] = None
) -> list[ScoringProfile]:
    stmt = select(ScoringProfile).where(ScoringProfile.org_id == org_id)
    if rule_set_id:
        stmt = stmt.where(ScoringProfile.rule_set_id == rule_set_id)
    result = await db.execute(stmt.order_by(ScoringProfile.created_at.desc()))
    return list(result.scalars().all())


async def update_scoring_profile(
    db: AsyncSession, profile_id: uuid.UUID, org_id: uuid.UUID, data: ScoringProfileUpdate
) -> ScoringProfile:
    profile = await get_scoring_profile(db, profile_id, org_id)
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(profile, field, value)
    await db.commit()
    await db.refresh(profile)
    return profile
