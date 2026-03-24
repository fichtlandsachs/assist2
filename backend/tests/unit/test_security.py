"""Unit tests for JWKS-based token validation."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt


def make_test_token(payload: dict, secret: str = "test-secret") -> str:
    """Create a test JWT signed with a symmetric key."""
    return pyjwt.encode(payload, secret, algorithm="HS256")


FAKE_JWKS = {"keys": [{"kty": "oct", "k": "dGVzdA", "alg": "HS256", "use": "sig"}]}


@pytest.mark.asyncio
async def test_validate_authentik_token_valid():
    """Valid token returns decoded payload; _fetch_jwks result is passed to _decode_jwt."""
    from app.core.security import validate_authentik_token
    from app.core.exceptions import UnauthorizedException

    payload = {
        "sub": "authentik-user-id-1",
        "email": "user@example.com",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    token = make_test_token(payload)

    with patch("app.core.security._fetch_jwks", new_callable=AsyncMock) as mock_jwks, \
         patch("app.core.security._decode_jwt") as mock_decode:
        mock_jwks.return_value = FAKE_JWKS
        mock_decode.return_value = payload
        result = await validate_authentik_token(token)

    mock_jwks.assert_called_once()
    mock_decode.assert_called_once_with(token, FAKE_JWKS)
    assert result["sub"] == "authentik-user-id-1"
    assert result["email"] == "user@example.com"


@pytest.mark.asyncio
async def test_validate_authentik_token_expired():
    """Expired token raises UnauthorizedException."""
    from app.core.security import validate_authentik_token
    from app.core.exceptions import UnauthorizedException

    with patch("app.core.security._fetch_jwks", new_callable=AsyncMock) as mock_jwks, \
         patch("app.core.security._decode_jwt") as mock_decode:
        mock_jwks.return_value = FAKE_JWKS
        mock_decode.side_effect = pyjwt.ExpiredSignatureError("Token expired")
        with pytest.raises(UnauthorizedException):
            await validate_authentik_token("expired.token.here")


@pytest.mark.asyncio
async def test_validate_authentik_token_invalid_signature():
    """Token with bad signature raises UnauthorizedException."""
    from app.core.security import validate_authentik_token
    from app.core.exceptions import UnauthorizedException

    with patch("app.core.security._fetch_jwks", new_callable=AsyncMock) as mock_jwks, \
         patch("app.core.security._decode_jwt") as mock_decode:
        mock_jwks.return_value = FAKE_JWKS
        mock_decode.side_effect = pyjwt.InvalidTokenError("Bad signature")
        with pytest.raises(UnauthorizedException):
            await validate_authentik_token("bad.token.here")


def test_hash_token_deterministic():
    """hash_token returns consistent SHA-256 hex string."""
    from app.core.security import hash_token
    result1 = hash_token("mytoken")
    result2 = hash_token("mytoken")
    assert result1 == result2
    assert len(result1) == 64  # SHA-256 hex = 64 chars


def test_encrypt_decrypt_roundtrip():
    """Encrypted value can be decrypted back to original."""
    from app.core.security import encrypt_value, decrypt_value
    from unittest.mock import patch, MagicMock
    from cryptography.fernet import Fernet
    import base64

    test_key = base64.urlsafe_b64encode(b"a" * 32).decode()
    mock_settings = MagicMock()
    mock_settings.ENCRYPTION_KEY = test_key

    with patch("app.core.security.get_settings", return_value=mock_settings):
        encrypted = encrypt_value("secret-value")
        decrypted = decrypt_value(encrypted)

    assert decrypted == "secret-value"
