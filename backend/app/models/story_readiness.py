from __future__ import annotations
import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.user import User


class ReadinessState(str, enum.Enum):
    not_ready = "not_ready"
    partially_ready = "partially_ready"
    mostly_ready = "mostly_ready"
    implementation_ready = "implementation_ready"


class StoryReadinessEvaluation(Base):
    __tablename__ = "story_readiness_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evaluated_for_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    triggered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    readiness_state: Mapped[ReadinessState] = mapped_column(
        Enum(ReadinessState, name="readiness_state", create_type=False),
        nullable=False,
    )

    # Structured evaluation results (JSONB arrays)
    open_topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    missing_inputs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_preparatory_work: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    blockers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    recommended_next_steps: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    story_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    story: Mapped[Optional["UserStory"]] = relationship("UserStory", foreign_keys=[story_id])
    evaluated_for_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[evaluated_for_user_id])
