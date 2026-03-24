import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    locale: str
    timezone: str
    is_active: bool
    created_at: datetime
    # NOTE: password_hash is intentionally excluded for security


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    avatar_url: Optional[str] = None


class UserWithLinks(UserRead):
    pass
