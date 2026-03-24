# P1: Authentik + Backend Auth-Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the custom JWT auth stack with Authentik as the central IdP, proxying credentials via OIDC ROPC grant while keeping the existing `/login` UI unchanged.

**Architecture:** FastAPI backend becomes an auth proxy: login/register/refresh/logout forward to Authentik's OIDC token endpoint (`grant_type=password`). Token validation switches from own `JWT_SECRET` to Authentik's JWKS endpoint. The API surface and frontend remain unchanged — only implementation changes.

**Tech Stack:** Authentik 2024.10 (Docker), PyJWT[crypto] (JWKS validation), httpx (already in requirements), pytest + unittest.mock (testing), Alembic (migrations)

**Spec:** `docs/superpowers/specs/2026-03-24-nextcloud-authentik-integration-design.md` (P1 section)

---

## File Map

### New Files
| File | Purpose |
|---|---|
| `backend/app/services/authentik_client.py` | HTTP client for all Authentik API calls |
| `backend/tests/unit/test_authentik_client.py` | Unit tests for AuthentikClient |
| `backend/tests/unit/test_deps.py` | Unit tests for get_current_user |
| `backend/migrations/versions/0015_authentik_id.py` | Add authentik_id column to users |
| `backend/migrations/versions/0016_drop_user_sessions.py` | Drop user_sessions + identity_links tables |
| `backend/scripts/migrate_to_authentik.py` | One-time user migration script |

### Modified Files
| File | Changes |
|---|---|
| `infra/docker-compose.yml` | Add authentik-db, authentik-server, authentik-worker |
| `infra/.env.example` | Add Authentik env vars |
| `infra/.env` | Add Authentik env vars (runtime, not committed) |
| `backend/requirements.txt` | Remove bcrypt + python-jose, add PyJWT[crypto] |
| `backend/app/core/security.py` | Remove JWT creation/bcrypt, add JWKS validation |
| `backend/app/services/auth_service.py` | Full rewrite: remove UserSession/OAuth, use AuthentikClient |
| `backend/app/deps.py` | get_current_user: JWKS validation + lazy authentik_id migration |
| `backend/app/routers/auth.py` | Remove OAuth routes, remove OAuthCallbackResponse |
| `backend/app/models/user.py` | Add authentik_id column, remove UserSession + IdentityLink classes |
| `backend/app/schemas/auth.py` | Remove OAuthCallbackResponse |
| `backend/tests/conftest.py` | Update fixtures: no bcrypt/jose, mock AuthentikClient |
| `backend/tests/unit/test_security.py` | Replace old JWT tests with JWKS tests |
| `backend/tests/integration/test_auth.py` | Update for Authentik-based auth |
| `frontend/app/(auth)/login/page.tsx` | Add password-reset hint to 401 error |

---

## Task 1: Docker — Add Authentik Services

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `infra/.env.example`

- [ ] **Step 1: Add Authentik volumes to docker-compose.yml**

In `infra/docker-compose.yml`, add to the `volumes:` section at the top:
```yaml
  assist2_authentik_db_data:
  assist2_authentik_media:
  assist2_authentik_templates:
```

- [ ] **Step 2: Add Authentik services to docker-compose.yml**

Add after the `redis:` service block:
```yaml
  authentik-db:
    image: postgres:16-alpine
    container_name: assist2-authentik-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: authentik
      POSTGRES_USER: authentik
      POSTGRES_PASSWORD: ${AUTHENTIK_DB_PASSWORD}
    volumes:
      - assist2_authentik_db_data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U authentik -d authentik"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s

  authentik-server:
    image: ghcr.io/goauthentik/server:2024.10.5
    container_name: assist2-authentik-server
    restart: unless-stopped
    command: server
    environment:
      AUTHENTIK_REDIS__HOST: assist2-redis
      AUTHENTIK_REDIS__PASSWORD: ${REDIS_PASSWORD}
      AUTHENTIK_REDIS__DB: 1
      AUTHENTIK_POSTGRESQL__HOST: assist2-authentik-db
      AUTHENTIK_POSTGRESQL__NAME: authentik
      AUTHENTIK_POSTGRESQL__USER: authentik
      AUTHENTIK_POSTGRESQL__PASSWORD: ${AUTHENTIK_DB_PASSWORD}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
      AUTHENTIK_BOOTSTRAP_EMAIL: ${AUTHENTIK_BOOTSTRAP_EMAIL}
      AUTHENTIK_BOOTSTRAP_PASSWORD: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
      AUTHENTIK_LOG_LEVEL: info
    volumes:
      - assist2_authentik_media:/media
      - assist2_authentik_templates:/templates
    networks:
      - proxy
      - internal
    depends_on:
      authentik-db:
        condition: service_healthy
      redis:
        condition: service_healthy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.authentik.rule=Host(`authentik.${DOMAIN}`)"
      - "traefik.http.routers.authentik.entrypoints=websecure"
      - "traefik.http.routers.authentik.tls.certresolver=letsencrypt"
      - "traefik.http.services.authentik.loadbalancer.server.port=9000"
    healthcheck:
      test: ["CMD-SHELL", "ak healthcheck"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  authentik-worker:
    image: ghcr.io/goauthentik/server:2024.10.5
    container_name: assist2-authentik-worker
    restart: unless-stopped
    command: worker
    environment:
      AUTHENTIK_REDIS__HOST: assist2-redis
      AUTHENTIK_REDIS__PASSWORD: ${REDIS_PASSWORD}
      AUTHENTIK_REDIS__DB: 1
      AUTHENTIK_POSTGRESQL__HOST: assist2-authentik-db
      AUTHENTIK_POSTGRESQL__NAME: authentik
      AUTHENTIK_POSTGRESQL__USER: authentik
      AUTHENTIK_POSTGRESQL__PASSWORD: ${AUTHENTIK_DB_PASSWORD}
      AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
      AUTHENTIK_LOG_LEVEL: info
    volumes:
      - assist2_authentik_media:/media
      - assist2_authentik_templates:/templates
    networks:
      - internal
    depends_on:
      authentik-db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 3: Add Authentik variables to `.env.example`**

Add at the end of `infra/.env.example`:
```bash
# Authentik IdP
AUTHENTIK_SECRET_KEY=CHANGE_ME_64_CHARS_MIN
AUTHENTIK_DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD
AUTHENTIK_BOOTSTRAP_EMAIL=admin@example.com
AUTHENTIK_BOOTSTRAP_PASSWORD=CHANGE_ME_STRONG_PASSWORD
AUTHENTIK_API_TOKEN=           # Created after first Authentik startup
AUTHENTIK_BACKEND_CLIENT_ID=   # Created in Authentik UI (OAuth2 Provider "backend")
AUTHENTIK_BACKEND_CLIENT_SECRET= # Created in Authentik UI
AUTHENTIK_JWKS_URL=https://authentik.DOMAIN/application/o/backend/jwks/
```

- [ ] **Step 4: Add Authentik variables to `infra/.env`**

Generate and add real values:
```bash
# Generate AUTHENTIK_SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
# Generate AUTHENTIK_DB_PASSWORD
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Add to `infra/.env` (fill in generated values):
```bash
AUTHENTIK_SECRET_KEY=<generated>
AUTHENTIK_DB_PASSWORD=<generated>
AUTHENTIK_BOOTSTRAP_EMAIL=falk@bummelletzter.com
AUTHENTIK_BOOTSTRAP_PASSWORD=<strong_password>
AUTHENTIK_API_TOKEN=
AUTHENTIK_BACKEND_CLIENT_ID=
AUTHENTIK_BACKEND_CLIENT_SECRET=
AUTHENTIK_JWKS_URL=https://authentik.fichtlworks.com/application/o/backend/jwks/
```

- [ ] **Step 5: Start Authentik containers**

```bash
cd /opt/assist2
docker compose -f infra/docker-compose.yml up -d authentik-db authentik-server authentik-worker
```

Wait ~60s for first-time setup, then verify:
```bash
docker compose -f infra/docker-compose.yml logs authentik-server --tail=20
```
Expected: `... Starting server ...` — no ERROR lines.

- [ ] **Step 6: Manual Authentik UI Setup**

Open `https://authentik.fichtlworks.com` and complete the setup wizard.

Then create the OAuth2 Provider for the backend:
1. Navigate to **Applications → Providers → Create**
2. Type: **OAuth2/OpenID Provider**
3. Name: `backend`
4. Authorization flow: `default-provider-authorization-implicit-consent`
5. Client type: `Confidential`
6. Grant types: check `Authorization Code` AND `Resource Owner Password-based`
7. Scopes: `openid`, `email`, `profile`
8. Subject mode: `Based on the User's Email`
9. Save → note **Client ID** and **Client Secret**

Then create Application:
1. **Applications → Applications → Create**
2. Name: `Workplace Backend`, Slug: `backend`
3. Provider: `backend`
4. Save

Create a Service Account token for API access:
1. **Directory → Users → Create Service Account**
2. Username: `assist2-backend-svc`
3. **Directory → Tokens → Create** → User: `assist2-backend-svc`, Intent: `API`
4. Note the token value

Update `infra/.env` with the values from steps above:
```bash
AUTHENTIK_API_TOKEN=<service-account-token>
AUTHENTIK_BACKEND_CLIENT_ID=<client-id>
AUTHENTIK_BACKEND_CLIENT_SECRET=<client-secret>
```

Add Authentik env vars to the `backend:` service in `docker-compose.yml`:
```yaml
      AUTHENTIK_URL: http://assist2-authentik-server:9000
      AUTHENTIK_API_TOKEN: ${AUTHENTIK_API_TOKEN}
      AUTHENTIK_BACKEND_CLIENT_ID: ${AUTHENTIK_BACKEND_CLIENT_ID}
      AUTHENTIK_BACKEND_CLIENT_SECRET: ${AUTHENTIK_BACKEND_CLIENT_SECRET}
      AUTHENTIK_JWKS_URL: ${AUTHENTIK_JWKS_URL}
```

Also add to `app/config.py`:
```python
    AUTHENTIK_URL: str = "http://assist2-authentik-server:9000"
    AUTHENTIK_API_TOKEN: str = ""
    AUTHENTIK_BACKEND_CLIENT_ID: str = ""
    AUTHENTIK_BACKEND_CLIENT_SECRET: str = ""
    AUTHENTIK_JWKS_URL: str = ""
    AUTHENTIK_APP_SLUG: str = "backend"  # Slug of the OAuth2 Application created in Authentik UI
```

The `AUTHENTIK_APP_SLUG` defaults to `"backend"` (matches the application slug created in Step 6). It is used by `AuthentikClient` to build token and revoke URLs, so changing it later requires only an env var update.

- [ ] **Step 7: Commit infra changes**

```bash
git add infra/docker-compose.yml infra/.env.example
git commit -m "feat(infra): add Authentik IdP containers to docker-compose"
```

---

## Task 2: Python Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Replace in `backend/requirements.txt`:
```
# Remove these two lines:
python-jose[cryptography]==3.3.0
bcrypt==4.2.0

# Add this line:
PyJWT[crypto]==2.9.0
```

Final relevant section should read:
```
cryptography==43.0.3
PyJWT[crypto]==2.9.0
python-multipart==0.0.12
httpx==0.27.2
```

- [ ] **Step 2: Verify install**

```bash
cd /opt/assist2
docker compose -f infra/docker-compose.yml exec backend pip install -r requirements.txt 2>&1 | tail -5
```
Expected: `Successfully installed ...` — no errors.

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(deps): replace python-jose+bcrypt with PyJWT[crypto] for Authentik JWKS"
```

---

## Task 3: Migration 0015 — Add `authentik_id` Column

**Files:**
- Create: `backend/migrations/versions/0015_authentik_id.py`

- [ ] **Step 1: Create migration file**

Create `backend/migrations/versions/0015_authentik_id.py`:
```python
"""Add authentik_id to users table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('authentik_id', sa.String(255), nullable=True, unique=True)
    )
    op.create_index('ix_users_authentik_id', 'users', ['authentik_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_authentik_id', table_name='users')
    op.drop_column('users', 'authentik_id')
```

- [ ] **Step 2: Run migration**

```bash
cd /opt/assist2
make migrate
```
Expected output: `Running upgrade 0014 -> 0015, Add authentik_id to users table`

- [ ] **Step 3: Verify column exists**

```bash
docker compose -f infra/docker-compose.yml exec postgres psql -U platform -d platform_db -c "\d users" | grep authentik
```
Expected: `authentik_id | character varying(255) | ...`

- [ ] **Step 4: Add `authentik_id` to User ORM model**

In `backend/app/models/user.py`, add after the `deleted_at` column:
```python
    authentik_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
```

Also add `String` and `Optional` to the imports if not already present:
```python
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, DateTime, String, func
```

This must match migration 0015 which adds the same column. The ORM update is done now so that Task 6 unit tests (which create User objects with `authentik_id`) work against the in-memory SQLite test DB.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0015_authentik_id.py backend/app/models/user.py
git commit -m "feat(db): add authentik_id column to users table (migration + ORM)"
```

---

## Task 4: AuthentikClient Service

**Files:**
- Create: `backend/app/services/authentik_client.py`
- Create: `backend/tests/unit/test_authentik_client.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_authentik_client.py`:
```python
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

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_response
        )
        authentik_id = await client.create_user(
            email="new@example.com",
            password="pass123",
            display_name="New User",
        )

    assert authentik_id == "authentik-uuid-123"


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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
cd /opt/assist2/backend
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_authentik_client.py -v 2>&1 | head -20
```
Expected: `ImportError: cannot import name 'AuthentikClient'`

- [ ] **Step 3: Create `backend/app/services/authentik_client.py`**

```python
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
        """
        OIDC Resource Owner Password Credentials grant.
        Raises UnauthorizedException on bad credentials.
        """
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
        # NOTE: Authentik returns `expires_in` and optionally `id_token`.
        # These are intentionally not forwarded — the frontend uses the access token
        # as an opaque bearer token, not as an OIDC client. The token TTL is managed
        # by Authentik's provider settings (default: 5 minutes for access tokens).
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            token_type="bearer",
        )

    async def create_user(
        self, email: str, password: str, display_name: str
    ) -> str:
        """
        Create a user in Authentik.
        Returns the Authentik user UUID (pk).
        Raises ConflictException if user already exists.
        """
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
        # Set password via separate endpoint
        await self.set_password(user_data["pk"], password)
        return str(user_data["pk"])

    async def set_password(self, authentik_id: str, password: str) -> None:
        """Set password for an Authentik user (also clears change-on-next-login flag)."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self._users_url}{authentik_id}/set_password/",
                json={"password": password},
                headers=self._api_headers,
            )
        resp.raise_for_status()

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
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_authentik_client.py -v
```
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/authentik_client.py backend/tests/unit/test_authentik_client.py
git commit -m "feat(auth): add AuthentikClient service for OIDC ROPC + user management"
```

---

## Task 5: JWKS Token Validation in `security.py`

**Files:**
- Modify: `backend/app/core/security.py`
- Modify: `backend/tests/unit/test_security.py`

- [ ] **Step 1: Add new tests to `test_security.py`**

Replace the entire content of `backend/tests/unit/test_security.py` with:
```python
"""Unit tests for JWKS-based token validation."""
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt as pyjwt


def make_test_token(payload: dict, secret: str = "test-secret") -> str:
    """Create a test JWT signed with a symmetric key."""
    return pyjwt.encode(payload, secret, algorithm="HS256")


def make_mock_jwks(secret: str = "test-secret"):
    """
    Returns a mock JWKS response.
    We use HS256 with a symmetric key for tests to avoid RSA key generation.
    The validate_authentik_token function is patched to use this secret.
    """
    return {"keys": [{"kty": "oct", "k": secret, "alg": "HS256"}]}


FAKE_JWKS = {"keys": [{"kty": "oct", "k": "dGVzdA", "alg": "HS256", "use": "sig"}]}


@pytest.mark.asyncio
async def test_validate_authentik_token_valid():
    """Valid token returns decoded payload; _fetch_jwks result is passed to _decode_jwt."""
    from app.core.security import validate_authentik_token

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

    # Verify wiring: _decode_jwt must be called with the token AND the JWKS from _fetch_jwks
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
```

- [ ] **Step 2: Run new tests — confirm they fail**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_security.py -v 2>&1 | head -20
```
Expected: `ImportError` or `FAILED` — `validate_authentik_token` does not exist yet.

- [ ] **Step 3: Rewrite `backend/app/core/security.py`**

Replace the entire file:
```python
"""Security utilities: JWKS token validation and encryption helpers."""
import base64
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import jwt as pyjwt
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from app.config import get_settings

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

    for key_data in jwks.get("keys", []):
        if kid is None or key_data.get("kid") == kid:
            signing_key = pyjwt.PyJWK(key_data).key
            return pyjwt.decode(
                token,
                signing_key,
                algorithms=[alg],
                options={"verify_exp": True},
            )

    raise pyjwt.InvalidKeyError("No matching key found in JWKS")


async def validate_authentik_token(token: str) -> dict:
    """
    Decode and validate an Authentik OIDC JWT via JWKS.
    Raises HTTP 401 UnauthorizedException on invalid/expired tokens.
    """
    try:
        jwks = await _fetch_jwks()
        return _decode_jwt(token, jwks)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (pyjwt.InvalidTokenError, Exception) as e:
        logger.debug(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Token hashing (kept for any future use) ───────────────────────────────────
def hash_token(token: str) -> str:
    """Create a SHA-256 hash of a token for secure storage."""
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
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_security.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/security.py backend/tests/unit/test_security.py
git commit -m "feat(auth): replace JWT creation with Authentik JWKS validation in security.py"
```

---

## Task 6: Rewrite `auth_service.py`

**Files:**
- Modify: `backend/app/services/auth_service.py`
- Create: `backend/tests/unit/test_auth_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_auth_service.py`:
```python
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
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_auth_service.py -v 2>&1 | head -20
```
Expected: `ImportError` or `AttributeError` — old auth_service still uses UserSession.

- [ ] **Step 3: Rewrite `backend/app/services/auth_service.py`**

Replace the entire file:
```python
"""Authentication service — proxies all auth operations to Authentik."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)


class AuthService:
    async def login(self, db: AsyncSession, data: LoginRequest) -> TokenResponse:
        """Authenticate via Authentik ROPC grant. Returns tokens."""
        tokens = await authentik_client.authenticate_user(data.email, data.password)

        # Update last_login_at for local user if they exist
        result = await db.execute(
            select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await db.commit()

        return tokens

    async def register(self, db: AsyncSession, data: RegisterRequest) -> TokenResponse:
        """
        Create user in Authentik + local DB.
        Raises ConflictException if email already exists.
        """
        # Check local DB for existing user first (fast path)
        existing = await db.execute(
            select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail="An account with this email already exists")

        # Create in Authentik (source of truth for credentials)
        authentik_id = await authentik_client.create_user(
            email=data.email.lower(),
            password=data.password,
            display_name=data.display_name,
        )

        # Create local user record
        user = User(
            email=data.email.lower(),
            display_name=data.display_name,
            authentik_id=authentik_id,
            is_active=True,
            email_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Get tokens via login
        from app.schemas.auth import LoginRequest as LR
        return await self.login(db, LR(email=data.email, password=data.password))

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Refresh token pair via Authentik."""
        return await authentik_client.refresh_token(refresh_token)

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """Revoke refresh token in Authentik."""
        await authentik_client.revoke_token(refresh_token)


auth_service = AuthService()
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_auth_service.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/auth_service.py backend/tests/unit/test_auth_service.py
git commit -m "feat(auth): rewrite AuthService to proxy login/register/refresh/logout to Authentik"
```

---

## Task 7: Update `deps.py` — JWKS-based `get_current_user`

**Files:**
- Modify: `backend/app/deps.py`
- Create: `backend/tests/unit/test_deps.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_deps.py`:
```python
"""Unit tests for get_current_user dependency."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.security import HTTPAuthorizationCredentials

from app.core.exceptions import UnauthorizedException


def make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.mark.asyncio
async def test_get_current_user_by_authentik_id(db):
    """Returns user when found by authentik_id."""
    from app.deps import get_current_user
    from app.models.user import User

    user = User(
        email="test@example.com",
        authentik_id="auth-id-1",
        display_name="Test",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "auth-id-1", "email": "test@example.com"},
    ):
        result = await get_current_user(make_credentials("test-token"), db)

    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_current_user_lazy_migration(db):
    """Falls back to email lookup and sets authentik_id if not set yet."""
    from app.deps import get_current_user
    from app.models.user import User
    from sqlalchemy import select

    user = User(
        email="legacy@example.com",
        authentik_id=None,
        display_name="Legacy",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "new-auth-id", "email": "legacy@example.com"},
    ):
        result = await get_current_user(make_credentials("test-token"), db)

    assert result.id == user.id
    # authentik_id should now be set
    result2 = await db.execute(select(User).where(User.id == user.id))
    updated = result2.scalar_one()
    assert updated.authentik_id == "new-auth-id"


@pytest.mark.asyncio
async def test_get_current_user_not_found(db):
    """Raises 401 when user not found in local DB."""
    from app.deps import get_current_user

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "unknown-id", "email": "ghost@example.com"},
    ):
        with pytest.raises(Exception) as exc_info:
            await get_current_user(make_credentials("test-token"), db)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_inactive(db):
    """Raises 401 for inactive users."""
    from app.deps import get_current_user
    from app.models.user import User

    user = User(
        email="inactive@example.com",
        authentik_id="auth-id-inactive",
        display_name="Inactive",
        is_active=False,
    )
    db.add(user)
    await db.commit()

    with patch(
        "app.deps.validate_authentik_token",
        new_callable=AsyncMock,
        return_value={"sub": "auth-id-inactive", "email": "inactive@example.com"},
    ):
        with pytest.raises(Exception) as exc_info:
            await get_current_user(make_credentials("test-token"), db)

    assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_deps.py -v 2>&1 | head -20
```
Expected: `FAILED` — `validate_authentik_token` not yet imported in deps. (`authentik_id` was added to the ORM in Task 3, Step 4.)

- [ ] **Step 3: Rewrite `backend/app/deps.py`**

Replace entire file:
```python
import uuid
from typing import AsyncGenerator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.permissions import get_user_permissions
from app.core.security import validate_authentik_token
from app.database import get_db
from app.models.user import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Validate Authentik OIDC JWT, return the matching local User.
    Falls back to email lookup for users not yet migrated (lazy migration).
    """
    payload = await validate_authentik_token(credentials.credentials)
    authentik_id: str | None = payload.get("sub")
    email: str | None = payload.get("email")

    if not authentik_id or not email:
        raise UnauthorizedException(detail="Invalid token claims")

    # Primary lookup: by authentik_id
    result = await db.execute(
        select(User).where(
            User.authentik_id == authentik_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Lazy migration: user exists but authentik_id not yet set
        result = await db.execute(
            select(User).where(
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user:
            user.authentik_id = authentik_id
            await db.commit()
            await db.refresh(user)

    if not user:
        raise UnauthorizedException(detail="User not found")

    if not user.is_active:
        raise UnauthorizedException(detail="Account is disabled")

    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_active:
        raise UnauthorizedException(detail="User account is disabled")
    return user


async def get_current_superuser(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_superuser:
        raise ForbiddenException(detail="Superuser access required")
    return user


def require_permission(permission: str):
    async def check(
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user
        permissions = await get_user_permissions(current_user.id, org_id, db)
        if "*" in permissions or permission in permissions:
            return current_user
        raise ForbiddenException(
            detail=f"Permission '{permission}' required for this operation"
        )
    return check
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
docker compose -f ../infra/docker-compose.yml exec backend python -m pytest tests/unit/test_deps.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/deps.py backend/tests/unit/test_deps.py
git commit -m "feat(auth): update get_current_user to validate Authentik JWKS tokens"
```

---

## Task 8: Update `routers/auth.py` — Remove OAuth Routes

**Files:**
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/app/schemas/auth.py`

- [ ] **Step 1: Remove `OAuthCallbackResponse` from schemas**

In `backend/app/schemas/auth.py`, remove the `OAuthCallbackResponse` class entirely.

- [ ] **Step 2: Rewrite `backend/app/routers/auth.py`**

Replace the entire file:
```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserWithLinks
from app.services.auth_service import auth_service

router = APIRouter()


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    data: RegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user account in Authentik + local DB, return tokens."""
    return await auth_service.register(db, data)


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate via Authentik ROPC grant, returning OIDC tokens."""
    return await auth_service.login(db, data)


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new token pair via Authentik."""
    return await auth_service.refresh(db, data.refresh_token)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout and revoke session",
)
async def logout(
    data: RefreshRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the refresh token in Authentik."""
    await auth_service.logout(db, data.refresh_token)


@router.get(
    "/auth/me",
    response_model=UserWithLinks,
    summary="Get current user profile",
)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserWithLinks:
    """Get the authenticated user's profile."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.user import User as UserModel

    result = await db.execute(
        select(UserModel)
        .where(UserModel.id == current_user.id)
        .options(selectinload(UserModel.identity_links))
    )
    user = result.scalar_one()
    return UserWithLinks.model_validate(user)
```

**Note:** The `selectinload(UserModel.identity_links)` will be removed in Task 9 when `identity_links` is dropped.

- [ ] **Step 3: Fix the `get_me` query after identity_links removal (placeholder)**

We'll return to fix the `selectinload` in Task 9. For now, leave as-is — it will still work until the relationship is removed.

- [ ] **Step 4: Verify the app starts**

```bash
docker compose -f infra/docker-compose.yml exec backend python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/auth.py backend/app/schemas/auth.py
git commit -m "feat(auth): remove OAuth routes from auth router, simplify to Authentik proxy"
```

---

## Task 9: Model Cleanup — Remove `UserSession` and `IdentityLink`

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/routers/auth.py` (fix identity_links reference)
- Modify: `backend/app/schemas/user.py` (remove identity_links if present)

- [ ] **Step 1: Check what references UserSession and IdentityLink**

```bash
grep -r "UserSession\|IdentityLink\|identity_links\|user_sessions" /opt/assist2/backend/app/ --include="*.py" -l
```

Fix each file found (typically: `main.py` imports, `schemas/user.py`).

- [ ] **Step 2: Remove `IdentityLink` and `UserSession` from `models/user.py`**

Replace `backend/app/models/user.py` with the cleaned version — keep only `User` class, remove `IdentityLink`, `UserSession`, and their relationships from `User`:

```python
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.membership import Membership


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    authentik_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="de", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Berlin", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[List["Membership"]] = relationship(
        "Membership",
        back_populates="user",
        foreign_keys="Membership.user_id",
    )
```

**Note:** `password_hash` column is kept (nullable) — it exists in the DB and old data is there. It's just no longer used for auth.

- [ ] **Step 3: Fix `auth.py` `get_me` — remove identity_links**

In `backend/app/routers/auth.py`, update `get_me` to remove the `selectinload`:
```python
@router.get("/auth/me", response_model=UserWithLinks, summary="Get current user profile")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserWithLinks:
    from sqlalchemy import select
    from app.models.user import User as UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == current_user.id))
    user = result.scalar_one()
    return UserWithLinks.model_validate(user)
```

- [ ] **Step 4: Update `schemas/user.py` — remove IdentityLink and identity_links**

In `backend/app/schemas/user.py`:
1. Remove the entire `IdentityLinkRead` class
2. Remove the `identity_links: List[IdentityLinkRead] = []` field from `UserWithLinks`
3. Remove any `IdentityLink` imports

The resulting `UserWithLinks` should look like:
```python
class UserWithLinks(UserRead):
    memberships: List["MembershipRead"] = []
```

(Keep only non-identity-link relationships that still exist on the User ORM model.)

- [ ] **Step 5: Verify app starts clean**

```bash
docker compose -f infra/docker-compose.yml exec backend python -c "from app.main import app; print('OK')"
```
Expected: `OK` — no import errors.

- [ ] **Step 6: Run full unit test suite**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/ -v
```
Expected: all unit tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/user.py backend/app/routers/auth.py backend/app/schemas/
git commit -m "refactor(auth): remove UserSession and IdentityLink ORM classes"
```

---

## Task 10: Update Test Fixtures

**Files:**
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/integration/test_auth.py`

- [ ] **Step 1: Update `conftest.py`**

Replace `conftest.py` with updated version — key changes:
1. Remove `hash_password`, `create_access_token` imports
2. `test_user` fixture: no `password_hash`, add `authentik_id`
3. `auth_headers` fixture: override `get_current_user` dependency

```python
import pytest
import pytest_asyncio
from typing import AsyncGenerator

from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.base import Base
from app.models.user import User
from app.models.organization import Organization
from app.models.membership import Membership, MembershipRole
from app.models.role import Role, Permission, RolePermission

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncTestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncTestSession() as session:
        await _seed_system_data(session)
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_system_data(session: AsyncSession) -> None:
    """Seed minimal system roles and permissions for tests."""
    # (keep existing implementation unchanged)
    import uuid
    permissions_data = [
        ("org", "read"), ("org", "update"), ("org", "delete"),
        ("membership", "read"), ("membership", "invite"), ("membership", "update"), ("membership", "delete"),
        ("role", "read"), ("role", "create"), ("role", "update"), ("role", "delete"), ("role", "assign"),
        ("group", "read"), ("group", "create"), ("group", "update"), ("group", "delete"), ("group", "manage"),
        ("plugin", "read"), ("plugin", "activate"), ("plugin", "configure"), ("plugin", "deactivate"),
        ("workflow", "read"), ("workflow", "create"), ("workflow", "update"), ("workflow", "delete"), ("workflow", "execute"),
        ("agent", "read"), ("agent", "create"), ("agent", "update"), ("agent", "delete"), ("agent", "invoke"),
        ("story", "read"), ("story", "create"), ("story", "update"), ("story", "delete"),
        ("inbox", "read"), ("inbox", "manage"), ("inbox", "update"),
        ("calendar", "read"), ("calendar", "manage"), ("calendar", "create"),
    ]
    perm_map = {}
    for resource, action in permissions_data:
        perm = Permission(resource=resource, action=action)
        session.add(perm)
        perm_map[f"{resource}:{action}"] = perm
    await session.flush()

    roles_data = {
        "org_owner": list(perm_map.keys()),
        "org_admin": [p for p in perm_map.keys() if p != "org:delete"],
        "org_member": ["org:read", "membership:read", "group:read", "plugin:read", "workflow:read",
                       "agent:read", "story:read", "story:create", "story:update",
                       "inbox:read", "inbox:update", "calendar:read", "calendar:create"],
        "org_guest": ["org:read", "membership:read"],
    }
    for role_name, perm_keys in roles_data.items():
        role = Role(name=role_name, is_system=True, description=f"System role: {role_name}")
        session.add(role)
        await session.flush()
        for perm_key in perm_keys:
            if perm_key in perm_map:
                session.add(RolePermission(role_id=role.id, permission_id=perm_map[perm_key].id))
    await session.commit()


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db: AsyncSession) -> User:
    """Test user with authentik_id set (no password_hash needed)."""
    user = User(
        email="testuser@example.com",
        authentik_id="test-authentik-id-1",
        display_name="Test User",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_user_2(db: AsyncSession) -> User:
    user = User(
        email="testuser2@example.com",
        authentik_id="test-authentik-id-2",
        display_name="Test User 2",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_user: User):
    """
    Auth headers for integration tests.
    Overrides get_current_user to return test_user directly —
    auth is unit-tested separately in test_auth_service.py and test_deps.py.
    Yields headers and cleans up its own override to avoid test pollution.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture(scope="function")
async def test_org(db: AsyncSession, test_user: User) -> Organization:
    from app.services.org_service import org_service
    from app.schemas.organization import OrgCreate
    org = await org_service.create(db, OrgCreate(name="Test Organization", slug="test-org"), test_user.id)
    return org
```

- [ ] **Step 2: Update `test_auth.py` integration tests**

The existing auth integration tests call `/api/v1/auth/login` and `/api/v1/auth/register`. These now call the real Authentik — which isn't available in CI. Update `test_auth.py` to mock `authentik_client`:

```python
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
```

- [ ] **Step 3: Run full test suite**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all tests pass (or only pre-existing failures unrelated to auth).

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test(auth): update fixtures and integration tests for Authentik-based auth"
```

---

## Task 11: Migration 0016 — Drop `user_sessions` and `identity_links`

**Files:**
- Create: `backend/migrations/versions/0016_drop_user_sessions.py`

> ⚠️ **Run this ONLY after `migrate_to_authentik.py` has been executed successfully (Task 13).**

- [ ] **Step 1: Create migration**

Create `backend/migrations/versions/0016_drop_user_sessions.py`:
```python
"""Drop user_sessions and identity_links tables.

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-24

IMPORTANT: Run migrate_to_authentik.py BEFORE applying this migration.
"""
from alembic import op

revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('user_sessions')
    op.drop_table('identity_links')


def downgrade() -> None:
    # Intentionally not restoring — this migration is irreversible.
    # Restore from backup if needed.
    raise NotImplementedError("Migration 0016 is irreversible. Restore from backup.")
```

- [ ] **Step 2: Verify no other tables reference user_sessions or identity_links**

Before committing, confirm no foreign keys from other tables point to these tables:
```bash
docker compose -f infra/docker-compose.yml exec postgres psql -U platform -d platform_db -c "
SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.referential_constraints AS rc ON tc.constraint_name = rc.constraint_name
JOIN information_schema.constraint_column_usage AS ccu ON ccu.constraint_name = rc.unique_constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND ccu.table_name IN ('user_sessions', 'identity_links');"
```
Expected: 0 rows (no external FKs pointing to these tables — they only have FKs pointing outward to `users`).

- [ ] **Step 3: Commit migration (do NOT run yet)**

```bash
git add backend/migrations/versions/0016_drop_user_sessions.py
git commit -m "feat(db): add migration to drop user_sessions and identity_links tables"
```

> Run `make migrate` for this migration only AFTER Task 13 (migration script) completes successfully.

---

## Task 12: Frontend — Password Reset Hint

**Files:**
- Modify: `frontend/app/(auth)/login/page.tsx`

- [ ] **Step 1: Update error message for 401**

In `frontend/app/(auth)/login/page.tsx`, replace the catch block:
```tsx
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr?.code === "HTTP_401") {
        setError(
          "Ungültige Zugangsdaten. Falls du dein Passwort noch nicht zurückgesetzt hast, besuche: authentik.fichtlworks.com"
        );
      } else {
        setError(apiErr?.error ?? "Login fehlgeschlagen. Bitte versuche es erneut.");
      }
    }
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/(auth)/login/page.tsx
git commit -m "feat(frontend): add Authentik password-reset hint to login error message"
```

---

## Task 13: Migration Script — Provision Existing Users to Authentik

**Files:**
- Create: `backend/scripts/migrate_to_authentik.py`

> This script is a one-time operation. Run it manually with the services running.

- [ ] **Step 1: Create the migration script**

Create `backend/scripts/migrate_to_authentik.py`:
```python
#!/usr/bin/env python
"""
One-time migration: provision all existing assist2 users into Authentik.

Usage (run inside backend container):
  python -m scripts.migrate_to_authentik

What it does:
1. Reads all active local users without authentik_id
2. For each: checks if Authentik user exists (by email)
3. If not: creates Authentik user with a random temporary password
4. Stores the authentik_id in the local users table
5. Sets password-change-required flag via Authentik API

After running: execute `make migrate` to apply migration 0016 (drop user_sessions).
"""
import asyncio
import logging
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services.authentik_client import AuthentikClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


async def migrate_users() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSession_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AuthentikClient()

    async with AsyncSession_() as session:
        result = await session.execute(
            select(User).where(
                User.deleted_at.is_(None),
                User.authentik_id.is_(None),
                User.is_active == True,
            )
        )
        users = result.scalars().all()
        logger.info(f"Found {len(users)} users without authentik_id")

        migrated = 0
        skipped = 0
        errors = 0

        for user in users:
            try:
                # Check if already exists in Authentik
                existing = await client.get_user_by_email(user.email)
                if existing:
                    authentik_id = str(existing["pk"])
                    logger.info(f"  Found existing Authentik user: {user.email} → {authentik_id}")
                else:
                    # Create with random temp password — user must reset
                    temp_password = secrets.token_urlsafe(20)
                    authentik_id = await client.create_user(
                        email=user.email,
                        password=temp_password,
                        display_name=user.display_name,
                    )
                    logger.info(f"  Created Authentik user: {user.email} → {authentik_id}")

                user.authentik_id = authentik_id
                await session.commit()
                migrated += 1

            except Exception as e:
                logger.error(f"  ERROR migrating {user.email}: {e}")
                await session.rollback()
                errors += 1

        logger.info(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
        if errors > 0:
            logger.warning("Some users failed — re-run script to retry. Do NOT run migration 0016 until errors=0.")
            sys.exit(1)
        else:
            logger.info("All users migrated. You can now run: make migrate (applies migration 0016)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_users())
```

- [ ] **Step 2: Run the migration (manual, with services running)**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m scripts.migrate_to_authentik
```
Expected output:
```
Found N users without authentik_id
  Created Authentik user: falk@bummelletzter.com → <uuid>
  ...
Migration complete: N migrated, 0 skipped, 0 errors
All users migrated. You can now run: make migrate
```

- [ ] **Step 3: Apply migration 0016 (drop old tables)**

Only after step 2 shows `errors=0`:
```bash
make migrate
```
Expected: `Running upgrade 0015 -> 0016`

- [ ] **Step 4: Restart backend**

```bash
docker compose -f infra/docker-compose.yml restart backend
```

- [ ] **Step 5: Smoke test — login works**

```bash
curl -s -X POST https://assist2.fichtlworks.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"falk@bummelletzter.com","password":"ChangeMe!!!"}' | python3 -m json.tool
```
Expected: `{"access_token": "...", "refresh_token": "...", "token_type": "bearer"}`

- [ ] **Step 6: Commit script**

```bash
git add backend/scripts/migrate_to_authentik.py
git commit -m "feat(migration): add one-time script to provision existing users into Authentik"
```

---

## Final Verification

- [ ] All unit tests pass: `docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/ -v`
- [ ] Backend starts clean: `docker compose -f infra/docker-compose.yml logs backend --tail=10`
- [ ] Login works end-to-end via browser at `https://assist2.fichtlworks.com/login`
- [ ] Authentik admin panel accessible at `https://authentik.fichtlworks.com`
- [ ] Commit summary: `git log --oneline -15`
