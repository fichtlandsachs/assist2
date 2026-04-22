# app/models/control.py
"""ISO 27001 / NIS2 compliance controls, scoped to capability nodes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.capability_node import CapabilityNode


class Control(Base):
    __tablename__ = "controls"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    control_type: Mapped[str] = mapped_column(String(20), nullable=False)
    implementation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_started"
    )
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_interval_days: Mapped[int] = mapped_column(Integer, default=365, nullable=False)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_review_due: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    framework_refs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    user_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    user_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_guiding_questions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    user_evidence_needed: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    capability_assignments: Mapped[List["ControlCapabilityAssignment"]] = relationship(
        "ControlCapabilityAssignment",
        back_populates="control",
        cascade="all, delete-orphan",
    )


class ControlCapabilityAssignment(Base):
    __tablename__ = "control_capability_assignments"
    __table_args__ = (
        UniqueConstraint("control_id", "capability_node_id", name="uq_cca_control_node"),
        CheckConstraint("maturity_level BETWEEN 1 AND 5", name="ck_cca_maturity_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("controls.id", ondelete="CASCADE"), nullable=False, index=True
    )
    capability_node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    maturity_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    effectiveness: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_assessed"
    )
    coverage_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    gap_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assessor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_assessed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_assessment_due: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_inherited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    inherited_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("control_capability_assignments.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    control: Mapped["Control"] = relationship(
        "Control", back_populates="capability_assignments"
    )
    capability_node: Mapped["CapabilityNode"] = relationship("CapabilityNode")
