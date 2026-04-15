"""Superadmin global config endpoints — GET and PATCH /api/v1/superadmin/config/."""
import asyncio
import smtplib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value, encrypt_value
from app.database import get_db
from app.models.global_config import ALLOWED_KEYS, SECRET_KEYS, GlobalConfig
from app.models.user import User
from app.routers.superadmin import get_admin_user
from app.services.system_settings_service import get_runtime_settings, invalidate_settings_cache

router = APIRouter(prefix="/api/v1/superadmin/config", tags=["SuperadminConfig"])


class ConfigPatchRequest(BaseModel):
    key: str
    value: str | None


@router.get("/")
async def get_config(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return all config keys. Secret values are never exposed — only is_set."""
    result = await db.execute(select(GlobalConfig))
    rows: dict[str, GlobalConfig] = {r.key: r for r in result.scalars().all()}

    out: dict[str, Any] = {}
    for key in ALLOWED_KEYS:
        is_secret = key in SECRET_KEYS
        row = rows.get(key)
        if is_secret:
            out[key] = {
                "value": None,
                "is_set": row is not None and row.value is not None,
                "is_secret": True,
            }
        else:
            out[key] = {
                "value": row.value if row else None,
                "is_secret": False,
            }
    return out


@router.patch("/", status_code=204)
async def patch_config(
    body: ConfigPatchRequest,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Set or clear one config key. Secret values are Fernet-encrypted before storage."""
    if body.key not in ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {body.key!r}")

    is_secret = body.key in SECRET_KEYS
    stored_value: str | None = None
    if body.value is not None:
        stored_value = encrypt_value(body.value) if is_secret else body.value

    row = await db.get(GlobalConfig, body.key)
    if row is None:
        row = GlobalConfig(
            key=body.key,
            value=stored_value,
            is_secret=is_secret,
            updated_at=datetime.now(timezone.utc),
            updated_by_id=admin.id,
        )
        db.add(row)
    else:
        row.value = stored_value
        row.updated_at = datetime.now(timezone.utc)
        row.updated_by_id = admin.id

    await db.commit()
    invalidate_settings_cache()
    return Response(status_code=204)


@router.post("/test-smtp")
async def test_smtp(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a test email using the current (effective) SMTP settings."""
    s = await get_runtime_settings(db)

    if not s.SMTP_USER or not s.SMTP_PASS:
        raise HTTPException(status_code=400, detail="SMTP-Zugangsdaten fehlen (smtp.user / smtp.pass).")

    def _send() -> None:
        from email.mime.text import MIMEText
        msg = MIMEText("Dies ist eine Test-E-Mail von heykarl.app — SMTP-Konfiguration erfolgreich.", "plain", "utf-8")
        msg["Subject"] = "heykarl.app SMTP-Test"
        msg["From"] = s.SMTP_FROM
        msg["To"] = s.CONTACT_EMAIL_TO

        if s.SMTP_PORT == 465:
            with smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as conn:
                conn.login(s.SMTP_USER, s.SMTP_PASS)
                conn.sendmail(s.SMTP_FROM, [s.CONTACT_EMAIL_TO], msg.as_string())
        else:
            with smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=10) as conn:
                conn.ehlo()
                conn.starttls()
                conn.login(s.SMTP_USER, s.SMTP_PASS)
                conn.sendmail(s.SMTP_FROM, [s.CONTACT_EMAIL_TO], msg.as_string())

    try:
        await asyncio.get_event_loop().run_in_executor(None, _send)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SMTP-Fehler: {exc}")

    return {"ok": True, "sent_to": s.CONTACT_EMAIL_TO}
