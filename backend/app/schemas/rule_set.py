from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class RuleDefinitionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    rule_type: str
    dimension: str
    weight: float = 1.0
    parameters: dict = {}
    prompt_template: Optional[str] = None
    order_index: int = 0

    @field_validator("rule_type")
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        allowed = {"quality", "completeness", "compliance", "testability", "custom"}
        if v not in allowed:
            raise ValueError(f"rule_type must be one of {allowed}")
        return v

    @field_validator("weight")
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("weight must be between 0.0 and 1.0")
        return v


class RuleDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_set_id: uuid.UUID
    name: str
    description: Optional[str]
    rule_type: str
    dimension: str
    weight: float
    parameters: dict
    prompt_template: Optional[str]
    is_active: bool
    order_index: int
    created_at: datetime
    updated_at: datetime


class RuleDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    weight: Optional[float] = None
    parameters: Optional[dict] = None
    prompt_template: Optional[str] = None
    is_active: Optional[bool] = None
    order_index: Optional[int] = None


class RuleSetCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RuleSetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    description: Optional[str]
    version: int
    status: str
    frozen_at: Optional[datetime]
    activated_at: Optional[datetime]
    archived_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    rules: list[RuleDefinitionRead] = []


class RuleSetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
