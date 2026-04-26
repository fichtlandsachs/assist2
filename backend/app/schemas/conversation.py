"""Pydantic schemas for Conversation Engine API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Conversation ─────────────────────────────────────────────────────────────

class ConversationStartRequest(BaseModel):
    title: Optional[str] = None
    initialMessage: Optional[str] = None
    mode: str = "exploration"  # exploration | story | review


class ConversationStartResponse(BaseModel):
    conversationId: str
    title: str
    mode: str
    status: str
    createdAt: datetime


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    status: str
    currentMode: str
    orgId: str
    userId: str
    createdAt: datetime
    updatedAt: datetime


class MessageRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    messageId: str
    response: str
    role: str = "assistant"
    createdAt: datetime


class ProcessMessageResponse(BaseModel):
    success: bool = True
    response: str
    mode: str
    factsExtracted: list[dict[str, Any]] = []
    protocolUpdates: dict[str, Any] = {}
    storySizing: Optional[dict[str, Any]] = None
    readiness: Optional[dict[str, Any]] = None
    nextQuestions: list[dict[str, Any]] = []
    structureProposal: Optional[dict[str, Any]] = None
    errors: list[str] = []


class ProtocolResponse(BaseModel):
    areaId: str
    key: str
    displayName: str
    description: Optional[str]
    helpText: Optional[str]
    isRequired: bool
    sortOrder: int
    status: str  # empty | suggested | confirmed
    entries: list[dict[str, Any]]


class ModeSwitchRequest(BaseModel):
    mode: str  # exploration | story | review


class ModeSwitchResponse(BaseModel):
    success: bool
    mode: str
    message: str


# ── Story ────────────────────────────────────────────────────────────────────

class StructureProposalResponse(BaseModel):
    proposalId: str
    recommendedType: str  # story | epic
    storyCount: int
    sizeScore: int
    sizeLabel: str
    reason: str
    items: list[dict[str, Any]]


class StructureProposalAcceptRequest(BaseModel):
    proposalId: str


class GenerateStoryRequest(BaseModel):
    conversationId: str


class GeneratedStoryResponse(BaseModel):
    storyTitle: str
    storyDescription: str
    acceptanceCriteria: list[str]
    userGroup: Optional[str]
    businessValue: Optional[str]


class EvaluateReadinessResponse(BaseModel):
    status: str  # not_ready | ready | excellent
    score: int
    maxScore: int
    percentage: int
    recommendation: str
    findings: list[dict[str, Any]]
    missingFields: list[dict[str, Any]]


# ── Observer ───────────────────────────────────────────────────────────────

class ObserverFindingResponse(BaseModel):
    id: str
    type: str
    severity: str
    reason: str
    suggestedImprovement: Optional[str]
    status: str
    createdAt: datetime


class ObserverProposalCreateRequest(BaseModel):
    findingId: str
    proposalType: str
    title: str
    description: str
    proposedChange: dict[str, Any]


class ObserverProposalResponse(BaseModel):
    id: str
    findingId: Optional[str]
    proposalType: str
    title: str
    description: Optional[str]
    expectedImpact: Optional[str]
    status: str
    createdAt: datetime
    reviewedAt: Optional[datetime]


class ObserverValidationResponse(BaseModel):
    id: str
    proposalId: str
    status: str
    metricsBefore: dict[str, Any]
    metricsAfter: dict[str, Any]
    successRate: Optional[float]
    recommendation: Optional[str]
