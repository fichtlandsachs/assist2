from __future__ import annotations
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.evaluation_step_result import EvaluationStepResult
    from app.models.evaluation_result_v2 import EvaluationResultV2


class EvaluationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AmpelStatus(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id"), nullable=False, index=True
    )
    triggered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status", create_type=False),
        default=EvaluationStatus.PENDING,
        nullable=False,
    )
    score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    ampel: Mapped[Optional[AmpelStatus]] = mapped_column(
        Enum(AmpelStatus, name="ampel_status", create_type=False), nullable=True
    )
    knockout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # v2 columns (all nullable for backward compat)
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    rule_set_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="RESTRICT"), nullable=True
    )
    rule_set_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    scoring_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("scoring_profiles.id", ondelete="SET NULL"), nullable=True
    )
    scoring_profile_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    langgraph_thread_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    parent_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="SET NULL"), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    step_results: Mapped[list["EvaluationStepResult"]] = relationship(
        "EvaluationStepResult", back_populates="run",
        cascade="all, delete-orphan", order_by="EvaluationStepResult.created_at"
    )
    result_v2: Mapped[Optional["EvaluationResultV2"]] = relationship(
        "EvaluationResultV2", back_populates="run", uselist=False,
        cascade="all, delete-orphan"
    )
