from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime, date
import uuid
from app.models.project import ProjectStatus, EffortLevel, ComplexityLevel


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    status: ProjectStatus = ProjectStatus.planning
    deadline: Optional[date] = None
    color: Optional[str] = None
    effort: Optional[EffortLevel] = None
    complexity: Optional[ComplexityLevel] = None
    owner_id: Optional[uuid.UUID] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    deadline: Optional[date] = None
    color: Optional[str] = None
    effort: Optional[EffortLevel] = None
    complexity: Optional[ComplexityLevel] = None
    owner_id: Optional[uuid.UUID] = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: Optional[str]
    status: ProjectStatus


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    created_by_id: uuid.UUID
    owner_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    status: ProjectStatus
    deadline: Optional[date]
    color: Optional[str]
    effort: Optional[EffortLevel]
    complexity: Optional[ComplexityLevel]
    created_at: datetime
    updated_at: datetime
