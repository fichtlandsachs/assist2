from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_run import EvaluationRun


class EvaluationStepResult(Base):
    __tablename__ = "evaluation_step_results"
    __table_args__ = (
        UniqueConstraint("evaluation_run_id", "step_name", name="uq_eval_step_run_step"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dimension: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # status: pending | running | completed | failed | skipped
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 4), nullable=True)
    findings: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    input_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    llm_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    run: Mapped["EvaluationRun"] = relationship("EvaluationRun", back_populates="step_results")
