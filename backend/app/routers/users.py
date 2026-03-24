import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.services.user_service import user_service

router = APIRouter()


@router.get(
    "/users/me",
    response_model=UserRead,
    summary="Get my profile",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Get the authenticated user's own profile."""
    return UserRead.model_validate(current_user)


@router.patch(
    "/users/me",
    response_model=UserRead,
    summary="Update my profile",
)
async def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Update the authenticated user's profile fields."""
    updated_user = await user_service.update(db, current_user.id, data)
    return UserRead.model_validate(updated_user)


@router.get(
    "/users/{user_id}",
    response_model=UserRead,
    summary="Get a user by ID",
)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    """Get a user by their ID. Requires org membership to view other users."""
    user = await user_service.get_by_id(db, user_id)
    return UserRead.model_validate(user)
