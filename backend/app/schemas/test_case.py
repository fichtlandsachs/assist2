from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid
from app.models.test_case import TestResult


class TestCaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None


class TestCaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    result: Optional[TestResult] = None
    notes: Optional[str] = None


class TestCaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    story_id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    title: str
    description: Optional[str]
    steps: Optional[str]
    expected_result: Optional[str]
    result: TestResult
    notes: Optional[str]
    is_ai_generated: bool
    created_at: datetime
    updated_at: datetime
