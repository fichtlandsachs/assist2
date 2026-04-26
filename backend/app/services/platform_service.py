# app/services/platform_service.py
"""
Platform Service — manages components, feature flags, org licensing,
effective configuration computation, and override policy enforcement.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.platform import (
    BUILT_IN_COMPONENTS, BUILT_IN_FEATURES,
    Component, FeatureFlag, OrgComponent, OrgFeatureOverride,
    OrgComponentStatus, OverridePolicy,
)

logger = logging.getLogger(__name__)


# ── Seed ─────────────────────────────────────────────────────────────────────

async def seed_platform(db: AsyncSession) -> dict:
    """Idempotently seed built-in components and feature flags."""
    components_created = 0
    features_created = 0

    comp_map: dict[str, Component] = {}

    for c_data in BUILT_IN_COMPONENTS:
        existing = await db.scalar(
            select(Component).where(Component.slug == c_data["slug"])
        )
        if not existing:
            comp = Component(**c_data)
            db.add(comp)
            await db.flush()
            comp_map[c_data["slug"]] = comp
            components_created += 1
        else:
            comp_map[c_data["slug"]] = existing

    for f_data in BUILT_IN_FEATURES:
        slug = f_data["slug"]
        comp_slug = f_data["component_slug"]
        comp = comp_map.get(comp_slug)
        if not comp:
            continue
        existing = await db.scalar(
            select(FeatureFlag).where(FeatureFlag.slug == slug)
        )
        if not existing:
            db.add(FeatureFlag(
                component_id=comp.id,
                slug=slug,
                name=f_data["name"],
                default_enabled=f_data["default_enabled"],
                override_policy=f_data["policy"],
            ))
            features_created += 1

    await db.flush()
    logger.info("Platform seeded: %d components, %d features", components_created, features_created)
    return {"components_created": components_created, "features_created": features_created}


# ── Effective feature resolution ──────────────────────────────────────────────

async def get_effective_features(
    db: AsyncSession,
    org_id: uuid.UUID,
) -> dict[str, dict]:
    """
    Return the effective feature map for an org.

    Resolution order:
    1. Check if the org has the component licensed (OrgComponent.status == active|trial)
    2. Apply FeatureFlag.default_enabled
    3. Apply OrgFeatureOverride (if policy allows and approval_status == approved)

    Returns: {feature_slug: {enabled, config, policy, component_slug, component_active}}
    """
    # 1. Load all features with their components
    features_result = await db.execute(
        select(FeatureFlag).options(selectinload(FeatureFlag.component))
    )
    all_features = features_result.scalars().all()

    # 2. Load org's licensed components
    org_comps_result = await db.execute(
        select(OrgComponent)
        .join(Component, OrgComponent.component_id == Component.id)
        .where(OrgComponent.org_id == org_id)
    )
    licensed_comp_ids: set[uuid.UUID] = set()
    for oc in org_comps_result.scalars().all():
        # active or trial
        if oc.status in (OrgComponentStatus.active.value, OrgComponentStatus.trial.value):
            # Check license expiry
            if oc.licensed_until is None or oc.licensed_until > datetime.now(timezone.utc):
                licensed_comp_ids.add(oc.component_id)

    # 3. Load org's feature overrides (approved only)
    overrides_result = await db.execute(
        select(OrgFeatureOverride).where(
            OrgFeatureOverride.org_id == org_id,
            OrgFeatureOverride.approval_status == "approved",
        )
    )
    overrides: dict[uuid.UUID, OrgFeatureOverride] = {
        o.feature_id: o for o in overrides_result.scalars().all()
    }

    effective: dict[str, dict] = {}
    for feat in all_features:
        comp = feat.component
        comp_active = comp.id in licensed_comp_ids

        # Base value from global default
        enabled = feat.default_enabled and comp_active
        config = feat.default_config or {}

        # Apply org override
        override = overrides.get(feat.id)
        policy = OverridePolicy(feat.override_policy)

        if override and comp_active:
            if policy == OverridePolicy.locked:
                pass  # ignore override
            elif policy == OverridePolicy.disable_only:
                if override.is_enabled is False:
                    enabled = False
            elif policy == OverridePolicy.approval_required:
                if override.is_enabled is not None:
                    enabled = override.is_enabled
                if override.config_override:
                    config = {**config, **override.config_override}
            else:  # overridable, extend_only
                if override.is_enabled is not None:
                    enabled = override.is_enabled
                if override.config_override:
                    if policy == OverridePolicy.extend_only:
                        # Merge (extend), don't replace
                        merged = {**config}
                        for k, v in override.config_override.items():
                            if k not in merged:
                                merged[k] = v
                            elif isinstance(merged[k], list) and isinstance(v, list):
                                merged[k] = merged[k] + [x for x in v if x not in merged[k]]
                        config = merged
                    else:
                        config = {**config, **override.config_override}

        effective[feat.slug] = {
            "enabled": enabled,
            "config": config,
            "policy": feat.override_policy,
            "component_slug": comp.slug,
            "component_active": comp_active,
            "feature_id": str(feat.id),
        }

    return effective


async def is_feature_enabled(
    db: AsyncSession,
    org_id: uuid.UUID,
    feature_slug: str,
) -> bool:
    """Quick check if a single feature is enabled for an org."""
    effective = await get_effective_features(db, org_id)
    return effective.get(feature_slug, {}).get("enabled", False)


# ── OrgComponent management ───────────────────────────────────────────────────

async def grant_component(
    db: AsyncSession,
    org_id: uuid.UUID,
    component_slug: str,
    granted_by_id: uuid.UUID,
    status: str = OrgComponentStatus.active.value,
    licensed_until: Optional[datetime] = None,
    notes: Optional[str] = None,
) -> OrgComponent:
    comp = await db.scalar(
        select(Component).where(Component.slug == component_slug)
    )
    if not comp:
        raise ValueError(f"Component '{component_slug}' not found")

    existing = await db.scalar(
        select(OrgComponent).where(
            OrgComponent.org_id == org_id,
            OrgComponent.component_id == comp.id,
        )
    )
    if existing:
        existing.status = status
        existing.licensed_until = licensed_until
        existing.granted_by_id = granted_by_id
        existing.notes = notes
        await db.flush()
        return existing

    oc = OrgComponent(
        org_id=org_id,
        component_id=comp.id,
        status=status,
        licensed_until=licensed_until,
        granted_by_id=granted_by_id,
        notes=notes,
    )
    db.add(oc)
    await db.flush()
    return oc


async def revoke_component(
    db: AsyncSession,
    org_id: uuid.UUID,
    component_slug: str,
) -> bool:
    comp = await db.scalar(
        select(Component).where(Component.slug == component_slug)
    )
    if not comp:
        return False
    existing = await db.scalar(
        select(OrgComponent).where(
            OrgComponent.org_id == org_id,
            OrgComponent.component_id == comp.id,
        )
    )
    if existing:
        existing.status = OrgComponentStatus.disabled.value
        await db.flush()
    return True


# ── OrgFeatureOverride management ─────────────────────────────────────────────

async def set_org_feature_override(
    db: AsyncSession,
    org_id: uuid.UUID,
    feature_slug: str,
    is_enabled: Optional[bool],
    config_override: Optional[dict],
    changed_by_id: uuid.UUID,
) -> dict:
    """
    Set or update an org's feature override.
    Enforces override policy — raises ValueError if policy forbids the change.
    """
    feat = await db.scalar(
        select(FeatureFlag).where(FeatureFlag.slug == feature_slug)
    )
    if not feat:
        raise ValueError(f"Feature '{feature_slug}' not found")

    policy = OverridePolicy(feat.override_policy)

    # Policy enforcement
    if policy == OverridePolicy.locked:
        raise ValueError(f"Feature '{feature_slug}' is locked and cannot be overridden by org admin")

    if policy == OverridePolicy.disable_only and is_enabled is True:
        raise ValueError(f"Feature '{feature_slug}' can only be disabled, not enabled, by org admin")

    approval_status = "approved"
    if policy == OverridePolicy.approval_required:
        approval_status = "pending"

    existing = await db.scalar(
        select(OrgFeatureOverride).where(
            OrgFeatureOverride.org_id == org_id,
            OrgFeatureOverride.feature_id == feat.id,
        )
    )

    if existing:
        existing.is_enabled = is_enabled
        existing.config_override = config_override
        existing.changed_by_id = changed_by_id
        existing.changed_at = datetime.now(timezone.utc)
        existing.approval_status = approval_status
        await db.flush()
        return {"id": str(existing.id), "approval_status": approval_status}

    override = OrgFeatureOverride(
        org_id=org_id,
        feature_id=feat.id,
        is_enabled=is_enabled,
        config_override=config_override,
        changed_by_id=changed_by_id,
        approval_status=approval_status,
    )
    db.add(override)
    await db.flush()
    return {"id": str(override.id), "approval_status": approval_status}


async def approve_feature_override(
    db: AsyncSession,
    override_id: uuid.UUID,
    approved_by_id: uuid.UUID,
) -> None:
    override = await db.get(OrgFeatureOverride, override_id)
    if not override:
        raise ValueError("Override not found")
    override.approval_status = "approved"
    override.changed_by_id = approved_by_id
    override.changed_at = datetime.now(timezone.utc)
    await db.flush()
