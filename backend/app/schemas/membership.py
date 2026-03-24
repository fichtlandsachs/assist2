import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr

from app.schemas.user import UserRead
from app.schemas.role import RoleRead


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user: UserRead
    organization_id: uuid.UUID
    status: str
    roles: List[RoleRead] = []
    joined_at: Optional[datetime] = None
    invited_at: Optional[datetime] = None


class InviteRequest(BaseModel):
    email: EmailStr
    role_ids: List[uuid.UUID] = []


class MembershipUpdate(BaseModel):
    status: Optional[str] = None


class RoleAssignRequest(BaseModel):
    role_id: uuid.UUID
