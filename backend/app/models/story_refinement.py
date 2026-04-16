from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.user import User


class StoryRefinementSession(Base):
    __tablename__ = "story_refinement_sessions"
    __table_args__ = (
        UniqueConstraint("story_id", name="uq_refinement_session_story"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    stage: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    last_proposal: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    readiness_state: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    story: Mapped[Optional["UserStory"]] = relationship("UserStory", foreign_keys=[story_id])
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
