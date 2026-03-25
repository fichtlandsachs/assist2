from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
import uuid
from app.models.mail_connection import MailProvider
from app.models.message import MessageStatus


class MailConnectionCreate(BaseModel):
    provider: MailProvider
    email_address: str
    display_name: Optional[str] = None
    # IMAP-specific fields (required when provider == "imap")
    imap_host: Optional[str] = None
    imap_port: Optional[int] = 993
    imap_password: Optional[str] = None  # plain-text, encrypted at rest
    imap_use_ssl: Optional[bool] = True


class MailConnectionUpdate(BaseModel):
    sync_interval_minutes: Optional[int] = Field(default=None, ge=1)
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class MailConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: MailProvider
    email_address: str
    display_name: Optional[str]
    is_active: bool
    last_sync_at: Optional[datetime]
    sync_interval_minutes: int = 15
    created_at: datetime
    # IMAP metadata (no password returned)
    imap_host: Optional[str] = None
    imap_port: Optional[int] = None
    imap_use_ssl: Optional[bool] = None


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    connection_id: uuid.UUID
    subject: Optional[str]
    sender_email: str
    sender_name: Optional[str]
    snippet: Optional[str]
    body_text: Optional[str] = None
    status: MessageStatus
    topic_cluster: Optional[str] = None
    received_at: Optional[datetime]
    created_at: datetime


class MessageUpdate(BaseModel):
    status: MessageStatus
