from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
import uuid
from app.models.calendar_connection import CalendarProvider
from app.models.calendar_event import EventStatus


class CalendarConnectionCreate(BaseModel):
    provider: CalendarProvider
    email_address: str
    display_name: Optional[str] = None


class CalendarConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: CalendarProvider
    email_address: str
    display_name: Optional[str]
    is_active: bool
    last_sync_at: Optional[datetime]
    created_at: datetime


class CalendarEventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_at: datetime
    end_at: datetime
    all_day: bool = False


class CalendarEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    connection_id: uuid.UUID
    external_id: str
    title: str
    description: Optional[str]
    location: Optional[str]
    start_at: datetime
    end_at: datetime
    all_day: bool
    status: EventStatus
    organizer_email: Optional[str]
    created_at: datetime
