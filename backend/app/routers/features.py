import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.core.billing_guard import require_active_subscription
from app.models.feature import Feature
from app.models.user import User
from app.core.story_filter import active_stories
from app.models.user_story import UserStory
from app.schemas.feature import FeatureCreate, FeatureRead, FeatureUpdate
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get("/features", response_model=List[FeatureRead])
async def list_features(
    org_id: uuid.UUID,
    story_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[FeatureRead]:
    stmt = select(Feature).where(Feature.organization_id == org_id)
    if story_id:
        stmt = stmt.where(Feature.story_id == story_id)
    if project_id:
        stmt = stmt.join(UserStory, Feature.story_id == UserStory.id).where(
            UserStory.project_id == project_id
        )
    stmt = stmt.order_by(Feature.created_at.desc())
    result = await db.execute(stmt)
    features = result.scalars().all()

    # Batch-fetch story titles
    story_ids = {f.story_id for f in features}
    story_titles: dict[uuid.UUID, str] = {}
    if story_ids:
        s_result = await db.execute(select(UserStory).where(UserStory.id.in_(story_ids)))
        story_titles = {s.id: s.title for s in s_result.scalars().all()}

    reads = []
    for f in features:
        r = FeatureRead.model_validate(f)
        r.story_title = story_titles.get(f.story_id)
        reads.append(r)
    return reads


@router.post("/features", response_model=FeatureRead, status_code=status.HTTP_201_CREATED)
async def create_feature(
    org_id: uuid.UUID,
    data: FeatureCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _billing=Depends(require_active_subscription),
) -> FeatureRead:
    feature = Feature(
        organization_id=org_id,
        created_by_id=current_user.id,
        story_id=data.story_id,
        epic_id=data.epic_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        story_points=data.story_points,
    )
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return FeatureRead.model_validate(feature)


@router.get("/features/{feature_id}", response_model=FeatureRead)
async def get_feature(
    feature_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureRead:
    stmt = select(Feature).where(Feature.id == feature_id)
    result = await db.execute(stmt)
    feature = result.scalar_one_or_none()
    if feature is None:
        raise NotFoundException("Feature not found")
    return FeatureRead.model_validate(feature)


@router.patch("/features/{feature_id}", response_model=FeatureRead)
async def update_feature(
    feature_id: uuid.UUID,
    data: FeatureUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FeatureRead:
    stmt = select(Feature).where(Feature.id == feature_id)
    result = await db.execute(stmt)
    feature = result.scalar_one_or_none()
    if feature is None:
        raise NotFoundException("Feature not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(feature, field, value)

    await db.commit()
    await db.refresh(feature)
    return FeatureRead.model_validate(feature)


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_feature(
    feature_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(Feature).where(Feature.id == feature_id)
    result = await db.execute(stmt)
    feature = result.scalar_one_or_none()
    if feature is None:
        raise NotFoundException("Feature not found")
    await db.delete(feature)
    await db.commit()
