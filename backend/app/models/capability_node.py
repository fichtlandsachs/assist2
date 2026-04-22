import enum
import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.artifact_assignment import ArtifactAssignment


class NodeType(str, enum.Enum):
    capability = "capability"
    level_1 = "level_1"
    level_2 = "level_2"
    level_3 = "level_3"


# Allowed standard assignment levels per artifact type (enforced in router)
ALLOWED_ASSIGNMENT_LEVELS: dict[str, list[NodeType]] = {
    "project":    [NodeType.capability, NodeType.level_1],
    "epic":       [NodeType.level_1, NodeType.level_2, NodeType.level_3],
    "user_story": [NodeType.level_2, NodeType.level_3],
}

# Levels that are allowed only as exceptions (require reason)
EXCEPTION_ALLOWED_LEVELS: dict[str, list[NodeType]] = {
    "epic":       [NodeType.level_1],
    "user_story": [NodeType.level_1],
}


class CapabilityNode(Base):
    __tablename__ = "capability_nodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("capability_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    external_import_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    parent: Mapped[Optional["CapabilityNode"]] = relationship(
        "CapabilityNode",
        remote_side="CapabilityNode.id",
        back_populates="children",
    )
    children: Mapped[List["CapabilityNode"]] = relationship(
        "CapabilityNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="CapabilityNode.sort_order",
    )
    assignments: Mapped[List["ArtifactAssignment"]] = relationship(
        "ArtifactAssignment",
        back_populates="node",
        cascade="all, delete-orphan",
    )
