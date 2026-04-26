from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid
from app.models.story_process_change import ProcessChangeStatus


class ProcessCreate(BaseModel):
    name: str
    confluence_page_id: Optional[str] = None
    capability_node_id: Optional[uuid.UUID] = None


class ProcessUpdate(BaseModel):
    name: Optional[str] = None
    confluence_page_id: Optional[str] = None
    capability_node_id: Optional[uuid.UUID] = None


class ProcessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    capability_node_id: Optional[uuid.UUID] = None
    confluence_page_id: Optional[str]
    created_at: datetime
    updated_at: datetime


class StoryProcessChangeCreate(BaseModel):
    process_id: uuid.UUID
    section_anchor: Optional[str] = None
    delta_text: Optional[str] = None


class StoryProcessChangeUpdate(BaseModel):
    section_anchor: Optional[str] = None
    delta_text: Optional[str] = None


class StoryProcessChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    process_id: uuid.UUID
    section_anchor: Optional[str]
    delta_text: Optional[str]
    status: ProcessChangeStatus
    released_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    process: ProcessRead


class EpicProcessSummary(BaseModel):
    """Aggregated pending changes per process for an epic."""
    process: ProcessRead
    pending_count: int
    changes: List[StoryProcessChangeRead]
