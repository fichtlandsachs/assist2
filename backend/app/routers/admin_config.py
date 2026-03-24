"""
Admin Configuration API
-----------------------
Endpoints for managing per-org system configs (learning, retrieval, prompts,
workflows, governance, LLM triggers).

All write operations require admin:config permission or superuser status.
Every change is version-incremented and written to ConfigHistory (audit trail).
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.admin_config import (
    ConfigHistoryRead,
    ConfigSectionRead,
    ConfigUpdateRequest,
    MergedConfigRead,
    RecommendationRead,
)
from app.services.admin_config_service import admin_config_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Permission helper (admin or superuser)
# ---------------------------------------------------------------------------

async def _require_admin(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Allow superusers and users with admin:config permission."""
    if current_user.is_superuser:
        return current_user

    from app.core.permissions import get_user_permissions
    perms = await get_user_permissions(current_user.id, org_id, db)
    if "*" in perms or "admin:config" in perms or "admin:*" in perms:
        return current_user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="admin:config permission required",
    )


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/admin/{org_id}/config",
    response_model=MergedConfigRead,
    summary="Get all admin config sections for an org",
)
async def get_admin_config(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MergedConfigRead:
    """Return all 6 config sections. Any authenticated member may read."""
    return await admin_config_service.get_merged_config(org_id, db)


@router.post(
    "/admin/{org_id}/config",
    response_model=ConfigSectionRead,
    summary="Update one admin config section",
)
async def update_admin_config(
    org_id: uuid.UUID,
    body: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConfigSectionRead:
    """Upsert a config section. Increments version and writes audit history."""
    await _require_admin(org_id, current_user, db)

    try:
        return await admin_config_service.upsert_config(
            org_id=org_id,
            config_type=body.config_type,
            payload=body.config_payload,
            changed_by_id=current_user.id,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/admin/{org_id}/config/{config_type}/history",
    response_model=list[ConfigHistoryRead],
    summary="Get change history for a config section",
)
async def get_config_history(
    org_id: uuid.UUID,
    config_type: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConfigHistoryRead]:
    """Return the last 50 changes for a config section (audit trail)."""
    rows = await admin_config_service.get_history(org_id, config_type, db)
    return [ConfigHistoryRead.model_validate(r) for r in rows]


# ---------------------------------------------------------------------------
# Recommendations (stub — ready for future learning engine integration)
# ---------------------------------------------------------------------------

@router.get(
    "/admin/{org_id}/recommendations",
    response_model=list[RecommendationRead],
    summary="List pending AI recommendations",
)
async def list_recommendations(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecommendationRead]:
    """Pending recommendations from the learning engine. Currently returns empty list."""
    return []


@router.post(
    "/admin/{org_id}/recommendations/{rec_id}/approve",
    summary="Approve a recommendation",
)
async def approve_recommendation(
    org_id: uuid.UUID,
    rec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _require_admin(org_id, current_user, db)
    raise HTTPException(status_code=404, detail="Recommendation not found")


@router.post(
    "/admin/{org_id}/recommendations/{rec_id}/reject",
    summary="Reject a recommendation",
)
async def reject_recommendation(
    org_id: uuid.UUID,
    rec_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    await _require_admin(org_id, current_user, db)
    raise HTTPException(status_code=404, detail="Recommendation not found")
