"""Audit Service - Handles conversation audit logging."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import ConversationAuditLog


class AuditService:
    """Service for audit logging."""

    @staticmethod
    async def log_action(
        db: AsyncSession,
        org_id: uuid.UUID,
        action: str,
        entity_type: str,
        entity_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_type: str = "user",
        conversation_id: Optional[uuid.UUID] = None,
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> ConversationAuditLog:
        """Log an audit action."""
        log_entry = ConversationAuditLog(
            org_id=org_id,
            conversation_id=conversation_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            data_json=metadata or {},
        )
        db.add(log_entry)
        await db.flush()
        return log_entry


# Convenience functions for backward compatibility
async def log_trust_change(
    db: AsyncSession,
    org_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    change_type: str,
    before_value: Any,
    after_value: Any,
    actor_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Log a trust-related change (backward compatibility)."""
    await AuditService.log_action(
        db=db,
        org_id=org_id,
        action=f"trust_{change_type}",
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        before_state={"value": before_value},
        after_state={"value": after_value},
        metadata=metadata,
    )


async def log_action(
    db: AsyncSession,
    org_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    **kwargs,
) -> None:
    """Simple log action function (backward compatibility)."""
    await AuditService.log_action(
        db=db,
        org_id=org_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        **kwargs,
    )
