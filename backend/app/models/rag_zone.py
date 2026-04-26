"""ORM models for RAG access-control zones."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class RagZone(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "rag_zones"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Zones marked ad_group_only cannot be opened via heyKarl role grants — AD membership required
    ad_group_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_rag_zones_org_slug"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="rag_zones"
    )
    memberships: Mapped[List["RagZoneMembership"]] = relationship(
        "RagZoneMembership",
        back_populates="zone",
        cascade="all, delete-orphan",
    )


class RagZoneMembership(UUIDMixin, Base):
    __tablename__ = "rag_zone_memberships"

    zone_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rag_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ad_group_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("zone_id", "ad_group_name", name="uq_rag_zone_memberships_zone_group"),
    )

    zone: Mapped["RagZone"] = relationship("RagZone", back_populates="memberships")
