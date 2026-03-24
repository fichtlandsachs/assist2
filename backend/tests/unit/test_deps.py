"""Unit tests for get_current_user dependency."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.security import HTTPAuthorizationCredentials

from app.core.exceptions import UnauthorizedException


def make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_user_by_authentik_id(db):
    """Returns user when found by authentik_id."""
    from app.deps import get_current_user
    from app.models.user import User

    user = User(
        email="test@example.com",
        authentik_id="auth-id-1",
        display_name="Test",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "auth-id-1", "email": "test@example.com"},
    ):
        result = await get_current_user(make_credentials("test-token"), db)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_lazy_migration(db):
    """Falls back to email lookup and sets authentik_id if not set yet."""
    from app.deps import get_current_user
    from app.models.user import User
    from sqlalchemy import select

    user = User(
        email="legacy@example.com",
        authentik_id=None,
        display_name="Legacy",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "new-auth-id", "email": "legacy@example.com"},
    ):
        result = await get_current_user(make_credentials("test-token"), db)

    assert result.id == user.id
    # authentik_id should now be set
    result2 = await db.execute(select(User).where(User.id == user.id))
    updated = result2.scalar_one()
    assert updated.authentik_id == "new-auth-id"


@pytest.mark.asyncio
async def test_get_current_user_not_found(db):
    """Raises 401 when user not found in local DB."""
    from app.deps import get_current_user

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "unknown-id", "email": "ghost@example.com"},
    ):
        with pytest.raises(Exception) as exc_info:
            await get_current_user(make_credentials("test-token"), db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_inactive(db):
    """Raises 401 for inactive users."""
    from app.deps import get_current_user
    from app.models.user import User

    user = User(
        email="inactive@example.com",
        authentik_id="auth-id-inactive",
        display_name="Inactive",
        is_active=False,
    )
    db.add(user)
    await db.commit()

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "auth-id-inactive", "email": "inactive@example.com"},
    ):
        with pytest.raises(Exception) as exc_info:
            await get_current_user(make_credentials("test-token"), db)

    assert exc_info.value.status_code == 401
