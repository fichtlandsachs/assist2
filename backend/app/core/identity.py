"""Identity context for RAG access control."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IdentityContext:
    user_id: uuid.UUID
    org_id: uuid.UUID
    ad_groups: list[str]
    zone_ids: list[uuid.UUID]
    is_superuser: bool


@dataclass
class AccessContext:
    identity: IdentityContext
    # Soft-revoked grants: user retains read access to docs created before revoked_at
    revoked_grants: list[tuple[uuid.UUID, datetime]] = field(default_factory=list)
    # classification_ceiling: str | None = None  # future extension
