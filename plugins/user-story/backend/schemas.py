import uuid
from datetime import datetime
from enum import Enum
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class StoryStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    CANCELLED = "cancelled"


class StoryPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestCaseType(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    E2E = "e2e"
    MANUAL = "manual"


class TestCaseStatus(str, Enum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    pages: int

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Story Schemas
# ---------------------------------------------------------------------------

class StoryCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: StoryPriority = StoryPriority.MEDIUM
    story_points: Optional[int] = Field(None, ge=1, le=13)
    group_id: Optional[uuid.UUID] = None
    acceptance_criteria: List[str] = Field(default_factory=list)
    assignee_id: Optional[uuid.UUID] = None
    target_audience: Optional[str] = None
    doc_version: Optional[str] = Field(None, max_length=20)

    @field_validator("story_points")
    @classmethod
    def validate_fibonacci(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in {1, 2, 3, 5, 8, 13}:
            raise ValueError("story_points must be a Fibonacci number: 1, 2, 3, 5, 8, or 13")
        return v


class StoryUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[StoryStatus] = None
    priority: Optional[StoryPriority] = None
    story_points: Optional[int] = Field(None, ge=1, le=13)
    assignee_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    acceptance_criteria: Optional[List[str]] = None
    target_audience: Optional[str] = None
    doc_version: Optional[str] = Field(None, max_length=20)

    @field_validator("story_points")
    @classmethod
    def validate_fibonacci(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in {1, 2, 3, 5, 8, 13}:
            raise ValueError("story_points must be a Fibonacci number: 1, 2, 3, 5, 8, or 13")
        return v


class StoryRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    description: Optional[str]
    status: StoryStatus
    priority: StoryPriority
    story_points: Optional[int]
    assignee_id: Optional[uuid.UUID]
    reporter_id: uuid.UUID
    group_id: Optional[uuid.UUID]
    parent_story_id: Optional[uuid.UUID]
    acceptance_criteria: Optional[List[str]]
    target_audience: Optional[str] = None
    doc_version: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class StoryFilter(BaseModel):
    status: Optional[StoryStatus] = None
    priority: Optional[StoryPriority] = None
    assignee_id: Optional[uuid.UUID] = None
    group_id: Optional[uuid.UUID] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


# Type alias for paginated story list
StoryList = PaginatedResponse[StoryRead]


# ---------------------------------------------------------------------------
# Status Transition
# ---------------------------------------------------------------------------

class StatusTransitionRequest(BaseModel):
    status: StoryStatus
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Delivery
# ---------------------------------------------------------------------------

class AIDeliveryRequest(BaseModel):
    """Trigger AI-Delivery workflow for a story."""
    additional_context: Optional[str] = None


class AIDeliveryResponse(BaseModel):
    execution_id: str
    process_id: str
    story_id: uuid.UUID
    status: str
    triggered_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# TestCase Schemas
# ---------------------------------------------------------------------------

class TestCaseCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    type: TestCaseType
    steps: Optional[List[str]] = None
    expected_result: Optional[str] = None


class TestCaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[TestCaseStatus] = None
    steps: Optional[List[str]] = None
    actual_result: Optional[str] = None


class TestCaseRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    story_id: uuid.UUID
    title: str
    description: Optional[str]
    type: TestCaseType
    status: TestCaseStatus
    steps: Optional[List[str]]
    expected_result: Optional[str]
    actual_result: Optional[str]
    created_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

class StoryScoreResponse(BaseModel):
    level: str       # "low" | "medium" | "high"
    confidence: float
    clarity: float
    complexity: float
    risk: float
    domain: str      # "technical" | "business" | "security" | "generic"
