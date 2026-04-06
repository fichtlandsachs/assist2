import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.project import Project
from app.models.epic import Epic
from app.models.user_story import UserStory
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from app.schemas.user_story import EpicRead, UserStoryRead
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("/projects", response_model=List[ProjectRead])
async def list_projects(
    org_id: uuid.UUID,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectRead]:
    stmt = select(Project).where(Project.organization_id == org_id).order_by(Project.created_at.desc())
    if status:
        stmt = stmt.where(Project.status == status)
    result = await db.execute(stmt)
    return [ProjectRead.model_validate(p) for p in result.scalars().all()]


@router.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    org_id: uuid.UUID,
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = Project(
        organization_id=org_id,
        created_by_id=current_user.id,
        owner_id=data.owner_id,
        name=data.name,
        description=data.description,
        status=data.status,
        deadline=data.deadline,
        color=data.color,
        effort=data.effort,
        complexity=data.complexity,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("/projects/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    return ProjectRead.model_validate(project)


@router.patch("/projects/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return ProjectRead.model_validate(project)


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(Project).where(Project.id == project_id)
    result = await db.execute(stmt)
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundException("Project not found")
    # Unlink epics before deletion
    epic_stmt = select(Epic).where(Epic.project_id == project_id)
    epics = (await db.execute(epic_stmt)).scalars().all()
    for epic in epics:
        epic.project_id = None
    # Unlink stories before deletion
    story_stmt = select(UserStory).where(UserStory.project_id == project_id)
    stories = (await db.execute(story_stmt)).scalars().all()
    for story in stories:
        story.project_id = None
    await db.delete(project)
    await db.commit()


@router.get("/projects/{project_id}/epics", response_model=List[EpicRead])
async def list_project_epics(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EpicRead]:
    stmt = select(Epic).where(Epic.project_id == project_id).order_by(Epic.created_at.desc())
    result = await db.execute(stmt)
    return [EpicRead.model_validate(e) for e in result.scalars().all()]


@router.get("/projects/{project_id}/stories", response_model=List[UserStoryRead])
async def list_project_stories(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[UserStoryRead]:
    """Stories directly assigned to this project without an epic."""
    stmt = (
        select(UserStory)
        .where(UserStory.project_id == project_id, UserStory.epic_id.is_(None))
        .order_by(UserStory.created_at.desc())
    )
    result = await db.execute(stmt)
    return [UserStoryRead.model_validate(s) for s in result.scalars().all()]
