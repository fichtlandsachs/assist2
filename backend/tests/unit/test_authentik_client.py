"""Unit tests for AuthentikClient — all httpx calls are mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.authentik_client import AuthentikClient
from app.schemas.auth import TokenResponse
from app.core.exceptions import UnauthorizedException, ConflictException


def make_mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_authenticate_user_success():
    """Login with correct credentials returns TokenResponse."""
    client = AuthentikClient()
    mock_response = make_mock_response(200, {
        "access_token": "test-access-token",
        "refresh_token": "test-refresh-token",
        "token_type": "bearer",
        "expires_in": 3600,
    })

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        result = await client.authenticate_user("user@example.com", "password123")

    assert result.access_token == "test-access-token"
    assert result.refresh_token == "test-refresh-token"


@pytest.mark.asyncio
async def test_authenticate_user_invalid_credentials():
    """Login with wrong credentials raises UnauthorizedException."""
    client = AuthentikClient()
    mock_response = make_mock_response(400, {"error": "invalid_grant"})

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        with pytest.raises(UnauthorizedException):
            await client.authenticate_user("user@example.com", "wrongpassword")


@pytest.mark.asyncio
async def test_create_user_success():
    """Creating a new user returns the Authentik user ID."""
    client = AuthentikClient()
    mock_response = make_mock_response(201, {"pk": "authentik-uuid-123"})
    mock_set_pw = AsyncMock()

    with patch("httpx.AsyncClient") as mock_http, \
         patch.object(client, "set_password", mock_set_pw):
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        authentik_id = await client.create_user(
            email="new@example.com",
            password="pass123",
            display_name="New User",
        )

    assert authentik_id == "authentik-uuid-123"
    mock_set_pw.assert_called_once_with("authentik-uuid-123", "pass123")


@pytest.mark.asyncio
async def test_create_user_conflict():
    """Creating a user that already exists raises ConflictException."""
    client = AuthentikClient()
    mock_response = make_mock_response(400, {"username": ["already exists"]})

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        with pytest.raises(ConflictException):
            await client.create_user("dup@example.com", "pass", "Dup")


@pytest.mark.asyncio
async def test_refresh_token_success():
    """Refresh token returns a new TokenResponse."""
    client = AuthentikClient()
    mock_response = make_mock_response(200, {
        "access_token": "new-access-token",
        "refresh_token": "new-refresh-token",
        "token_type": "bearer",
    })

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        result = await client.refresh_token("old-refresh-token")

    assert result.access_token == "new-access-token"


@pytest.mark.asyncio
async def test_get_user_by_email_found():
    """Returns user dict when found."""
    client = AuthentikClient()
    mock_response = make_mock_response(200, {
        "results": [{"pk": "uuid-1", "email": "found@example.com"}],
        "count": 1,
    })

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        user = await client.get_user_by_email("found@example.com")

    assert user is not None
    assert user["pk"] == "uuid-1"


@pytest.mark.asyncio
async def test_revoke_token_success():
    """revoke_token calls the revoke endpoint and returns None."""
    client = AuthentikClient()

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(200, {})
        )
        result = await client.revoke_token("some-token")

    assert result is None


@pytest.mark.asyncio
async def test_revoke_token_swallows_request_error():
    """revoke_token silently ignores httpx.RequestError (fire-and-forget)."""
    import httpx as _httpx
    client = AuthentikClient()

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=_httpx.RequestError("connection refused")
        )
        # Must not raise
        await client.revoke_token("some-token")


@pytest.mark.asyncio
async def test_get_user_by_email_not_found():
    """Returns None when no user found."""
    client = AuthentikClient()
    mock_response = make_mock_response(200, {"results": [], "count": 0})

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )
        user = await client.get_user_by_email("missing@example.com")

    assert user is None
