"""Atlassian OAuth 2.0 — Authorization Code Flow (3-legged)."""
import logging
import secrets
import uuid
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


async def _build_auth_url(state: str, settings) -> str:
    params = urlencode({
        "audience": "api.atlassian.com",
        "client_id": settings.ATLASSIAN_CLIENT_ID,
        "scope": settings.ATLASSIAN_SCOPES,
        "redirect_uri": settings.ATLASSIAN_REDIRECT_URI,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    })
    return f"https://auth.atlassian.com/authorize?{params}"


@router.get("/start")
async def atlassian_start():
    """
    Generate Atlassian OAuth authorization URL for login.
    Returns {"auth_url": "..."} — frontend opens this in a popup.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(16)

    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.setex(f"oauth_state:atlassian:{state}", 300, "login")

    return {"auth_url": await _build_auth_url(state, settings)}


@router.get("/link-start")
async def atlassian_link_start(
    current_user: User = Depends(get_current_user),
):
    """
    Generate Atlassian OAuth URL for linking to an existing account.
    Requires the user to already be authenticated.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(16)

    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    # Store the current user's ID so the callback can link to them directly
    await redis.setex(f"oauth_state:atlassian:{state}", 300, f"link:{current_user.id}")

    return {"auth_url": await _build_auth_url(state, settings)}


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
    state_key = f"oauth_state:atlassian:{state}"
    state_value = await redis.get(state_key)
    if not state_value:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis.delete(state_key)

    link_mode = state_value.startswith("link:")
    link_user_id: str | None = state_value[5:] if link_mode else None

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

    # ── 4a. Link mode: attach to existing logged-in user and return ──────────
    if link_mode and link_user_id:
        result = await db.execute(
            select(User).where(
                User.id == uuid.UUID(link_user_id),
                User.deleted_at.is_(None),
            )
        )
        link_user = result.scalar_one_or_none()
        if link_user:
            link_user.atlassian_account_id = account_id
            link_user.atlassian_email = email or None
            await db.commit()
            await atlassian_token_store.save(link_user.id, access_token, refresh_token, expires_in, cloud_id)

        app_origin = settings.APP_BASE_URL.rstrip("/")
        html = f"""<!DOCTYPE html>
<html><body><script>
(function() {{
  if (window.opener) {{
    window.opener.postMessage({{ "type": "atlassian_linked" }}, '{app_origin}');
  }}
  window.close();
}})();
</script></body></html>"""
        return HTMLResponse(content=html)

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

        user = User(
            email=email.lower() if email else f"atlassian_{account_id}@noreply.local",
            display_name=display_name,
            avatar_url=avatar_url,
            authentik_id=authentik_pk,
            atlassian_account_id=account_id,
            atlassian_email=email or None,
            password_hash=None,
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
    import json as _json
    app_origin = settings.APP_BASE_URL.rstrip("/")
    payload_json = _json.dumps({
        "type": "workspace_login",
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "user": {"email": user.email, "name": user.display_name},
    })
    html = f"""<!DOCTYPE html>
<html><body><script>
(function() {{
  var payload = {payload_json};
  if (window.opener) {{
    window.opener.postMessage(payload, '{app_origin}');
  }}
  window.close();
}})();
</script></body></html>"""
    return HTMLResponse(content=html)


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
