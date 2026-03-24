import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class WorkflowDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    version: int
    description: Optional[str] = None
    trigger_type: str
    is_active: bool
    created_at: datetime


class WorkflowCreate(BaseModel):
    name: str
    slug: str
    trigger_type: str
    description: Optional[str] = None
    definition: Dict[str, Any]
    n8n_workflow_id: str


class WorkflowExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    definition_id: uuid.UUID
    definition_version: int
    status: str
    triggered_by: Optional[uuid.UUID] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class WorkflowExecutionDetail(WorkflowExecutionRead):
    input_snapshot: Optional[Dict[str, Any]] = None
    context_snapshot: Optional[Dict[str, Any]] = None
    result_snapshot: Optional[Dict[str, Any]] = None


class TriggerRequest(BaseModel):
    input: Dict[str, Any] = {}
