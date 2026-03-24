from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserWithLinks
from app.services.auth_service import auth_service

router = APIRouter()


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account in Authentik + local DB, return tokens."""
    return await auth_service.register(db, data)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate via Authentik ROPC grant, returning OIDC tokens."""
    return await auth_service.login(db, data)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair via Authentik."""
    return await auth_service.refresh(db, data.refresh_token)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke session",
)
async def logout(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the refresh token in Authentik."""
    await auth_service.logout(db, data.refresh_token)


@router.get(
    "/auth/me",
    response_model=UserWithLinks,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserWithLinks:
    """Get the authenticated user's profile."""
    return UserWithLinks.model_validate(current_user)
