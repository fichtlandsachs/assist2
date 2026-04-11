from __future__ import annotations
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.story_version import StoryVersion
from app.models.user_story import UserStory
from app.schemas.story_version import StoryVersionCreate


def _compute_content_hash(data: StoryVersionCreate) -> str:
    """SHA-256 over deterministic JSON of story content."""
    content = {
        "title": data.title,
        "description": data.description or "",
        "as_a": data.as_a or "",
        "i_want": data.i_want or "",
        "so_that": data.so_that or "",
        "acceptance_criteria": sorted(
            json.dumps(c, sort_keys=True) for c in (data.acceptance_criteria or [])
        ),
    }
    serialized = json.dumps(content, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def create_version(
    db: AsyncSession,
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    data: StoryVersionCreate,
    created_by: uuid.UUID,
) -> StoryVersion:
    # Verify story exists and belongs to org
    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Story not found")

    content_hash = _compute_content_hash(data)

    # Dedup: reject if identical content already has a version
    existing_hash = await db.execute(
        select(StoryVersion).where(
            StoryVersion.story_id == story_id,
            StoryVersion.content_hash == content_hash,
        )
    )
    if existing_hash.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Identical content already exists as a version")

    # Next version number
    max_ver_result = await db.execute(
        select(func.max(StoryVersion.version_number)).where(
            StoryVersion.story_id == story_id
        )
    )
    max_ver: int = max_ver_result.scalar() or 0

    version = StoryVersion(
        story_id=story_id,
        org_id=org_id,
        version_number=max_ver + 1,
        title=data.title,
        description=data.description,
        as_a=data.as_a,
        i_want=data.i_want,
        so_that=data.so_that,
        acceptance_criteria=data.acceptance_criteria or [],
        priority=data.priority,
        story_points=data.story_points,
        status="draft",
        content_hash=content_hash,
        created_by=created_by,
    )
    db.add(version)

    # Update story.current_version_id
    story.current_version_id = version.id
    story.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(version)
    return version


async def list_versions(
    db: AsyncSession, story_id: uuid.UUID, org_id: uuid.UUID
) -> list[StoryVersion]:
    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Story not found")
    result = await db.execute(
        select(StoryVersion)
        .where(StoryVersion.story_id == story_id)
        .order_by(StoryVersion.version_number.asc())
    )
    return list(result.scalars().all())


async def get_version(
    db: AsyncSession, story_id: uuid.UUID, version_id: uuid.UUID, org_id: uuid.UUID
) -> StoryVersion:
    result = await db.execute(
        select(StoryVersion).where(
            StoryVersion.id == version_id,
            StoryVersion.story_id == story_id,
            StoryVersion.org_id == org_id,
        )
    )
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Story version not found")
    return version
