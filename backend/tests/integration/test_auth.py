"""Integration tests for authentication endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test that a new user can register and receives tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@example.com",
            "password": "securepassword123",
            "display_name": "New User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0
    assert len(data["refresh_token"]) > 0


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, test_user: User):
    """Test that registering with a duplicate email returns 409."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "testuser@example.com",
            "password": "anotherpassword123",
            "display_name": "Duplicate User",
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    """Test that registering with an invalid email returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "not-an-email",
            "password": "securepassword123",
            "display_name": "Test User",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    """Test that registering with a short password returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "valid@example.com",
            "password": "short",
            "display_name": "Test User",
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user: User):
    """Test that a user can login successfully and receives tokens."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user: User):
    """Test that login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """Test that login with non-existent user returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "somepassword123",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_case_insensitive_email(client: AsyncClient, test_user: User):
    """Test that login works with uppercase email."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "TESTUSER@EXAMPLE.COM",
            "password": "testpassword123",
        },
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, test_user: User):
    """Test that a valid refresh token produces a new token pair."""
    # First login to get tokens
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "testpassword123",
        },
    )
    assert login_response.status_code == 200
    tokens = login_response.json()

    # Use refresh token to get new tokens
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    new_tokens = refresh_response.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    # New tokens should be different from old ones
    assert new_tokens["access_token"] != tokens["access_token"]


@pytest.mark.asyncio
async def test_refresh_token_invalid(client: AsyncClient):
    """Test that an invalid refresh token returns 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.jwt.token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient, test_user: User):
    """Test that logout invalidates the session."""
    # Login first
    login_response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "testuser@example.com",
            "password": "testpassword123",
        },
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    # Logout
    logout_response = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=headers,
    )
    assert logout_response.status_code == 204

    # Try to use the same refresh token again (should fail)
    refresh_response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, test_user: User, auth_headers: dict):
    """Test that the authenticated user can retrieve their own profile."""
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "testuser@example.com"
    assert data["display_name"] == "Test User"
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_get_me_no_token(client: AsyncClient):
    """Test that accessing /auth/me without a token returns 403."""
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_me_invalid_token(client: AsyncClient):
    """Test that accessing /auth/me with invalid token returns 403."""
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"},
    )

    assert response.status_code in (401, 403)
