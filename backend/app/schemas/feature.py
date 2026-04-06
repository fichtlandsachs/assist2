from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid
from app.models.feature import FeatureStatus
from app.models.user_story import StoryPriority
from app.schemas.user_story import Source


class AIFeatureSuggestion(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"   # low | medium | high | critical
    story_points: Optional[int] = None
    sources: list[Source] = []


class AIFeatureSuggestResponse(BaseModel):
    suggestions: list[AIFeatureSuggestion]


class FeatureCreate(BaseModel):
    story_id: uuid.UUID
    title: str
    description: Optional[str] = None
    priority: StoryPriority = StoryPriority.medium
    story_points: Optional[int] = None
    epic_id: Optional[uuid.UUID] = None


class FeatureUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[FeatureStatus] = None
    priority: Optional[StoryPriority] = None
    story_points: Optional[int] = None
    epic_id: Optional[uuid.UUID] = None


class FeatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    story_id: uuid.UUID
    story_title: Optional[str] = None
    epic_id: Optional[uuid.UUID]
    created_by_id: uuid.UUID
    title: str
    description: Optional[str]
    status: FeatureStatus
    priority: StoryPriority
    story_points: Optional[int]
    created_at: datetime
    updated_at: datetime
