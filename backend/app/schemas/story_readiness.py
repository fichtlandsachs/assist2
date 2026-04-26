"""Pydantic schemas for Story Readiness Evaluation."""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field


# ── Sub-item schemas ──────────────────────────────────────────────────────────

class OpenTopic(BaseModel):
    topic: str
    source: Literal["documented", "inferred", "unknown"] = "unknown"
    detail: Optional[str] = None


class MissingInput(BaseModel):
    input: str
    importance: Literal["high", "medium", "low"] = "medium"


class PreparatoryWork(BaseModel):
    task: str
    owner: Optional[str] = None
    urgency: Literal["high", "medium", "low"] = "medium"


class Dependency(BaseModel):
    name: str
    type: Literal["technical", "business", "team", "external"] = "technical"
    status: Literal["resolved", "pending", "unknown"] = "unknown"


class Blocker(BaseModel):
    description: str
    severity: Literal["critical", "major", "minor"] = "major"


class Risk(BaseModel):
    description: str
    probability: Literal["high", "medium", "low"] = "medium"
    impact: Literal["high", "medium", "low"] = "medium"


class NextStep(BaseModel):
    step: str
    priority: int = Field(default=1, ge=1, le=10)
    responsible: Optional[str] = None


# ── Main evaluation schema ────────────────────────────────────────────────────

class StoryReadinessResult(BaseModel):
    """Returned by the AI evaluation for a single story."""
    readiness_score: int = Field(..., ge=0, le=100)
    readiness_state: Literal["not_ready", "partially_ready", "mostly_ready", "implementation_ready"]
    open_topics: list[OpenTopic] = Field(default_factory=list)
    missing_inputs: list[MissingInput] = Field(default_factory=list)
    required_preparatory_work: list[PreparatoryWork] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    blockers: list[Blocker] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    recommended_next_steps: list[NextStep] = Field(default_factory=list)
    summary: str = ""
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


# ── API read schemas ──────────────────────────────────────────────────────────

class StoryReadinessEvaluationRead(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    organization_id: uuid.UUID
    evaluated_for_user_id: Optional[uuid.UUID]
    readiness_score: int
    readiness_state: str
    open_topics: list[dict]
    missing_inputs: list[dict]
    required_preparatory_work: list[dict]
    dependencies: list[dict]
    blockers: list[dict]
    risks: list[dict]
    recommended_next_steps: list[dict]
    summary: Optional[str]
    model_used: Optional[str]
    confidence: Optional[float]
    error_message: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class StoryWithReadiness(BaseModel):
    """A user story augmented with its latest readiness evaluation."""
    story_id: uuid.UUID
    title: str
    status: str
    priority: str
    story_points: Optional[int]
    epic_id: Optional[uuid.UUID]
    epic_title: Optional[str]
    latest_evaluation: Optional[StoryReadinessEvaluationRead]


class MyReadinessResponse(BaseModel):
    """Complete response for 'Meine Story-Lage'."""
    total_stories: int
    implementation_ready: int
    blocked: int
    missing_inputs_count: int
    not_ready: int
    stories: list[StoryWithReadiness]


class EvaluateMyStoriesRequest(BaseModel):
    """Optional filters for batch evaluation."""
    story_ids: Optional[list[uuid.UUID]] = None   # if None → evaluate all assigned
    force: bool = False


class EvaluateMyStoriesResponse(BaseModel):
    evaluated: int
    failed: int
    results: list[StoryReadinessEvaluationRead]
