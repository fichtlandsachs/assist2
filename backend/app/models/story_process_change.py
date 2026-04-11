import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user_story import UserStory
    from app.models.process import Process


class ProcessChangeStatus(str, enum.Enum):
    pending = "pending"
    released = "released"


class StoryProcessChange(Base):
    __tablename__ = "story_process_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_stories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    process_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("processes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_anchor: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    delta_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ProcessChangeStatus] = mapped_column(
        Enum(ProcessChangeStatus), default=ProcessChangeStatus.pending, nullable=False
    )
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    story: Mapped["UserStory"] = relationship("UserStory", back_populates="process_changes")
    process: Mapped["Process"] = relationship("Process", back_populates="changes")
