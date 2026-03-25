import uuid
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class MailProvider(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"
    imap = "imap"


class MailConnection(Base):
    __tablename__ = "mail_connections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    provider: Mapped[MailProvider] = mapped_column(Enum(MailProvider), nullable=False)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    access_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # Fernet encrypted
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Fernet encrypted
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # IMAP-specific
    imap_host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    imap_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    imap_password_enc: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Fernet encrypted
    imap_use_ssl: Mapped[Optional[bool]] = mapped_column(Boolean, default=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
