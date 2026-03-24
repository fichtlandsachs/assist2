"""Authentication service — proxies all auth operations to Authentik."""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)


class AuthService:
    async def login(self, db: AsyncSession, data: LoginRequest) -> TokenResponse:
        """Authenticate via Authentik ROPC grant. Returns tokens."""
        tokens = await authentik_client.authenticate_user(data.email, data.password)

        # Update last_login_at for local user if they exist
        result = await db.execute(
            select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            await db.commit()

        return tokens

    async def register(self, db: AsyncSession, data: RegisterRequest) -> TokenResponse:
        """
        Create user in Authentik + local DB.
        Raises ConflictException if email already exists.
        """
        # Check local DB for existing user first (fast path)
        existing = await db.execute(
            select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail="An account with this email already exists")

        # Create in Authentik (source of truth for credentials)
        authentik_id = await authentik_client.create_user(
            email=data.email.lower(),
            password=data.password,
            display_name=data.display_name,
        )

        # Create local user record
        user = User(
            email=data.email.lower(),
            display_name=data.display_name,
            authentik_id=authentik_id,
            is_active=True,
            email_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Get tokens via login
        from app.schemas.auth import LoginRequest as LR
        return await self.login(db, LR(email=data.email, password=data.password))

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Refresh token pair via Authentik."""
        return await authentik_client.refresh_token(refresh_token)

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """Revoke refresh token in Authentik."""
        await authentik_client.revoke_token(refresh_token)


auth_service = AuthService()
