"""Atlassian OAuth token store — Redis-backed, Fernet-encrypted."""
import json
import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.core.exceptions import UnauthorizedException
from app.core.security import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

_REDIS_KEY = "atlassian_token:{user_id}"
_TIMEOUT = httpx.Timeout(10.0)


class AtlassianTokenStore:
    """
    Manages Atlassian API tokens in Redis with Fernet encryption.

    Redis key: atlassian_token:{user_id}
    TTL: expires_in + 300s (refresh buffer)
    Value: Fernet-encrypted JSON with access_token, refresh_token, cloud_id, expires_at
    """

    def _key(self, user_id) -> str:
        return _REDIS_KEY.format(user_id=user_id)

    async def _get_redis(self):
        import redis.asyncio as aioredis
        settings = get_settings()
        return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def save(
        self,
        user_id,
        access_token: str,
        refresh_token: str,
        expires_in: int,
        cloud_id: str,
    ) -> None:
        """Encrypt and persist token data with TTL."""
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        payload = json.dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "cloud_id": cloud_id,
            "expires_at": expires_at,
        })
        encrypted = encrypt_value(payload)
        ttl = expires_in + 300
        redis = await self._get_redis()
        await redis.setex(self._key(user_id), ttl, encrypted)

    async def get(self, user_id) -> dict | None:
        """Return decrypted token dict, or None if key missing."""
        redis = await self._get_redis()
        raw = await redis.get(self._key(user_id))
        if not raw:
            return None
        try:
            return json.loads(decrypt_value(raw))
        except Exception:
            logger.warning("Failed to decrypt Atlassian token for user %s", user_id)
            return None

    async def get_valid_token(self, user_id) -> str | None:
        """Return access_token, refreshing first if within 120s of expiry."""
        data = await self.get(user_id)
        if not data:
            return None
        now = datetime.now(timezone.utc).timestamp()
        if data["expires_at"] - now < 120:
            return await self._refresh(
                user_id,
                data["refresh_token"],
                data["cloud_id"],
            )
        return data["access_token"]

    async def _refresh(self, user_id, refresh_token: str, cloud_id: str) -> str:
        """Exchange refresh_token for new tokens. Raises 401 on failure."""
        settings = get_settings()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                "https://auth.atlassian.com/oauth/token",
                json={
                    "grant_type": "refresh_token",
                    "client_id": settings.ATLASSIAN_CLIENT_ID,
                    "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
                    "refresh_token": refresh_token,
                },
            )
        if resp.status_code in (400, 401):
            await self.delete(user_id)
            raise UnauthorizedException(detail="Atlassian session abgelaufen — bitte erneut anmelden")
        resp.raise_for_status()
        data = resp.json()
        await self.save(
            user_id,
            data["access_token"],
            data.get("refresh_token", refresh_token),
            data.get("expires_in", 3600),
            cloud_id,
        )
        return data["access_token"]

    async def delete(self, user_id) -> None:
        """Remove token from Redis."""
        redis = await self._get_redis()
        await redis.delete(self._key(user_id))


atlassian_token_store = AtlassianTokenStore()
