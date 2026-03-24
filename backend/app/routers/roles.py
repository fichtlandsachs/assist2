import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.role import PermissionRead, RoleCreate, RoleRead, RoleUpdate
from app.services.permission_service import permission_service

router = APIRouter()


@router.get(
    "/permissions",
    response_model=List[PermissionRead],
    summary="List all system permissions",
)
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PermissionRead]:
    """List all available permissions in the system."""
    permissions = await permission_service.get_all_permissions(db)
    return [PermissionRead.model_validate(p) for p in permissions]


@router.get(
    "/organizations/{org_id}/roles",
    response_model=List[RoleRead],
    summary="List roles for an organization",
)
async def list_roles(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:read")),
) -> List[RoleRead]:
    """List all roles available for an organization (system + custom)."""
    roles = await permission_service.get_roles_for_org(db, org_id)
    return [RoleRead.model_validate(r) for r in roles]


@router.post(
    "/organizations/{org_id}/roles",
    response_model=RoleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a custom role",
)
async def create_role(
    org_id: uuid.UUID,
    data: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:create")),
) -> RoleRead:
    """Create a custom role for the organization."""
    role = await permission_service.create_role(db, org_id, data)
    return RoleRead.model_validate(role)


@router.patch(
    "/organizations/{org_id}/roles/{role_id}",
    response_model=RoleRead,
    summary="Update a role",
)
async def update_role(
    org_id: uuid.UUID,
    role_id: uuid.UUID,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:update")),
) -> RoleRead:
    """Update a custom role. System roles cannot be modified."""
    role = await permission_service.update_role(db, role_id, data)
    return RoleRead.model_validate(role)


@router.delete(
    "/organizations/{org_id}/roles/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a custom role",
)
async def delete_role(
    org_id: uuid.UUID,
    role_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:delete")),
) -> None:
    """Delete a custom role. System roles cannot be deleted."""
    await permission_service.delete_role(db, role_id)
