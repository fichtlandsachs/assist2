"""Security utilities: JWKS token validation and encryption helpers."""
import base64
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt as pyjwt
from cryptography.fernet import Fernet

from app.config import get_settings
from app.core.exceptions import UnauthorizedException

logger = logging.getLogger(__name__)

# ── JWKS cache ────────────────────────────────────────────────────────────────
_jwks_cache: Optional[dict] = None
_jwks_fetched_at: Optional[datetime] = None
_JWKS_TTL_SECONDS = 300  # 5 minutes


async def _fetch_jwks() -> dict:
    """Fetch JWKS from Authentik with in-process TTL cache."""
    global _jwks_cache, _jwks_fetched_at
    now = datetime.now(timezone.utc)
    if (
        _jwks_cache is not None
        and _jwks_fetched_at is not None
        and (now - _jwks_fetched_at).total_seconds() < _JWKS_TTL_SECONDS
    ):
        return _jwks_cache

    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(settings.AUTHENTIK_JWKS_URL)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_fetched_at = now
    return _jwks_cache


def _decode_jwt(token: str, jwks: dict) -> dict:
    """
    Decode and verify a JWT using keys from the provided JWKS dict.
    Uses pyjwt.PyJWK to parse each key, matching by `kid` header if present.
    """
    header = pyjwt.get_unverified_header(token)
    kid = header.get("kid")
    alg = header.get("alg", "RS256")

    settings = get_settings()
    for key_data in jwks.get("keys", []):
        if kid is None or key_data.get("kid") == kid:
            signing_key = pyjwt.PyJWK(key_data).key
            return pyjwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                audience=settings.AUTHENTIK_BACKEND_CLIENT_ID,
                options={"verify_exp": True},
            )

    raise pyjwt.InvalidKeyError("No matching key found in JWKS")


async def validate_authentik_token(token: str) -> dict:
    """
    Decode and validate an Authentik OIDC JWT via JWKS.
    Raises UnauthorizedException on invalid/expired tokens.
    """
    try:
        jwks = await _fetch_jwks()
        return _decode_jwt(token, jwks)
    except pyjwt.ExpiredSignatureError:
        raise UnauthorizedException(detail="Token has expired")
    except pyjwt.InvalidTokenError as e:
        logger.debug(f"Token validation failed: {e}")
        raise UnauthorizedException(detail="Could not validate credentials")


# ── Token hashing (kept for any future use) ───────────────────────────────────
def hash_token(token: str) -> str:
    """Create a SHA-256 hex hash of a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── Symmetric encryption (used for integration secrets) ───────────────────────
def get_fernet() -> Fernet:
    """Get a Fernet instance using the ENCRYPTION_KEY from settings."""
    settings = get_settings()
    key = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
    if len(key) != 32:
        raise ValueError("ENCRYPTION_KEY must be exactly 32 bytes when base64-decoded")
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)


def encrypt_value(value: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption."""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decrypt a Fernet-encrypted string value."""
    return get_fernet().decrypt(value.encode()).decode()


# ── Backward-compatibility stubs (removed in future tasks) ────────────────────
def hash_password(password: str) -> str:  # noqa: ARG001
    """Deprecated: auth is now handled by Authentik. (legacy — removed in Task 6)"""
    raise NotImplementedError("Password hashing moved to Authentik")


def verify_password(plain: str, hashed: str) -> bool:  # noqa: ARG001
    """Deprecated: auth is now handled by Authentik. (legacy — removed in Task 6)"""
    raise NotImplementedError("Password verification moved to Authentik")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a HS256 JWT access token. (legacy — to be removed)"""
    from datetime import datetime
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access", "iat": datetime.now(timezone.utc)})
    return pyjwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """Create a HS256 JWT refresh token. (legacy — to be removed)"""
    from datetime import datetime
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "iat": datetime.now(timezone.utc)})
    return pyjwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode a HS256 JWT. (legacy — to be removed)"""
    from datetime import datetime
    settings = get_settings()
    try:
        return pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError as e:
        raise UnauthorizedException(detail="Token has expired") from e
    except pyjwt.InvalidTokenError as e:
        raise UnauthorizedException(detail="Could not validate credentials") from e
