import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from app.core.permissions import invalidate_permission_cache
from app.models.role import Permission, Role, RolePermission
from app.schemas.role import RoleCreate, RoleUpdate


class PermissionService:
    async def get_all_permissions(self, db: AsyncSession) -> List[Permission]:
        """Get all system permissions."""
        result = await db.execute(select(Permission).order_by(Permission.resource, Permission.action))
        return list(result.scalars().all())

    async def get_roles_for_org(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> List[Role]:
        """Get all roles available for an organization (system roles + org-specific roles)."""
        result = await db.execute(
            select(Role)
            .where(
                (Role.organization_id == org_id) | (Role.organization_id.is_(None))
            )
            .options(
                selectinload(Role.role_permissions).selectinload(RolePermission.permission)
            )
            .order_by(Role.is_system.desc(), Role.name)
        )
        return list(result.scalars().all())

    async def get_role_by_id(
        self,
        db: AsyncSession,
        role_id: uuid.UUID,
    ) -> Role:
        """Get a role by ID with its permissions loaded."""
        result = await db.execute(
            select(Role)
            .where(Role.id == role_id)
            .options(
                selectinload(Role.role_permissions).selectinload(RolePermission.permission)
            )
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundException(detail="Role not found")
        return role

    async def create_role(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: RoleCreate,
    ) -> Role:
        """Create a custom role for an organization."""
        role = Role(
            organization_id=org_id,
            name=data.name,
            description=data.description,
            is_system=False,
        )
        db.add(role)
        await db.flush()

        # Assign permissions
        for permission_id in data.permission_ids:
            perm_result = await db.execute(
                select(Permission).where(Permission.id == permission_id)
            )
            perm = perm_result.scalar_one_or_none()
            if perm:
                role_perm = RolePermission(
                    role_id=role.id,
                    permission_id=perm.id,
                )
                db.add(role_perm)

        await db.commit()
        await db.refresh(role)
        return await self.get_role_by_id(db, role.id)

    async def update_role(
        self,
        db: AsyncSession,
        role_id: uuid.UUID,
        data: RoleUpdate,
    ) -> Role:
        """Update a custom role. System roles cannot be modified."""
        role = await self.get_role_by_id(db, role_id)

        if role.is_system:
            raise ForbiddenException(detail="System roles cannot be modified")

        if data.name is not None:
            role.name = data.name
        if data.description is not None:
            role.description = data.description

        # Update permissions if provided
        if data.permission_ids is not None:
            # Remove existing permissions
            await db.execute(
                RolePermission.__table__.delete().where(RolePermission.role_id == role_id)
            )

            # Add new permissions
            for permission_id in data.permission_ids:
                perm_result = await db.execute(
                    select(Permission).where(Permission.id == permission_id)
                )
                perm = perm_result.scalar_one_or_none()
                if perm:
                    role_perm = RolePermission(
                        role_id=role.id,
                        permission_id=perm.id,
                    )
                    db.add(role_perm)

        await db.commit()
        return await self.get_role_by_id(db, role_id)

    async def delete_role(
        self,
        db: AsyncSession,
        role_id: uuid.UUID,
    ) -> None:
        """Delete a custom role. System roles cannot be deleted."""
        role = await self.get_role_by_id(db, role_id)

        if role.is_system:
            raise ForbiddenException(detail="System roles cannot be deleted")

        await db.delete(role)
        await db.commit()

    async def invalidate_permission_cache(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
    ) -> None:
        """Invalidate the Redis permission cache for a user in an org."""
        await invalidate_permission_cache(user_id, org_id)


permission_service = PermissionService()
