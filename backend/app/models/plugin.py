import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Plugin(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "plugins"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    entry_point: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_config: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    activations: Mapped[list["OrganizationPluginActivation"]] = relationship(
        "OrganizationPluginActivation",
        back_populates="plugin",
        cascade="all, delete-orphan",
    )


class OrganizationPluginActivation(UUIDMixin, Base):
    __tablename__ = "org_plugin_activations"
    __table_args__ = (
        UniqueConstraint("organization_id", "plugin_id", name="uq_org_plugin_activations_org_plugin"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plugin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    activated_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", back_populates="plugin_activations")
    plugin: Mapped["Plugin"] = relationship("Plugin", back_populates="activations")
    activator = relationship("User", foreign_keys=[activated_by])
