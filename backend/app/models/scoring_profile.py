from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.rule_set import RuleSet


class ScoringProfile(Base):
    __tablename__ = "scoring_profiles"
    __table_args__ = (
        UniqueConstraint("org_id", "rule_set_id", "name", "version",
                         name="uq_scoring_profiles_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    rule_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    dimension_weights: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pass_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.70)
    warn_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.50)
    auto_approve_threshold: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.90)
    require_review_below: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.60)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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

    rule_set: Mapped["RuleSet"] = relationship("RuleSet", back_populates="scoring_profiles")

    def to_snapshot_dict(self) -> dict:
        return {
            "profile_id": str(self.id),
            "dimension_weights": self.dimension_weights or {},
            "pass_threshold": float(self.pass_threshold),
            "warn_threshold": float(self.warn_threshold),
            "auto_approve_threshold": float(self.auto_approve_threshold),
            "require_review_below": float(self.require_review_below),
        }
