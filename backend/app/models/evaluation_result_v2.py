from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class EvaluationResultV2(Base):
    __tablename__ = "evaluation_results_v2"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True
    )
    overall_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    # overall_status: pass | warn | fail | pending
    overall_status: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rewrite_suggestions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_final: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="result_v2")
