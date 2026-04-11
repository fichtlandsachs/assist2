from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory


class StoryVersion(Base):
    __tablename__ = "story_versions"
    __table_args__ = (
        UniqueConstraint("story_id", "version_number", name="uq_story_versions_story_ver"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    as_a: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    i_want: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    so_that: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # JSON so it works in both SQLite (tests) and PostgreSQL (JSONB)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    story: Mapped["UserStory"] = relationship(
        "UserStory", back_populates="versions", foreign_keys=[story_id]
    )
