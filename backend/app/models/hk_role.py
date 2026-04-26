"""ORM models for heyKarl-internal role assignments (additive to AD roles)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.rag_zone import RagZone
    from app.models.user import User


class HkRoleAssignment(UUIDMixin, Base):
    __tablename__ = "hk_role_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User")


class HkRoleZoneGrant(UUIDMixin, Base):
    __tablename__ = "hk_role_zone_grants"

    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role_name: Mapped[str] = mapped_column(String(100), nullable=False)
    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rag_zones.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("org_id", "role_name", "zone_id", name="uq_hk_role_zone_grant"),
    )

    zone: Mapped["RagZone"] = relationship("RagZone")
