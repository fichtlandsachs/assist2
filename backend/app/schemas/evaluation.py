from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel
import uuid


class EvaluationStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AmpelEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class CriterionScoreRead(BaseModel):
    score: float
    weight: float
    explanation: str


class FindingRead(BaseModel):
    id: str
    severity: str
    category: str
    title: str
    description: str
    suggestion: str


class RewriteRead(BaseModel):
    title: str
    story: str
    acceptance_criteria: list[str]


class EvaluationResultRead(BaseModel):
    model_config = {"protected_namespaces": ()}

    score: float
    ampel: AmpelEnum
    knockout: bool
    confidence: float
    criteria_scores: dict[str, CriterionScoreRead]
    findings: list[FindingRead]
    open_questions: list[str]
    rewrite: RewriteRead
    model_used: str
    input_tokens: int
    output_tokens: int


class EvaluationRunRead(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    org_id: uuid.UUID
    status: EvaluationStatusEnum
    score: Optional[float] = None
    ampel: Optional[AmpelEnum] = None
    knockout: bool = False
    confidence: Optional[float] = None
    result: Optional[EvaluationResultRead] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StartEvaluationResponse(BaseModel):
    run_id: uuid.UUID
    status: EvaluationStatusEnum
    result: Optional[EvaluationResultRead] = None


class DuplicateCandidate(BaseModel):
    story_id: uuid.UUID
    title: str
    similarity_score: float
    explanation: str


class DuplicateCheckResponse(BaseModel):
    duplicates: list[DuplicateCandidate]
    similar: list[DuplicateCandidate]
