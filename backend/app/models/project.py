import enum
import uuid
from datetime import datetime, timezone, date
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.epic import Epic
    from app.models.user_story import UserStory


class ProjectStatus(str, enum.Enum):
    planning = "planning"
    active = "active"
    done = "done"
    archived = "archived"


class EffortLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    xl = "xl"


class ComplexityLevel(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    xl = "xl"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.planning, nullable=False
    )
    deadline: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    effort: Mapped[Optional[EffortLevel]] = mapped_column(Enum(EffortLevel), nullable=True)
    complexity: Mapped[Optional[ComplexityLevel]] = mapped_column(Enum(ComplexityLevel), nullable=True)

    # Project brief & timeline
    project_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planned_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Jira reference fields
    jira_project_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_project_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    jira_project_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    jira_project_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    jira_project_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jira_project_lead: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_board_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    jira_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    jira_source_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    epics: Mapped[List["Epic"]] = relationship("Epic", back_populates="project")
    stories: Mapped[List["UserStory"]] = relationship("UserStory", back_populates="project")
