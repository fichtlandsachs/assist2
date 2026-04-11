from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.rule_definition import RuleDefinition
    from app.models.scoring_profile import ScoringProfile


class RuleSet(Base):
    __tablename__ = "rule_sets"
    __table_args__ = (
        UniqueConstraint("org_id", "name", "version", name="uq_rule_sets_org_name_ver"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # status: draft | active | archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    frozen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
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

    rules: Mapped[list["RuleDefinition"]] = relationship(
        "RuleDefinition", back_populates="rule_set",
        cascade="all, delete-orphan", order_by="RuleDefinition.order_index"
    )
    scoring_profiles: Mapped[list["ScoringProfile"]] = relationship(
        "ScoringProfile", back_populates="rule_set"
    )

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None

    def to_snapshot_dict(self) -> dict:
        """Frozen snapshot for evaluation_runs. Call before starting a run."""
        return {
            "rule_set_id": str(self.id),
            "name": self.name,
            "version": self.version,
            "frozen_at": self.frozen_at.isoformat() if self.frozen_at else None,
            "rules": [
                {
                    "rule_id": str(r.id),
                    "name": r.name,
                    "dimension": r.dimension,
                    "weight": float(r.weight),
                    "parameters": r.parameters or {},
                    "prompt_template": r.prompt_template,
                }
                for r in self.rules if r.is_active
            ],
        }
