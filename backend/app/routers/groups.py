import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.group import Group, GroupMember
from app.models.user import User
from app.schemas.group import GroupCreate, GroupMemberCreate, GroupMemberRead, GroupRead, GroupUpdate
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get(
    "/organizations/{org_id}/groups",
    response_model=List[GroupRead],
    summary="List groups",
)
async def list_groups(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:read")),
) -> List[GroupRead]:
    """List all groups in an organization."""
    result = await db.execute(
        select(Group)
        .where(Group.organization_id == org_id)
        .order_by(Group.name)
    )
    groups = result.scalars().all()
    return [GroupRead.model_validate(g) for g in groups]


@router.post(
    "/organizations/{org_id}/groups",
    response_model=GroupRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a group",
)
async def create_group(
    org_id: uuid.UUID,
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:create")),
) -> GroupRead:
    """Create a new group in an organization."""
    group = Group(
        organization_id=org_id,
        name=data.name,
        type=data.type,
        description=data.description,
        parent_group_id=data.parent_group_id,
        is_active=True,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return GroupRead.model_validate(group)


@router.get(
    "/organizations/{org_id}/groups/{group_id}",
    response_model=GroupRead,
    summary="Get a group",
)
async def get_group(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:read")),
) -> GroupRead:
    """Get a specific group."""
    result = await db.execute(
        select(Group).where(
            Group.id == group_id,
            Group.organization_id == org_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")
    return GroupRead.model_validate(group)


@router.patch(
    "/organizations/{org_id}/groups/{group_id}",
    response_model=GroupRead,
    summary="Update a group",
)
async def update_group(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:update")),
) -> GroupRead:
    """Update group details."""
    result = await db.execute(
        select(Group).where(
            Group.id == group_id,
            Group.organization_id == org_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return GroupRead.model_validate(group)


@router.delete(
    "/organizations/{org_id}/groups/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a group",
)
async def delete_group(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:delete")),
) -> None:
    """Delete a group."""
    result = await db.execute(
        select(Group).where(
            Group.id == group_id,
            Group.organization_id == org_id,
        )
    )
    group = result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")
    await db.delete(group)
    await db.commit()


@router.get(
    "/organizations/{org_id}/groups/{group_id}/members",
    response_model=List[GroupMemberRead],
    summary="List group members",
)
async def list_group_members(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:read")),
) -> List[GroupMemberRead]:
    """List all members of a group."""
    # Verify group belongs to org
    group_result = await db.execute(
        select(Group).where(Group.id == group_id, Group.organization_id == org_id)
    )
    group = group_result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")

    result = await db.execute(
        select(GroupMember)
        .where(GroupMember.group_id == group_id)
        .options(selectinload(GroupMember.user))
        .order_by(GroupMember.added_at)
    )
    members = result.scalars().all()
    return [GroupMemberRead.model_validate(m) for m in members]


@router.post(
    "/organizations/{org_id}/groups/{group_id}/members",
    response_model=GroupMemberRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a group member",
)
async def add_group_member(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    data: GroupMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:manage")),
) -> GroupMemberRead:
    """Add a user or agent to a group."""
    # Verify group belongs to org
    group_result = await db.execute(
        select(Group).where(Group.id == group_id, Group.organization_id == org_id)
    )
    group = group_result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")

    member = GroupMember(
        group_id=group_id,
        member_type=data.member_type,
        user_id=data.user_id,
        agent_id=data.agent_id,
        role=data.role,
    )
    db.add(member)
    await db.commit()

    # Reload with relations
    result = await db.execute(
        select(GroupMember)
        .where(GroupMember.id == member.id)
        .options(selectinload(GroupMember.user))
    )
    member = result.scalar_one()
    return GroupMemberRead.model_validate(member)


@router.delete(
    "/organizations/{org_id}/groups/{group_id}/members/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a group member",
)
async def remove_group_member(
    org_id: uuid.UUID,
    group_id: uuid.UUID,
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("group:manage")),
) -> None:
    """Remove a member from a group."""
    # Verify group belongs to org
    group_result = await db.execute(
        select(Group).where(Group.id == group_id, Group.organization_id == org_id)
    )
    group = group_result.scalar_one_or_none()
    if not group:
        raise NotFoundException(detail="Group not found")

    member_result = await db.execute(
        select(GroupMember).where(
            GroupMember.id == member_id,
            GroupMember.group_id == group_id,
        )
    )
    member = member_result.scalar_one_or_none()
    if not member:
        raise NotFoundException(detail="Group member not found")

    await db.delete(member)
    await db.commit()
