"""Nextcloud plugin API routes."""
import uuid

import httpx
from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ForbiddenException
from app.database import get_db
from app.deps import get_current_user
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.schemas.nextcloud import NextcloudFileList, NextcloudUploadResult
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


@router.get(
    "/organizations/{org_id}/nextcloud/files/download",
    tags=["Nextcloud"],
)
async def download_nextcloud_file(
    org_id: uuid.UUID,
    path: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Proxy-download a file from Nextcloud WebDAV."""
    from fastapi.responses import StreamingResponse

    # Membership check
    membership_result = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == org_id,
            Membership.status == "active",
        )
    )
    if not membership_result.scalar_one_or_none():
        raise ForbiddenException()

    settings = get_settings()
    url = f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/{settings.NEXTCLOUD_ADMIN_USER}/{path}"
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
    filename = path.split("/")[-1]

    async def stream():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("GET", url, auth=auth) as resp:
                resp.raise_for_status()
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    yield chunk

    return StreamingResponse(
        stream(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/organizations/{org_id}/nextcloud/files/upload",
    response_model=NextcloudUploadResult,
    tags=["Nextcloud"],
)
async def upload_nextcloud_file(
    org_id: uuid.UUID,
    file: UploadFile,
    subfolder: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextcloudUploadResult:
    """Upload a file to the org's Nextcloud group folder via WebDAV."""
    # Membership check
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

    settings = get_settings()
    safe_subfolder = subfolder.strip("/")
    dest_path = f"Organizations/{org.slug}"
    if safe_subfolder:
        dest_path = f"{dest_path}/{safe_subfolder}"
    dest_path = f"{dest_path}/{file.filename}"

    url = f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/{settings.NEXTCLOUD_ADMIN_USER}/{dest_path}"
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)

    content = await file.read()
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.put(url, content=content, auth=auth)
        resp.raise_for_status()

    return NextcloudUploadResult(ok=True, path=dest_path)
