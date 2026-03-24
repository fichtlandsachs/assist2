"""Integration tests for auth endpoints — AuthentikClient is mocked."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app.schemas.auth import TokenResponse

MOCK_TOKENS = TokenResponse(
    access_token="test-access-token",
    refresh_token="test-refresh-token",
    token_type="bearer",
)


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    with patch("app.services.auth_service.authentik_client.create_user",
               new_callable=AsyncMock, return_value="new-authentik-id"), \
         patch("app.services.auth_service.authentik_client.authenticate_user",
               new_callable=AsyncMock, return_value=MOCK_TOKENS):
        response = await client.post("/api/v1/auth/register", json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "display_name": "New User",
        })

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    with patch("app.services.auth_service.authentik_client.authenticate_user",
               new_callable=AsyncMock, return_value=MOCK_TOKENS):
        response = await client.post("/api/v1/auth/login", json={
            "email": "testuser@example.com",
            "password": "testpassword123",
        })

    assert response.status_code == 200
    assert response.json()["access_token"] == "test-access-token"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    from app.core.exceptions import UnauthorizedException
    with patch("app.services.auth_service.authentik_client.authenticate_user",
               new_callable=AsyncMock,
               side_effect=UnauthorizedException(detail="Invalid email or password")):
        response = await client.post("/api/v1/auth/login", json={
            "email": "user@example.com",
            "password": "wrong",
        })

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout_success(client: AsyncClient, auth_headers: dict):
    """Logout revokes token via Authentik and returns 204."""
    with patch("app.services.auth_service.authentik_client.revoke_token",
               new_callable=AsyncMock):
        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "some-refresh-token"},
            headers=auth_headers,
        )

    assert response.status_code == 204
