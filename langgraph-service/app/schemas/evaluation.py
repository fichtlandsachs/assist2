from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class FindingCategory(str, Enum):
    CLARITY = "CLARITY"
    COMPLETENESS = "COMPLETENESS"
    TESTABILITY = "TESTABILITY"
    FEASIBILITY = "FEASIBILITY"
    BUSINESS_VALUE = "BUSINESS_VALUE"


class Ampel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class EvalFinding(BaseModel):
    id: str
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    suggestion: str


class CriterionScore(BaseModel):
    score: float = Field(ge=0, le=10)
    weight: float = Field(ge=0, le=1)
    explanation: str


class RewriteSuggestion(BaseModel):
    title: str
    story: str
    acceptance_criteria: list[str]


class EvaluateRequest(BaseModel):
    run_id: str
    story_id: str
    org_id: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    context_hints: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    run_id: str
    story_id: str
    org_id: str
    score: float = Field(ge=0, le=10)
    ampel: Ampel
    knockout: bool
    confidence: float = Field(ge=0, le=1)
    criteria_scores: dict[str, CriterionScore]
    findings: list[EvalFinding]
    open_questions: list[str]
    rewrite: RewriteSuggestion
    model_used: str
    input_tokens: int
    output_tokens: int


def compute_ampel(score: float, knockout: bool) -> Ampel:
    """Deterministic ampel — no LLM involved."""
    if knockout:
        return Ampel.RED
    if score >= 7.5:
        return Ampel.GREEN
    if score >= 5.0:
        return Ampel.YELLOW
    return Ampel.RED
