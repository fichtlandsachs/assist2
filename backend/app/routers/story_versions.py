from __future__ import annotations
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.story_version import StoryVersionCreate, StoryVersionRead
from app.services import story_version_service

router = APIRouter(prefix="/api/v1/stories", tags=["story-versions"])


@router.post("/{story_id}/versions", response_model=StoryVersionRead, status_code=201)
async def create_version(
    story_id: uuid.UUID,
    data: StoryVersionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(UserStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.create_version(
        db, story_id, story.organization_id, data, current_user.id
    )


@router.get("/{story_id}/versions", response_model=list[StoryVersionRead])
async def list_versions(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(UserStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.list_versions(db, story_id, story.organization_id)


@router.get("/{story_id}/versions/{version_id}", response_model=StoryVersionRead)
async def get_version(
    story_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    story = await db.get(UserStory, story_id)
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")
    return await story_version_service.get_version(
        db, story_id, version_id, story.organization_id
    )
