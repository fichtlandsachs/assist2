import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator
import re


class OrgCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        v = v.lower().strip()
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,98}[a-z0-9]$", v):
            raise ValueError(
                "Slug must be 3-100 characters, lowercase alphanumeric and hyphens only, "
                "cannot start or end with a hyphen"
            )
        return v


class OrgRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    plan: str
    is_active: bool
    max_members: Optional[int] = None
    created_at: datetime


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
