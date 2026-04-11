"""
Integration settings router.

All endpoints operate on a specific organization and require authentication.
API tokens are write-only: once saved they return only a boolean `*_set` flag.
"""
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.organization import Organization
from app.models.user import User
from app.services import org_integrations_service as svc
from app.core.exceptions import NotFoundException

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class JiraSettingsUpdate(BaseModel):
    base_url: str = ""
    user: str = ""
    api_token: Optional[str] = None   # None = keep existing


class ConfluenceSettingsUpdate(BaseModel):
    base_url: str = ""
    user: str = ""
    api_token: Optional[str] = None
    default_space_key: Optional[str] = None
    default_parent_page_id: Optional[str] = None


class AISettingsUpdate(BaseModel):
    dor_rules: Optional[list[str]] = None      # None = keep existing
    min_quality_score: Optional[int] = None    # None = keep existing


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_org(org_id: uuid.UUID, db: AsyncSession) -> Organization:
    stmt = select(Organization).where(Organization.id == org_id)
    result = await db.execute(stmt)
    org = result.scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organization not found")
    return org


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/organizations/{org_id}/integrations",
    summary="Get all integration settings for an organization",
)
async def get_integrations(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    org = await _get_org(org_id, db)
    return svc.get_all_settings(org)


@router.patch(
    "/organizations/{org_id}/integrations/jira",
    summary="Update Jira integration settings",
)
async def update_jira(
    org_id: uuid.UUID,
    data: JiraSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    org = await _get_org(org_id, db)
    svc.set_jira_settings(org, data.base_url, data.user, data.api_token)
    await db.commit()
    await db.refresh(org)
    return svc.get_jira_settings(org)


@router.patch(
    "/organizations/{org_id}/integrations/confluence",
    summary="Update Confluence integration settings",
)
async def update_confluence(
    org_id: uuid.UUID,
    data: ConfluenceSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    org = await _get_org(org_id, db)
    svc.set_confluence_settings(org, data.base_url, data.user, data.api_token, data.default_space_key, data.default_parent_page_id)
    await db.commit()
    await db.refresh(org)
    return svc.get_confluence_settings(org)


@router.patch(
    "/organizations/{org_id}/integrations/ai",
    summary="Update AI integration settings",
)
async def update_ai(
    org_id: uuid.UUID,
    data: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    org = await _get_org(org_id, db)
    svc.set_ai_settings(
        org,
        dor_rules=data.dor_rules,
        min_quality_score=data.min_quality_score,
    )
    await db.commit()
    await db.refresh(org)
    return svc.get_ai_settings(org)
