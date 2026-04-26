# app/models/control_standards.py
"""
Standard- and Control-Family models.

StandardDefinition  — a named compliance standard or framework
                       (ISO 9001, ISO 27001, NIS2, Internal Governance, …)

ControlStandardMapping  — M:N bridge: one Master-Control ↔ many Standards
                          with optional section reference and display priority.

The ControlDefinition.control_family column (added via migration) groups
sibling controls inside a category into a named "Control-Familie".
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class StandardDefinition(Base):
    """
    A compliance standard or governance framework.
    Examples: ISO 9001, ISO 27001, NIS2, Internal Governance, Product-specific Norm.
    """
    __tablename__ = "pg_standards"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)   # badge label
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    standard_type: Mapped[str] = mapped_column(String(40), nullable=False, default="external")
    # external | internal | product_specific | customer_specific | regulatory

    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)        # tailwind color key
    icon: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    mappings: Mapped[list["ControlStandardMapping"]] = relationship(
        "ControlStandardMapping", back_populates="standard", cascade="all, delete-orphan"
    )


class ControlStandardMapping(Base):
    """
    Many-to-many: one ControlDefinition can belong to many StandardDefinitions.
    Carries the section/clause reference within that standard.
    """
    __tablename__ = "pg_control_standard_mappings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    control_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_control_definitions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    standard_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pg_standards.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Optional: the chapter / clause in the standard, e.g. "8.1", "A.12.6"
    section_ref: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Human label for that section, e.g. "Operational planning and control"
    section_label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Display order within the standard's control list
    display_order: Mapped[int] = mapped_column(Integer, default=50, nullable=False)

    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # True if this standard is the "primary" framework for this control

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    standard: Mapped["StandardDefinition"] = relationship(
        "StandardDefinition", back_populates="mappings"
    )

    __table_args__ = (
        UniqueConstraint("control_id", "standard_id", name="uq_pg_ctrl_std_mapping"),
    )
