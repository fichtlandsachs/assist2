import uuid
from typing import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import get_user_permissions
from app.core.security import validate_authentik_token
from app.database import get_db
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate Authentik OIDC JWT, return the matching local User.
    Falls back to email lookup for users not yet migrated (lazy migration).
    """
    payload = await validate_authentik_token(credentials.credentials)
    authentik_id: str | None = payload.get("sub")
    email: str | None = payload.get("email")

    if not authentik_id or not email:
        raise UnauthorizedException(detail="Invalid token claims")

    # Primary lookup: by authentik_id
    result = await db.execute(
        select(User).where(
            User.authentik_id == authentik_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Lazy migration: user exists but authentik_id not yet set
        result = await db.execute(
            select(User).where(
                User.email == email.lower(),
                User.authentik_id.is_(None),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user:
            user.authentik_id = authentik_id
            await db.commit()
            await db.refresh(user)

    if not user:
        raise UnauthorizedException(detail="User not found")

    if not user.is_active:
        raise UnauthorizedException(detail="Account is disabled")

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    return user


async def get_current_superuser(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_superuser:
        raise ForbiddenException(detail="Superuser access required")
    return user


def require_permission(permission: str):
    async def check(
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        permissions = await get_user_permissions(current_user.id, org_id, db)
        if "*" in permissions or permission in permissions:
            return current_user
        raise ForbiddenException(
            detail=f"Permission '{permission}' required for this operation"
        )
    return check


from app.services.atlassian_token import atlassian_token_store


async def get_atlassian_token(
    current_user: User = Depends(get_current_user),
) -> tuple[str, str]:
    """
    Dependency for Jira routes.
    Returns (access_token, cloud_id). Transparently refreshes if near expiry.
    Raises 403 when no Atlassian account is linked.
    """
    data = await atlassian_token_store.get(current_user.id)
    if not data:
        raise ForbiddenException(
            detail="Kein Atlassian-Account verknüpft. Bitte über Atlassian einloggen."
        )
    token = await atlassian_token_store.get_valid_token(current_user.id)
    return token, data["cloud_id"]
