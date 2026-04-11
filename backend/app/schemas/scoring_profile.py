from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator


class ScoringProfileCreate(BaseModel):
    rule_set_id: uuid.UUID
    name: str
    dimension_weights: dict[str, float] = {}
    pass_threshold: float = 0.70
    warn_threshold: float = 0.50
    auto_approve_threshold: float = 0.90
    require_review_below: float = 0.60
    is_default: bool = False

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ScoringProfileCreate":
        if not (self.warn_threshold < self.pass_threshold < self.auto_approve_threshold):
            raise ValueError(
                "Thresholds must satisfy: warn < pass < auto_approve"
            )
        return self


class ScoringProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    rule_set_id: uuid.UUID
    name: str
    version: int
    dimension_weights: dict
    pass_threshold: float
    warn_threshold: float
    auto_approve_threshold: float
    require_review_below: float
    is_default: bool
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime


class ScoringProfileUpdate(BaseModel):
    name: Optional[str] = None
    dimension_weights: Optional[dict[str, float]] = None
    pass_threshold: Optional[float] = None
    warn_threshold: Optional[float] = None
    auto_approve_threshold: Optional[float] = None
    require_review_below: Optional[float] = None
    is_default: Optional[bool] = None
