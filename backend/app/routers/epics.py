import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.epic import Epic
from app.models.user import User
from app.schemas.user_story import EpicCreate, EpicRead, EpicUpdate
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.patch("/epics/{epic_id}", response_model=EpicRead)
async def update_epic(
    epic_id: uuid.UUID,
    data: EpicUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EpicRead:
    stmt = select(Epic).where(Epic.id == epic_id)
    result = await db.execute(stmt)
    epic = result.scalar_one_or_none()
    if epic is None:
        raise NotFoundException("Epic not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(epic, field, value)
    await db.commit()
    await db.refresh(epic)
    return EpicRead.model_validate(epic)


@router.get("/epics", response_model=List[EpicRead])
async def list_epics(
    org_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EpicRead]:
    stmt = select(Epic).where(Epic.organization_id == org_id).order_by(Epic.created_at.desc())
    if project_id is not None:
        stmt = stmt.where(Epic.project_id == project_id)
    result = await db.execute(stmt)
    return [EpicRead.model_validate(e) for e in result.scalars().all()]


@router.post("/epics", response_model=EpicRead, status_code=status.HTTP_201_CREATED)
async def create_epic(
    org_id: uuid.UUID,
    data: EpicCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EpicRead:
    epic = Epic(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=data.title,
        description=data.description,
        project_id=data.project_id,
    )
    db.add(epic)
    await db.commit()
    await db.refresh(epic)
    return EpicRead.model_validate(epic)
