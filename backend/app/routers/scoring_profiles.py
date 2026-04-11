from __future__ import annotations
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.scoring_profile import ScoringProfileCreate, ScoringProfileRead, ScoringProfileUpdate
from app.services import scoring_profile_service

router = APIRouter(prefix="/api/v1/scoring-profiles", tags=["scoring-profiles"])


@router.get("", response_model=list[ScoringProfileRead])
async def list_profiles(
    org_id: uuid.UUID = Query(...),
    rule_set_id: Optional[uuid.UUID] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.list_scoring_profiles(db, org_id, rule_set_id)


@router.post("", response_model=ScoringProfileRead, status_code=201)
async def create_profile(
    data: ScoringProfileCreate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.create_scoring_profile(db, org_id, data, current_user.id)


@router.get("/{profile_id}", response_model=ScoringProfileRead)
async def get_profile(
    profile_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.get_scoring_profile(db, profile_id, org_id)


@router.patch("/{profile_id}", response_model=ScoringProfileRead)
async def update_profile(
    profile_id: uuid.UUID,
    data: ScoringProfileUpdate,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await scoring_profile_service.update_scoring_profile(db, profile_id, org_id, data)
