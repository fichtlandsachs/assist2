import enum
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, ForeignKey, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SuggestionStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"
    reassigned = "reassigned"


class ProcessMappingSuggestion(Base):
    __tablename__ = "process_mapping_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    process_name: Mapped[str] = mapped_column(String(500), nullable=False)
    detected_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="SET NULL"), nullable=True
    )
    suggested_node_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_reference: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
