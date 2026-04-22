# app/schemas/capability.py
from __future__ import annotations
from typing import Optional, Any
import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class CapabilityNodeCreate(BaseModel):
    node_type: str  # capability | level_1 | level_2 | level_3
    title: str
    description: Optional[str] = None
    parent_id: Optional[uuid.UUID] = None
    sort_order: int = 0
    external_import_key: Optional[str] = None
    source_type: Optional[str] = None  # excel | template | demo | manual

    @field_validator("node_type")
    @classmethod
    def validate_node_type(cls, v: str) -> str:
        allowed = {"capability", "level_1", "level_2", "level_3"}
        if v not in allowed:
            raise ValueError(f"node_type must be one of {allowed}")
        return v


class CapabilityNodeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class CapabilityNodeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    parent_id: Optional[uuid.UUID]
    node_type: str
    title: str
    description: Optional[str]
    sort_order: int
    is_active: bool
    external_import_key: Optional[str]
    source_type: Optional[str]
    created_at: datetime
    updated_at: datetime


class CapabilityTreeNode(BaseModel):
    """A node in the serialised capability tree (includes children + story count)."""
    id: str
    org_id: str
    parent_id: Optional[str]
    node_type: str
    title: str
    description: Optional[str]
    sort_order: int
    is_active: bool
    external_import_key: Optional[str]
    source_type: Optional[str]
    story_count: int = 0
    children: list[CapabilityTreeNode] = []


class ArtifactAssignmentCreate(BaseModel):
    artifact_type: str  # project | epic | user_story
    artifact_id: uuid.UUID
    node_id: uuid.UUID
    relation_type: str = "primary"  # primary | secondary
    assignment_is_exception: bool = False
    assignment_exception_reason: Optional[str] = None

    @field_validator("artifact_type")
    @classmethod
    def validate_artifact_type(cls, v: str) -> str:
        if v not in {"project", "epic", "user_story"}:
            raise ValueError("artifact_type must be project, epic, or user_story")
        return v

    @field_validator("relation_type")
    @classmethod
    def validate_relation_type(cls, v: str) -> str:
        if v not in {"primary", "secondary"}:
            raise ValueError("relation_type must be primary or secondary")
        return v


class ArtifactAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    artifact_type: str
    artifact_id: uuid.UUID
    node_id: uuid.UUID
    relation_type: str
    assignment_is_exception: bool
    assignment_exception_reason: Optional[str]
    created_at: datetime
    created_by_id: Optional[uuid.UUID]


class ImportIssue(BaseModel):
    level: str  # "error" | "warning"
    message: str
    row: Optional[int] = None
    field: Optional[str] = None


class ImportValidationResult(BaseModel):
    is_valid: bool
    error_count: int
    warning_count: int
    capability_count: int
    level_1_count: int
    level_2_count: int
    level_3_count: int
    issues: list[ImportIssue]
    nodes: list[dict[str, Any]] = []


class OrgInitStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    initialization_status: str
    initialization_completed_at: Optional[datetime]
    capability_map_version: int
    initial_setup_source: Optional[str]


class OrgInitAdvance(BaseModel):
    status: str
    source: Optional[str] = None  # excel | template | demo

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {
            "capability_setup_in_progress",
            "capability_setup_validated",
            "entry_chat_in_progress",
            "initialized",
        }
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}")
        return v
