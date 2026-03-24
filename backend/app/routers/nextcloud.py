"""Nextcloud plugin API routes."""
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException
from app.database import get_db
from app.deps import get_current_user
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.nextcloud import NextcloudFileList
from app.services.nextcloud_service import nextcloud_service

router = APIRouter()


@router.get(
    "/organizations/{org_id}/nextcloud/files",
    response_model=NextcloudFileList,
    tags=["Nextcloud"],
)
async def get_nextcloud_files(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextcloudFileList:
    """List recent files from the org's Nextcloud group folder."""
    # Explicit membership check — multi-tenancy invariant
    membership_result = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == org_id,
            Membership.status == "active",
        )
    )
    if not membership_result.scalar_one_or_none():
        raise ForbiddenException()

    org_result = await db.execute(
        select(Organization).where(
            Organization.id == org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise ForbiddenException()

    return await nextcloud_service.list_files(org.slug)
