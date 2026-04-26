# app/services/control_service.py
"""Business logic for capability-scoped compliance controls."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, delete

from app.models.control import Control, ControlCapabilityAssignment
from app.models.capability_node import CapabilityNode
from app.models.artifact_assignment import ArtifactAssignment


async def get_ancestor_ids(db: AsyncSession, node_id: uuid.UUID) -> list[uuid.UUID]:
    """Walk up the parent chain and return list of ancestor UUIDs (not including node_id itself)."""
    ancestors: list[uuid.UUID] = []
    current_id: Optional[uuid.UUID] = node_id
    visited: set[uuid.UUID] = {node_id}

    while True:
        result = await db.execute(
            select(CapabilityNode.parent_id).where(CapabilityNode.id == current_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            break
        if row in visited:
            break
        ancestors.append(row)
        visited.add(row)
        current_id = row

    return ancestors


async def get_all_descendant_ids(db: AsyncSession, node_id: uuid.UUID) -> list[uuid.UUID]:
    """BFS down through children, return flat list of descendant UUIDs (not including node_id)."""
    descendants: list[uuid.UUID] = []
    queue: list[uuid.UUID] = [node_id]
    visited: set[uuid.UUID] = {node_id}

    while queue:
        current_batch = queue[:]
        queue = []
        result = await db.execute(
            select(CapabilityNode.id).where(CapabilityNode.parent_id.in_(current_batch))
        )
        for child_id in result.scalars().all():
            if child_id not in visited:
                visited.add(child_id)
                descendants.append(child_id)
                queue.append(child_id)

    return descendants


async def assign_control_to_capability(
    db: AsyncSession,
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    capability_node_id: uuid.UUID,
    maturity_level: int,
    effectiveness: str,
    coverage_note: Optional[str],
    gap_description: Optional[str],
    assessor_id: Optional[uuid.UUID],
    propagate_to_children: bool = False,
) -> list[ControlCapabilityAssignment]:
    """Upsert a control assignment on a capability node, optionally propagating to children."""
    now = datetime.now(timezone.utc)

    # Check for existing assignment
    result = await db.execute(
        select(ControlCapabilityAssignment).where(
            and_(
                ControlCapabilityAssignment.control_id == control_id,
                ControlCapabilityAssignment.capability_node_id == capability_node_id,
                ControlCapabilityAssignment.org_id == org_id,
            )
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.maturity_level = maturity_level
        existing.effectiveness = effectiveness
        existing.coverage_note = coverage_note
        existing.gap_description = gap_description
        existing.assessor_id = assessor_id
        existing.is_inherited = False
        existing.updated_at = now
        primary_assignment = existing
    else:
        primary_assignment = ControlCapabilityAssignment(
            org_id=org_id,
            control_id=control_id,
            capability_node_id=capability_node_id,
            maturity_level=maturity_level,
            effectiveness=effectiveness,
            coverage_note=coverage_note,
            gap_description=gap_description,
            assessor_id=assessor_id,
            is_inherited=False,
        )
        db.add(primary_assignment)

    await db.flush()  # ensure primary_assignment.id is populated

    created_or_updated = [primary_assignment]

    if propagate_to_children:
        descendant_ids = await get_all_descendant_ids(db, capability_node_id)
        for desc_id in descendant_ids:
            # Only create inherited entries where no explicit assignment exists
            check = await db.execute(
                select(ControlCapabilityAssignment).where(
                    and_(
                        ControlCapabilityAssignment.control_id == control_id,
                        ControlCapabilityAssignment.capability_node_id == desc_id,
                        ControlCapabilityAssignment.org_id == org_id,
                        ControlCapabilityAssignment.is_inherited == False,
                    )
                )
            )
            if check.scalar_one_or_none() is not None:
                continue  # explicit assignment exists — skip

            # Check for existing inherited entry
            inherited_check = await db.execute(
                select(ControlCapabilityAssignment).where(
                    and_(
                        ControlCapabilityAssignment.control_id == control_id,
                        ControlCapabilityAssignment.capability_node_id == desc_id,
                        ControlCapabilityAssignment.org_id == org_id,
                    )
                )
            )
            inherited_existing = inherited_check.scalar_one_or_none()
            if inherited_existing:
                inherited_existing.inherited_from_id = primary_assignment.id
                inherited_existing.updated_at = now
                created_or_updated.append(inherited_existing)
            else:
                inherited = ControlCapabilityAssignment(
                    org_id=org_id,
                    control_id=control_id,
                    capability_node_id=desc_id,
                    maturity_level=maturity_level,
                    effectiveness=effectiveness,
                    coverage_note=coverage_note,
                    gap_description=gap_description,
                    assessor_id=assessor_id,
                    is_inherited=True,
                    inherited_from_id=primary_assignment.id,
                )
                db.add(inherited)
                created_or_updated.append(inherited)

    await db.commit()
    for obj in created_or_updated:
        await db.refresh(obj)

    return created_or_updated


async def get_controls_for_capability(
    db: AsyncSession,
    org_id: uuid.UUID,
    capability_node_id: uuid.UUID,
    include_ancestors: bool = True,
) -> list[dict]:
    """
    Return controls assigned to this node (and optionally its ancestors).
    Deduplicates by control_id, preferring the most specific (non-inherited) assignment.
    """
    scope_ids: list[uuid.UUID] = [capability_node_id]
    if include_ancestors:
        ancestors = await get_ancestor_ids(db, capability_node_id)
        scope_ids.extend(ancestors)

    # Build specificity map: index 0 = most specific (the node itself)
    specificity: dict[uuid.UUID, int] = {nid: idx for idx, nid in enumerate(scope_ids)}

    result = await db.execute(
        select(ControlCapabilityAssignment, Control)
        .join(Control, ControlCapabilityAssignment.control_id == Control.id)
        .where(
            and_(
                ControlCapabilityAssignment.capability_node_id.in_(scope_ids),
                ControlCapabilityAssignment.org_id == org_id,
                Control.org_id == org_id,
                Control.is_active == True,
            )
        )
    )
    rows = result.all()

    # Deduplicate: for each control_id keep the most specific assignment
    best: dict[uuid.UUID, tuple[int, ControlCapabilityAssignment, Control]] = {}
    for cca, ctrl in rows:
        spec = specificity.get(cca.capability_node_id, len(scope_ids))
        existing = best.get(cca.control_id)
        if existing is None or spec < existing[0]:
            best[cca.control_id] = (spec, cca, ctrl)

    return [
        {
            "control": ctrl,
            "assessment": cca,
            "applies_via_node_id": cca.capability_node_id,
        }
        for _, cca, ctrl in best.values()
    ]


async def get_controls_for_story(
    db: AsyncSession,
    org_id: uuid.UUID,
    story_id: uuid.UUID,
) -> list[dict]:
    """Return controls relevant to the capability node a user story is assigned to."""
    result = await db.execute(
        select(ArtifactAssignment).where(
            and_(
                ArtifactAssignment.artifact_type == "user_story",
                ArtifactAssignment.artifact_id == story_id,
                ArtifactAssignment.org_id == org_id,
            )
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        return []

    return await get_controls_for_capability(db, org_id, assignment.node_id, include_ancestors=True)


async def remove_control_from_capability(
    db: AsyncSession,
    org_id: uuid.UUID,
    control_id: uuid.UUID,
    capability_node_id: uuid.UUID,
) -> None:
    """Delete a control assignment and any inherited entries derived from it."""
    # Find the primary assignment first to get its id
    result = await db.execute(
        select(ControlCapabilityAssignment).where(
            and_(
                ControlCapabilityAssignment.control_id == control_id,
                ControlCapabilityAssignment.capability_node_id == capability_node_id,
                ControlCapabilityAssignment.org_id == org_id,
            )
        )
    )
    primary = result.scalar_one_or_none()
    if primary:
        # Delete inherited entries that point to this assignment
        await db.execute(
            delete(ControlCapabilityAssignment).where(
                ControlCapabilityAssignment.inherited_from_id == primary.id
            )
        )
        await db.delete(primary)

    await db.commit()


async def get_coverage_stats_for_node(
    db: AsyncSession,
    org_id: uuid.UUID,
    node_id: uuid.UUID,
) -> dict:
    """Calculate control coverage statistics for a single capability node (direct only)."""
    # Load the node title
    node_result = await db.execute(
        select(CapabilityNode).where(
            and_(CapabilityNode.id == node_id, CapabilityNode.org_id == org_id)
        )
    )
    node = node_result.scalar_one_or_none()
    node_title = node.title if node else ""

    result = await db.execute(
        select(ControlCapabilityAssignment, Control)
        .join(Control, ControlCapabilityAssignment.control_id == Control.id)
        .where(
            and_(
                ControlCapabilityAssignment.capability_node_id == node_id,
                ControlCapabilityAssignment.org_id == org_id,
                Control.is_active == True,
            )
        )
    )
    rows = result.all()
    control_count = len(rows)

    if control_count == 0:
        return {
            "node_id": node_id,
            "node_title": node_title,
            "control_count": 0,
            "avg_maturity": 0.0,
            "coverage_pct": 0.0,
        }

    total_maturity = sum(cca.maturity_level for cca, _ in rows)
    avg_maturity = total_maturity / control_count

    effective_count = sum(
        1 for cca, _ in rows if cca.effectiveness in ("effective", "fully_effective")
    )
    coverage_pct = effective_count / control_count

    return {
        "node_id": node_id,
        "node_title": node_title,
        "control_count": control_count,
        "avg_maturity": avg_maturity,
        "coverage_pct": coverage_pct,
    }
