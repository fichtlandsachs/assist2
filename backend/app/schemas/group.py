import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserRead


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    type: str
    is_active: bool
    parent_group_id: Optional[uuid.UUID] = None
    created_at: datetime


class GroupCreate(BaseModel):
    name: str
    type: str
    description: Optional[str] = None
    parent_group_id: Optional[uuid.UUID] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class GroupMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    member_type: str
    user: Optional[UserRead] = None
    agent_id: Optional[uuid.UUID] = None
    role: str
    added_at: datetime


class GroupMemberCreate(BaseModel):
    member_type: str
    user_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    role: str = "member"
