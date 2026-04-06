"""Webhook endpoints for Confluence and Jira change notifications."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_db
from app.tasks.rag_tasks import index_confluence_space, index_jira_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


async def _find_org_by_secret(secret: str, secret_key: str, db: AsyncSession):
    """Return the org whose metadata_.webhook_secrets[secret_key] matches secret."""
    from app.models.organization import Organization

    result = await db.execute(
        select(Organization).where(Organization.deleted_at.is_(None))
    )
    for org in result.scalars().all():
        meta = org.metadata_ or {}
        if meta.get("webhook_secrets", {}).get(secret_key) == secret:
            return org
    return None


@router.post("/webhooks/confluence")
async def confluence_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Confluence page events and trigger re-indexing."""
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    org = await _find_org_by_secret(x_webhook_secret, "confluence", db)
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload: dict[str, Any] = await request.json()
    event = payload.get("event", "")
    page_id = str(
        payload.get("page", {}).get("id", "")
        or payload.get("pageId", "")
    )

    if not page_id:
        return {"status": "ignored", "reason": "no page_id in payload"}

    if event == "page_deleted":
        from sqlalchemy import delete as sql_delete
        from app.models.document_chunk import DocumentChunk
        await db.execute(
            sql_delete(DocumentChunk).where(
                DocumentChunk.org_id == org.id,
                DocumentChunk.source_ref == f"confluence:{page_id}",
            )
        )
        await db.commit()
        return {"status": "deleted", "page_id": page_id}

    # Re-index full space (single-page API not yet available in index tasks)
    index_confluence_space.delay(str(org.id))
    return {"status": "queued", "org_id": str(org.id), "page_id": page_id}


@router.post("/webhooks/jira")
async def jira_webhook(
    request: Request,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive Jira issue events and trigger re-indexing."""
    if not x_webhook_secret:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Secret header")

    org = await _find_org_by_secret(x_webhook_secret, "jira", db)
    if org is None:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload: dict[str, Any] = await request.json()
    issue_key = (
        payload.get("issue", {}).get("key", "")
        or payload.get("issueKey", "")
    )

    if not issue_key:
        return {"status": "ignored", "reason": "no issue_key in payload"}

    index_jira_ticket.delay(str(issue_key), str(org.id))
    return {"status": "queued", "ticket_key": str(issue_key)}
