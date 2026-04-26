# app/models/trust_profile.py
"""
Trust Profile ORM model.

Each ExternalSource gets a TrustProfile that controls how its chunks
are ranked in retrieval. Trust classes V1–V5 determine which retrieval
contexts a source is eligible for (e.g. security, compliance, general).

Trust is NOT a single score — it is a multi-dimensional profile.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, String, Text, CheckConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TrustClass(str, enum.Enum):
    """
    V5 = verbindlich (binding) — highest authority
    V4 = approved official source
    V3 = reviewed internal
    V2 = draft / unreviewed internal
    V1 = community / supporting only
    """
    V5 = "V5"
    V4 = "V4"
    V3 = "V3"
    V2 = "V2"
    V1 = "V1"


class SourceCategory(str, enum.Enum):
    """
    Determines the conflict resolution precedence and retrieval eligibility.
    """
    manufacturer  = "manufacturer"    # Hersteller-Doku → führend für Produktstandards
    internal_approved = "internal_approved"  # Interne freigegebene Doku → führend für Prozesse
    internal_draft    = "internal_draft"     # Interne Entwürfe → NICHT produktiv
    partner           = "partner"            # Partner-Doku
    community         = "community"          # Community → nur unterstützend
    standard_norm     = "standard_norm"      # Norm/Standard → methodisch stark


class TrustProfile(Base):
    """
    Trust profile for an ExternalSource.
    One-to-one with ExternalSource (enforced via unique constraint on source_id).
    """
    __tablename__ = "trust_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Trust class
    trust_class: Mapped[str] = mapped_column(
        String(4), nullable=False, default=TrustClass.V3.value
    )

    # Source category (determines conflict resolution + eligibility rules)
    source_category: Mapped[str] = mapped_column(
        String(30), nullable=False, default=SourceCategory.internal_approved.value
    )

    # Trust dimensions (0.0–1.0 each)
    authority_score:     Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    standard_score:      Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    context_score:       Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    freshness_score:     Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    governance_score:    Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    traceability_score:  Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Computed composite trust score (cached, updated when dimensions change)
    composite_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Eligibility rules (JSONB) — which contexts this source is allowed in
    # Example: {"security": false, "compliance": false, "general": true}
    eligibility: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        default=lambda: {
            "security":    True,
            "compliance":  True,
            "general":     True,
            "architecture": True,
        }
    )

    # Admin notes
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint("authority_score >= 0.0 AND authority_score <= 1.0"),
        CheckConstraint("standard_score >= 0.0 AND standard_score <= 1.0"),
        CheckConstraint("context_score >= 0.0 AND context_score <= 1.0"),
        CheckConstraint("freshness_score >= 0.0 AND freshness_score <= 1.0"),
        CheckConstraint("governance_score >= 0.0 AND governance_score <= 1.0"),
        CheckConstraint("traceability_score >= 0.0 AND traceability_score <= 1.0"),
    )
