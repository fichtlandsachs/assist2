# app/routers/platform.py
"""
Platform Management API — Superadmin and OrgAdmin endpoints.

SuperAdmin routes (require superadmin role):
  GET    /api/v1/platform/components
  POST   /api/v1/platform/components/{slug}/seed
  POST   /api/v1/platform/seed
  GET    /api/v1/platform/features
  PATCH  /api/v1/platform/features/{slug}

  GET    /api/v1/platform/orgs/{org_id}/components
  POST   /api/v1/platform/orgs/{org_id}/components
  PATCH  /api/v1/platform/orgs/{org_id}/components/{slug}

  GET    /api/v1/platform/orgs/{org_id}/feature-overrides
  POST   /api/v1/platform/feature-overrides/{override_id}/approve

OrgAdmin routes (require org membership with admin role):
  GET    /api/v1/platform/my-org/components          (active for this org)
  GET    /api/v1/platform/my-org/effective-features  (effective feature map)
  PATCH  /api/v1/platform/my-org/feature-overrides   (subject to policy)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.platform import (
    Component, FeatureFlag, OrgComponent, OrgFeatureOverride,
    OverridePolicy, OrgComponentStatus,
)
from app.models.membership import Membership
from app.models.organization import Organization
from app.services.platform_service import (
    seed_platform, get_effective_features,
    grant_component, revoke_component, set_org_feature_override,
    approve_feature_override,
)
from app.routers.superadmin import get_admin_user

router = APIRouter(prefix="/platform", tags=["Platform"])


# ── Integrity endpoints ───────────────────────────────────────────────────────

@router.get("/integrity/story-stats")
async def story_integrity_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return soft-delete statistics for user_stories."""
    from sqlalchemy import func, text
    from app.models.user_story import UserStory

    total = await db.scalar(select(func.count(UserStory.id))) or 0
    deleted = await db.scalar(
        select(func.count(UserStory.id)).where(UserStory.is_deleted == True)  # noqa: E712
    ) or 0
    oldest_row = await db.execute(
        select(UserStory.deleted_at)
        .where(UserStory.is_deleted == True)  # noqa: E712
        .order_by(UserStory.deleted_at.asc())
        .limit(1)
    )
    newest_row = await db.execute(
        select(UserStory.deleted_at)
        .where(UserStory.is_deleted == True)  # noqa: E712
        .order_by(UserStory.deleted_at.desc())
        .limit(1)
    )
    oldest = oldest_row.scalar_one_or_none()
    newest = newest_row.scalar_one_or_none()
    return {
        "total_stories": total,
        "deleted_stories": deleted,
        "deleted_percentage": round(deleted / total * 100, 2) if total > 0 else 0,
        "oldest_deletion": oldest.isoformat() if oldest else None,
        "newest_deletion": newest.isoformat() if newest else None,
    }


@router.delete("/integrity/purge-deleted-stories")
async def purge_deleted_stories(
    days_old: int = 90,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Hard-delete soft-deleted stories older than days_old days.
    IRREVERSIBLE. Only run after confirming soft-delete audit trail.
    """
    from datetime import timedelta
    from sqlalchemy import delete
    from app.models.user_story import UserStory

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)
    result = await db.execute(
        delete(UserStory).where(
            UserStory.is_deleted == True,  # noqa: E712
            UserStory.deleted_at < cutoff,
        )
    )
    await db.commit()
    return {"purged": result.rowcount, "cutoff": cutoff.isoformat()}


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def _get_org_admin(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Verify that current_user is an admin of the given org."""
    result = await db.execute(
        select(Membership).where(
            Membership.organization_id == org_id,
            Membership.user_id == current_user.id,
        )
    )
    m = result.scalar_one_or_none()
    if not m or m.role not in ("admin", "owner"):
        raise HTTPException(403, "Org admin access required")
    return current_user


# ── Schemas ───────────────────────────────────────────────────────────────────

class ComponentOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str]
    status: str
    display_order: int
    is_core: bool
    feature_count: int


class FeatureOut(BaseModel):
    id: str
    slug: str
    name: str
    description: Optional[str]
    component_slug: str
    default_enabled: bool
    override_policy: str


class FeaturePatch(BaseModel):
    default_enabled: Optional[bool] = None
    override_policy: Optional[str] = None
    description: Optional[str] = None


class OrgComponentOut(BaseModel):
    component_slug: str
    component_name: str
    status: str
    licensed_until: Optional[datetime]
    notes: Optional[str]


class OrgComponentGrant(BaseModel):
    component_slug: str
    status: str = OrgComponentStatus.active.value
    licensed_until: Optional[datetime] = None
    notes: Optional[str] = None


class OrgComponentPatch(BaseModel):
    status: Optional[str] = None
    licensed_until: Optional[datetime] = None
    notes: Optional[str] = None


class OrgFeatureOverrideIn(BaseModel):
    feature_slug: str
    is_enabled: Optional[bool] = None
    config_override: Optional[dict] = None


class OrgFeatureOverrideOut(BaseModel):
    id: str
    feature_slug: str
    component_slug: str
    is_enabled: Optional[bool]
    config_override: Optional[dict]
    approval_status: str
    policy: str


class EffectiveFeature(BaseModel):
    slug: str
    enabled: bool
    config: dict
    policy: str
    component_slug: str
    component_active: bool


# ── SuperAdmin: Component catalogue ───────────────────────────────────────────

@router.post("/seed")
async def seed_platform_data(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed all built-in components and feature flags. Idempotent."""
    result = await seed_platform(db)
    await db.commit()
    return result


@router.get("/components")
async def list_components(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[ComponentOut]:
    result = await db.execute(
        select(Component)
        .options(selectinload(Component.features))
        .order_by(Component.display_order)
    )
    return [
        ComponentOut(
            id=str(c.id), slug=c.slug, name=c.name,
            description=c.description, status=c.status,
            display_order=c.display_order, is_core=c.is_core,
            feature_count=len(c.features),
        )
        for c in result.scalars().all()
    ]


@router.get("/features")
async def list_features(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[FeatureOut]:
    result = await db.execute(
        select(FeatureFlag)
        .options(selectinload(FeatureFlag.component))
        .order_by(FeatureFlag.slug)
    )
    return [
        FeatureOut(
            id=str(f.id), slug=f.slug, name=f.name,
            description=f.description, component_slug=f.component.slug,
            default_enabled=f.default_enabled, override_policy=f.override_policy,
        )
        for f in result.scalars().all()
    ]


@router.patch("/features/{slug}")
async def patch_feature(
    slug: str,
    payload: FeaturePatch,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> FeatureOut:
    feat = await db.scalar(select(FeatureFlag).where(FeatureFlag.slug == slug))
    if not feat:
        raise HTTPException(404, "Feature not found")

    if payload.default_enabled is not None:
        feat.default_enabled = payload.default_enabled
    if payload.override_policy is not None:
        try:
            OverridePolicy(payload.override_policy)
        except ValueError:
            raise HTTPException(422, f"Invalid policy: {payload.override_policy}")
        feat.override_policy = payload.override_policy
    if payload.description is not None:
        feat.description = payload.description

    await db.commit()
    await db.refresh(feat)
    comp = await db.get(Component, feat.component_id)
    return FeatureOut(
        id=str(feat.id), slug=feat.slug, name=feat.name,
        description=feat.description, component_slug=comp.slug if comp else "",
        default_enabled=feat.default_enabled, override_policy=feat.override_policy,
    )


# ── SuperAdmin: Org component licensing ───────────────────────────────────────

@router.get("/orgs/{org_id}/components")
async def get_org_components(
    org_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgComponentOut]:
    result = await db.execute(
        select(OrgComponent, Component)
        .join(Component, OrgComponent.component_id == Component.id)
        .where(OrgComponent.org_id == org_id)
        .order_by(Component.display_order)
    )
    return [
        OrgComponentOut(
            component_slug=comp.slug, component_name=comp.name,
            status=oc.status, licensed_until=oc.licensed_until, notes=oc.notes,
        )
        for oc, comp in result.fetchall()
    ]


@router.post("/orgs/{org_id}/components")
async def grant_org_component(
    org_id: uuid.UUID,
    payload: OrgComponentGrant,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> OrgComponentOut:
    try:
        oc = await grant_component(
            db, org_id, payload.component_slug,
            granted_by_id=admin.id,
            status=payload.status,
            licensed_until=payload.licensed_until,
            notes=payload.notes,
        )
        await db.commit()
        comp = await db.get(Component, oc.component_id)
        return OrgComponentOut(
            component_slug=comp.slug if comp else payload.component_slug,
            component_name=comp.name if comp else "",
            status=oc.status, licensed_until=oc.licensed_until, notes=oc.notes,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.patch("/orgs/{org_id}/components/{slug}")
async def patch_org_component(
    org_id: uuid.UUID,
    slug: str,
    payload: OrgComponentPatch,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> OrgComponentOut:
    comp = await db.scalar(select(Component).where(Component.slug == slug))
    if not comp:
        raise HTTPException(404, "Component not found")
    oc = await db.scalar(
        select(OrgComponent).where(
            OrgComponent.org_id == org_id,
            OrgComponent.component_id == comp.id,
        )
    )
    if not oc:
        raise HTTPException(404, "Org does not have this component")
    if payload.status:
        oc.status = payload.status
    if payload.licensed_until is not None:
        oc.licensed_until = payload.licensed_until
    if payload.notes is not None:
        oc.notes = payload.notes
    await db.commit()
    return OrgComponentOut(
        component_slug=comp.slug, component_name=comp.name,
        status=oc.status, licensed_until=oc.licensed_until, notes=oc.notes,
    )


@router.delete("/orgs/{org_id}/components/{slug}")
async def revoke_org_component(
    org_id: uuid.UUID,
    slug: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await revoke_component(db, org_id, slug)
    await db.commit()
    return {"status": "disabled"}


# ── SuperAdmin: Feature override approval ─────────────────────────────────────

@router.get("/orgs/{org_id}/feature-overrides")
async def get_org_feature_overrides(
    org_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrgFeatureOverrideOut]:
    result = await db.execute(
        select(OrgFeatureOverride, FeatureFlag, Component)
        .join(FeatureFlag, OrgFeatureOverride.feature_id == FeatureFlag.id)
        .join(Component, FeatureFlag.component_id == Component.id)
        .where(OrgFeatureOverride.org_id == org_id)
        .order_by(Component.display_order, FeatureFlag.slug)
    )
    return [
        OrgFeatureOverrideOut(
            id=str(o.id), feature_slug=f.slug, component_slug=c.slug,
            is_enabled=o.is_enabled, config_override=o.config_override,
            approval_status=o.approval_status, policy=f.override_policy,
        )
        for o, f, c in result.fetchall()
    ]


@router.post("/feature-overrides/{override_id}/approve")
async def approve_override(
    override_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        await approve_feature_override(db, override_id, admin.id)
        await db.commit()
        return {"status": "approved"}
    except ValueError as e:
        raise HTTPException(404, str(e))


# ── OrgAdmin: My-org effective features ───────────────────────────────────────

@router.get("/my-org/{org_id}/components")
async def get_my_org_components(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrgComponentOut]:
    await _get_org_admin(org_id, current_user, db)
    result = await db.execute(
        select(OrgComponent, Component)
        .join(Component, OrgComponent.component_id == Component.id)
        .where(
            OrgComponent.org_id == org_id,
            OrgComponent.status.in_([OrgComponentStatus.active.value, OrgComponentStatus.trial.value]),
        )
        .order_by(Component.display_order)
    )
    return [
        OrgComponentOut(
            component_slug=comp.slug, component_name=comp.name,
            status=oc.status, licensed_until=oc.licensed_until, notes=oc.notes,
        )
        for oc, comp in result.fetchall()
    ]


@router.get("/my-org/{org_id}/effective-features")
async def get_my_org_effective_features(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[EffectiveFeature]:
    await _get_org_admin(org_id, current_user, db)
    effective = await get_effective_features(db, org_id)
    return [
        EffectiveFeature(
            slug=slug,
            enabled=v["enabled"],
            config=v["config"],
            policy=v["policy"],
            component_slug=v["component_slug"],
            component_active=v["component_active"],
        )
        for slug, v in sorted(effective.items())
    ]


@router.patch("/my-org/{org_id}/feature-overrides")
async def set_my_org_feature_override(
    org_id: uuid.UUID,
    payload: OrgFeatureOverrideIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_org_admin(org_id, current_user, db)
    try:
        result = await set_org_feature_override(
            db, org_id,
            feature_slug=payload.feature_slug,
            is_enabled=payload.is_enabled,
            config_override=payload.config_override,
            changed_by_id=current_user.id,
        )
        await db.commit()
        return result
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/my-org/{org_id}/feature-overrides")
async def get_my_org_feature_overrides(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[OrgFeatureOverrideOut]:
    await _get_org_admin(org_id, current_user, db)
    result = await db.execute(
        select(OrgFeatureOverride, FeatureFlag, Component)
        .join(FeatureFlag, OrgFeatureOverride.feature_id == FeatureFlag.id)
        .join(Component, FeatureFlag.component_id == Component.id)
        .where(OrgFeatureOverride.org_id == org_id)
        .order_by(Component.display_order, FeatureFlag.slug)
    )
    return [
        OrgFeatureOverrideOut(
            id=str(o.id), feature_slug=f.slug, component_slug=c.slug,
            is_enabled=o.is_enabled, config_override=o.config_override,
            approval_status=o.approval_status, policy=f.override_policy,
        )
        for o, f, c in result.fetchall()
    ]
