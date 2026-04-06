"""ORM model for suggestion feedback (rejected suggestions)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SuggestionFeedback(Base):
    __tablename__ = "suggestion_feedback"
    __table_args__ = (
        Index("ix_suggestion_feedback_org_type", "organization_id", "suggestion_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    suggestion_type: Mapped[str] = mapped_column(String(32), nullable=False)
    suggestion_text: Mapped[str] = mapped_column(String(1000), nullable=False)
    feedback: Mapped[str] = mapped_column(String(32), nullable=False, default="rejected")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
