from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class StoryVersionCreate(BaseModel):
    title: str
    description: Optional[str] = None
    as_a: Optional[str] = None
    i_want: Optional[str] = None
    so_that: Optional[str] = None
    acceptance_criteria: list[dict] = []
    priority: Optional[str] = None
    story_points: Optional[int] = None


class StoryVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    version_number: int
    title: str
    description: Optional[str]
    as_a: Optional[str]
    i_want: Optional[str]
    so_that: Optional[str]
    acceptance_criteria: list
    priority: Optional[str]
    story_points: Optional[int]
    status: str
    content_hash: str
    created_by: Optional[uuid.UUID]
    created_at: datetime
