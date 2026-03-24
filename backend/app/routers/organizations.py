import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.organization import OrgCreate, OrgRead, OrgUpdate
from app.services.org_service import org_service

router = APIRouter()


@router.post(
    "/organizations",
    response_model=OrgRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    data: OrgCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrgRead:
    """Create a new organization. The creator becomes the org_owner."""
    org = await org_service.create(db, data, current_user.id)
    return OrgRead.model_validate(org)


@router.get(
    "/organizations",
    response_model=List[OrgRead],
    summary="List my organizations",
)
async def list_organizations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[OrgRead]:
    """List all organizations the current user is an active member of."""
    orgs = await org_service.list_for_user(db, current_user.id)
    return [OrgRead.model_validate(org) for org in orgs]


@router.get(
    "/organizations/{org_id}",
    response_model=OrgRead,
    summary="Get an organization",
)
async def get_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:read")),
) -> OrgRead:
    """Get organization details. Requires org:read permission."""
    org = await org_service.get_by_id(db, org_id)
    return OrgRead.model_validate(org)


@router.patch(
    "/organizations/{org_id}",
    response_model=OrgRead,
    summary="Update an organization",
)
async def update_organization(
    org_id: uuid.UUID,
    data: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> OrgRead:
    """Update organization details. Requires org:update permission."""
    org = await org_service.update(db, org_id, data)
    return OrgRead.model_validate(org)


@router.delete(
    "/organizations/{org_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an organization",
)
async def delete_organization(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:delete")),
) -> None:
    """Soft-delete an organization. Requires org:delete permission."""
    await org_service.delete(db, org_id)
