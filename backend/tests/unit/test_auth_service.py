"""Unit tests for AuthService — AuthentikClient is mocked."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.core.exceptions import UnauthorizedException


MOCK_TOKEN_RESPONSE = TokenResponse(
    access_token="access-123",
    refresh_token="refresh-456",
    token_type="bearer",
)


@pytest.mark.asyncio
async def test_login_success(db: AsyncSession):
    """login() calls AuthentikClient and returns tokens."""
    from app.services.auth_service import auth_service

    with patch(
        "app.services.auth_service.authentik_client.authenticate_user",
        new_callable=AsyncMock,
        return_value=MOCK_TOKEN_RESPONSE,
    ):
        result = await auth_service.login(db, LoginRequest(
            email="user@example.com", password="pass123"
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
        return_value="authentik-id-abc",
    ), patch(
        "app.services.auth_service.authentik_client.authenticate_user",
        new_callable=AsyncMock,
        return_value=MOCK_TOKEN_RESPONSE,
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
    assert user.authentik_id == "authentik-id-abc"


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
