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
    from app.models.story_process_change import StoryProcessChange
    from app.models.story_version import StoryVersion


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
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
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
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    jira_ticket_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    jira_ticket_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # ── Jira Sync ────────────────────────────────────────────────────────────
    jira_creator: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_reporter: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    jira_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    jira_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jira_linked_issue_keys: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    jira_last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("story_versions.id", use_alter=True,
                   name="fk_stories_current_version"),
        nullable=True,
    )

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="stories")
    epic: Mapped[Optional["Epic"]] = relationship("Epic", back_populates="stories", foreign_keys=[epic_id])
    sub_stories: Mapped[list["UserStory"]] = relationship("UserStory", foreign_keys="UserStory.parent_story_id", passive_deletes=True)
    features: Mapped[list["Feature"]] = relationship("Feature", back_populates="story", passive_deletes=True)
    process_changes: Mapped[list["StoryProcessChange"]] = relationship("StoryProcessChange", back_populates="story", passive_deletes=True)
    versions: Mapped[list["StoryVersion"]] = relationship(
        "StoryVersion",
        back_populates="story",
        foreign_keys="StoryVersion.story_id",
        order_by="StoryVersion.version_number",
        passive_deletes=True,
    )
    # ── Soft-delete (CRITICAL: never expose deleted stories) ─────────────────
    # All queries MUST add .where(UserStory.is_deleted == False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
