import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.membership import MembershipRole
from app.models.role import RolePermission
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.membership import InviteRequest, MembershipRead, MembershipUpdate, RoleAssignRequest
from app.schemas.role import RoleRead
from app.schemas.user import UserRead
from app.services.membership_service import membership_service

router = APIRouter()


def _membership_to_read(membership) -> MembershipRead:
    """Convert a Membership ORM object to MembershipRead schema."""
    roles = []
    for mr in membership.membership_roles:
        if mr.role:
            perms = [p for p in mr.role.permissions] if hasattr(mr.role, 'permissions') else []
            roles.append(RoleRead(
                id=mr.role.id,
                name=mr.role.name,
                description=mr.role.description,
                is_system=mr.role.is_system,
                organization_id=mr.role.organization_id,
                permissions=[],
            ))

    return MembershipRead(
        id=membership.id,
        user=UserRead.model_validate(membership.user),
        organization_id=membership.organization_id,
        status=membership.status,
        roles=roles,
        joined_at=membership.joined_at,
        invited_at=membership.invited_at,
    )


@router.get(
    "/organizations/{org_id}/members",
    response_model=PaginatedResponse[MembershipRead],
    summary="List organization members",
)
async def list_members(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("membership:read")),
) -> PaginatedResponse[MembershipRead]:
    """List all members of an organization with pagination."""
    memberships, total = await membership_service.list(db, org_id, page, page_size)
    items = [_membership_to_read(m) for m in memberships]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "/organizations/{org_id}/members/invite",
    response_model=MembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member",
)
async def invite_member(
    org_id: uuid.UUID,
    data: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("membership:invite")),
) -> MembershipRead:
    """Invite a user to the organization by email."""
    membership = await membership_service.invite(db, org_id, data, current_user.id)
    # Reload with relations
    memberships, _ = await membership_service.list(db, org_id, 1, 1000)
    for m in memberships:
        if m.id == membership.id:
            return _membership_to_read(m)
    return MembershipRead(
        id=membership.id,
        user=UserRead(
            id=membership.user_id,
            email="",
            display_name="",
            locale="de",
            timezone="Europe/Berlin",
            is_active=False,
            created_at=membership.created_at,
        ),
        organization_id=membership.organization_id,
        status=membership.status,
        roles=[],
        joined_at=membership.joined_at,
        invited_at=membership.invited_at,
    )


@router.patch(
    "/organizations/{org_id}/members/{membership_id}",
    response_model=MembershipRead,
    summary="Update membership status",
)
async def update_membership(
    org_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: MembershipUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("membership:update")),
) -> MembershipRead:
    """Update a membership's status (e.g., suspend or reactivate)."""
    membership = await membership_service.update(db, org_id, membership_id, data)
    memberships, _ = await membership_service.list(db, org_id, 1, 1000)
    for m in memberships:
        if m.id == membership.id:
            return _membership_to_read(m)
    return MembershipRead(
        id=membership.id,
        user=UserRead(
            id=membership.user_id,
            email="",
            display_name="",
            locale="de",
            timezone="Europe/Berlin",
            is_active=True,
            created_at=membership.created_at,
        ),
        organization_id=membership.organization_id,
        status=membership.status,
        roles=[],
        joined_at=membership.joined_at,
        invited_at=membership.invited_at,
    )


@router.delete(
    "/organizations/{org_id}/members/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member",
)
async def remove_member(
    org_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("membership:delete")),
) -> None:
    """Remove a member from the organization."""
    await membership_service.remove(db, org_id, membership_id)


@router.post(
    "/organizations/{org_id}/members/{membership_id}/roles",
    response_model=MembershipRead,
    summary="Assign a role to a member",
)
async def assign_role(
    org_id: uuid.UUID,
    membership_id: uuid.UUID,
    data: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:assign")),
) -> MembershipRead:
    """Assign a role to a membership."""
    await membership_service.assign_role(db, membership_id, data.role_id, current_user.id)
    memberships, _ = await membership_service.list(db, org_id, 1, 1000)
    for m in memberships:
        if m.id == membership_id:
            return _membership_to_read(m)
    raise Exception("Membership not found after role assignment")
