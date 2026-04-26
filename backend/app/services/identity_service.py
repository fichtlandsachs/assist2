"""IdentityContextResolver: resolves and caches zone grants for RAG ACL."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity import AccessContext, IdentityContext
from app.core.permissions import get_redis_client
from app.models.user import User

logger = logging.getLogger(__name__)

_CACHE_TTL = 300
_CACHE_KEY = "rag_identity:{user_id}:{org_id}"

# Grant tuple types
# ActiveGrant: (zone_id, project_scope) — project_scope=None means org-wide
ActiveGrant = tuple[uuid.UUID, uuid.UUID | None]
RevokedGrant = tuple[uuid.UUID, datetime]


class IdentityContextResolver:
    async def resolve(
        self,
        user: User,
        org_id: uuid.UUID,
        ad_groups: list[str],
        db: AsyncSession,
        scope_id: uuid.UUID | None = None,
    ) -> AccessContext:
        if user.is_superuser:
            return AccessContext(
                identity=IdentityContext(
                    user_id=user.id,
                    org_id=org_id,
                    ad_groups=[],
                    zone_ids=[],
                    is_superuser=True,
                )
            )

        active_grants, revoked_grants = await self._load_grants(user.id, org_id, ad_groups, db)
        zone_ids = _filter_active_zones(active_grants, scope_id)

        return AccessContext(
            identity=IdentityContext(
                user_id=user.id,
                org_id=org_id,
                ad_groups=ad_groups,
                zone_ids=zone_ids,
                is_superuser=False,
            ),
            revoked_grants=revoked_grants,
        )

    async def _load_grants(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        ad_groups: list[str],
        db: AsyncSession,
    ) -> tuple[list[ActiveGrant], list[RevokedGrant]]:
        """Load from Redis cache or DB. Cache is scope-agnostic; scope filtering happens in resolve()."""
        cache_key = _CACHE_KEY.format(user_id=user_id, org_id=org_id)
        redis = await get_redis_client()
        if redis:
            try:
                cached = await redis.get(cache_key)
                if cached:
                    return _deserialize(cached)
            except Exception as e:
                logger.warning("rag_identity: Redis read failed: %s", e)
            finally:
                try:
                    await redis.aclose()
                except Exception:
                    pass

        active_grants, revoked_grants = await self._resolve_grants(user_id, org_id, ad_groups, db)

        redis = await get_redis_client()
        if redis:
            try:
                await redis.setex(cache_key, _CACHE_TTL, _serialize(active_grants, revoked_grants))
            except Exception as e:
                logger.warning("rag_identity: Redis write failed: %s", e)
            finally:
                try:
                    await redis.aclose()
                except Exception:
                    pass

        return active_grants, revoked_grants

    async def _resolve_grants(
        self,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        ad_groups: list[str],
        db: AsyncSession,
    ) -> tuple[list[ActiveGrant], list[RevokedGrant]]:
        """
        Query all zone grants from three sources:
        1. AD groups → rag_zone_memberships (always org-wide, no project scope)
        2. user_zone_access (direct grants, may have project_scope; soft-revocable)
        3. hk_role_assignments → hk_role_zone_grants (role-based, may have scope_id)
        """
        active: dict[uuid.UUID, uuid.UUID | None] = {}   # zone_id → project_scope
        revoked: list[RevokedGrant] = []
        now = datetime.now(timezone.utc)

        # Source 1: AD groups → rag_zone_memberships (org-wide, always active)
        # HS256/legacy tokens carry no groups claim → ad_groups is [].
        # These users see only NULL-zone (public) chunks — zone ACL requires OIDC tokens.
        if ad_groups:
            try:
                result = await db.execute(
                    text("""
                        SELECT DISTINCT rzm.zone_id
                        FROM rag_zone_memberships rzm
                        JOIN rag_zones rz ON rzm.zone_id = rz.id
                        WHERE rz.organization_id = :org_id
                          AND rz.is_active = TRUE
                          AND rzm.ad_group_name = ANY(:ad_groups)
                    """),
                    {"org_id": str(org_id), "ad_groups": ad_groups},
                )
                for row in result.fetchall():
                    active[row[0]] = None  # org-wide
            except Exception as e:
                logger.warning("rag_identity: AD zone resolution failed: %s", e)

        # Source 2: Direct user_zone_access grants (project-scoped or org-wide)
        # valid_to / revoked_at semantics: if set and in the future → still active;
        # if set and in the past → soft-revoked (historical access retained).
        try:
            result = await db.execute(
                text("""
                    SELECT zone_id, project_scope, revoked_at
                    FROM user_zone_access
                    WHERE user_id = :user_id
                      AND org_id  = :org_id
                """),
                {"user_id": str(user_id), "org_id": str(org_id)},
            )
            for row in result.fetchall():
                if row.revoked_at is None or row.revoked_at > now:
                    # Active: null revoked_at (permanent) or future valid_to (not yet expired)
                    if row.zone_id not in active:
                        active[row.zone_id] = row.project_scope
                else:
                    revoked.append((row.zone_id, row.revoked_at))
        except Exception as e:
            logger.warning("rag_identity: user_zone_access resolution failed: %s", e)

        # Source 3: hk_role_assignments → hk_role_zone_grants
        # Governance: ad_group_only zones are not reachable via hk roles.
        try:
            result = await db.execute(
                text("""
                    SELECT DISTINCT rzg.zone_id, ra.scope_id
                    FROM hk_role_zone_grants rzg
                    JOIN hk_role_assignments ra
                      ON ra.role_name = rzg.role_name
                     AND ra.org_id    = rzg.org_id
                    JOIN rag_zones rz ON rzg.zone_id = rz.id
                    WHERE ra.user_id   = :user_id
                      AND ra.org_id    = :org_id
                      AND rz.is_active      = TRUE
                      AND rz.ad_group_only  = FALSE
                      AND (ra.valid_to IS NULL OR ra.valid_to > now())
                """),
                {"user_id": str(user_id), "org_id": str(org_id)},
            )
            for row in result.fetchall():
                if row.zone_id not in active:
                    active[row.zone_id] = row.scope_id  # scope_id=None means org-wide
        except Exception as e:
            logger.warning("rag_identity: hk_role zone resolution failed: %s", e)

        return list(active.items()), revoked

    async def invalidate(self, user_id: uuid.UUID, org_id: uuid.UUID) -> None:
        cache_key = _CACHE_KEY.format(user_id=user_id, org_id=org_id)
        redis = await get_redis_client()
        if redis:
            try:
                await redis.delete(cache_key)
            except Exception as e:
                logger.warning("rag_identity: cache invalidation failed: %s", e)
            finally:
                try:
                    await redis.aclose()
                except Exception:
                    pass


# ── Helpers ────────────────────────────────────────────────────────────────────

def _filter_active_zones(
    active_grants: list[ActiveGrant],
    scope_id: uuid.UUID | None,
) -> list[uuid.UUID]:
    """
    Filter active grants by request scope:
    - scope_id=None → only org-wide grants (project_scope IS NULL)
    - scope_id set  → org-wide grants + grants matching that project
    """
    result: set[uuid.UUID] = set()
    for zone_id, project_scope in active_grants:
        if project_scope is None:
            result.add(zone_id)
        elif scope_id is not None and project_scope == scope_id:
            result.add(zone_id)
    return list(result)


def _serialize(
    active_grants: list[ActiveGrant],
    revoked_grants: list[RevokedGrant],
) -> str:
    return json.dumps({
        "active_grants": [
            {"zone_id": str(z), "project_scope": str(s) if s else None}
            for z, s in active_grants
        ],
        "revoked_grants": [
            {"zone_id": str(z), "revoked_at": ts.isoformat()}
            for z, ts in revoked_grants
        ],
    })


def _deserialize(raw: str) -> tuple[list[ActiveGrant], list[RevokedGrant]]:
    data = json.loads(raw)
    active = [
        (uuid.UUID(g["zone_id"]), uuid.UUID(g["project_scope"]) if g["project_scope"] else None)
        for g in data.get("active_grants", [])
    ]
    revoked = [
        (uuid.UUID(g["zone_id"]), datetime.fromisoformat(g["revoked_at"]))
        for g in data.get("revoked_grants", [])
    ]
    return active, revoked


identity_resolver = IdentityContextResolver()
