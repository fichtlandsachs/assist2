import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class UserStory(Base):
    __tablename__ = "user_stories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="draft",
        server_default="draft",
        index=True,
    )
    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        server_default="medium",
    )
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_story_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_stories.id", ondelete="SET NULL"),
        nullable=True,
    )
    acceptance_criteria: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doc_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    subtasks: Mapped[List["UserStory"]] = relationship(
        "UserStory",
        back_populates="parent_story",
        foreign_keys=[parent_story_id],
    )
    parent_story: Mapped[Optional["UserStory"]] = relationship(
        "UserStory",
        back_populates="subtasks",
        foreign_keys=[parent_story_id],
        remote_side="UserStory.id",
    )
    test_cases: Mapped[List["TestCase"]] = relationship(
        "TestCase",
        back_populates="story",
        cascade="all, delete-orphan",
    )


class TestCase(Base):
    __tablename__ = "test_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("user_stories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    steps: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    expected_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_result: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    # Relationships
    story: Mapped["UserStory"] = relationship(
        "UserStory",
        back_populates="test_cases",
    )
