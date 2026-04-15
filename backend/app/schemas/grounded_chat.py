"""Pydantic schemas for the structured /ai/chat/grounded endpoint."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class CitationSchema(BaseModel):
    source_type: str
    source_name: str
    excerpt_location: str | None = None
    relevance_score: float


class ValidationFindingSchema(BaseModel):
    code: str
    severity: Literal["info", "warning", "error", "blocking"]
    message: str
    affected_field: str | None = None
    blocking: bool = False


class UsedSourceSchema(BaseModel):
    source_type: str
    source_name: str
    url: str | None = None
    relevance_score: float
    freshness_score: float
    authority_score: float
    usable: bool


class GroundedChatRequest(BaseModel):
    messages: list[dict]            # [{role, content}]
    mode: str = "chat"
    org_id: str | None = None
    policy_mode: Literal[
        "strict_grounded",
        "grounded_with_explicit_uncertainty",
        "draft_mode",
        "block_on_insufficient_evidence",
    ] = "strict_grounded"


class GroundedChatResponse(BaseModel):
    answer: str
    summary: str = ""
    facts: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    citations: list[CitationSchema] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_findings: list[ValidationFindingSchema] = Field(default_factory=list)
    confidence: Literal["HIGH", "MEDIUM", "LOW", "UNGROUNDED"] = "UNGROUNDED"
    grounded: bool = False
    blocked: bool = False
    policy_mode: str = "strict_grounded"
    source_mode: Literal["internal_only", "internal_plus_web"] = "internal_only"
    used_sources: list[UsedSourceSchema] = Field(default_factory=list)
    fallback_applied: bool = False
