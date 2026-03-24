import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class PluginRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    version: str
    type: str
    is_active: bool
    requires_config: bool


class OrgPluginRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plugin: PluginRead
    is_enabled: bool
    config: Optional[Dict[str, Any]] = None
    activated_at: datetime


class PluginActivateRequest(BaseModel):
    config: Optional[Dict[str, Any]] = None


class PluginConfigUpdate(BaseModel):
    config: Dict[str, Any]
