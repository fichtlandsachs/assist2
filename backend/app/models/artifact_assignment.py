import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.capability_node import CapabilityNode


class ArtifactType(str, enum.Enum):
    project = "project"
    epic = "epic"
    user_story = "user_story"


class RelationType(str, enum.Enum):
    primary = "primary"
    secondary = "secondary"


class ArtifactAssignment(Base):
    __tablename__ = "artifact_assignments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_id: Mapped[uuid.UUID] = mapped_column(nullable=False, index=True)
    node_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False, default="primary")
    assignment_is_exception: Mapped[bool] = mapped_column(Boolean, default=False)
    assignment_exception_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    node: Mapped["CapabilityNode"] = relationship(
        "CapabilityNode", back_populates="assignments"
    )
