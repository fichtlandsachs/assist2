"""Jira REST API proxy endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_atlassian_token, get_current_user
from app.models.jira_story import JiraStory
from app.models.user import User
from app.services.jira_service import jira_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["Jira"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class JiraAIRequest(BaseModel):
    action: str  # "userstory"
    summary: str
    description: str = ""


class JiraWriteRequest(BaseModel):
    ticket_key: str
    ticket_id: str = ""
    summary: str = ""
    description: str


class JiraStoryCreate(BaseModel):
    ticket_key: str
    project: str
    source_summary: str
    content: str
    status: str = "draft"
    org_id: uuid.UUID


class JiraStoryUpdate(BaseModel):
    status: str | None = None
    content: str | None = None


class JiraStoryRead(BaseModel):
    id: uuid.UUID
    ticket_key: str
    project: str
    source_summary: str
    content: str
    status: str
    organization_id: uuid.UUID
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


# ── Ticket search + fetch ─────────────────────────────────────────────────────

@router.get("/tickets")
async def search_tickets(
    project: str = Query(..., description="Jira project key, e.g. ABC"),
    q: str = Query("", description="Free text or JQL fragment"),
    atlassian: tuple[str, str] = Depends(get_atlassian_token),
) -> dict:
    """Search Jira tickets. Returns {tickets, project, count}."""
    access_token, cloud_id = atlassian
    try:
        tickets = await jira_service.search_tickets(access_token, cloud_id, project, q)
    except Exception as exc:
        logger.error("Jira search error: %s", exc)
        raise HTTPException(status_code=502, detail="Jira nicht erreichbar")
    return {"tickets": tickets, "project": project, "count": len(tickets)}


@router.get("/ticket/{key}")
async def get_ticket(
    key: str,
    atlassian: tuple[str, str] = Depends(get_atlassian_token),
) -> dict:
    """Fetch a single Jira ticket with plaintext description."""
    access_token, cloud_id = atlassian
    try:
        ticket = await jira_service.get_ticket(access_token, cloud_id, key.upper())
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Ticket {key} nicht gefunden")
        logger.error("Jira ticket fetch error %s: %s", key, exc)
        raise HTTPException(status_code=502, detail="Jira nicht erreichbar")
    return ticket


# ── AI transformation + write-back ───────────────────────────────────────────

@router.post("/ai")
async def jira_ai(
    body: JiraAIRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Transform a Jira ticket into a User Story using AI. action='userstory'."""
    if body.action != "userstory":
        raise HTTPException(status_code=400, detail=f"Unbekannte action: {body.action}")
    try:
        story_md = await jira_service.generate_user_story(
            key="",
            summary=body.summary,
            description=body.description,
        )
    except Exception as exc:
        logger.error("Jira AI error: %s", exc)
        raise HTTPException(status_code=502, detail="KI-Service nicht erreichbar")
    return {"summary": body.summary, "description": story_md}


@router.post("/write")
async def write_ticket(
    body: JiraWriteRequest,
    atlassian: tuple[str, str] = Depends(get_atlassian_token),
) -> dict:
    """Write a user story (Markdown) back to Jira as ADF description."""
    access_token, cloud_id = atlassian
    try:
        await jira_service.write_ticket(
            access_token=access_token,
            cloud_id=cloud_id,
            key=body.ticket_key.upper(),
            summary=body.summary,
            description_md=body.description,
        )
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 404:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_key} nicht gefunden")
        logger.error("Jira write error %s: %s", body.ticket_key, exc)
        raise HTTPException(status_code=502, detail="Jira Write fehlgeschlagen")
    return {"message": f"{body.ticket_key} in Jira aktualisiert", "ticket_key": body.ticket_key}


# ── Story CRUD ────────────────────────────────────────────────────────────────

@router.post("/stories", response_model=JiraStoryRead)
async def create_story(
    body: JiraStoryCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JiraStory:
    """Persist a Jira-derived user story in the workspace."""
    story = JiraStory(
        organization_id=body.org_id,
        ticket_key=body.ticket_key.upper(),
        project=body.project.upper(),
        source_summary=body.source_summary,
        content=body.content,
        status=body.status,
        created_by=current_user.id,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.get("/stories", response_model=list[JiraStoryRead])
async def list_stories(
    org_id: uuid.UUID = Query(...),
    project: str = Query(""),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[JiraStory]:
    """List Jira-derived user stories for an org."""
    stmt = select(JiraStory).where(JiraStory.organization_id == org_id)
    if project:
        stmt = stmt.where(JiraStory.project == project.upper())
    stmt = stmt.order_by(JiraStory.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.patch("/stories/{story_id}", response_model=JiraStoryRead)
async def update_story(
    story_id: uuid.UUID,
    body: JiraStoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JiraStory:
    """Update status or content of a Jira-derived user story."""
    result = await db.execute(
        select(JiraStory).where(JiraStory.id == story_id)
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story nicht gefunden")
    if body.status is not None:
        story.status = body.status
    if body.content is not None:
        story.content = body.content
    await db.commit()
    await db.refresh(story)
    return story
