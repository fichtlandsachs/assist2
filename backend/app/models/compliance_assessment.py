# app/models/compliance_assessment.py
"""
Compliance Assessment Data Models.

Entities:
  ComplianceAssessment       — Top-level object tying a subject (project/product/custom) to
                               a set of active controls and an overall compliance status.
  ComplianceAssessmentItem   — One active control in the context of an assessment. Holds
                               the current score, status, rationale, and all metadata.
  ComplianceScoreEntry       — Append-only score history for a single assessment item.
  ComplianceEvidenceLink     — Links an assessment item to evidence files / references.
  ComplianceAction           — Open actions / Maßnahmen attached to an assessment item.
  ComplianceStatusSnapshot   — Frozen summary of assessment state at a point in time.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class AssessmentObjectType(str, enum.Enum):
    project = "project"
    product = "product"
    custom  = "custom"


class ItemStatus(str, enum.Enum):
    open             = "open"
    in_progress      = "in_progress"
    fulfilled        = "fulfilled"
    deviation        = "deviation"
    not_fulfilled    = "not_fulfilled"
    not_assessable   = "not_assessable"


class ActivationSource(str, enum.Enum):
    fixed    = "fixed"      # Always-on system control
    trigger  = "trigger"    # Activated by a DynamicTriggerRule
    gate     = "gate"       # Required by a specific gate
    manual   = "manual"     # Manually added by admin


class EvidenceStatus(str, enum.Enum):
    complete   = "complete"
    partial    = "partial"
    missing    = "missing"


class ApprovalStatus(str, enum.Enum):
    pending  = "pending"
    approved = "approved"
    rejected = "rejected"


class OverallComplianceStatus(str, enum.Enum):
    compliant          = "compliant"
    partially_compliant = "partially_compliant"
    non_compliant      = "non_compliant"
    not_assessed       = "not_assessed"


class ActionStatus(str, enum.Enum):
    open       = "open"
    in_progress= "in_progress"
    done       = "done"
    escalated  = "escalated"
    overdue    = "overdue"


class TrafficLight(str, enum.Enum):
    green  = "green"
    yellow = "yellow"
    red    = "red"
    grey   = "grey"


# ── ComplianceAssessment ──────────────────────────────────────────────────────

class ComplianceAssessment(Base):
    """
    Anchors all compliance work to a concrete subject object
    (project, product, or any custom entity).
    """
    __tablename__ = "ca_assessments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Subject reference — flexible: store type + UUID of the subject
    object_type: Mapped[str] = mapped_column(String(30), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    object_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Snapshot of context params used to derive active controls
    context_params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Aggregated scores (recomputed on each assessment refresh)
    total_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fulfilled_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deviation_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    not_assessed_controls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_stop_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hard_stop_critical: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    traffic_light: Mapped[str] = mapped_column(
        String(10), default=TrafficLight.grey.value, nullable=False
    )
    compliance_status: Mapped[str] = mapped_column(
        String(30), default=OverallComplianceStatus.not_assessed.value, nullable=False
    )
    gate_readiness: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Lifecycle
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
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    items: Mapped[List["ComplianceAssessmentItem"]] = relationship(
        "ComplianceAssessmentItem",
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
    snapshots: Mapped[List["ComplianceStatusSnapshot"]] = relationship(
        "ComplianceStatusSnapshot",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="ComplianceStatusSnapshot.created_at",
    )

    __table_args__ = (
        UniqueConstraint("org_id", "object_type", "object_id", name="uq_ca_assessment_object"),
    )


# ── ComplianceAssessmentItem ──────────────────────────────────────────────────

class ComplianceAssessmentItem(Base):
    """
    One active control instance within an assessment.
    Mirrors the ControlDefinition but carries object-specific evaluation state.
    """
    __tablename__ = "ca_assessment_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_control_definitions.id", ondelete="CASCADE"), nullable=False
    )

    # Copied from ControlDefinition at activation time (immutable snapshot of metadata)
    control_slug: Mapped[str] = mapped_column(String(200), nullable=False)
    control_name: Mapped[str] = mapped_column(String(500), nullable=False)
    control_kind: Mapped[str] = mapped_column(String(20), nullable=False)   # fixed / dynamic
    category_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    gate_phases: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    hard_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hard_stop_threshold: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    default_weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    control_objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_relevant: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_to_check: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guiding_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    required_evidence_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    responsible_role: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    control_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Activation context
    activation_source: Mapped[str] = mapped_column(
        String(20), default=ActivationSource.fixed.value, nullable=False
    )
    activating_trigger_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("pg_trigger_rules.id", ondelete="SET NULL"), nullable=True
    )
    activating_trigger_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    activating_gate: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)

    # Current evaluation state
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default=ItemStatus.open.value, nullable=False
    )
    traffic_light: Mapped[str] = mapped_column(
        String(10), default=TrafficLight.grey.value, nullable=False
    )
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    residual_risk: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_status: Mapped[str] = mapped_column(
        String(20), default=EvidenceStatus.missing.value, nullable=False
    )
    evidence_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(
        String(20), default=ApprovalStatus.pending.value, nullable=False
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assessed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assessed_by_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    assessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Derived gate-blocking flag (computed, not persisted via trigger)
    blocks_gate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    assessment: Mapped["ComplianceAssessment"] = relationship(
        "ComplianceAssessment", back_populates="items"
    )
    score_history: Mapped[List["ComplianceScoreEntry"]] = relationship(
        "ComplianceScoreEntry",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ComplianceScoreEntry.created_at",
    )
    evidence_links: Mapped[List["ComplianceEvidenceLink"]] = relationship(
        "ComplianceEvidenceLink",
        back_populates="item",
        cascade="all, delete-orphan",
    )
    actions: Mapped[List["ComplianceAction"]] = relationship(
        "ComplianceAction",
        back_populates="item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("assessment_id", "control_id", name="uq_ca_item_control"),
    )


# ── ComplianceScoreEntry ──────────────────────────────────────────────────────

class ComplianceScoreEntry(Base):
    """Append-only score change history for one assessment item."""
    __tablename__ = "ca_score_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_score: Mapped[int] = mapped_column(Integer, nullable=False)
    to_score: Mapped[int] = mapped_column(Integer, nullable=False)
    from_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gate_impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    changed_by_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    item: Mapped["ComplianceAssessmentItem"] = relationship(
        "ComplianceAssessmentItem", back_populates="score_history"
    )


# ── ComplianceEvidenceLink ────────────────────────────────────────────────────

class ComplianceEvidenceLink(Base):
    """Links an assessment item to an uploaded file or external reference."""
    __tablename__ = "ca_evidence_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evidence_type_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    item: Mapped["ComplianceAssessmentItem"] = relationship(
        "ComplianceAssessmentItem", back_populates="evidence_links"
    )


# ── ComplianceAction ──────────────────────────────────────────────────────────

class ComplianceAction(Base):
    """Open action / Maßnahme attached to a specific assessment item."""
    __tablename__ = "ca_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ActionStatus.open.value, nullable=False
    )
    priority: Mapped[str] = mapped_column(String(10), default="medium", nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    owner_name: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    item: Mapped["ComplianceAssessmentItem"] = relationship(
        "ComplianceAssessmentItem", back_populates="actions"
    )


# ── ComplianceStatusSnapshot ──────────────────────────────────────────────────

class ComplianceStatusSnapshot(Base):
    """
    Frozen, append-only summary of an assessment at a given point in time.
    Created whenever a gate decision is requested or the assessment is published.
    """
    __tablename__ = "ca_status_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ca_assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    trigger_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    compliance_status: Mapped[str] = mapped_column(String(30), nullable=False)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    traffic_light: Mapped[str] = mapped_column(String(10), nullable=False)
    gate_readiness: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    assessment: Mapped["ComplianceAssessment"] = relationship(
        "ComplianceAssessment", back_populates="snapshots"
    )
