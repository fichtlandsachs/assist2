import uuid
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class MessageStatus(str, enum.Enum):
    unread = "unread"
    read = "read"
    archived = "archived"
    deleted = "deleted"


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("mail_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)  # Gmail message ID
    thread_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False)
    sender_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.unread)
    topic_cluster: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, index=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
