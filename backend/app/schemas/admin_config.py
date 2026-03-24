from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Per-type config payloads (typed defaults)
# ---------------------------------------------------------------------------

class RetrievalConfig(BaseModel):
    top_k: int = Field(5, ge=1, le=50)
    similarity_weight: float = Field(0.7, ge=0.0, le=1.0)
    recency_weight: float = Field(0.1, ge=0.0, le=1.0)
    usage_weight: float = Field(0.1, ge=0.0, le=1.0)
    organization_weight: float = Field(0.1, ge=0.0, le=1.0)
    learning_based_ranking: bool = False


class PromptLearningConfig(BaseModel):
    enabled: bool = False
    affected_agents: list[str] = Field(default_factory=list)
    max_parallel_versions: int = Field(2, ge=1, le=10)
    min_acceptance_rate: float = Field(0.7, ge=0.0, le=1.0)
    max_rework_rate: float = Field(0.3, ge=0.0, le=1.0)


class WorkflowLearningConfig(BaseModel):
    enabled: bool = False
    observed_workflows: list[str] = Field(default_factory=list)
    auto_suggestions: bool = False


class ApprovalRequired(BaseModel):
    prompt_updates: bool = True
    ranking_changes: bool = True
    workflow_changes: bool = True


class GovernanceConfig(BaseModel):
    approval_required: ApprovalRequired = Field(default_factory=ApprovalRequired)
    approver_roles: list[str] = Field(default_factory=lambda: ["admin", "architect_ai", "security_ai"])


class LearningSensitivityConfig(BaseModel):
    mode: Literal["conservative", "balanced", "aggressive"] = "conservative"


class LLMTriggerConfig(BaseModel):
    min_input_length: int = Field(50, ge=0)
    idle_time_threshold: int = Field(300, ge=0)
    retrieval_only: bool = False


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ConfigUpdateRequest(BaseModel):
    config_type: Literal[
        "retrieval", "prompt_learning", "workflow_learning",
        "governance", "learning_sensitivity", "llm_trigger"
    ]
    config_payload: dict[str, Any]


class ConfigSectionRead(BaseModel):
    config_type: str
    config_payload: dict[str, Any]
    version: int
    updated_at: datetime


class MergedConfigRead(BaseModel):
    organization_id: uuid.UUID
    sections: dict[str, ConfigSectionRead]


class ConfigHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    config_id: uuid.UUID
    changed_by_id: Optional[uuid.UUID]
    previous_value: Optional[dict[str, Any]]
    new_value: dict[str, Any]
    timestamp: datetime


class RecommendationRead(BaseModel):
    id: uuid.UUID
    config_type: str
    description: str
    suggested_payload: dict[str, Any]
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime


# ---------------------------------------------------------------------------
# Default payloads (used when no DB row exists yet)
# ---------------------------------------------------------------------------

DEFAULTS: dict[str, dict] = {
    "retrieval": RetrievalConfig().model_dump(),
    "prompt_learning": PromptLearningConfig().model_dump(),
    "workflow_learning": WorkflowLearningConfig().model_dump(),
    "governance": GovernanceConfig().model_dump(),
    "learning_sensitivity": LearningSensitivityConfig().model_dump(),
    "llm_trigger": LLMTriggerConfig().model_dump(),
}
