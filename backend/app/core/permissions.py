import json
import logging
import uuid
from typing import Optional

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PERMISSIONS: dict[str, list[str]] = {
    "org_owner": ["*"],
    "org_admin": [
        "org:read", "org:update",
        "membership:read", "membership:invite", "membership:update", "membership:delete",
        "role:read", "role:create", "role:update", "role:delete", "role:assign",
        "group:read", "group:create", "group:update", "group:delete", "group:manage",
        "plugin:read", "plugin:activate", "plugin:configure", "plugin:deactivate",
        "workflow:read", "workflow:create", "workflow:update", "workflow:delete", "workflow:execute",
        "agent:read", "agent:create", "agent:update", "agent:delete", "agent:invoke",
        "story:read", "story:create", "story:update", "story:delete",
        "inbox:read", "inbox:manage", "inbox:update",
        "calendar:read", "calendar:manage", "calendar:create",
    ],
    "org_member": [
        "org:read",
        "membership:read",
        "group:read",
        "plugin:read",
        "workflow:read",
        "agent:read",
        "story:read", "story:create", "story:update",
        "inbox:read", "inbox:update",
        "calendar:read", "calendar:create",
    ],
    "org_guest": [
        "org:read",
        "membership:read",
    ],
}


async def get_redis_client() -> Optional[aioredis.Redis]:
    """Get an async Redis client."""
    try:
        settings = get_settings()
        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return client
    except Exception as e:
        logger.warning(f"Failed to connect to Redis: {e}")
        return None


async def get_user_permissions(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> set[str]:
    """
    Aggregate all permissions for a user in an organization.
    Permissions are fetched from all active roles assigned through memberships.
    Results are cached in Redis with TTL of 300 seconds.
    """
    from app.models.membership import Membership, MembershipRole
    from app.models.role import Role, RolePermission, Permission

    cache_key = f"permissions:{user_id}:{org_id}"

    # Try to get from Redis cache
    redis_client = await get_redis_client()
    if redis_client:
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                await redis_client.aclose()
                return set(json.loads(cached))
        except Exception as e:
            logger.warning(f"Redis cache read failed: {e}")
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass

    # Fetch from database
    stmt = (
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .join(Membership, Membership.id == MembershipRole.membership_id)
        .where(
            Membership.user_id == user_id,
            Membership.organization_id == org_id,
            Membership.status == "active",
        )
    )

    result = await db.execute(stmt)
    permissions_list = result.scalars().all()
    permissions = {f"{p.resource}:{p.action}" for p in permissions_list}

    # Check if user has org_owner role (which grants "*")
    owner_stmt = (
        select(Role)
        .join(MembershipRole, MembershipRole.role_id == Role.id)
        .join(Membership, Membership.id == MembershipRole.membership_id)
        .where(
            Membership.user_id == user_id,
            Membership.organization_id == org_id,
            Membership.status == "active",
            Role.name == "org_owner",
            Role.is_system == True,
        )
    )
    owner_result = await db.execute(owner_stmt)
    if owner_result.scalar_one_or_none():
        permissions.add("*")

    # Cache in Redis
    redis_client = await get_redis_client()
    if redis_client:
        try:
            await redis_client.setex(cache_key, 300, json.dumps(list(permissions)))
        except Exception as e:
            logger.warning(f"Redis cache write failed: {e}")
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass

    return permissions


async def invalidate_permission_cache(user_id: uuid.UUID, org_id: uuid.UUID) -> None:
    """Invalidate the permission cache for a user in an organization."""
    cache_key = f"permissions:{user_id}:{org_id}"
    redis_client = await get_redis_client()
    if redis_client:
        try:
            await redis_client.delete(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate permission cache: {e}")
        finally:
            try:
                await redis_client.aclose()
            except Exception:
                pass
