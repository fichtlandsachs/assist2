import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Zones ──────────────────────────────────────────────────────────────────────

class RagZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    ad_group_only: bool
    created_at: datetime
    updated_at: datetime


class RagZoneCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    is_default: bool = False
    ad_group_only: bool = False


class RagZoneUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None
    ad_group_only: Optional[bool] = None


# ── AD-group memberships ────────────────────────────────────────────────────────

class RagZoneMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zone_id: uuid.UUID
    ad_group_name: str
    created_at: datetime


class RagZoneMembershipCreate(BaseModel):
    ad_group_name: str


# ── User zone access grants ────────────────────────────────────────────────────

class UserZoneAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    zone_id: uuid.UUID
    org_id: uuid.UUID
    project_scope: Optional[uuid.UUID] = None
    granted_via: str
    granted_by: Optional[uuid.UUID] = None
    granted_at: datetime
    revoked_at: Optional[datetime] = None


class UserZoneAccessGrant(BaseModel):
    user_id: uuid.UUID
    project_scope: Optional[uuid.UUID] = None
    # valid_to: grant is active until this date; None = permanent until manually revoked
    valid_to: Optional[datetime] = None


# ── heyKarl-internal role assignments ─────────────────────────────────────────

class HkRoleAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    org_id: uuid.UUID
    role_name: str
    scope_type: Optional[str] = None
    scope_id: Optional[uuid.UUID] = None
    valid_from: datetime
    valid_to: Optional[datetime] = None
    granted_by: Optional[uuid.UUID] = None
    created_at: datetime


class HkRoleAssignmentCreate(BaseModel):
    user_id: uuid.UUID
    role_name: str
    scope_type: Optional[str] = None  # "org" | "project" | "epic" | "story"
    scope_id: Optional[uuid.UUID] = None
    valid_to: Optional[datetime] = None


class HkRoleZoneGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    role_name: str
    zone_id: uuid.UUID


class HkRoleZoneGrantCreate(BaseModel):
    zone_id: uuid.UUID


# ── Ingestion zone config ──────────────────────────────────────────────────────

class IngestionZoneConfig(BaseModel):
    """Maps source_type slugs to zone slugs for automatic zone assignment during ingestion."""
    nextcloud: Optional[str] = None
    karl_story: Optional[str] = None
    jira: Optional[str] = None
    confluence: Optional[str] = None
    user_action: Optional[str] = None
