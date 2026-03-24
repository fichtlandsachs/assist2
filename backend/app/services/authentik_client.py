"""HTTP client for Authentik IdP API calls."""
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings
from app.core.exceptions import ConflictException, UnauthorizedException
from app.schemas.auth import TokenResponse

logger = logging.getLogger(__name__)


class AuthentikClient:
    """Wraps all Authentik OIDC and admin API calls."""

    @property
    def _settings(self):
        return get_settings()

    @property
    def _token_url(self) -> str:
        return f"{self._settings.AUTHENTIK_URL}/application/o/{self._settings.AUTHENTIK_APP_SLUG}/token/"

    @property
    def _revoke_url(self) -> str:
        return f"{self._settings.AUTHENTIK_URL}/application/o/{self._settings.AUTHENTIK_APP_SLUG}/revoke/"

    @property
    def _users_url(self) -> str:
        return f"{self._settings.AUTHENTIK_URL}/api/v3/core/users/"

    @property
    def _api_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._settings.AUTHENTIK_API_TOKEN}",
            "Content-Type": "application/json",
        }

    async def authenticate_user(self, email: str, password: str) -> TokenResponse:
        """OIDC Resource Owner Password Credentials grant."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "password",
                    "username": email,
                    "password": password,
                    "client_id": self._settings.AUTHENTIK_BACKEND_CLIENT_ID,
                    "client_secret": self._settings.AUTHENTIK_BACKEND_CLIENT_SECRET,
                    "scope": "openid email profile",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code in (400, 401):
            raise UnauthorizedException(detail="Invalid email or password")
        resp.raise_for_status()

        data = resp.json()
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            token_type="bearer",
        )

    async def create_user(
        self, email: str, password: str, display_name: str
    ) -> str:
        """Create a user in Authentik. Returns the Authentik user UUID (pk)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._users_url,
                json={
                    "username": email,
                    "email": email,
                    "name": display_name,
                    "is_active": True,
                    "type": "internal",
                },
                headers=self._api_headers,
            )

        if resp.status_code == 400:
            raise ConflictException(detail="An account with this email already exists")
        resp.raise_for_status()

        user_data = resp.json()
        await self.set_password(user_data["pk"], password)
        return str(user_data["pk"])

    async def set_password(self, authentik_id: str, password: str) -> None:
        """Set password for an Authentik user."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._users_url}{authentik_id}/set_password/",
                json={"password": password},
                headers=self._api_headers,
            )
        if resp.status_code >= 400:
            raise UnauthorizedException(
                detail=f"Failed to set password for Authentik user {authentik_id}"
            )

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Exchange refresh token for a new token pair."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._settings.AUTHENTIK_BACKEND_CLIENT_ID,
                    "client_secret": self._settings.AUTHENTIK_BACKEND_CLIENT_SECRET,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if resp.status_code in (400, 401):
            raise UnauthorizedException(detail="Invalid or expired refresh token")
        resp.raise_for_status()

        data = resp.json()
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            token_type="bearer",
        )

    async def revoke_token(self, token: str) -> None:
        """Revoke an access or refresh token."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    self._revoke_url,
                    data={
                        "token": token,
                        "client_id": self._settings.AUTHENTIK_BACKEND_CLIENT_ID,
                        "client_secret": self._settings.AUTHENTIK_BACKEND_CLIENT_SECRET,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
        except httpx.RequestError as e:
            logger.warning(f"Failed to revoke token: {e}")

    async def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        """Find an Authentik user by email. Returns None if not found."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                self._users_url,
                params={"email": email, "type": "internal"},
                headers=self._api_headers,
            )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        return results[0] if results else None


authentik_client = AuthentikClient()
