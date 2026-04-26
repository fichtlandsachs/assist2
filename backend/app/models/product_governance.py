# app/models/product_governance.py
"""
Product Governance & Control Management System — Data Models.

Entities:
  ControlCategory        — Grouping (12 energy product categories)
  ProductScope           — Product type / class scope
  MarketScope            — Market / region scope
  CustomerSegment        — B2B, B2C, etc.
  RiskDimension          — Risk types (financial, quality, supply, ...)
  EvidenceType           — Evidence/proof types (FMEA, Lastenheft, ...)
  ScoringScheme          — Scoring scale and rules
  GateDefinition         — G1–G4 gate definitions
  GateVersion            — Versioned gate snapshots
  ControlDefinition      — Main control entity (fixed + additional)
  ControlVersion         — Versioned snapshots of controls
  DynamicTriggerRule     — Trigger rules that activate controls
  RoleAssignment         — Role-based responsibility on controls
  GovernanceChangeLog    — Append-only audit trail
  SimulationScenario     — Saved simulation inputs/results
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class ControlKind(str, enum.Enum):
    fixed    = "fixed"      # System controls, always active, limited edit
    dynamic  = "dynamic"    # Admin-defined, fully configurable


class ControlStatus(str, enum.Enum):
    draft     = "draft"
    review    = "review"
    approved  = "approved"
    archived  = "archived"


class GatePhase(str, enum.Enum):
    G1 = "G1"   # Opportunity / Business Case
    G2 = "G2"   # Entwicklungsfreigabe
    G3 = "G3"   # Markt- / Serienfreigabe
    G4 = "G4"   # Scale-up / Portfolio-Fortführung


class GateOutcome(str, enum.Enum):
    go             = "go"
    conditional_go = "conditional_go"
    no_go          = "no_go"


class TriggerOperator(str, enum.Enum):
    AND = "AND"
    OR  = "OR"
    NOT = "NOT"


class EvidenceRequirement(str, enum.Enum):
    mandatory = "mandatory"
    optional  = "optional"


# ── Supporting lookup tables ───────────────────────────────────────────────────

class ControlCategory(Base):
    __tablename__ = "pg_control_categories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProductScope(Base):
    __tablename__ = "pg_product_scopes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("pg_product_scopes.id", ondelete="SET NULL"), nullable=True
    )
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class MarketScope(Base):
    __tablename__ = "pg_market_scopes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    countries: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    regulatory_framework: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CustomerSegment(Base):
    __tablename__ = "pg_customer_segments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    segment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # B2B, B2C, B2B2C
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class RiskDimension(Base):
    __tablename__ = "pg_risk_dimensions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    risk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class EvidenceType(Base):
    __tablename__ = "pg_evidence_types"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class ScoringScheme(Base):
    __tablename__ = "pg_scoring_schemes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scale_min: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scale_max: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    # Array of {"value": int, "label": str, "color": str, "description": str}
    scale_labels: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # {"green": {"min": 2.5}, "yellow": {"min": 1.5}, "red": {"max": 1.5}}
    traffic_light: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    formula: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── Gate Definitions ──────────────────────────────────────────────────────────

class GateDefinition(Base):
    __tablename__ = "pg_gate_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    phase: Mapped[str] = mapped_column(String(4), nullable=False)  # G1–G4
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # IDs of fixed controls required at this gate
    required_fixed_control_slugs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    # Hard-stop rule: if any control with hard_stop=True scores <= hard_stop_threshold → NoGo
    hard_stop_threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Escalation and approver roles
    approver_roles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    escalation_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Possible outcomes configuration
    outcomes_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ControlStatus.approved.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class GateVersion(Base):
    """Immutable snapshot of a GateDefinition."""
    __tablename__ = "pg_gate_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    gate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_gate_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("gate_id", "version", name="uq_gate_version"),
    )


# ── Core Control Definition ───────────────────────────────────────────────────

class ControlDefinition(Base):
    """
    The central entity. Covers both fixed (system) and dynamic (admin-defined) controls.

    Fixed controls:
      - system_id is set and immutable
      - kind = 'fixed'
      - cannot be deleted
      - limited fields editable

    Dynamic controls:
      - kind = 'dynamic'
      - fully admin-configurable
    """
    __tablename__ = "pg_control_definitions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Identity
    system_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=ControlKind.dynamic.value)

    # ── Layer 1: User-facing fields ───────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_relevant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_to_check: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_to_do: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guiding_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    help_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Layer 2: Governance fields ────────────────────────────────────────────
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("pg_control_categories.id", ondelete="SET NULL"), nullable=True
    )
    control_objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    escalation_logic: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Gate configuration
    gate_phases: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)  # ["G1", "G2", ...]

    # Scoring
    scoring_scheme_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("pg_scoring_schemes.id", ondelete="SET NULL"), nullable=True
    )
    default_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hard_stop_threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Trigger
    requires_trigger: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trigger_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Evidence requirements: [{"evidence_type_id": uuid, "requirement": "mandatory|optional"}]
    evidence_requirements: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Scope linkage
    product_scope_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    market_scope_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    customer_segment_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    risk_dimension_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Framework mapping (ISO, IEC, EN, ...)
    framework_refs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    # Admin metadata
    review_interval_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    audit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Control family grouping (set via standards_seed or admin UI)
    control_family: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Status & versioning
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ControlStatus.draft.value)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_visible_in_frontend: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    versions: Mapped[List["ControlVersion"]] = relationship(
        "ControlVersion", back_populates="control", cascade="all, delete-orphan",
        order_by="ControlVersion.version"
    )


class ControlVersion(Base):
    """Immutable snapshot — created on every publish/approve action."""
    __tablename__ = "pg_control_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    control: Mapped["ControlDefinition"] = relationship("ControlDefinition", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("control_id", "version", name="uq_control_version"),
    )


# ── Trigger Rules ─────────────────────────────────────────────────────────────

class DynamicTriggerRule(Base):
    """
    Admin-configurable trigger that activates one or more controls
    when product/market/risk conditions are met.

    condition_tree is a recursive JSON structure:
    {
      "operator": "AND",
      "conditions": [
        {"field": "product_type", "op": "eq", "value": "battery_storage"},
        {"operator": "OR", "conditions": [
          {"field": "market", "op": "in", "value": ["EU", "DE"]},
          {"field": "customer_segment", "op": "eq", "value": "B2B"}
        ]}
      ]
    }
    """
    __tablename__ = "pg_trigger_rules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    condition_tree: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # IDs of ControlDefinition records this trigger activates
    activates_control_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    conflict_resolution: Mapped[str] = mapped_column(String(50), default="latest_wins", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ControlStatus.approved.value, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


# ── Governance Change Log ─────────────────────────────────────────────────────

class GovernanceChangeLog(Base):
    """Append-only audit trail for all governance configuration changes."""
    __tablename__ = "pg_governance_changelog"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    entity_slug: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    # draft, review, approved, archived
    from_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    from_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    to_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diff: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )


# ── Simulation Scenario ───────────────────────────────────────────────────────

class SimulationScenario(Base):
    """Saved simulation inputs and results for admin preview/testing."""
    __tablename__ = "pg_simulation_scenarios"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Input parameters
    input_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Computed result
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result_computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
