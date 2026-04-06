import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.membership import Membership
from app.models.user import User
from app.schemas.user import UserUpdate


class UserService:
    async def get_by_id(self, db: AsyncSession, user_id: uuid.UUID) -> User:
        """Get a user by ID. Raises NotFoundException if not found."""
        result = await db.execute(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundException(detail="User not found")
        return user

    async def get_by_email(
        self, db: AsyncSession, email: str
    ) -> Optional[User]:
        """Get a user by email address."""
        result = await db.execute(
            select(User).where(User.email == email.lower(), User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        data: UserUpdate,
    ) -> User:
        """Update a user's profile fields."""
        user = await self.get_by_id(db, user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await db.commit()
        await db.refresh(user)
        return user

    async def update_password(self, db: AsyncSession, user_id: uuid.UUID, new_hash: str) -> None:
        """Set a new bcrypt password hash for a user."""
        user = await self.get_by_id(db, user_id)
        user.password_hash = new_hash
        await db.commit()

    async def list_org_members(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = "active",
    ) -> List[User]:
        """List all users who are members of an organization."""
        stmt = (
            select(User)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organization_id == org_id,
                User.deleted_at.is_(None),
            )
        )

        if status:
            stmt = stmt.where(Membership.status == status)

        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(stmt)
        return list(result.scalars().all())


user_service = UserService()
