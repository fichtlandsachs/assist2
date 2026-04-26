# app/core/story_filter.py
"""
CRITICAL: Soft-delete filter for UserStory.

Every query touching UserStory MUST go through active_stories() or
explicitly add .where(UserStory.is_deleted == False).

This module provides:
  - active_stories()  → base SELECT with soft-delete filter applied
  - require_active_story() → raise 404 if story is deleted or not found
  - soft_delete_story() → perform a soft delete

NEVER return or process a story where is_deleted == True.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_story import UserStory


def active_stories():
    """
    Return a base SELECT for UserStory that strictly excludes deleted stories.
    Usage:
        stmt = active_stories().where(UserStory.organization_id == org_id)
    """
    return select(UserStory).where(UserStory.is_deleted == False)  # noqa: E712


async def require_active_story(
    db: AsyncSession,
    story_id: uuid.UUID,
    *,
    options: list | None = None,
) -> UserStory:
    """
    Load a UserStory by ID, raising 404 if not found OR if soft-deleted.
    This is the ONLY safe way to load a single story by ID.
    """
    stmt = active_stories().where(UserStory.id == story_id)
    if options:
        for opt in options:
            stmt = stmt.options(opt)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise HTTPException(status_code=404, detail="User Story not found")
    return story


async def soft_delete_story(
    db: AsyncSession,
    story_id: uuid.UUID,
    deleted_by_id: uuid.UUID,
) -> Optional[UserStory]:
    """
    Soft-delete a story. Sets is_deleted=True, deleted_at, deleted_by_id.
    Returns the story if found and not already deleted; None if already gone.
    Does NOT commit — caller must commit.
    """
    stmt = active_stories().where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        return None

    story.is_deleted = True
    story.deleted_at = datetime.now(timezone.utc)
    story.deleted_by_id = deleted_by_id
    return story
