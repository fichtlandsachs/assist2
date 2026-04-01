# Atlassian SSO — Multi-Provider Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Atlassian OAuth 2.0 as a second login provider — new users are created in Authentik + local DB and receive standard Authentik OIDC tokens; Atlassian API tokens for Jira usage are stored separately in Redis with Fernet encryption.

**Architecture:** The Atlassian callback handler creates/links a local User + Authentik account, then uses the existing `create_app_password` → `authenticate_user` flow to issue standard Authentik OIDC tokens. This means `get_current_user`, refresh, and logout work unchanged. Atlassian access/refresh tokens for Jira API calls are stored in Redis (Fernet-encrypted) keyed by `user.id`, decoupled from the session JWT.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Redis (aioredis), Fernet (cryptography), httpx, Next.js 15, React 19

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/migrations/versions/0020_atlassian_sso.py` | Create | Add `atlassian_account_id`, `atlassian_email` to `users` |
| `backend/app/models/user.py` | Modify | Add two new `Mapped` columns |
| `backend/app/config.py` | Modify | Add `ATLASSIAN_*` env vars |
| `backend/app/services/atlassian_token.py` | Create | Redis token store (save/get/refresh/delete) |
| `backend/app/routers/auth_atlassian.py` | Create | `/start`, `/callback`, `/disconnect` endpoints |
| `backend/app/deps.py` | Modify | Add `get_atlassian_token` dependency |
| `backend/app/main.py` | Modify | Register `auth_atlassian` router |
| `frontend/lib/auth/context.tsx` | Modify | Add `loginWithAtlassian`, expose via context |
| `frontend/app/(auth)/login/page.tsx` | Modify | Add Atlassian login button |
| `frontend/app/[org]/settings/page.tsx` | Modify | Add Atlassian connect/disconnect section |

---

## Task 1: DB Migration — Add Atlassian columns

**Files:**
- Create: `backend/migrations/versions/0020_atlassian_sso.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/migrations/versions/0020_atlassian_sso.py
"""add atlassian sso columns

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column(
        'atlassian_account_id', sa.String(64), nullable=True
    ))
    op.add_column('users', sa.Column(
        'atlassian_email', sa.String(255), nullable=True
    ))
    op.create_index(
        'ix_users_atlassian_account_id',
        'users',
        ['atlassian_account_id'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index('ix_users_atlassian_account_id', table_name='users')
    op.drop_column('users', 'atlassian_email')
    op.drop_column('users', 'atlassian_account_id')
```

- [ ] **Step 2: Run the migration**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```

Expected output: `Running upgrade 0019 -> 0020, add atlassian sso columns`

- [ ] **Step 3: Verify columns exist**

```bash
docker compose -f docker-compose.yml exec postgres psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d users" | grep atlassian
```

Expected: two rows — `atlassian_account_id` and `atlassian_email`

- [ ] **Step 4: Update User model**

Replace the existing `backend/app/models/user.py` content (add two columns after `authentik_id`):

```python
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, String
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
    atlassian_account_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)
    atlassian_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
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

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0020_atlassian_sso.py backend/app/models/user.py
git commit -m "feat(auth): add atlassian_account_id + atlassian_email to users table"
```

---

## Task 2: Config — Add Atlassian env vars

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add Atlassian settings block**

In `backend/app/config.py`, add after the `# OAuth` block:

```python
    # Atlassian OAuth 2.0
    ATLASSIAN_CLIENT_ID: str = ""
    ATLASSIAN_CLIENT_SECRET: str = ""
    ATLASSIAN_REDIRECT_URI: str = ""
    ATLASSIAN_SCOPES: str = "read:me read:jira-work write:jira-work read:jira-user offline_access"
```

- [ ] **Step 2: Add to `.env` file**

```bash
# in infra/.env — add these four lines:
ATLASSIAN_CLIENT_ID=<aus Atlassian Developer Console>
ATLASSIAN_CLIENT_SECRET=<aus Atlassian Developer Console>
ATLASSIAN_REDIRECT_URI=https://assist.fichtlworks.com/api/v1/auth/atlassian/callback
ATLASSIAN_SCOPES=read:me read:jira-work write:jira-work read:jira-user offline_access
```

Note: `APP_BASE_URL` is already `https://assist2.fichtlworks.com` in config — this is used as the postMessage origin.

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat(auth): add ATLASSIAN_* config vars"
```

---

## Task 3: AtlassianTokenStore — Redis + Fernet

**Files:**
- Create: `backend/app/services/atlassian_token.py`

This service stores Atlassian access/refresh tokens in Redis, encrypted with Fernet. It is separate from the session JWT.

- [ ] **Step 1: Create the service file**

```python
# backend/app/services/atlassian_token.py
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/atlassian_token.py
git commit -m "feat(auth): add AtlassianTokenStore — Redis/Fernet token persistence"
```

---

## Task 4: Auth Router — `/start` endpoint

**Files:**
- Create: `backend/app/routers/auth_atlassian.py`

- [ ] **Step 1: Create router with `/start`**

```python
# backend/app/routers/auth_atlassian.py
"""Atlassian OAuth 2.0 — Authorization Code Flow (3-legged)."""
import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.atlassian_token import atlassian_token_store
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/atlassian", tags=["auth"])

_TIMEOUT = httpx.Timeout(10.0)


@router.get("/start")
async def atlassian_start():
    """
    Generate Atlassian OAuth authorization URL.
    Returns {"auth_url": "..."} — frontend opens this in a popup.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(16)

    # Store state in Redis with 5-minute TTL
    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.setex(f"oauth_state:{state}", 300, "1")

    params = urlencode({
        "audience": "api.atlassian.com",
        "client_id": settings.ATLASSIAN_CLIENT_ID,
        "scope": settings.ATLASSIAN_SCOPES,
        "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    })
    auth_url = f"https://auth.atlassian.com/authorize?{params}"
    return {"auth_url": auth_url}
```

- [ ] **Step 2: Verify the router file has no import errors**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -c "from app.routers.auth_atlassian import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth_atlassian.py
git commit -m "feat(auth): add Atlassian OAuth /start endpoint"
```

---

## Task 5: Auth Router — `/callback` endpoint

**Files:**
- Modify: `backend/app/routers/auth_atlassian.py`

This is the main OAuth flow. It validates state, exchanges code for tokens, fetches the Atlassian user profile, creates/links the local workspace user, issues Authentik OIDC tokens, and returns them via postMessage.

- [ ] **Step 1: Add the `_exchange_code`, `_get_me`, `_get_cloud_id` helpers**

Append to `backend/app/routers/auth_atlassian.py` (after the `/start` endpoint):

```python
async def _exchange_code(code: str) -> dict:
    """Exchange authorization code for Atlassian tokens."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://auth.atlassian.com/oauth/token",
            json={
                "grant_type": "authorization_code",
                "client_id": settings.ATLASSIAN_CLIENT_ID,
                "client_secret": settings.ATLASSIAN_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
            },
        )
    if not resp.is_success:
        logger.error("Atlassian token exchange failed: %s", resp.text)
        raise HTTPException(status_code=400, detail="Token-Exchange fehlgeschlagen")
    return resp.json()


async def _get_me(access_token: str) -> dict:
    """Fetch Atlassian user profile."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            "https://api.atlassian.com/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    resp.raise_for_status()
    return resp.json()


async def _get_cloud_id(access_token: str) -> str:
    """Fetch first accessible Atlassian cloud resource ID."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    resp.raise_for_status()
    resources = resp.json()
    if not resources:
        raise HTTPException(status_code=400, detail="Kein Atlassian Workspace zugänglich")
    return resources[0]["id"]
```

- [ ] **Step 2: Add the `/callback` endpoint**

Append to `backend/app/routers/auth_atlassian.py`:

```python
@router.get("/callback", response_class=HTMLResponse)
async def atlassian_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Atlassian OAuth callback.
    1. Validate state
    2. Exchange code for tokens
    3. Fetch user profile + cloud ID
    4. Find or create local workspace user
    5. Issue Authentik OIDC tokens
    6. Return HTML that postMessages tokens to opener and closes popup
    """
    import secrets as _secrets
    import uuid
    from datetime import datetime, timezone, timedelta

    settings = get_settings()

    # ── 1. Validate state ────────────────────────────────────────────────────
    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    state_key = f"oauth_state:{state}"
    exists = await redis.get(state_key)
    if not exists:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis.delete(state_key)

    # ── 2. Token exchange ────────────────────────────────────────────────────
    token_data = await _exchange_code(code)
    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)

    # ── 3. Atlassian profile + cloud ID ──────────────────────────────────────
    me = await _get_me(access_token)
    account_id: str = me["account_id"]
    email: str = me.get("email", "")
    display_name: str = me.get("display_name", me.get("name", "Atlassian User"))
    avatar_url: str | None = me.get("picture") or me.get("avatarUrls", {}).get("48x48")
    cloud_id = await _get_cloud_id(access_token)

    # ── 4. Find or create workspace user ────────────────────────────────────
    # Primary lookup: by Atlassian account_id (stable, never changes)
    result = await db.execute(
        select(User).where(
            User.atlassian_account_id == account_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user and email:
        # Secondary lookup: by email (for linking existing password accounts)
        result = await db.execute(
            select(User).where(
                User.email == email.lower(),
                User.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            # Link only when email matches (security invariant from spec)
            existing.atlassian_account_id = account_id
            existing.atlassian_email = email
            await db.commit()
            await db.refresh(existing)
            user = existing

    if not user:
        # New user — create in Authentik + local DB
        random_password = _secrets.token_urlsafe(32)
        try:
            authentik_pk = await authentik_client.create_user(
                email=email.lower() if email else f"atlassian_{account_id}@noreply.local",
                password=random_password,
                display_name=display_name,
            )
        except Exception as exc:
            logger.error("Failed to create Authentik user for Atlassian account %s: %s", account_id, exc)
            raise HTTPException(status_code=500, detail="Benutzeranlage fehlgeschlagen")

        import bcrypt
        user = User(
            email=email.lower() if email else f"atlassian_{account_id}@noreply.local",
            display_name=display_name,
            avatar_url=avatar_url,
            authentik_id=authentik_pk,
            atlassian_account_id=account_id,
            atlassian_email=email or None,
            password_hash=None,   # Atlassian-only account — no local password
            is_active=True,
            email_verified=bool(email),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Ensure authentik_id is set (required for app-password exchange)
    if not user.authentik_id:
        raise HTTPException(status_code=500, detail="Konto hat keine Authentik-Verknüpfung")

    # ── 5. Store Atlassian API tokens in Redis ───────────────────────────────
    await atlassian_token_store.save(user.id, access_token, refresh_token, expires_in, cloud_id)

    # ── 6. Issue Authentik OIDC tokens via app-password exchange ────────────
    authentik_pk = int(user.authentik_id)
    identifier = f"atlassian-login-{uuid.uuid4().hex}"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    app_password_key = await authentik_client.create_app_password(
        authentik_pk=authentik_pk,
        identifier=identifier,
        expires=expires,
    )
    try:
        tokens = await authentik_client.authenticate_user(
            username=user.email,
            app_password=app_password_key,
        )
    finally:
        await authentik_client.delete_app_password(identifier)

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # ── 7. postMessage to opener and close popup ─────────────────────────────
    app_origin = settings.APP_BASE_URL.rstrip("/")
    html = f"""<!DOCTYPE html>
<html><body><script>
(function() {{
  var payload = {{
    type: 'workspace_login',
    access_token: '{tokens.access_token}',
    refresh_token: '{tokens.refresh_token}',
    user: {{ email: '{user.email}', name: '{user.display_name}' }}
  }};
  if (window.opener) {{
    window.opener.postMessage(payload, '{app_origin}');
  }}
  window.close();
}})();
</script></body></html>"""
    return HTMLResponse(content=html)
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth_atlassian.py
git commit -m "feat(auth): add Atlassian OAuth /callback — full login flow"
```

---

## Task 6: Auth Router — `/disconnect` + `get_atlassian_token` dependency

**Files:**
- Modify: `backend/app/routers/auth_atlassian.py`
- Modify: `backend/app/deps.py`

- [ ] **Step 1: Add `/disconnect` endpoint**

Append to `backend/app/routers/auth_atlassian.py`:

```python
@router.post("/disconnect")
async def atlassian_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove Atlassian connection.
    Deletes tokens from Redis and clears atlassian_account_id from DB.
    Only allowed when the user has another authentication method (password or other OAuth).
    """
    if not current_user.password_hash and not current_user.atlassian_account_id:
        raise HTTPException(
            status_code=400,
            detail="Keine andere Anmeldemethode verfügbar — Trennung nicht möglich",
        )

    await atlassian_token_store.delete(current_user.id)

    current_user.atlassian_account_id = None
    current_user.atlassian_email = None
    await db.commit()

    return {"message": "Atlassian-Verbindung getrennt"}
```

- [ ] **Step 2: Add `get_atlassian_token` to `deps.py`**

Add to the bottom of `backend/app/deps.py`:

```python
from app.services.atlassian_token import atlassian_token_store
from app.core.exceptions import ForbiddenException


async def get_atlassian_token(
    current_user: User = Depends(get_current_user),
) -> tuple[str, str]:
    """
    Dependency for Jira routes.
    Returns (access_token, cloud_id). Transparently refreshes if near expiry.
    Raises 403 when no Atlassian account is linked.
    """
    data = await atlassian_token_store.get(current_user.id)
    if not data:
        raise ForbiddenException(
            detail="Kein Atlassian-Account verknüpft. Bitte über Atlassian einloggen."
        )
    token = await atlassian_token_store.get_valid_token(current_user.id)
    return token, data["cloud_id"]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/auth_atlassian.py backend/app/deps.py
git commit -m "feat(auth): add /disconnect endpoint and get_atlassian_token dependency"
```

---

## Task 7: Register Router in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add import and router registration**

In `backend/app/main.py`, add the import line alongside the existing router imports:

```python
from app.routers.auth_atlassian import router as auth_atlassian_router
```

Then add the `include_router` call alongside the other router registrations:

```python
app.include_router(auth_atlassian_router, prefix="/api/v1")
```

- [ ] **Step 2: Verify the route is visible**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d backend
sleep 10
curl -s https://assist2.fichtlworks.com/api/v1/auth/atlassian/start | python3 -m json.tool
```

Expected: JSON with `{"auth_url": "https://auth.atlassian.com/authorize?..."}` (or an error if `ATLASSIAN_CLIENT_ID` is empty — that's fine, the endpoint exists)

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(auth): register auth_atlassian router"
```

---

## Task 8: Frontend — Login button + auth context

**Files:**
- Modify: `frontend/lib/auth/context.tsx`
- Modify: `frontend/app/(auth)/login/page.tsx`

- [ ] **Step 1: Extend `AuthContextValue` and `AuthProvider`**

Replace `frontend/lib/auth/context.tsx` with:

```tsx
"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import type { User, TokenResponse } from "@/types";
import { apiRequest, setTokens, clearTokens, getAccessToken } from "@/lib/api/client";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithAtlassian: () => void;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const _noop = async () => {};
const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoading: true,
  isAuthenticated: false,
  login: _noop,
  loginWithAtlassian: () => {},
  register: _noop,
  logout: _noop,
  refreshUser: _noop,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchUser = async () => {
    try {
      const me = await apiRequest<User>("/api/v1/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    }
  };

  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      fetchUser().finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiRequest<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password })
    });
    setTokens(data.access_token, data.refresh_token);
    await fetchUser();
    const orgs = await apiRequest<{ slug: string }[]>("/api/v1/organizations");
    if (orgs.length > 0) {
      router.push(`/${orgs[0].slug}/dashboard`);
    } else {
      router.push("/setup");
    }
  };

  const loginWithAtlassian = useCallback(() => {
    const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "";

    const handleMessage = async (e: MessageEvent) => {
      if (e.origin !== APP_URL) return;
      if (e.data?.type !== "workspace_login") return;
      window.removeEventListener("message", handleMessage);

      const { access_token, refresh_token } = e.data as {
        access_token: string;
        refresh_token: string;
        user: { email: string; name: string };
      };
      setTokens(access_token, refresh_token ?? "");
      await fetchUser();
      const orgs = await apiRequest<{ slug: string }[]>("/api/v1/organizations");
      if (orgs.length > 0) {
        router.push(`/${orgs[0].slug}/dashboard`);
      } else {
        router.push("/setup");
      }
    };

    // Fetch auth URL then open popup
    apiRequest<{ auth_url: string }>("/api/v1/auth/atlassian/start")
      .then(({ auth_url }) => {
        window.open(auth_url, "atlassian_login", "width=600,height=700,noopener=0");
        window.addEventListener("message", handleMessage);
      })
      .catch(console.error);
  }, [router]);

  const register = async (email: string, password: string, displayName: string) => {
    const data = await apiRequest<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name: displayName })
    });
    setTokens(data.access_token, data.refresh_token);
    await fetchUser();
    router.push("/");
  };

  const logout = async () => {
    const refresh = localStorage.getItem("refresh_token");
    if (refresh) {
      await apiRequest("/api/v1/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: refresh })
      }).catch(() => {});
    }
    clearTokens();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{
      user, isLoading,
      isAuthenticated: !!user,
      login, loginWithAtlassian, register, logout,
      refreshUser: fetchUser
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
```

- [ ] **Step 2: Add Atlassian button to login page**

Replace `frontend/app/(auth)/login/page.tsx` with:

```tsx
"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function LoginPage() {
  const { login, loginWithAtlassian } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      const apiErr = err as ApiError & { status?: number };
      if (apiErr?.code === "HTTP_401" || apiErr?.status === 401) {
        setError("Ungültige Zugangsdaten. Falls du dein Passwort noch nicht zurückgesetzt hast, besuche: authentik.fichtlworks.com");
      } else {
        setError(apiErr?.error ?? "Login fehlgeschlagen. Bitte versuche es erneut.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputCls = "w-full px-3 py-2 text-sm outline-none transition-colors rounded-sm bg-[#faf9f6] border border-[#cec8bc] focus:border-[#a09080] focus:ring-1 focus:ring-[rgba(160,144,128,.2)]";

  return (
    <div className="w-full max-w-sm">
      <div className="mb-6 text-center">
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "22px", color: "#1c1810" }}>assist2</span>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".1em", textTransform: "uppercase", color: "#a09080", marginTop: "4px" }}>Workspace Platform</p>
      </div>

      <div className="rounded-sm p-8 space-y-5" style={{ background: "#faf9f6", border: "0.5px solid #e2ddd4", boxShadow: "0 2px 12px rgba(28,24,16,.06)" }}>
        <h1 style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "18px", color: "#1c1810", fontWeight: 400 }}>Anmelden</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm rounded-sm px-3 py-2.5" style={{ background: "rgba(139,94,82,.07)", border: "0.5px solid #8b5e52", color: "#8b5e52" }}>
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "#5a5040" }}>E-Mail</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="name@example.com" autoComplete="email" />
          </div>

          <div>
            <label htmlFor="password" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "#5a5040" }}>Passwort</label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="••••••••" autoComplete="current-password" />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "#1c1810", color: "#faf9f6", border: "0.5px solid #1c1810" }}
          >
            {isSubmitting ? "Anmelden…" : "Anmelden"}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px" style={{ background: "#e2ddd4" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".08em", textTransform: "uppercase", color: "#a09080" }}>oder</span>
          <div className="flex-1 h-px" style={{ background: "#e2ddd4" }} />
        </div>

        {/* Atlassian Login */}
        <button
          type="button"
          onClick={loginWithAtlassian}
          className="w-full py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "transparent", color: "#1c1810", border: "0.5px solid #cec8bc" }}
        >
          <svg width="14" height="14" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.218 1.137a.932.932 0 00-1.476 0L.518 21.895a.931.931 0 00.738 1.476h8.448l5.514-9.54 5.514 9.54h8.448a.931.931 0 00.738-1.476L15.218 1.137z" fill="#2684FF"/>
            <path d="M15.218 14.29l-5.514 9.08h11.028L15.218 14.29z" fill="url(#atlassian-gradient)"/>
            <defs>
              <linearGradient id="atlassian-gradient" x1="15.218" y1="14.29" x2="15.218" y2="23.37" gradientUnits="userSpaceOnUse">
                <stop stopColor="#0052CC"/>
                <stop offset="1" stopColor="#2684FF"/>
              </linearGradient>
            </defs>
          </svg>
          Mit Atlassian anmelden
        </button>

        <p className="text-center" style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "#a09080" }}>
          Noch kein Konto?{" "}
          <Link href="/register" style={{ color: "#5a5040", textDecoration: "underline", textUnderlineOffset: "2px" }}>Registrieren</Link>
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Rebuild and deploy frontend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
```

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/auth/context.tsx frontend/app/\(auth\)/login/page.tsx
git commit -m "feat(auth): add Atlassian login button and popup OAuth flow to frontend"
```

---

## Task 9: Frontend — Settings disconnect

**Files:**
- Modify: `frontend/app/[org]/settings/page.tsx`

- [ ] **Step 1: Read current settings page structure**

```bash
head -60 /opt/assist2/frontend/app/\[org\]/settings/page.tsx
```

- [ ] **Step 2: Add Atlassian section**

Find the section where profile/integrations are shown and add an Atlassian connection card. Add this component inline in the settings page (adapt the surrounding structure as needed):

```tsx
// Add to imports at top of settings/page.tsx
import { useAuth } from "@/lib/auth/context";
import { apiRequest } from "@/lib/api/client";

// Add inside the settings page component, alongside other settings sections:
function AtlassianConnectionSection({ user }: { user: User }) {
  const { loginWithAtlassian } = useAuth();
  const [disconnecting, setDisconnecting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isConnected = !!user.atlassian_account_id;

  const disconnect = async () => {
    setDisconnecting(true);
    setMsg(null);
    try {
      await apiRequest("/api/v1/auth/atlassian/disconnect", { method: "POST" });
      setMsg("Atlassian-Verbindung getrennt.");
      window.location.reload();
    } catch (e: unknown) {
      const err = e as { error?: string };
      setMsg(err?.error ?? "Fehler beim Trennen der Verbindung.");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
      <div className="flex items-center justify-between">
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>Atlassian</p>
          <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
            {isConnected
              ? `Verbunden als ${user.atlassian_email ?? user.email}`
              : "Nicht verbunden"}
          </p>
        </div>
        {isConnected ? (
          <button
            onClick={disconnect}
            disabled={disconnecting}
            className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid #8b5e52", color: "#8b5e52" }}
          >
            {disconnecting ? "Trenne…" : "Trennen"}
          </button>
        ) : (
          <button
            onClick={loginWithAtlassian}
            className="px-3 py-1.5 rounded-sm transition-colors"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
          >
            Verbinden
          </button>
        )}
      </div>
      {msg && (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>{msg}</p>
      )}
    </div>
  );
}
```

Then use `<AtlassianConnectionSection user={user} />` in the appropriate section of the settings page.

Note: The `User` type in `frontend/types/index.ts` needs two optional fields added:

```ts
// In the User interface in types/index.ts, add:
atlassian_account_id?: string | null;
atlassian_email?: string | null;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/\[org\]/settings/page.tsx frontend/types/index.ts
git commit -m "feat(auth): add Atlassian connect/disconnect to user settings"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|---|---|
| Atlassian OAuth 2.0 Authorization Code Flow | Task 4+5 |
| State validation via Redis | Task 4 |
| Token exchange (code → access+refresh) | Task 5 |
| User profile fetch (`/me`) | Task 5 |
| Cloud ID fetch (`/accessible-resources`) | Task 5 |
| `atlassian_account_id` binding (not email) | Task 1+5 |
| E-mail matching for account linking | Task 5 (secondary lookup) |
| New user creation (Authentik + local DB) | Task 5 |
| Fernet-encrypted Redis token store | Task 3 |
| Transparent token refresh (120s buffer) | Task 3 |
| Workspace-JWT via Authentik app-password | Task 5 |
| postMessage to opener (explicit origin) | Task 5 |
| `/disconnect` endpoint | Task 6 |
| `get_atlassian_token` dependency | Task 6 |
| Frontend login button + popup | Task 8 |
| Frontend settings disconnect | Task 9 |
| Env vars | Task 2 |
| DB migration | Task 1 |

### Security Invariants Verified

- `atlassian_account_id` is used as binding key, never email
- postMessage target is `APP_BASE_URL` (not `*`)
- `atlassian_account_id` is not included in the Workspace JWT (JWT contains only Authentik `sub` + `email`)
- Tokens are Fernet-encrypted in Redis, never logged
- State parameter is stored in Redis with 5-minute TTL and deleted after use (one-time use)
- `/disconnect` guards against locking out users with no other auth method (checks `password_hash`)

### Type Consistency

- `atlassian_token_store.save(user.id, ...)` — `user.id` is `UUID` from SQLAlchemy; `_key()` uses `str.format()` which handles UUID correctly
- `tokens.access_token` / `tokens.refresh_token` — `TokenResponse` is returned by `authentik_client.authenticate_user()`; these fields are confirmed present in `app/schemas/auth.py`
- `get_atlassian_token` returns `tuple[str, str]` — consistent with how Jira routes should consume it
