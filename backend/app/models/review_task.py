from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.review_decision import ReviewDecision


class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    story_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", ondelete="RESTRICT"), nullable=True
    )
    # review_type: threshold_review | compliance_review | escalation | final_approval
    review_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # status: pending | in_review | approved | rejected | escalated | expired | cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # priority: low | normal | high | critical
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="normal")
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # timeout_action: auto_approve | auto_reject | escalate
    timeout_action: Mapped[str] = mapped_column(String(20), nullable=False, default="escalate")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    opened_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    decisions: Mapped[list["ReviewDecision"]] = relationship(
        "ReviewDecision", back_populates="task", cascade="all, delete-orphan"
    )
