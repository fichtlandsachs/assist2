import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    role: str
    model: str
    is_active: bool
    created_at: datetime


class AgentCreate(BaseModel):
    name: str
    role: str
    model: str = "claude-sonnet-4-6"
    config: Dict[str, Any] = {}
    system_prompt_ref: Optional[str] = None


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    model: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class InvokeRequest(BaseModel):
    input: Dict[str, Any]


class InvokeResponse(BaseModel):
    invocation_id: str
    status: str = "running"
