"""GitHub OAuth token store — Redis-backed, Fernet-encrypted.

GitHub OAuth Apps do not issue refresh tokens. Access tokens are long-lived and
only invalidated by the user revoking access in GitHub settings.
TTL in Redis: 30 days.
Token material is NEVER persisted to the database.
"""
import json
import logging

from app.config import get_settings
from app.core.security import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

_REDIS_KEY = "github_token:{user_id}"
_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class GitHubTokenStore:
    """
    Manages GitHub API tokens in Redis with Fernet encryption.

    Redis key: github_token:{user_id}
    TTL: 30 days
    Value: Fernet-encrypted JSON with access_token
    Token material is never written to the database.
    """

    def _key(self, user_id) -> str:
        return _REDIS_KEY.format(user_id=user_id)

    async def _get_redis(self):
        import redis.asyncio as aioredis
        settings = get_settings()
        return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    async def save(self, user_id, access_token: str) -> None:
        """Encrypt and persist access token with 30-day TTL."""
        payload = json.dumps({"access_token": access_token})
        encrypted = encrypt_value(payload)
        redis = await self._get_redis()
        await redis.setex(self._key(user_id), _TTL_SECONDS, encrypted)

    async def get(self, user_id) -> dict | None:
        """Return decrypted token dict, or None if key missing."""
        redis = await self._get_redis()
        raw = await redis.get(self._key(user_id))
        if not raw:
            return None
        try:
            return json.loads(decrypt_value(raw))
        except Exception:
            logger.warning("Failed to decrypt GitHub token for user %s", user_id)
            return None

    async def get_token(self, user_id) -> str | None:
        """Return access_token or None. GitHub tokens are long-lived — no refresh needed."""
        data = await self.get(user_id)
        if not data:
            return None
        return data.get("access_token")

    async def delete(self, user_id) -> None:
        """Remove token from Redis."""
        redis = await self._get_redis()
        await redis.delete(self._key(user_id))


github_token_store = GitHubTokenStore()
