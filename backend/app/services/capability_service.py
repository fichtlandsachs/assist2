# app/services/capability_service.py
"""Capability node CRUD, tree assembly, and story-count aggregation."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.capability_node import CapabilityNode
from app.models.artifact_assignment import ArtifactAssignment
from app.models.organization import Organization
from app.schemas.capability import (
    CapabilityNodeCreate,
    CapabilityNodeUpdate,
    OrgInitAdvance,
)


# ── Tree helpers ──────────────────────────────────────────────────────────────

def _node_to_dict(node: CapabilityNode) -> dict[str, Any]:
    return {
        "id": str(node.id),
        "org_id": str(node.org_id),
        "parent_id": str(node.parent_id) if node.parent_id else None,
        "node_type": node.node_type,
        "title": node.title,
        "description": node.description,
        "sort_order": node.sort_order,
        "is_active": node.is_active,
        "external_import_key": node.external_import_key,
        "source_type": node.source_type,
        "children": [],
        "story_count": 0,
    }


def _build_tree(flat: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assemble a parent-child tree from a flat node list."""
    by_id = {n["id"]: n for n in flat}
    roots: list[dict[str, Any]] = []
    for node in flat:
        pid = node["parent_id"]
        if pid and pid in by_id:
            by_id[pid]["children"].append(node)
        else:
            roots.append(node)
    return roots


def _apply_counts(nodes: list[dict[str, Any]], counts: dict[str, int]) -> int:
    """Set story_count on each node = direct + all descendant counts. Returns subtree total."""
    total = 0
    for node in nodes:
        child_total = _apply_counts(node["children"], counts)
        direct = counts.get(node["id"], 0)
        node["story_count"] = direct + child_total
        total += direct + child_total
    return total


# ── DB queries ─────────────────────────────────────────────────────────────────

async def get_capability_tree(db: AsyncSession, org_id: uuid.UUID) -> list[dict[str, Any]]:
    """Return the full active tree for an org (no story counts)."""
    stmt = (
        select(CapabilityNode)
        .where(CapabilityNode.org_id == org_id, CapabilityNode.is_active == True)  # noqa: E712
        .order_by(CapabilityNode.node_type, CapabilityNode.sort_order, CapabilityNode.title)
    )
    result = await db.execute(stmt)
    flat = [_node_to_dict(n) for n in result.scalars().all()]
    return _build_tree(flat)


async def get_capability_tree_with_counts(
    db: AsyncSession, org_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Return tree with aggregated story counts per node."""
    tree = await get_capability_tree(db, org_id)
    stmt = (
        select(ArtifactAssignment.node_id, func.count(ArtifactAssignment.id))
        .where(
            ArtifactAssignment.org_id == org_id,
            ArtifactAssignment.artifact_type == "user_story",
        )
        .group_by(ArtifactAssignment.node_id)
    )
    result = await db.execute(stmt)
    counts = {str(row[0]): row[1] for row in result.all()}
    _apply_counts(tree, counts)
    return tree


async def get_node(
    db: AsyncSession, org_id: uuid.UUID, node_id: uuid.UUID
) -> Optional[CapabilityNode]:
    stmt = select(CapabilityNode).where(
        CapabilityNode.org_id == org_id, CapabilityNode.id == node_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_node(
    db: AsyncSession, org_id: uuid.UUID, data: CapabilityNodeCreate
) -> CapabilityNode:
    node = CapabilityNode(
        org_id=org_id,
        parent_id=data.parent_id,
        node_type=data.node_type,
        title=data.title,
        description=data.description,
        sort_order=data.sort_order,
        external_import_key=data.external_import_key,
        source_type=data.source_type,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


async def update_node(
    db: AsyncSession, node: CapabilityNode, data: CapabilityNodeUpdate
) -> CapabilityNode:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    await db.commit()
    await db.refresh(node)
    return node


async def delete_org_nodes(db: AsyncSession, org_id: uuid.UUID) -> None:
    """Delete all capability nodes for an org (used before re-import)."""
    await db.execute(
        delete(CapabilityNode).where(CapabilityNode.org_id == org_id)
    )
    await db.commit()


async def bulk_create_nodes(
    db: AsyncSession, org_id: uuid.UUID, nodes: list[dict[str, Any]]
) -> int:
    """Insert pre-validated node dicts. Returns count inserted."""
    objs = [
        CapabilityNode(
            org_id=org_id,
            parent_id=n.get("parent_id"),
            node_type=n["node_type"],
            title=n["title"],
            description=n.get("description"),
            sort_order=n.get("sort_order", 0),
            external_import_key=n.get("external_import_key"),
            source_type=n.get("source_type"),
            is_active=n.get("is_active", True),
        )
        for n in nodes
    ]
    db.add_all(objs)
    await db.commit()
    return len(objs)


async def get_org_init_status(db: AsyncSession, org: Organization) -> dict[str, Any]:
    return {
        "initialization_status": org.initialization_status,
        "initialization_completed_at": org.initialization_completed_at,
        "capability_map_version": org.capability_map_version,
        "initial_setup_source": org.initial_setup_source,
    }


async def advance_org_init_status(
    db: AsyncSession, org: Organization, data: OrgInitAdvance, user_id: uuid.UUID
) -> Organization:
    org.initialization_status = data.status
    if data.source:
        org.initial_setup_source = data.source
    if data.status == "initialized":
        org.initialization_completed_at = datetime.now(timezone.utc)
        org.initial_setup_completed_by_id = user_id
        org.capability_map_version = (org.capability_map_version or 0) + 1
    await db.commit()
    await db.refresh(org)
    return org
