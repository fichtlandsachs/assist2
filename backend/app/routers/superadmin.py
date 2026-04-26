"""Superadmin endpoints — only accessible to is_superuser users."""
import logging
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.security import validate_admin_token
from app.database import get_db
from app.deps import get_current_user
from app.models.feature import Feature
from app.models.global_config import GlobalConfig
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.user import User
from app.models.user_story import UserStory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/superadmin", tags=["superadmin"])

_security = HTTPBearer()


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Security(_security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate admin OIDC token and ensure user is_superuser."""
    claims = await validate_admin_token(credentials.credentials)
    email = claims.get("email", "")
    result = await db.execute(
        select(User).where(User.email == email, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user or not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return user


async def require_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require standard Authentik JWT + is_superuser=True. Used by new endpoints."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return current_user


# ── Component status ───────────────────────────────────────────────────────────

COMPONENTS = [
    {
        "name": "Authentik",
        "label": "Identity Provider",
        "internal_url": "http://heykarl-authentik-server:9000",
        "health_path": "/-/health/ready/",
        "admin_url": "https://authentik.heykarl.app/if/admin/",
    },
    {
        "name": "n8n",
        "label": "Workflow Engine",
        "internal_url": "http://heykarl-n8n:5678",
        "health_path": "/healthz",
        "admin_url": "https://admin.heykarl.app/n8n/",
    },
    {
        "name": "LiteLLM",
        "label": "AI Proxy",
        "internal_url": "http://heykarl-litellm:4000",
        "health_path": "/health/liveliness",
        "admin_url": "https://admin.heykarl.app/litellm/ui",
    },
    {
        "name": "Nextcloud",
        "label": "Dateiverwaltung",
        "internal_url": "http://heykarl-nextcloud",
        "health_path": "/status.php",
        # Use /login so browser base URL is not …/nextcloud/ (trailing slash), which can
        # mis-resolve relative links to …/nextcloud/Nextcloud (Nextcloud 404).
        "admin_url": "https://admin.heykarl.app/nextcloud/login",
    },
    {
        "name": "Stirling PDF",
        "label": "PDF-Tools",
        "internal_url": "http://heykarl-stirling-pdf:8080",
        "health_path": "/",
        "admin_url": "https://admin.heykarl.app/pdf",
    },
    {
        "name": "Whisper",
        "label": "Transkription",
        "internal_url": "http://heykarl-whisper:9000",
        "health_path": "/",
        "admin_url": "https://admin.heykarl.app/whisper",
    },
    {
        "name": "pgAdmin",
        "label": "PostgreSQL UI",
        "internal_url": "http://heykarl-pgadmin:80",
        "health_path": "/pgadmin/misc/ping",
        "admin_url": "https://admin.heykarl.app/pgadmin",
    },
    {
        "name": "phpMyAdmin",
        "label": "MariaDB UI",
        "internal_url": "http://heykarl-phpmyadmin:80",
        "health_path": "/",
        "admin_url": "https://admin.heykarl.app/phpmyadmin",
    },
    {
        "name": "Redis Commander",
        "label": "Redis UI",
        "internal_url": "http://heykarl-redis-commander:8081",
        "health_path": "/redis/",
        "admin_url": "https://admin.heykarl.app/redis",
    },
]


@router.get("/status")
async def get_component_status(
    _: User = Depends(get_admin_user),
) -> list[dict]:
    """Check reachability of all internal Karl components."""
    results = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for comp in COMPONENTS:
            url = comp["internal_url"].rstrip("/") + "/" + comp["health_path"].lstrip("/")
            try:
                resp = await client.get(url)
                available = resp.status_code < 500
            except Exception:
                available = False

            results.append({
                "name": comp["name"],
                "label": comp["label"],
                "available": available,
                "admin_url": comp["admin_url"],
            })
    return results


# ── Organization resource overview ────────────────────────────────────────────

DEFAULT_PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free":       {"stories": 50,   "members": 5},
    "pro":        {"stories": 500,  "members": 50},
    "enterprise": {"stories": 9999, "members": 9999},
}


async def get_plan_limits(db: AsyncSession) -> dict[str, dict[str, int]]:
    """Return plan limits, overriding defaults with any values stored in global_config."""
    result = await db.execute(
        select(GlobalConfig).where(GlobalConfig.key.like("plans.%"))
    )
    rows = {r.key: r.value for r in result.scalars().all()}

    limits: dict[str, dict[str, int]] = {
        plan: dict(vals) for plan, vals in DEFAULT_PLAN_LIMITS.items()
    }
    for plan in limits:
        for metric in ("stories", "members"):
            key = f"plans.{plan}.{metric}"
            if rows.get(key) is not None:
                try:
                    limits[plan][metric] = int(rows[key])
                except ValueError:
                    pass
    return limits


@router.get("/organizations")
async def get_organizations_overview(
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return all organizations with resource usage metrics (paginated)."""
    PLAN_LIMITS = await get_plan_limits(db)
    stmt = select(Organization).where(Organization.deleted_at.is_(None))
    if search:
        stmt = stmt.where(
            or_(
                Organization.name.ilike(f"%{search}%"),
                Organization.slug.ilike(f"%{search}%"),
            )
        )

    total_res = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total: int = total_res.scalar() or 0

    stmt = stmt.order_by(Organization.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    orgs = result.scalars().all()

    overview = []
    for org in orgs:
        member_count_res = await db.execute(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.organization_id == org.id,
                Membership.status == "active",
            )
        )
        member_count: int = member_count_res.scalar() or 0

        story_count_res = await db.execute(
            select(func.count())
            .select_from(UserStory)
            .where(UserStory.organization_id == org.id)
        )
        story_count: int = story_count_res.scalar() or 0

        feature_count_res = await db.execute(
            select(func.count())
            .select_from(Feature)
            .where(Feature.organization_id == org.id)
        )
        feature_count: int = feature_count_res.scalar() or 0

        # Last login: find the member with the most recent last_login_at
        last_login_res = await db.execute(
            select(User.last_login_at, User.display_name, User.email)
            .join(Membership, Membership.user_id == User.id)
            .where(
                Membership.organization_id == org.id,
                Membership.status == "active",
                User.last_login_at.isnot(None),
            )
            .order_by(User.last_login_at.desc())
            .limit(1)
        )
        last_login_row = last_login_res.first()
        last_login_at = last_login_row[0].isoformat() if last_login_row else None
        last_active_user = last_login_row[1] or last_login_row[2] if last_login_row else None

        plan = org.plan or "free"
        limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
        story_pct = (
            round((story_count / limits["stories"]) * 100)
            if limits["stories"] < 9999
            else 0
        )
        member_pct = (
            round((member_count / limits["members"]) * 100)
            if limits["members"] < 9999
            else 0
        )

        overview.append({
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "plan": plan,
            "is_active": org.is_active,
            "member_count": member_count,
            "story_count": story_count,
            "feature_count": feature_count,
            "story_limit": limits["stories"],
            "member_limit": limits["members"],
            "story_usage_pct": story_pct,
            "member_usage_pct": member_pct,
            "warning": story_pct >= 80 or member_pct >= 80,
            "created_at": org.created_at.isoformat(),
            "last_login_at": last_login_at,
            "last_active_user": last_active_user,
        })
    return {"items": overview, "total": total, "page": page, "page_size": page_size}


@router.get("/organizations/{org_id}", summary="Get single org (superadmin)")
async def get_org_superadmin(
    org_id: uuid.UUID,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    member_count_res = await db.execute(
        select(func.count()).select_from(Membership).where(
            Membership.organization_id == org.id,
            Membership.status == "active",
        )
    )
    member_count: int = member_count_res.scalar() or 0

    story_count_res = await db.execute(
        select(func.count()).select_from(UserStory).where(UserStory.organization_id == org.id)
    )
    story_count: int = story_count_res.scalar() or 0

    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan or "free",
        "is_active": org.is_active,
        "member_count": member_count,
        "story_count": story_count,
        "created_at": org.created_at.isoformat(),
    }


# ── User management ────────────────────────────────────────────────────────────

class SuperAdminUserPatch(BaseModel):
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None


@router.get("/users", summary="List all users (superadmin)")
async def list_all_users(
    search: Optional[str] = None,
    org_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return all non-deleted users with their org memberships."""
    stmt = select(User).where(User.deleted_at.is_(None))
    if search:
        stmt = stmt.where(
            or_(
                User.email.ilike(f"%{search}%"),
                User.display_name.ilike(f"%{search}%"),
            )
        )
    if org_id:
        stmt = stmt.join(Membership, Membership.user_id == User.id).where(
            Membership.organization_id == org_id,
            Membership.status == "active",
        )

    total_res = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total: int = total_res.scalar() or 0

    stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    items = []
    for u in users:
        mem_res = await db.execute(
            select(Membership, Organization)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(
                Membership.user_id == u.id,
                Membership.status == "active",
                Organization.deleted_at.is_(None),
            )
        )
        orgs = [
            {"id": str(org.id), "name": org.name, "slug": org.slug}
            for _, org in mem_res.all()
        ]
        items.append({
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "created_at": u.created_at.isoformat(),
            "organizations": orgs,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/users/{user_id}", summary="Update user (superadmin)")
async def patch_user(
    user_id: uuid.UUID,
    data: SuperAdminUserPatch,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.is_superuser is not None:
        user.is_superuser = data.is_superuser
    await db.commit()
    await db.refresh(user)
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "is_active": user.is_active,
        "is_superuser": user.is_superuser,
        "created_at": user.created_at.isoformat(),
    }


@router.delete("/users/{user_id}", status_code=204, summary="Soft-delete user (superadmin)")
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    result = await db.execute(
        select(User).where(User.id == user_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from datetime import datetime, timezone
    user.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# ── Org management ─────────────────────────────────────────────────────────────

class SuperAdminOrgCreate(BaseModel):
    name: str
    slug: str
    plan: str = "free"


class SuperAdminOrgPatch(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    is_active: Optional[bool] = None


@router.post("/organizations", status_code=201, summary="Create org (superadmin)")
async def create_org_superadmin(
    data: SuperAdminOrgCreate,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    existing = await db.execute(
        select(Organization).where(Organization.slug == data.slug, Organization.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already in use")
    org = Organization(name=data.name, slug=data.slug, plan=data.plan, is_active=True)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "is_active": org.is_active,
        "created_at": org.created_at.isoformat(),
    }


@router.patch("/organizations/{org_id}", summary="Update org (superadmin)")
async def patch_org_superadmin(
    org_id: uuid.UUID,
    data: SuperAdminOrgPatch,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if data.name is not None:
        org.name = data.name
    if data.plan is not None:
        org.plan = data.plan
    if data.is_active is not None:
        org.is_active = data.is_active
    await db.commit()
    await db.refresh(org)
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "plan": org.plan,
        "is_active": org.is_active,
        "created_at": org.created_at.isoformat(),
    }


@router.delete("/organizations/{org_id}", status_code=204, summary="Soft-delete org (superadmin)")
async def delete_org_superadmin(
    org_id: uuid.UUID,
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    from datetime import datetime, timezone
    org.deleted_at = datetime.now(timezone.utc)
    await db.commit()


@router.get("/organizations/{org_id}/integrations", summary="Get org integration settings (superadmin)")
async def get_org_integrations_superadmin(
    org_id: uuid.UUID,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.org_integrations_service import get_all_settings
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return get_all_settings(org)


class OrgJiraPatch(BaseModel):
    base_url: str = ""
    user: str = ""
    api_token: Optional[str] = None


class OrgConfluencePatch(BaseModel):
    base_url: str = ""
    user: str = ""
    api_token: Optional[str] = None
    default_space_key: Optional[str] = None
    default_parent_page_id: Optional[str] = None


class OrgSSOPatch(BaseModel):
    enabled: bool = False
    client_id: str = ""
    client_secret: Optional[str] = None


@router.patch("/organizations/{org_id}/integrations/jira", status_code=204, summary="Update org Jira settings (superadmin)")
async def patch_org_jira_superadmin(
    org_id: uuid.UUID,
    body: OrgJiraPatch,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.services.org_integrations_service import set_jira_settings
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    set_jira_settings(org, body.base_url, body.user, body.api_token)
    await db.commit()


@router.patch("/organizations/{org_id}/integrations/confluence", status_code=204, summary="Update org Confluence settings (superadmin)")
async def patch_org_confluence_superadmin(
    org_id: uuid.UUID,
    body: OrgConfluencePatch,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.services.org_integrations_service import set_confluence_settings
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    set_confluence_settings(org, body.base_url, body.user, body.api_token,
                            body.default_space_key, body.default_parent_page_id)
    await db.commit()


@router.patch("/organizations/{org_id}/integrations/github", status_code=204, summary="Update org GitHub SSO settings (superadmin)")
async def patch_org_github_superadmin(
    org_id: uuid.UUID,
    body: OrgSSOPatch,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.services.org_integrations_service import set_github_settings
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    set_github_settings(org, body.enabled, body.client_id, body.client_secret)
    await db.commit()


@router.patch("/organizations/{org_id}/integrations/atlassian", status_code=204, summary="Update org Atlassian SSO settings (superadmin)")
async def patch_org_atlassian_superadmin(
    org_id: uuid.UUID,
    body: OrgSSOPatch,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    from app.services.org_integrations_service import set_atlassian_settings
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    set_atlassian_settings(org, body.enabled, body.client_id, body.client_secret)
    await db.commit()


@router.get("/organizations/{org_id}/members", summary="List org members (superadmin)")
async def get_org_members_superadmin(
    org_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_superuser),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.services.membership_service import membership_service
    from app.routers.memberships import _membership_to_read
    memberships, total = await membership_service.list(db, org_id, page, page_size)
    items = [_membership_to_read(m).model_dump(mode="json") for m in memberships]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/debug/token-check")
async def debug_token_check(
    credentials: HTTPAuthorizationCredentials = Security(_security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Temporary debug endpoint - shows token validation result."""
    import jwt as pyjwt
    from app.core.security import decode_token, validate_authentik_token
    from app.deps import _lookup_user_hs256, _lookup_user_oidc
    
    token = credentials.credentials
    result = {"token_prefix": token[:20] + "...", "steps": []}
    
    # Step 1: try HS256
    try:
        payload = decode_token(token)
        result["steps"].append({"step": "hs256_decode", "status": "ok", "type": payload.get("type"), "sub": str(payload.get("sub",""))[:20]})
        if payload.get("type") == "access":
            try:
                user = await _lookup_user_hs256(payload, db)
                result["steps"].append({"step": "hs256_user_lookup", "status": "ok", "email": user.email, "is_superuser": user.is_superuser})
                return result
            except Exception as e:
                result["steps"].append({"step": "hs256_user_lookup", "status": "fail", "error": str(e)})
    except Exception as e:
        result["steps"].append({"step": "hs256_decode", "status": "fail", "error": str(e)})
    
    # Step 2: try OIDC
    unverified = pyjwt.decode(token, options={"verify_signature": False})
    result["oidc_raw"] = {
        "aud": unverified.get("aud"),
        "iss": unverified.get("iss"),
        "sub": str(unverified.get("sub",""))[:30],
        "email": unverified.get("email"),
    }
    try:
        payload = await validate_authentik_token(token)
        result["steps"].append({"step": "oidc_decode", "status": "ok"})
        try:
            user = await _lookup_user_oidc(payload, db)
            result["steps"].append({"step": "oidc_user_lookup", "status": "ok", "email": user.email, "is_superuser": user.is_superuser})
        except Exception as e:
            result["steps"].append({"step": "oidc_user_lookup", "status": "fail", "error": str(e)})
    except Exception as e:
        result["steps"].append({"step": "oidc_decode", "status": "fail", "error": str(e)})
    
    return result
