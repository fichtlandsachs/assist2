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


class StoryAssistantSession(Base):
    """Generic AI chat session for DoD and Features assistants."""

    __tablename__ = "story_assistant_sessions"
    __table_args__ = (
        UniqueConstraint("story_id", "session_type", name="uq_assistant_session_story_type"),
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
    # "dod" or "features"
    session_type: Mapped[str] = mapped_column(String(30), nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # JSON array: list of DoDItem or FeatureItem dicts
    last_proposal: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
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
