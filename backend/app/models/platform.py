# app/models/platform.py
"""
Platform-level multi-tenancy models.

Component      — top-level feature module (Core, Compliance, Integration, …)
FeatureFlag    — granular feature inside a component
OrgComponent   — which components are licensed / active for an org
OrgFeatureOverride — per-org override of a feature flag
PlatformConfigEntry — key/value global platform config (override of GlobalConfig for platform settings)
OrgConfigOverride  — org-level override of a platform config entry

Override Policy:
  locked           — org cannot change
  overridable      — org can freely override
  extend_only      — org can only add values (lists)
  disable_only     — org can only disable (not enable more)
  approval_required — org can request, superadmin must approve
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class OverridePolicy(str, enum.Enum):
    locked            = "locked"
    overridable       = "overridable"
    extend_only       = "extend_only"
    disable_only      = "disable_only"
    approval_required = "approval_required"


class ComponentStatus(str, enum.Enum):
    active     = "active"
    beta       = "beta"
    deprecated = "deprecated"
    disabled   = "disabled"


class OrgComponentStatus(str, enum.Enum):
    active    = "active"
    suspended = "suspended"
    trial     = "trial"
    disabled  = "disabled"


# ── Component catalogue ───────────────────────────────────────────────────────

BUILT_IN_COMPONENTS = [
    {
        "slug": "core",
        "name": "Core",
        "description": "User Story Engine, Conversation Control, Artifacts, Dialog, Roles",
        "display_order": 10,
    },
    {
        "slug": "compliance",
        "name": "Compliance",
        "description": "Frameworks, Control Library, Scoring, Evidence, Gates, Audit",
        "display_order": 20,
    },
    {
        "slug": "integration",
        "name": "Integration Layer",
        "description": "Jira, Confluence, GitHub, Fileshare, ServiceNow, Webhooks, Sync",
        "display_order": 30,
    },
    {
        "slug": "knowledge",
        "name": "Knowledge / RAG",
        "description": "Sources, Ingest, Trust Engine, Retrieval Rules, Permission Filter",
        "display_order": 40,
    },
    {
        "slug": "runtime",
        "name": "Runtime / Services",
        "description": "Docker, LiteLLM, LangGraph, n8n, Vector DB, Worker, Monitoring",
        "display_order": 50,
    },
    {
        "slug": "system",
        "name": "System",
        "description": "Tenants, Licenses, Feature Flags, Security, Backup",
        "display_order": 60,
    },
]

BUILT_IN_FEATURES = [
    # Core
    {"component_slug": "core", "slug": "core.user_stories",         "name": "User Stories",            "default_enabled": True,  "policy": "locked"},
    {"component_slug": "core", "slug": "core.epics",                 "name": "Epics",                   "default_enabled": True,  "policy": "locked"},
    {"component_slug": "core", "slug": "core.projects",              "name": "Projects",                "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "core", "slug": "core.conversation_control",  "name": "Conversation Control",    "default_enabled": True,  "policy": "locked"},
    {"component_slug": "core", "slug": "core.dialog_profiles",       "name": "Dialog Profiles",         "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "core", "slug": "core.prompt_steering",       "name": "Prompt Steering",         "default_enabled": True,  "policy": "approval_required"},
    {"component_slug": "core", "slug": "core.bcm",                   "name": "BCM / Capability Map",    "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "core", "slug": "core.processes",             "name": "Process Registry",        "default_enabled": True,  "policy": "overridable"},
    # Compliance
    {"component_slug": "compliance", "slug": "compliance.iso9001",   "name": "ISO 9001",                "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.iso27001",  "name": "ISO 27001",               "default_enabled": False, "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.nis2",      "name": "NIS2",                    "default_enabled": False, "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.custom",    "name": "Custom Frameworks",       "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.gates",     "name": "Gate Decisions",          "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.evidence",  "name": "Evidence Engine",         "default_enabled": True,  "policy": "overridable"},
    {"component_slug": "compliance", "slug": "compliance.auditlog",  "name": "Audit Log",               "default_enabled": True,  "policy": "locked"},
    # Integration
    {"component_slug": "integration", "slug": "integration.jira",       "name": "Jira",       "default_enabled": False, "policy": "overridable"},
    {"component_slug": "integration", "slug": "integration.confluence",  "name": "Confluence", "default_enabled": False, "policy": "overridable"},
    {"component_slug": "integration", "slug": "integration.github",      "name": "GitHub",     "default_enabled": False, "policy": "overridable"},
    {"component_slug": "integration", "slug": "integration.servicenow",  "name": "ServiceNow", "default_enabled": False, "policy": "approval_required"},
    {"component_slug": "integration", "slug": "integration.webhooks",    "name": "Webhooks",   "default_enabled": False, "policy": "overridable"},
    # Knowledge
    {"component_slug": "knowledge", "slug": "knowledge.rag",          "name": "RAG Pipeline",       "default_enabled": False, "policy": "approval_required"},
    {"component_slug": "knowledge", "slug": "knowledge.trust_engine",  "name": "Trust Engine",       "default_enabled": False, "policy": "locked"},
    {"component_slug": "knowledge", "slug": "knowledge.web_search",    "name": "Web Search",         "default_enabled": False, "policy": "overridable"},
    # Runtime
    {"component_slug": "runtime", "slug": "runtime.litellm",       "name": "LiteLLM",        "default_enabled": True,  "policy": "locked"},
    {"component_slug": "runtime", "slug": "runtime.n8n",           "name": "n8n Workflows",  "default_enabled": False, "policy": "overridable"},
    {"component_slug": "runtime", "slug": "runtime.monitoring",    "name": "Monitoring",     "default_enabled": False, "policy": "overridable"},
]


class Component(Base):
    """Top-level platform component (module)."""
    __tablename__ = "platform_components"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ComponentStatus.active.value)
    display_order: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    is_core: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    features: Mapped[list["FeatureFlag"]] = relationship(
        "FeatureFlag", back_populates="component", cascade="all, delete-orphan"
    )
    org_components: Mapped[list["OrgComponent"]] = relationship(
        "OrgComponent", back_populates="component"
    )


class FeatureFlag(Base):
    """Granular feature inside a component."""
    __tablename__ = "platform_features"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    override_policy: Mapped[str] = mapped_column(
        String(30), nullable=False, default=OverridePolicy.overridable.value
    )
    # Optional JSON schema for the feature's config value
    config_schema: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # Default config value (JSON)
    default_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    component: Mapped["Component"] = relationship("Component", back_populates="features")
    org_overrides: Mapped[list["OrgFeatureOverride"]] = relationship(
        "OrgFeatureOverride", back_populates="feature"
    )


class OrgComponent(Base):
    """Which components are licensed / active for an org."""
    __tablename__ = "org_components"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    component_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_components.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=OrgComponentStatus.active.value
    )
    licensed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    component: Mapped["Component"] = relationship("Component", back_populates="org_components")

    __table_args__ = (
        UniqueConstraint("org_id", "component_id", name="uq_org_component"),
    )


class OrgFeatureOverride(Base):
    """Per-org override of a feature flag (enabled/disabled + optional config)."""
    __tablename__ = "org_feature_overrides"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    feature_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_features.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_enabled: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    config_override: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    # For approval_required: pending | approved | rejected
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="approved")
    changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    feature: Mapped["FeatureFlag"] = relationship("FeatureFlag", back_populates="org_overrides")

    __table_args__ = (
        UniqueConstraint("org_id", "feature_id", name="uq_org_feature_override"),
    )
