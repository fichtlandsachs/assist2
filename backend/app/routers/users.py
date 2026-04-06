import uuid

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.post(
    "/users/me/password",
    status_code=204,
    summary="Change my password",
)
async def change_my_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the authenticated user's password (local accounts only)."""
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="Passwort kann für SSO-Konten nicht geändert werden.")
    try:
        valid = bcrypt.checkpw(data.current_password.encode(), current_user.password_hash.encode())
    except Exception:
        valid = False
    if not valid:
        raise HTTPException(status_code=400, detail="Aktuelles Passwort ist falsch.")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=422, detail="Das neue Passwort muss mindestens 8 Zeichen lang sein.")
    new_hash = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()
    await user_service.update_password(db, current_user.id, new_hash)


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
