"""Superadmin endpoints — only accessible to is_superuser users via admin OIDC token."""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import validate_admin_token
from app.database import get_db
from app.models.feature import Feature
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


# ── Component status ───────────────────────────────────────────────────────────

COMPONENTS = [
    {
        "name": "Authentik",
        "label": "Identity Provider",
        "internal_url": "http://assist2-authentik-server:9000",
        "health_path": "/-/health/ready/",
        "admin_url": "https://authentik.fichtlworks.com/if/admin/",
    },
    {
        "name": "n8n",
        "label": "Workflow Engine",
        "internal_url": "http://assist2-n8n:5678",
        "health_path": "/healthz",
        "admin_url": None,
    },
    {
        "name": "LiteLLM",
        "label": "AI Proxy",
        "internal_url": "http://assist2-litellm:4000",
        "health_path": "/health/liveliness",
        "admin_url": None,
    },
    {
        "name": "Nextcloud",
        "label": "Dateiverwaltung",
        "internal_url": "http://assist2-nextcloud",
        "health_path": "/status.php",
        "admin_url": "https://nextcloud.fichtlworks.com",
    },
    {
        "name": "Stirling PDF",
        "label": "PDF-Tools",
        "internal_url": "http://assist2-stirling-pdf:8080",
        "health_path": "/api/v1/info",
        "admin_url": None,
    },
    {
        "name": "Whisper",
        "label": "Transkription",
        "internal_url": "http://assist2-whisper:9000",
        "health_path": "/",
        "admin_url": None,
    },
]


@router.get("/status")
async def get_component_status(
    _: User = Depends(get_admin_user),
) -> list[dict]:
    """Check reachability of all internal Assist2 components."""
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

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free":       {"stories": 50,   "members": 5},
    "pro":        {"stories": 500,  "members": 50},
    "enterprise": {"stories": 9999, "members": 9999},
}


@router.get("/organizations")
async def get_organizations_overview(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return all organizations with resource usage metrics."""
    result = await db.execute(
        select(Organization)
        .where(Organization.deleted_at.is_(None))
        .order_by(Organization.created_at)
    )
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
        })
    return overview
