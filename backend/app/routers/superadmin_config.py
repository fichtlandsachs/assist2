"""Superadmin global config endpoints — GET and PATCH /api/v1/superadmin/config/."""
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
    return Response(status_code=204)
