import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.core.permissions import invalidate_permission_cache
from app.models.membership import Membership, MembershipRole
from app.models.role import Role
from app.models.user import User
from app.schemas.membership import InviteRequest, MembershipUpdate


class MembershipService:
    async def invite(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: InviteRequest,
        inviter_id: uuid.UUID,
    ) -> Membership:
        """
        Invite a user to an organization.
        If the user doesn't exist, a placeholder account is created.
        """
        # Find or create user by email
        user_result = await db.execute(
            select(User).where(
                User.email == data.email.lower(),
                User.deleted_at.is_(None),
            )
        )
        user = user_result.scalar_one_or_none()

        if not user:
            # Create placeholder user
            user = User(
                email=data.email.lower(),
                display_name=data.email.split("@")[0],
                is_active=False,
                email_verified=False,
            )
            db.add(user)
            await db.flush()

        # Check if membership already exists
        existing_result = await db.execute(
            select(Membership).where(
                Membership.user_id == user.id,
                Membership.organization_id == org_id,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            raise ConflictException(detail="User is already a member or has a pending invitation")

        # Create membership with invited status
        membership = Membership(
            user_id=user.id,
            organization_id=org_id,
            status="invited",
            invited_by=inviter_id,
            invited_at=datetime.now(timezone.utc),
        )
        db.add(membership)
        await db.flush()

        # Assign roles
        for role_id in data.role_ids:
            role_result = await db.execute(select(Role).where(Role.id == role_id))
            role = role_result.scalar_one_or_none()
            if role:
                membership_role = MembershipRole(
                    membership_id=membership.id,
                    role_id=role.id,
                    assigned_by=inviter_id,
                )
                db.add(membership_role)

        await db.commit()
        await db.refresh(membership)
        return membership

    async def accept(
        self,
        db: AsyncSession,
        membership_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Membership:
        """Accept a membership invitation."""
        result = await db.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.user_id == user_id,
                Membership.status == "invited",
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise NotFoundException(detail="Invitation not found")

        membership.status = "active"
        membership.joined_at = datetime.now(timezone.utc)

        await db.commit()
        await db.refresh(membership)
        return membership

    async def update(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
        data: MembershipUpdate,
    ) -> Membership:
        """Update membership status."""
        result = await db.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.organization_id == org_id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise NotFoundException(detail="Membership not found")

        if data.status is not None:
            membership.status = data.status

        await db.commit()
        await db.refresh(membership)

        # Invalidate permission cache
        await invalidate_permission_cache(membership.user_id, org_id)

        return membership

    async def remove(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> None:
        """Remove a membership from an organization."""
        result = await db.execute(
            select(Membership).where(
                Membership.id == membership_id,
                Membership.organization_id == org_id,
            )
        )
        membership = result.scalar_one_or_none()

        if not membership:
            raise NotFoundException(detail="Membership not found")

        user_id = membership.user_id
        await db.delete(membership)
        await db.commit()

        # Invalidate permission cache
        await invalidate_permission_cache(user_id, org_id)

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Membership], int]:
        """List memberships for an organization with pagination."""
        # Count total
        count_result = await db.execute(
            select(func.count(Membership.id)).where(
                Membership.organization_id == org_id
            )
        )
        total = count_result.scalar_one()

        # Fetch with relations
        result = await db.execute(
            select(Membership)
            .where(Membership.organization_id == org_id)
            .options(
                selectinload(Membership.user),
                selectinload(Membership.membership_roles).selectinload(MembershipRole.role),
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        memberships = list(result.scalars().all())
        return memberships, total

    async def assign_role(
        self,
        db: AsyncSession,
        membership_id: uuid.UUID,
        role_id: uuid.UUID,
        assigner_id: uuid.UUID,
    ) -> MembershipRole:
        """Assign a role to a membership."""
        # Verify membership exists
        membership_result = await db.execute(
            select(Membership).where(Membership.id == membership_id)
        )
        membership = membership_result.scalar_one_or_none()

        if not membership:
            raise NotFoundException(detail="Membership not found")

        # Verify role exists
        role_result = await db.execute(select(Role).where(Role.id == role_id))
        role = role_result.scalar_one_or_none()

        if not role:
            raise NotFoundException(detail="Role not found")

        # Check if already assigned
        existing_result = await db.execute(
            select(MembershipRole).where(
                MembershipRole.membership_id == membership_id,
                MembershipRole.role_id == role_id,
            )
        )
        if existing_result.scalar_one_or_none():
            raise ConflictException(detail="Role already assigned to this membership")

        membership_role = MembershipRole(
            membership_id=membership_id,
            role_id=role_id,
            assigned_by=assigner_id,
        )
        db.add(membership_role)
        await db.commit()
        await db.refresh(membership_role)

        # Invalidate permission cache
        await invalidate_permission_cache(membership.user_id, membership.organization_id)

        return membership_role


membership_service = MembershipService()
