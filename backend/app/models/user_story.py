import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, ForeignKey, Enum, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
import enum

if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.feature import Feature
    from app.models.project import Project


class StoryStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    ready = "ready"
    in_progress = "in_progress"
    testing = "testing"
    done = "done"
    archived = "archived"


class StoryPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class UserStory(Base):
    __tablename__ = "user_stories"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[StoryStatus] = mapped_column(
        Enum(StoryStatus), default=StoryStatus.draft, nullable=False
    )
    priority: Mapped[StoryPriority] = mapped_column(
        Enum(StoryPriority), default=StoryPriority.medium, nullable=False
    )
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dor_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    ai_suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    generated_docs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    confluence_page_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Project / Epic / split
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    epic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("epics.id"), nullable=True, index=True)
    parent_story_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user_stories.id"), nullable=True)
    is_split: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    definition_of_done: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    doc_additional_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_workarounds: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="stories")
    epic: Mapped[Optional["Epic"]] = relationship("Epic", back_populates="stories", foreign_keys=[epic_id])
    sub_stories: Mapped[list["UserStory"]] = relationship("UserStory", foreign_keys="UserStory.parent_story_id", passive_deletes=True)
    features: Mapped[list["Feature"]] = relationship("Feature", back_populates="story", passive_deletes=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
