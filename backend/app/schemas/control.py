# app/schemas/control.py
"""Pydantic v2 schemas for compliance controls and capability assignments."""
from __future__ import annotations

from typing import Optional, Any
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

VALID_CONTROL_TYPES = {"preventive", "detective", "corrective", "compensating"}
VALID_IMPL_STATUSES = {"not_started", "in_progress", "implemented", "verified"}
VALID_EFFECTIVENESS = {
    "not_assessed",
    "not_effective",
    "partially_effective",
    "effective",
    "fully_effective",
}


class ControlCreate(BaseModel):
    title: str
    description: Optional[str] = None
    control_type: str
    implementation_status: str = "not_started"
    owner_id: Optional[uuid.UUID] = None
    review_interval_days: int = 365
    framework_refs: Optional[list[str]] = []
    user_title: Optional[str] = None
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = None
    user_evidence_needed: Optional[list[str]] = None

    @field_validator("control_type")
    @classmethod
    def validate_control_type(cls, v: str) -> str:
        if v not in VALID_CONTROL_TYPES:
            raise ValueError(f"control_type must be one of {VALID_CONTROL_TYPES}")
        return v

    @field_validator("implementation_status")
    @classmethod
    def validate_impl_status(cls, v: str) -> str:
        if v not in VALID_IMPL_STATUSES:
            raise ValueError(f"implementation_status must be one of {VALID_IMPL_STATUSES}")
        return v


class ControlUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    control_type: Optional[str] = None
    implementation_status: Optional[str] = None
    owner_id: Optional[uuid.UUID] = None
    review_interval_days: Optional[int] = None
    last_reviewed_at: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    is_active: Optional[bool] = None
    framework_refs: Optional[list[str]] = None
    user_title: Optional[str] = None
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = None
    user_evidence_needed: Optional[list[str]] = None

    @field_validator("control_type", mode="before")
    @classmethod
    def validate_control_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_CONTROL_TYPES:
            raise ValueError(f"control_type must be one of {VALID_CONTROL_TYPES}")
        return v

    @field_validator("implementation_status", mode="before")
    @classmethod
    def validate_impl_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_IMPL_STATUSES:
            raise ValueError(f"implementation_status must be one of {VALID_IMPL_STATUSES}")
        return v


class ControlRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    title: str
    description: Optional[str] = None
    control_type: str
    implementation_status: str
    owner_id: Optional[uuid.UUID] = None
    review_interval_days: int
    last_reviewed_at: Optional[datetime] = None
    next_review_due: Optional[datetime] = None
    is_active: bool
    framework_refs: Optional[list[str]] = None
    user_title: Optional[str] = None
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = None
    user_evidence_needed: Optional[list[str]] = None
    version: int
    created_at: datetime
    updated_at: datetime


class ControlUserView(BaseModel):
    """User-facing view: only plain-language fields, no governance data."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_title: Optional[str] = None
    title: str
    user_explanation: Optional[str] = None
    user_action: Optional[str] = None
    user_guiding_questions: Optional[list[str]] = None
    user_evidence_needed: Optional[list[str]] = None
    is_inherited: bool = False
    applies_via_node_id: Optional[uuid.UUID] = None


class ControlCapabilityAssignmentCreate(BaseModel):
    control_id: uuid.UUID
    capability_node_id: uuid.UUID
    maturity_level: int = 1
    effectiveness: str = "not_assessed"
    coverage_note: Optional[str] = None
    gap_description: Optional[str] = None
    assessor_id: Optional[uuid.UUID] = None
    propagate_to_children: bool = False

    @field_validator("maturity_level")
    @classmethod
    def validate_maturity(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError("maturity_level must be between 1 and 5")
        return v

    @field_validator("effectiveness")
    @classmethod
    def validate_effectiveness(cls, v: str) -> str:
        if v not in VALID_EFFECTIVENESS:
            raise ValueError(f"effectiveness must be one of {VALID_EFFECTIVENESS}")
        return v


class ControlCapabilityAssignmentUpdate(BaseModel):
    maturity_level: Optional[int] = None
    effectiveness: Optional[str] = None
    coverage_note: Optional[str] = None
    gap_description: Optional[str] = None
    assessor_id: Optional[uuid.UUID] = None
    last_assessed_at: Optional[datetime] = None
    next_assessment_due: Optional[datetime] = None

    @field_validator("maturity_level", mode="before")
    @classmethod
    def validate_maturity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not 1 <= v <= 5:
            raise ValueError("maturity_level must be between 1 and 5")
        return v

    @field_validator("effectiveness", mode="before")
    @classmethod
    def validate_effectiveness(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_EFFECTIVENESS:
            raise ValueError(f"effectiveness must be one of {VALID_EFFECTIVENESS}")
        return v


class ControlCapabilityAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    control_id: uuid.UUID
    capability_node_id: uuid.UUID
    maturity_level: int
    effectiveness: str
    coverage_note: Optional[str] = None
    gap_description: Optional[str] = None
    assessor_id: Optional[uuid.UUID] = None
    last_assessed_at: Optional[datetime] = None
    next_assessment_due: Optional[datetime] = None
    is_inherited: bool
    inherited_from_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ControlWithAssessment(BaseModel):
    control: ControlRead
    assessment: ControlCapabilityAssignmentRead
    applies_via_node_id: uuid.UUID


class ControlCoverageStats(BaseModel):
    node_id: uuid.UUID
    node_title: str
    control_count: int
    avg_maturity: float
    coverage_pct: float
