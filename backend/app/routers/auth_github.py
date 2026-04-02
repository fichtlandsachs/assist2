"""GitHub OAuth 2.0 — Authorization Code Flow."""
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta
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
from app.services.github_token import github_token_store
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/github", tags=["auth"])

_TIMEOUT = httpx.Timeout(10.0)


@router.get("/start")
async def github_start():
    """
    Generate GitHub OAuth authorization URL.
    Returns {"auth_url": "..."} — frontend opens this in a popup.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(16)

    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis.setex(f"oauth_state:github:{state}", 300, "1")

    params = urlencode({
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": settings.GITHUB_SCOPES,
        "state": state,
    })
    auth_url = f"https://github.com/login/oauth/authorize?{params}"
    return {"auth_url": auth_url}


async def _exchange_code(code: str) -> dict:
    """Exchange authorization code for GitHub access token."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
    data = resp.json()
    if "error" in data:
        logger.error("GitHub token exchange error: %s", data)
        raise HTTPException(status_code=400, detail="Autorisierungscode abgelaufen oder ungültig")
    return data


async def _get_github_user(access_token: str) -> dict:
    """Fetch GitHub user profile."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    resp.raise_for_status()
    return resp.json()


async def _get_primary_email(access_token: str) -> str:
    """Fetch primary verified email from GitHub."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    resp.raise_for_status()
    emails = resp.json()
    for entry in emails:
        if entry.get("primary") and entry.get("verified"):
            return entry["email"]
    raise HTTPException(
        status_code=400,
        detail="Kein verifizierter E-Mail-Account bei GitHub",
    )


@router.get("/callback", response_class=HTMLResponse)
async def github_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    GitHub OAuth callback.
    1. Validate state
    2. Exchange code for access token
    3. Fetch user profile + primary verified email
    4. Find or create local workspace user
    5. Store GitHub token in Redis (Fernet-encrypted, never in DB)
    6. Issue Authentik OIDC tokens
    7. Return HTML that postMessages tokens to opener and closes popup
    """
    settings = get_settings()

    # ── 1. Validate state ────────────────────────────────────────────────────
    import redis.asyncio as aioredis
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    state_key = f"oauth_state:github:{state}"
    exists = await redis.get(state_key)
    if not exists:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
    await redis.delete(state_key)

    # ── 2. Token exchange ────────────────────────────────────────────────────
    token_data = await _exchange_code(code)
    access_token: str = token_data["access_token"]

    # ── 3. GitHub profile + verified email ───────────────────────────────────
    gh_user = await _get_github_user(access_token)
    github_id: int = gh_user["id"]
    github_username: str = gh_user.get("login", "")
    display_name: str = gh_user.get("name") or github_username
    avatar_url: str | None = gh_user.get("avatar_url")

    primary_email = await _get_primary_email(access_token)

    # ── 4. Find or create workspace user ─────────────────────────────────────
    # Primary lookup: by GitHub user ID (stable, never changes)
    result = await db.execute(
        select(User).where(
            User.github_id == github_id,
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        # Secondary lookup: link to existing account if email matches
        result = await db.execute(
            select(User).where(
                User.email == primary_email.lower(),
                User.deleted_at.is_(None),
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.github_id = github_id
            existing.github_username = github_username
            existing.github_email = primary_email
            await db.commit()
            await db.refresh(existing)
            user = existing

    if not user:
        # New user — create in Authentik + local DB
        random_password = secrets.token_urlsafe(32)
        try:
            authentik_pk = await authentik_client.create_user(
                email=primary_email.lower(),
                password=random_password,
                display_name=display_name,
            )
        except Exception as exc:
            logger.error(
                "Failed to create Authentik user for GitHub account %s: %s",
                github_id,
                exc,
            )
            raise HTTPException(status_code=500, detail="Benutzeranlage fehlgeschlagen")

        user = User(
            email=primary_email.lower(),
            display_name=display_name,
            avatar_url=avatar_url,
            authentik_id=authentik_pk,
            github_id=github_id,
            github_username=github_username,
            github_email=primary_email,
            password_hash=None,
            is_active=True,
            email_verified=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    if not user.authentik_id:
        raise HTTPException(status_code=500, detail="Konto hat keine Authentik-Verknüpfung")

    # ── 5. Store GitHub access token in Redis (Fernet-encrypted, never in DB) ─
    await github_token_store.save(user.id, access_token)

    # ── 6. Issue Authentik OIDC tokens via app-password exchange ─────────────
    authentik_pk = int(user.authentik_id)
    identifier = f"github-login-{uuid.uuid4().hex}"
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
async def github_disconnect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Remove GitHub connection.
    Deletes token from Redis and clears github_id from DB.
    Optionally revokes the token at GitHub.
    """
    if not current_user.github_id:
        raise HTTPException(status_code=400, detail="Kein GitHub-Konto verknüpft")

    if not current_user.password_hash and not current_user.atlassian_account_id:
        raise HTTPException(
            status_code=400,
            detail="Keine andere Anmeldemethode verfügbar — Trennung nicht möglich",
        )

    settings = get_settings()

    # Attempt token revocation at GitHub (best-effort, non-fatal)
    access_token = await github_token_store.get_token(current_user.id)
    if access_token:
        try:
            import base64 as _b64
            credentials = _b64.b64encode(
                f"{settings.GITHUB_CLIENT_ID}:{settings.GITHUB_CLIENT_SECRET}".encode()
            ).decode()
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                await client.delete(
                    f"https://api.github.com/applications/{settings.GITHUB_CLIENT_ID}/token",
                    headers={
                        "Authorization": f"Basic {credentials}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json={"access_token": access_token},
                )
        except Exception as exc:
            logger.warning("GitHub token revocation failed (non-fatal): %s", exc)

    # Delete token from Redis
    await github_token_store.delete(current_user.id)

    # Clear GitHub fields from DB (no token material ever stored there)
    current_user.github_id = None
    current_user.github_username = None
    current_user.github_email = None
    await db.commit()

    return {"message": "GitHub-Verbindung getrennt"}
