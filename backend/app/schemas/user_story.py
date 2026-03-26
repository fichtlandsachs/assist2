from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid
from app.models.user_story import StoryStatus, StoryPriority


class UserStoryCreate(BaseModel):
    title: str
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    priority: StoryPriority = StoryPriority.medium
    story_points: Optional[int] = None
    epic_id: Optional[uuid.UUID] = None


class UserStoryUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    status: Optional[StoryStatus] = None
    priority: Optional[StoryPriority] = None
    story_points: Optional[int] = None
    dor_passed: Optional[bool] = None
    definition_of_done: Optional[str] = None
    doc_additional_info: Optional[str] = None
    doc_workarounds: Optional[str] = None
    epic_id: Optional[uuid.UUID] = None


class UserStoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    description: Optional[str]
    acceptance_criteria: Optional[str]
    status: StoryStatus
    priority: StoryPriority
    story_points: Optional[int]
    dor_passed: bool
    quality_score: Optional[int]
    ai_suggestions: Optional[str]
    generated_docs: Optional[str]
    confluence_page_url: Optional[str]
    is_split: bool
    epic_id: Optional[uuid.UUID]
    parent_story_id: Optional[uuid.UUID]
    definition_of_done: Optional[str]
    doc_additional_info: Optional[str]
    doc_workarounds: Optional[str]
    created_at: datetime
    updated_at: datetime


class AISuggestRequest(BaseModel):
    title: str
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    story_id: Optional[uuid.UUID] = None  # if set, quality_score is persisted


class AISuggestion(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    explanation: str
    dor_issues: list[str] = []
    quality_score: int  # 0-100


class AISuggestResponse(BaseModel):
    suggestions: AISuggestion


class StoryDocsSave(BaseModel):
    changelog_entry: str
    pdf_outline: list[str]
    summary: str
    technical_notes: str
    confluence_space_key: Optional[str] = None
    confluence_parent_page_id: Optional[str] = None


class StoryDocsRead(BaseModel):
    changelog_entry: str
    pdf_outline: list[str]
    summary: str
    technical_notes: str
    confluence_page_url: Optional[str] = None
    additional_info: Optional[str] = None
    workarounds: Optional[str] = None
    nextcloud_path: Optional[str] = None


class EpicCreate(BaseModel):
    title: str
    description: Optional[str] = None


class EpicUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class EpicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: Optional[str]
    status: str = "planning"
    created_at: datetime
    updated_at: datetime


class StorySplitItem(BaseModel):
    title: str
    description: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    story_points: Optional[int] = None


class StorySplitSuggestion(BaseModel):
    stories: list[StorySplitItem]


class StorySplitSave(BaseModel):
    stories: list[StorySplitItem]
    epic_title: Optional[str] = None
    epic_description: Optional[str] = None
    continue_with_index: int = 0   # index into stories list


class StorySplitResult(BaseModel):
    epic: Optional[EpicRead]
    stories: list[UserStoryRead]
    continue_with_id: uuid.UUID


class AITestCaseSuggestion(BaseModel):
    title: str
    steps: Optional[str] = None
    expected_result: Optional[str] = None


class AITestCaseSuggestResponse(BaseModel):
    suggestions: list[AITestCaseSuggestion]


class DoDItem(BaseModel):
    text: str
    done: bool = False


class AIDoDSuggestion(BaseModel):
    text: str
    category: Optional[str] = None  # e.g. "Qualität", "Tests", "Dokumentation"


class AIDoDSuggestResponse(BaseModel):
    suggestions: list[AIDoDSuggestion]
