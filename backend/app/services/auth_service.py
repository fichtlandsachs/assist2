"""Authentication service — proxies all auth operations to Authentik."""
import logging
import secrets
import uuid
from datetime import datetime, timezone, timedelta

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, UnauthorizedException
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


class AuthService:
    async def login(self, db: AsyncSession, data: LoginRequest) -> TokenResponse:
        """
        Authenticate a user.

        1. Look up user in local DB.
        2. Verify password against bcrypt hash.
        3. Create a short-lived Authentik app-password token for that user.
        4. Exchange it via grant_type=password for OIDC tokens.
        5. Delete the app-password token.
        """
        result = await db.execute(
            select(User).where(
                User.email == data.email.lower(),
                User.deleted_at.is_(None),
                User.is_active == True,
            )
        )
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            raise UnauthorizedException(detail="Invalid email or password")

        if not _verify_password(data.password, user.password_hash):
            raise UnauthorizedException(detail="Invalid email or password")

        if not user.authentik_id:
            raise UnauthorizedException(detail="Account not provisioned to identity provider")

        # Authentik pk is stored as string in authentik_id column
        authentik_pk = int(user.authentik_id)
        identifier = f"login-{uuid.uuid4().hex}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=2)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        app_password_key = await authentik_client.create_app_password(
            authentik_pk=authentik_pk,
            identifier=identifier,
            expires=expires,
        )
        try:
            tokens = await authentik_client.authenticate_user(
                username=data.email.lower(),
                app_password=app_password_key,
            )
        finally:
            await authentik_client.delete_app_password(identifier)

        # Update last_login_at
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        return tokens

    async def register(self, db: AsyncSession, data: RegisterRequest) -> TokenResponse:
        """
        Create user in Authentik + local DB.
        Raises ConflictException if email already exists.
        """
        existing = await db.execute(
            select(User).where(User.email == data.email.lower(), User.deleted_at.is_(None))
        )
        if existing.scalar_one_or_none():
            raise ConflictException(detail="An account with this email already exists")

        authentik_id = await authentik_client.create_user(
            email=data.email.lower(),
            password=data.password,
            display_name=data.display_name,
        )

        user = User(
            email=data.email.lower(),
            display_name=data.display_name,
            authentik_id=authentik_id,
            password_hash=_hash_password(data.password),
            is_active=True,
            email_verified=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return await self.login(db, LoginRequest(email=data.email.lower(), password=data.password))

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Refresh token pair via Authentik."""
        return await authentik_client.refresh_token(refresh_token)

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """Revoke refresh token in Authentik."""
        await authentik_client.revoke_token(refresh_token)


auth_service = AuthService()
