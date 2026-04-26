import uuid
from typing import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import get_user_permissions
from app.core.security import decode_token, validate_authentik_token
from app.database import get_db
from app.models.user import User

security = HTTPBearer()


async def _lookup_user_hs256(payload: dict, db: AsyncSession) -> User | None:
    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedException(detail="Invalid token claims")
    result = await db.execute(
        select(User).where(
            User.id == uuid.UUID(user_id),
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedException(detail="User not found")
    if not user.is_active:
        raise UnauthorizedException(detail="Account is disabled")
    return user


async def _lookup_user_oidc(payload: dict, db: AsyncSession) -> User:
    authentik_id: str | None = payload.get("sub")
    email: str | None = payload.get("email")
    if not authentik_id or not email:
        raise UnauthorizedException(detail="Invalid token claims")

    # Primary lookup: exact authentik_id match
    result = await db.execute(
        select(User).where(
            User.authentik_id == authentik_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Fallback: look up by email regardless of existing authentik_id value.
        # This handles cases where the stored authentik_id is stale/incorrect.
        result = await db.execute(
            select(User).where(
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user:
            # Sync the correct authentik_id
            user.authentik_id = authentik_id
            await db.commit()
            await db.refresh(user)

    if not user:
        raise UnauthorizedException(detail="User not found")
    if not user.is_active:
        raise UnauthorizedException(detail="Account is disabled")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate JWT (HS256 or Authentik OIDC), return the matching local User.

    Strategy:
    1. Peek at the JWT header — if alg=HS256, treat as internal token.
    2. Otherwise (RS256 etc.) go straight to Authentik OIDC validation.
    This avoids the old pattern where any HS256 decode failure would
    short-circuit the OIDC fallback.
    """
    import logging as _logging
    import jwt as _pyjwt

    _log = _logging.getLogger("app.auth")
    token = credentials.credentials

    # Peek at header without verifying signature
    try:
        header = _pyjwt.get_unverified_header(token)
        alg = header.get("alg", "")
    except Exception:
        raise UnauthorizedException(detail="Malformed token")

    if alg == "HS256":
        # Internal HS256 token — validate fully
        return await _lookup_user_hs256(decode_token(token), db)

    # Authentik OIDC token (RS256 or similar)
    try:
        payload = await validate_authentik_token(token)
    except UnauthorizedException:
        raise
    except Exception as e:
        _log.warning(f"OIDC validation error: {e}")
        raise UnauthorizedException(detail="Could not validate credentials")

    return await _lookup_user_oidc(payload, db)


async def get_current_user_with_groups(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, list[str]]:
    """Like get_current_user but also returns AD groups from the Authentik OIDC groups claim."""
    import jwt as _pyjwt

    token = credentials.credentials

    try:
        header = _pyjwt.get_unverified_header(token)
        alg = header.get("alg", "")
    except Exception:
        raise UnauthorizedException(detail="Malformed token")

    if alg == "HS256":
        user = await _lookup_user_hs256(decode_token(token), db)
        return user, []

    payload = await validate_authentik_token(token)
    user = await _lookup_user_oidc(payload, db)
    groups = [str(g) for g in payload.get("groups", []) if g]
    return user, groups


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
