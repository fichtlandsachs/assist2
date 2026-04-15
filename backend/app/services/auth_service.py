"""Authentication service — bcrypt password verification + HS256 JWTs."""
import logging
import re
import uuid
from datetime import datetime, timezone

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, UnauthorizedException
from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.organization import OrgCreate
from app.services.authentik_client import authentik_client
from app.services.org_service import org_service

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
        Authenticate a user via bcrypt + issue HS256 JWTs.

        1. Look up user in local DB.
        2. Verify password against bcrypt hash.
        3. Issue HS256 access + refresh tokens.
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

        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

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

        authentik_id: str | None = None
        try:
            authentik_id = await authentik_client.create_user(
                email=data.email.lower(),
                password=data.password,
                display_name=data.display_name,
            )
        except Exception as e:
            logger.warning("Authentik user creation failed (continuing without IdP sync): %s", e)

        locale = data.locale if data.locale in ("de", "en") else "de"
        user = User(
            email=data.email.lower(),
            display_name=data.display_name,
            authentik_id=authentik_id,
            password_hash=_hash_password(data.password),
            is_active=True,
            email_verified=False,
            locale=locale,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Create organization and make user the owner
        base_slug = re.sub(r"[^a-z0-9]+", "-", data.organization_name.lower()).strip("-")
        base_slug = base_slug[:48] if len(base_slug) > 48 else base_slug
        if len(base_slug) < 2:
            base_slug = "org"
        slug = base_slug
        suffix = 0
        while True:
            try:
                await org_service.create(db, OrgCreate(name=data.organization_name, slug=slug), user.id)
                break
            except ConflictException:
                suffix += 1
                slug = f"{base_slug}-{suffix}"

        return await self.login(db, LoginRequest(email=data.email.lower(), password=data.password))

    async def refresh(self, db: AsyncSession, refresh_token: str) -> TokenResponse:
        """Issue a new HS256 access token from a valid refresh token."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedException(detail="Invalid refresh token")
        token_data = {"sub": payload["sub"], "email": payload.get("email", "")}
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)
        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
            token_type="bearer",
        )

    async def logout(self, db: AsyncSession, refresh_token: str) -> None:
        """No-op: stateless HS256 tokens expire on their own."""
        pass


auth_service = AuthService()
