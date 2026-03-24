import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from app.models.user_story import StoryPriority

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.epic import Epic


class FeatureStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    testing = "testing"
    done = "done"
    archived = "archived"


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    story_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_stories.id"), nullable=False, index=True)
    epic_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("epics.id"), nullable=True, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[FeatureStatus] = mapped_column(Enum(FeatureStatus), default=FeatureStatus.draft, nullable=False)
    priority: Mapped[StoryPriority] = mapped_column(Enum(StoryPriority), default=StoryPriority.medium, nullable=False)
    story_points: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    story: Mapped["UserStory"] = relationship("UserStory", back_populates="features")
    epic: Mapped[Optional["Epic"]] = relationship("Epic", back_populates="features")
