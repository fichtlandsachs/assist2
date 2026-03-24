import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.role import Role
from app.schemas.organization import OrgCreate, OrgUpdate


class OrgService:
    async def create(
        self,
        db: AsyncSession,
        data: OrgCreate,
        creator_id: uuid.UUID,
    ) -> Organization:
        """
        Create a new organization.
        The creator is automatically added as an active member with the org_owner role.
        Raises ConflictException if slug is already taken.
        """
        # Check for duplicate slug
        existing = await db.execute(
            select(Organization).where(
                Organization.slug == data.slug,
                Organization.deleted_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail=f"Organization slug '{data.slug}' is already taken")

        # Create organization
        org = Organization(
            slug=data.slug,
            name=data.name,
            description=data.description,
        )
        db.add(org)
        await db.flush()

        # Create membership for creator
        membership = Membership(
            user_id=creator_id,
            organization_id=org.id,
            status="active",
            joined_at=datetime.now(timezone.utc),
        )
        db.add(membership)
        await db.flush()

        # Assign org_owner role
        owner_role_result = await db.execute(
            select(Role).where(Role.name == "org_owner", Role.is_system == True)
        )
        owner_role = owner_role_result.scalar_one_or_none()

        if owner_role:
            membership_role = MembershipRole(
                membership_id=membership.id,
                role_id=owner_role.id,
                assigned_by=creator_id,
            )
            db.add(membership_role)

        await db.commit()
        await db.refresh(org)
        return org

    async def get_by_id(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> Organization:
        """Get an organization by ID. Raises NotFoundException if not found."""
        result = await db.execute(
            select(Organization).where(
                Organization.id == org_id,
                Organization.deleted_at.is_(None),
            )
        )
        org = result.scalar_one_or_none()
        if not org:
            raise NotFoundException(detail="Organization not found")
        return org

    async def get_by_slug(
        self,
        db: AsyncSession,
        slug: str,
    ) -> Optional[Organization]:
        """Get an organization by its slug."""
        result = await db.execute(
            select(Organization).where(
                Organization.slug == slug,
                Organization.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Organization]:
        """List all organizations the user is an active member of."""
        result = await db.execute(
            select(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .where(
                Membership.user_id == user_id,
                Membership.status == "active",
                Organization.deleted_at.is_(None),
                Organization.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: OrgUpdate,
    ) -> Organization:
        """Update organization details."""
        org = await self.get_by_id(db, org_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(org, field, value)

        await db.commit()
        await db.refresh(org)
        return org

    async def delete(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> None:
        """Soft-delete an organization."""
        org = await self.get_by_id(db, org_id)
        org.deleted_at = datetime.now(timezone.utc)
        org.is_active = False
        await db.commit()


org_service = OrgService()
