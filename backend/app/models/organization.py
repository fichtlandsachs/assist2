import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.group import Group
    from app.models.plugin import OrganizationPluginActivation
    from app.models.workflow import WorkflowDefinition


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_members: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    memberships: Mapped[List["Membership"]] = relationship(
        "Membership",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    groups: Mapped[List["Group"]] = relationship(
        "Group",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    plugin_activations: Mapped[List["OrganizationPluginActivation"]] = relationship(
        "OrganizationPluginActivation",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    workflow_definitions: Mapped[List["WorkflowDefinition"]] = relationship(
        "WorkflowDefinition",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
