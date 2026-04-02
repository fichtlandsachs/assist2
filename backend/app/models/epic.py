import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.feature import Feature
    from app.models.project import Project


class EpicStatus(str, enum.Enum):
    planning = "planning"
    in_progress = "in_progress"
    done = "done"
    archived = "archived"


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[EpicStatus] = mapped_column(Enum(EpicStatus), default=EpicStatus.planning, nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="epics")
    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="epic", foreign_keys="UserStory.epic_id")
    features: Mapped[List["Feature"]] = relationship("Feature", back_populates="epic")
