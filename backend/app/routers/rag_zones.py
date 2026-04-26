"""RAG zone management: zones, AD-group memberships, user zone access grants, heyKarl role assignments."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.hk_role import HkRoleAssignment, HkRoleZoneGrant
from app.models.organization import Organization
from app.models.rag_zone import RagZone, RagZoneMembership
from app.models.user import User
from app.models.user_zone_access import UserZoneAccess
from app.schemas.rag_zone import (
    HkRoleAssignmentCreate,
    HkRoleAssignmentRead,
    HkRoleZoneGrantCreate,
    HkRoleZoneGrantRead,
    IngestionZoneConfig,
    RagZoneCreate,
    RagZoneMembershipCreate,
    RagZoneMembershipRead,
    RagZoneRead,
    RagZoneUpdate,
    UserZoneAccessGrant,
    UserZoneAccessRead,
)
from app.core.exceptions import NotFoundException
from app.services.identity_service import identity_resolver

router = APIRouter()


# ── Ingestion config (static path — must come before /{zone_id}) ───────────────

@router.get(
    "/organizations/{org_id}/rag-zones/ingestion-config",
    response_model=IngestionZoneConfig,
    summary="Get source-type → zone slug mapping for ingestion",
)
async def get_ingestion_config(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:read")),
) -> IngestionZoneConfig:
    result = await db.execute(
        select(Organization.metadata_).where(Organization.id == org_id)
    )
    row = result.first()
    if row is None:
        raise NotFoundException(detail="Organization not found")
    metadata = row[0] or {}
    return IngestionZoneConfig(**metadata.get("rag_zones", {}))


@router.patch(
    "/organizations/{org_id}/rag-zones/ingestion-config",
    response_model=IngestionZoneConfig,
    summary="Update source-type → zone slug mapping for ingestion",
)
async def update_ingestion_config(
    org_id: uuid.UUID,
    data: IngestionZoneConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> IngestionZoneConfig:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundException(detail="Organization not found")
    metadata = dict(org.metadata_ or {})
    metadata["rag_zones"] = data.model_dump(exclude_none=True)
    org.metadata_ = metadata
    await db.commit()
    return data


# ── User zone access list (static path — must come before /{zone_id}) ─────────

@router.get(
    "/organizations/{org_id}/rag-zones/access",
    response_model=List[UserZoneAccessRead],
    summary="List all user zone access grants for an org",
)
async def list_access_grants(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> List[UserZoneAccessRead]:
    result = await db.execute(
        select(UserZoneAccess)
        .where(UserZoneAccess.org_id == org_id)
        .order_by(UserZoneAccess.granted_at.desc())
    )
    return [UserZoneAccessRead.model_validate(a) for a in result.scalars().all()]


# ── Zones ──────────────────────────────────────────────────────────────────────

@router.get(
    "/organizations/{org_id}/rag-zones",
    response_model=List[RagZoneRead],
    summary="List RAG zones",
)
async def list_zones(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:read")),
) -> List[RagZoneRead]:
    result = await db.execute(
        select(RagZone).where(RagZone.organization_id == org_id).order_by(RagZone.name)
    )
    return [RagZoneRead.model_validate(z) for z in result.scalars().all()]


@router.post(
    "/organizations/{org_id}/rag-zones",
    response_model=RagZoneRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a RAG zone",
)
async def create_zone(
    org_id: uuid.UUID,
    data: RagZoneCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:create")),
) -> RagZoneRead:
    zone = RagZone(
        organization_id=org_id,
        name=data.name,
        slug=data.slug,
        description=data.description,
        is_default=data.is_default,
        ad_group_only=data.ad_group_only,
    )
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return RagZoneRead.model_validate(zone)


@router.get(
    "/organizations/{org_id}/rag-zones/{zone_id}",
    response_model=RagZoneRead,
    summary="Get a RAG zone",
)
async def get_zone(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:read")),
) -> RagZoneRead:
    return RagZoneRead.model_validate(await _get_zone_or_404(org_id, zone_id, db))


@router.patch(
    "/organizations/{org_id}/rag-zones/{zone_id}",
    response_model=RagZoneRead,
    summary="Update a RAG zone",
)
async def update_zone(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    data: RagZoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:update")),
) -> RagZoneRead:
    zone = await _get_zone_or_404(org_id, zone_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    await db.commit()
    await db.refresh(zone)
    return RagZoneRead.model_validate(zone)


@router.delete(
    "/organizations/{org_id}/rag-zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a RAG zone",
)
async def delete_zone(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:delete")),
) -> None:
    zone = await _get_zone_or_404(org_id, zone_id, db)
    await db.delete(zone)
    await db.commit()


# ── AD-group memberships ────────────────────────────────────────────────────────

@router.get(
    "/organizations/{org_id}/rag-zones/{zone_id}/memberships",
    response_model=List[RagZoneMembershipRead],
    summary="List AD-group memberships for a zone",
)
async def list_memberships(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:read")),
) -> List[RagZoneMembershipRead]:
    await _get_zone_or_404(org_id, zone_id, db)
    result = await db.execute(
        select(RagZoneMembership)
        .where(RagZoneMembership.zone_id == zone_id)
        .order_by(RagZoneMembership.ad_group_name)
    )
    return [RagZoneMembershipRead.model_validate(m) for m in result.scalars().all()]


@router.post(
    "/organizations/{org_id}/rag-zones/{zone_id}/memberships",
    response_model=RagZoneMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an AD group to a zone",
)
async def add_membership(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    data: RagZoneMembershipCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> RagZoneMembershipRead:
    await _get_zone_or_404(org_id, zone_id, db)
    membership = RagZoneMembership(zone_id=zone_id, ad_group_name=data.ad_group_name)
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return RagZoneMembershipRead.model_validate(membership)


@router.delete(
    "/organizations/{org_id}/rag-zones/{zone_id}/memberships/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an AD group from a zone",
)
async def remove_membership(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    membership_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> None:
    await _get_zone_or_404(org_id, zone_id, db)
    result = await db.execute(
        select(RagZoneMembership).where(
            RagZoneMembership.id == membership_id,
            RagZoneMembership.zone_id == zone_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise NotFoundException(detail="Membership not found")
    await db.delete(membership)
    await db.commit()


# ── User zone access grants ────────────────────────────────────────────────────

@router.post(
    "/organizations/{org_id}/rag-zones/{zone_id}/access",
    response_model=UserZoneAccessRead,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a user access to a zone",
)
async def grant_access(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    data: UserZoneAccessGrant,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> UserZoneAccessRead:
    zone = await _get_zone_or_404(org_id, zone_id, db)
    _require_not_ad_only(zone)
    grant = UserZoneAccess(
        user_id=data.user_id,
        zone_id=zone_id,
        org_id=org_id,
        project_scope=data.project_scope,
        granted_via="hk_role",
        granted_by=current_user.id,
        revoked_at=data.valid_to,  # valid_to = scheduled expiry (active until that date)
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    await identity_resolver.invalidate(data.user_id, org_id)
    return UserZoneAccessRead.model_validate(grant)


@router.delete(
    "/organizations/{org_id}/rag-zones/{zone_id}/access/{access_id}",
    response_model=UserZoneAccessRead,
    summary="Revoke a user's zone access (soft-revoke — historical docs remain visible)",
)
async def revoke_access(
    org_id: uuid.UUID,
    zone_id: uuid.UUID,
    access_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> UserZoneAccessRead:
    result = await db.execute(
        select(UserZoneAccess).where(
            UserZoneAccess.id == access_id,
            UserZoneAccess.zone_id == zone_id,
            UserZoneAccess.org_id == org_id,
        )
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise NotFoundException(detail="Access grant not found")
    now = datetime.now(timezone.utc)
    if grant.revoked_at is None or grant.revoked_at > now:
        grant.revoked_at = now
        await db.commit()
        await db.refresh(grant)
        await identity_resolver.invalidate(grant.user_id, org_id)
    return UserZoneAccessRead.model_validate(grant)


# ── heyKarl-internal role assignments ─────────────────────────────────────────

@router.get(
    "/organizations/{org_id}/rag-roles/assignments",
    response_model=List[HkRoleAssignmentRead],
    summary="List heyKarl role assignments for an org",
)
async def list_role_assignments(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> List[HkRoleAssignmentRead]:
    result = await db.execute(
        select(HkRoleAssignment)
        .where(HkRoleAssignment.org_id == org_id)
        .order_by(HkRoleAssignment.created_at.desc())
    )
    return [HkRoleAssignmentRead.model_validate(a) for a in result.scalars().all()]


@router.post(
    "/organizations/{org_id}/rag-roles/assignments",
    response_model=HkRoleAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a heyKarl role to a user",
)
async def create_role_assignment(
    org_id: uuid.UUID,
    data: HkRoleAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> HkRoleAssignmentRead:
    assignment = HkRoleAssignment(
        user_id=data.user_id,
        org_id=org_id,
        role_name=data.role_name,
        scope_type=data.scope_type,
        scope_id=data.scope_id,
        valid_to=data.valid_to,
        granted_by=current_user.id,
    )
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    await identity_resolver.invalidate(data.user_id, org_id)
    return HkRoleAssignmentRead.model_validate(assignment)


@router.delete(
    "/organizations/{org_id}/rag-roles/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a heyKarl role assignment",
)
async def delete_role_assignment(
    org_id: uuid.UUID,
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> None:
    result = await db.execute(
        select(HkRoleAssignment).where(
            HkRoleAssignment.id == assignment_id,
            HkRoleAssignment.org_id == org_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise NotFoundException(detail="Role assignment not found")
    user_id = assignment.user_id
    await db.delete(assignment)
    await db.commit()
    await identity_resolver.invalidate(user_id, org_id)


# ── heyKarl role → zone grants ─────────────────────────────────────────────────

@router.get(
    "/organizations/{org_id}/rag-roles/{role_name}/zone-grants",
    response_model=List[HkRoleZoneGrantRead],
    summary="List zone grants for a heyKarl role",
)
async def list_role_zone_grants(
    org_id: uuid.UUID,
    role_name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:read")),
) -> List[HkRoleZoneGrantRead]:
    result = await db.execute(
        select(HkRoleZoneGrant).where(
            HkRoleZoneGrant.org_id == org_id,
            HkRoleZoneGrant.role_name == role_name,
        )
    )
    return [HkRoleZoneGrantRead.model_validate(g) for g in result.scalars().all()]


@router.post(
    "/organizations/{org_id}/rag-roles/{role_name}/zone-grants",
    response_model=HkRoleZoneGrantRead,
    status_code=status.HTTP_201_CREATED,
    summary="Grant a zone to a heyKarl role",
)
async def add_role_zone_grant(
    org_id: uuid.UUID,
    role_name: str,
    data: HkRoleZoneGrantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> HkRoleZoneGrantRead:
    zone = await _get_zone_or_404(org_id, data.zone_id, db)
    _require_not_ad_only(zone)
    grant = HkRoleZoneGrant(org_id=org_id, role_name=role_name, zone_id=data.zone_id)
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    # All users with this role now have access — bulk invalidation not implemented;
    # cache will expire naturally within TTL (300s).
    return HkRoleZoneGrantRead.model_validate(grant)


@router.delete(
    "/organizations/{org_id}/rag-roles/{role_name}/zone-grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a zone from a heyKarl role",
)
async def remove_role_zone_grant(
    org_id: uuid.UUID,
    role_name: str,
    grant_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("zone:manage")),
) -> None:
    result = await db.execute(
        select(HkRoleZoneGrant).where(
            HkRoleZoneGrant.id == grant_id,
            HkRoleZoneGrant.org_id == org_id,
            HkRoleZoneGrant.role_name == role_name,
        )
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise NotFoundException(detail="Zone grant not found")
    await db.delete(grant)
    await db.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_zone_or_404(
    org_id: uuid.UUID, zone_id: uuid.UUID, db: AsyncSession
) -> RagZone:
    result = await db.execute(
        select(RagZone).where(RagZone.id == zone_id, RagZone.organization_id == org_id)
    )
    zone = result.scalar_one_or_none()
    if not zone:
        raise NotFoundException(detail="Zone not found")
    return zone


def _require_not_ad_only(zone: RagZone) -> None:
    if zone.ad_group_only:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This zone requires AD group membership and cannot be granted via heyKarl roles.",
        )
