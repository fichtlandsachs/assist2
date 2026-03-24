"""Unit tests for AuthService — AuthentikClient is mocked."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.core.exceptions import UnauthorizedException
from app.models.user import User


MOCK_TOKEN_RESPONSE = TokenResponse(
    access_token="access-123",
    refresh_token="refresh-456",
    token_type="bearer",
)


@pytest.mark.asyncio
async def test_login_success(db: AsyncSession):
    """login() looks up user, verifies password, calls AuthentikClient and returns tokens."""
    from app.services.auth_service import auth_service

    password = "pass123"
    user = User(
        email="user@example.com",
        authentik_id="99",
        display_name="Test User",
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        is_active=True,
    )
    db.add(user)
    await db.commit()

    with patch(
        "app.services.auth_service.authentik_client.create_app_password",
        new_callable=AsyncMock,
        return_value="app-key-xyz",
    ), patch(
        "app.services.auth_service.authentik_client.authenticate_user",
        new_callable=AsyncMock,
        return_value=MOCK_TOKEN_RESPONSE,
    ), patch(
        "app.services.auth_service.authentik_client.delete_app_password",
        new_callable=AsyncMock,
    ):
        result = await auth_service.login(db, LoginRequest(
            email="user@example.com", password=password
        ))

    assert result.access_token == "access-123"
    assert result.refresh_token == "refresh-456"


@pytest.mark.asyncio
async def test_login_invalid_credentials(db: AsyncSession):
    """login() propagates UnauthorizedException from AuthentikClient."""
    from app.services.auth_service import auth_service

    with patch(
        "app.services.auth_service.authentik_client.authenticate_user",
        new_callable=AsyncMock,
        side_effect=UnauthorizedException(detail="Invalid email or password"),
    ):
        with pytest.raises(UnauthorizedException):
            await auth_service.login(db, LoginRequest(
                email="user@example.com", password="wrong"
            ))


@pytest.mark.asyncio
async def test_register_creates_user_in_db(db: AsyncSession):
    """register() creates a local User record with authentik_id set."""
    from app.services.auth_service import auth_service
    from app.models.user import User
    from sqlalchemy import select

    with patch(
        "app.services.auth_service.authentik_client.create_user",
        new_callable=AsyncMock,
        return_value="42",  # Authentik returns integer PK as string
    ), patch(
        "app.services.auth_service.authentik_client.create_app_password",
        new_callable=AsyncMock,
        return_value="app-key-xyz",
    ), patch(
        "app.services.auth_service.authentik_client.authenticate_user",
        new_callable=AsyncMock,
        return_value=MOCK_TOKEN_RESPONSE,
    ), patch(
        "app.services.auth_service.authentik_client.delete_app_password",
        new_callable=AsyncMock,
    ):
        result = await auth_service.register(db, RegisterRequest(
            email="new@example.com",
            password="pass12345",
            display_name="New User",
        ))

    assert result.access_token != ""
    # Verify user in DB
    db_result = await db.execute(
        select(User).where(User.email == "new@example.com")
    )
    user = db_result.scalar_one_or_none()
    assert user is not None
    assert user.authentik_id == "42"


@pytest.mark.asyncio
async def test_refresh_delegates_to_authentik(db: AsyncSession):
    """refresh() calls AuthentikClient.refresh_token."""
    from app.services.auth_service import auth_service

    with patch(
        "app.services.auth_service.authentik_client.refresh_token",
        new_callable=AsyncMock,
        return_value=MOCK_TOKEN_RESPONSE,
    ):
        result = await auth_service.refresh(db, "old-refresh-token")

    assert result.access_token == "access-123"
