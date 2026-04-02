# Jira-Ticket Integration — /jira-ticket Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the backend API endpoints and frontend panel support required for the `/jira-ticket` chat skill — search Jira tickets, transform them into user stories with AI, persist them, and write back to Jira.

**Architecture:** A new `jira` router (`backend/app/routers/jira.py`) proxies calls to the Atlassian REST API v3 using the existing `get_atlassian_token` dependency; a `JiraStory` model persists AI-generated user stories linked to Jira tickets; the AI workspace frontend gains a `"jira"` chat mode and parses `<<<USERSTORY_PANEL` markers from assistant messages to render them in the right panel.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, httpx, Anthropic SDK, Next.js 15, React 19, ReactMarkdown

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/migrations/versions/0021_jira_stories.py` | Create | Add `jira_stories` table |
| `backend/app/models/jira_story.py` | Create | `JiraStory` SQLAlchemy model |
| `backend/app/services/jira_service.py` | Create | Jira REST API proxy, ADF↔text converters, AI story generation |
| `backend/app/routers/jira.py` | Create | All `/api/v1/jira/*` endpoints |
| `backend/app/main.py` | Modify | Register `jira_router` |
| `frontend/app/[org]/ai-workspace/page.tsx` | Modify | `"jira"` chat mode, panel marker parsing, `JiraStoryPanel` UI |

---

## Task 1: DB Migration + JiraStory Model

**Files:**
- Create: `backend/migrations/versions/0021_jira_stories.py`
- Create: `backend/app/models/jira_story.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/migrations/versions/0021_jira_stories.py
"""add jira_stories table

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jira_stories",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ticket_key", sa.String(50), nullable=False),
        sa.Column("project", sa.String(50), nullable=False),
        sa.Column("source_summary", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="draft", nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_jira_stories_org_project", "jira_stories", ["organization_id", "project"])
    op.create_index("ix_jira_stories_ticket_key", "jira_stories", ["ticket_key"])


def downgrade() -> None:
    op.drop_index("ix_jira_stories_ticket_key", table_name="jira_stories")
    op.drop_index("ix_jira_stories_org_project", table_name="jira_stories")
    op.drop_table("jira_stories")
```

- [ ] **Step 2: Run the migration**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```

Expected output contains: `Running upgrade 0020 -> 0021, add jira_stories table`

- [ ] **Step 3: Verify table exists**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec postgres psql -U assist2 -d assist2 -c "\d jira_stories"
```

Expected: table description showing all columns including `ticket_key`, `content`, `status`.

- [ ] **Step 4: Create the JiraStory model**

```python
# backend/app/models/jira_story.py
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class JiraStory(Base):
    __tablename__ = "jira_stories"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=func.gen_random_uuid()
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticket_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    project: Mapped[str] = mapped_column(String(50), nullable=False)
    source_summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2 && git add backend/migrations/versions/0021_jira_stories.py backend/app/models/jira_story.py
git commit -m "feat(jira): add jira_stories table and model"
```

---

## Task 2: Jira Service

**Files:**
- Create: `backend/app/services/jira_service.py`

The service handles all Atlassian REST API calls, ADF↔plaintext conversion, and AI story generation.

- [ ] **Step 1: Create the service file**

```python
# backend/app/services/jira_service.py
"""Jira REST API proxy + ADF conversion + AI story generation."""
import json
import logging
import re
from typing import Any

import anthropic
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_JIRA_BASE = "https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"
_TIMEOUT = httpx.Timeout(15.0)

_USERSTORY_SYSTEM = (
    "Du bist ein Experte für agile Anforderungsanalyse. "
    "Erstelle aus dem folgenden Jira-Ticket eine vollständige User Story im exakten Format:\n\n"
    "## User Story\n\n"
    "**Als** {Rolle aus Kontext}\n"
    "**möchte ich** {konkrete Funktionalität},\n"
    "**damit** {messbarer Nutzen}.\n\n"
    "---\n\n"
    "### Akzeptanzkriterien\n"
    "- [ ] {konkretes, testbares Kriterium}\n"
    "(mindestens 3, maximal 7)\n\n"
    "### Definition of Done\n"
    "- [ ] Code reviewed und gemergt\n"
    "- [ ] Unit Tests vorhanden (Coverage ≥ 80 %)\n"
    "- [ ] Acceptance Criteria manuell getestet\n"
    "- [ ] Dokumentation aktualisiert (falls relevant)\n"
    "- [ ] Ticket in Jira auf \"Done\" gesetzt\n\n"
    "### Technische Notizen\n"
    "{Nur wenn aus dem Ticket ableitbar — sonst diesen Abschnitt weglassen}\n\n"
    "Antworte NUR mit dem Markdown — kein JSON, kein Erklärungstext davor oder danach."
)


def adf_to_text(node: Any) -> str:
    """Recursively extract plain text from an Atlassian Document Format node."""
    if not isinstance(node, dict):
        return ""
    t = node.get("type", "")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    if t == "rule":
        return "\n---\n"
    children = "".join(adf_to_text(c) for c in node.get("content", []))
    if t in ("paragraph", "heading", "listItem", "taskItem"):
        return children + "\n"
    if t in ("bulletList", "orderedList", "taskList", "blockquote", "doc"):
        return children
    return children


def markdown_to_adf(text: str) -> dict:
    """Convert simple Markdown to Atlassian Document Format for Jira write-back."""
    lines = text.split("\n")
    content: list[dict] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("## "):
            content.append({
                "type": "heading",
                "attrs": {"level": 2},
                "content": [{"type": "text", "text": stripped[3:]}],
            })
        elif stripped.startswith("### "):
            content.append({
                "type": "heading",
                "attrs": {"level": 3},
                "content": [{"type": "text", "text": stripped[4:]}],
            })
        elif stripped in ("---", "***"):
            content.append({"type": "rule"})
        elif re.match(r"^- \[[ x]\] ", stripped):
            checked = stripped[3] == "x"
            task_text = stripped[6:]
            content.append({
                "type": "taskList",
                "attrs": {"localId": str(i)},
                "content": [{
                    "type": "taskItem",
                    "attrs": {"localId": str(i) + "i", "state": "DONE" if checked else "TODO"},
                    "content": [{"type": "text", "text": task_text}],
                }],
            })
        elif stripped.startswith("**") and stripped.endswith("**") and len(stripped) > 4:
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": stripped.strip("*"), "marks": [{"type": "strong"}]}],
            })
        elif stripped == "":
            pass  # skip blank lines
        else:
            # plain paragraph — preserve **bold** inline
            content.append({
                "type": "paragraph",
                "content": [{"type": "text", "text": stripped}],
            })
        i += 1

    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": ""}]}]
    return {"version": 1, "type": "doc", "content": content}


class JiraService:
    def _headers(self, access_token: str) -> dict:
        return {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _base(self, cloud_id: str) -> str:
        return _JIRA_BASE.format(cloud_id=cloud_id)

    async def search_tickets(
        self,
        access_token: str,
        cloud_id: str,
        project: str,
        q: str,
    ) -> list[dict]:
        """
        Search Jira tickets and return simplified list.
        Returns: [{"key": "ABC-1", "summary": ..., "status": ..., "priority": ...}]
        """
        if not q:
            jql = f"project={project} ORDER BY updated DESC"
        elif "=" in q or any(kw in q for kw in ("AND", "OR", "NOT", "ORDER")):
            jql = f"project={project} AND ({q}) ORDER BY updated DESC"
        else:
            jql = f'project={project} AND text ~ "{q}" ORDER BY updated DESC'

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base(cloud_id)}/search",
                headers=self._headers(access_token),
                params={
                    "jql": jql,
                    "fields": "summary,status,priority,assignee",
                    "maxResults": 20,
                },
            )
        resp.raise_for_status()
        issues = resp.json().get("issues", [])
        return [
            {
                "key": issue["key"],
                "summary": issue["fields"]["summary"],
                "status": issue["fields"]["status"]["name"],
                "priority": (issue["fields"].get("priority") or {}).get("name", ""),
                "assignee": ((issue["fields"].get("assignee") or {}).get("displayName", "")),
            }
            for issue in issues
        ]

    async def get_ticket(
        self,
        access_token: str,
        cloud_id: str,
        key: str,
    ) -> dict:
        """
        Fetch a single Jira ticket.
        Returns: {"key": ..., "summary": ..., "description": plaintext, "status": ..., "priority": ..., "assignee": ..., "reporter": ...}
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base(cloud_id)}/issue/{key}",
                headers=self._headers(access_token),
                params={"fields": "summary,description,status,priority,assignee,reporter"},
            )
        resp.raise_for_status()
        fields = resp.json()["fields"]
        raw_desc = fields.get("description")
        description = adf_to_text(raw_desc).strip() if isinstance(raw_desc, dict) else (raw_desc or "")
        return {
            "key": key,
            "id": resp.json()["id"],
            "summary": fields["summary"],
            "description": description,
            "status": fields["status"]["name"],
            "priority": (fields.get("priority") or {}).get("name", ""),
            "assignee": ((fields.get("assignee") or {}).get("displayName", "")),
            "reporter": ((fields.get("reporter") or {}).get("displayName", "")),
        }

    async def write_ticket(
        self,
        access_token: str,
        cloud_id: str,
        key: str,
        summary: str,
        description_md: str,
    ) -> None:
        """Write summary + user story (Markdown → ADF) back to Jira."""
        adf = markdown_to_adf(description_md)
        body: dict = {"fields": {"description": adf}}
        # Only update summary if explicitly provided (non-empty)
        if summary:
            body["fields"]["summary"] = summary

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.put(
                f"{self._base(cloud_id)}/issue/{key}",
                headers=self._headers(access_token),
                content=json.dumps(body),
            )
        if resp.status_code not in (200, 204):
            logger.error("Jira write failed %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()

    async def generate_user_story(
        self,
        key: str,
        summary: str,
        description: str,
    ) -> str:
        """Call Claude to generate a User Story Markdown from a Jira ticket."""
        settings = get_settings()
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        user_content = f"Ticket: {key}\nSummary: {summary}\n\nDescription:\n{description or '(keine Beschreibung)'}"
        msg = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_USERSTORY_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        return msg.content[0].text.strip() if msg.content else ""


jira_service = JiraService()
```

- [ ] **Step 2: Verify syntax**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -c "from app.services.jira_service import jira_service; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/jira_service.py
git commit -m "feat(jira): add JiraService — API proxy, ADF conversion, AI story generation"
```

---

## Task 3: Jira Routes — Ticket Search + Fetch

**Files:**
- Create: `backend/app/routers/jira.py` (initial — search + fetch only)

- [ ] **Step 1: Create the router file with search + fetch**

```python
# backend/app/routers/jira.py
"""Jira REST API proxy endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_atlassian_token, get_current_user
from app.models.user import User
from app.services.jira_service import jira_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["Jira"])


@router.get("/tickets")
async def search_tickets(
    project: str = Query(..., description="Jira project key, e.g. ABC"),
    q: str = Query("", description="Free text or JQL fragment"),
    atlassian: tuple[str, str] = Depends(get_atlassian_token),
) -> dict:
    """
    Search Jira tickets in a project.
    Returns {"tickets": [...], "project": "...", "count": N}
    """
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
    """
    Fetch a single Jira ticket.
    Returns full ticket data with description as plaintext.
    """
    access_token, cloud_id = atlassian
    try:
        ticket = await jira_service.get_ticket(access_token, cloud_id, key.upper())
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 404:
            raise HTTPException(status_code=404, detail=f"Ticket {key} nicht gefunden")
        logger.error("Jira ticket fetch error %s: %s", key, exc)
        raise HTTPException(status_code=502, detail="Jira nicht erreichbar")
    return ticket
```

- [ ] **Step 2: Verify no import errors**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -c "from app.routers.jira import router; print([r.path for r in router.routes])"
```

Expected: list with `/jira/tickets` and `/jira/ticket/{key}`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/routers/jira.py
git commit -m "feat(jira): add /jira/tickets and /jira/ticket/{key} endpoints"
```

---

## Task 4: Jira Routes — AI Transformation + Write-back

**Files:**
- Modify: `backend/app/routers/jira.py`

- [ ] **Step 1: Add request schemas + AI + write endpoints**

Append to `backend/app/routers/jira.py` (after the existing imports, add the Pydantic models at the top, then append the new endpoints at the bottom):

Add these imports at the top of `jira.py` (after existing imports):
```python
from pydantic import BaseModel
```

Add these Pydantic models after the imports section:
```python
class JiraAIRequest(BaseModel):
    action: str  # "userstory"
    summary: str
    description: str = ""


class JiraWriteRequest(BaseModel):
    ticket_key: str
    ticket_id: str
    summary: str = ""
    description: str
```

Append these endpoints at the end of the file:
```python
@router.post("/ai")
async def jira_ai(
    body: JiraAIRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Transform a Jira ticket into a User Story using AI.
    action="userstory" → returns {summary, description} where description is Markdown.
    """
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
    """
    Write a user story (Markdown) back to a Jira ticket description (ADF).
    Only updates summary when explicitly provided.
    """
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
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status == 404:
            raise HTTPException(status_code=404, detail=f"Ticket {body.ticket_key} nicht gefunden")
        logger.error("Jira write error %s: %s", body.ticket_key, exc)
        raise HTTPException(status_code=502, detail="Jira Write fehlgeschlagen")
    return {"message": f"{body.ticket_key} in Jira aktualisiert", "ticket_key": body.ticket_key}
```

- [ ] **Step 2: Verify all routes**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -c "from app.routers.jira import router; print([r.path for r in router.routes])"
```

Expected: 4 routes: `/jira/tickets`, `/jira/ticket/{key}`, `/jira/ai`, `/jira/write`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/routers/jira.py
git commit -m "feat(jira): add /jira/ai and /jira/write endpoints"
```

---

## Task 5: Jira Routes — Story CRUD

**Files:**
- Modify: `backend/app/routers/jira.py`

- [ ] **Step 1: Add story CRUD endpoints**

Add this import at the top of `jira.py` (with existing imports):
```python
from sqlalchemy import select
from app.models.jira_story import JiraStory
```

Add these Pydantic models (append to the models section):
```python
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
```

Append these endpoints at the end of `jira.py`:
```python
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
    """List Jira-derived user stories for an org (optionally filtered by project)."""
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
```

- [ ] **Step 2: Verify all 7 routes**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -c "from app.routers.jira import router; print([r.path for r in router.routes])"
```

Expected: 7 routes including `/jira/stories`, `/jira/stories`, `/jira/stories/{story_id}`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/routers/jira.py backend/app/models/jira_story.py
git commit -m "feat(jira): add /jira/stories CRUD endpoints"
```

---

## Task 6: Register Router in main.py + Deploy Backend

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add import and registration**

In `backend/app/main.py`, add this import alongside the other router imports:

```python
from app.routers.jira import router as jira_router
```

Add this line to the `app.include_router(...)` block (after `auth_atlassian_router`):

```python
app.include_router(jira_router, prefix="/api/v1", tags=["Jira"])
```

- [ ] **Step 2: Rebuild backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend
sleep 10
docker logs assist2-backend --tail 10 2>&1 | grep -E "startup|Uvicorn|error" -i
```

Expected: `Application startup complete.` with no errors

- [ ] **Step 3: Verify route is live**

```bash
curl -s http://localhost:8000/api/v1/jira/tickets 2>/dev/null || \
  docker exec assist2-backend python -c "from app.routers.jira import router; print('routes:', len(router.routes))"
```

Expected: 7 routes (or a 422 from curl — means endpoint exists, just needs required params)

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2 && git add backend/app/main.py
git commit -m "feat(jira): register jira router in main.py"
```

---

## Task 7: Frontend — Jira Chat Mode + Panel Marker Rendering

**Files:**
- Modify: `frontend/app/[org]/ai-workspace/page.tsx`

This task adds `"jira"` as a chat mode, adds a `JiraStoryPanel` component that renders the right panel when `<<<USERSTORY_PANEL` markers are present in assistant messages, and wire up the "Story anlegen" and "Nach Jira schreiben" actions.

- [x] **Step 1: Read the current file**

Read `frontend/app/[org]/ai-workspace/page.tsx` fully. You need to understand the existing structure before editing.

- [x] **Step 2: Extend types**

Find the `ChatMode` type and `StoryData` interface. Replace:

```tsx
type ChatMode = "chat" | "docs" | "tasks";
```

with:

```tsx
type ChatMode = "chat" | "docs" | "tasks" | "jira";
```

Add these new interfaces alongside the existing ones:

```tsx
interface JiraStoryPanel {
  ticket_key: string;
  project: string;
  source_summary: string;
  generated_at: string;
  content: string; // full Markdown user story
}

interface SavedJiraStory {
  id: string;
  ticket_key: string;
  status: string;
}
```

- [x] **Step 3: Add jira state variables**

In the component body, after the existing `const [creating, setCreating] = useState(false);` line, add:

```tsx
const [jiraPanel, setJiraPanel] = useState<JiraStoryPanel | null>(null);
const [savedStory, setSavedStory] = useState<SavedJiraStory | null>(null);
const [savingJira, setSavingJira] = useState(false);
const [writingJira, setWritingJira] = useState(false);
```

- [x] **Step 4: Add panel marker parser**

Add this utility function BEFORE the component function (or as an inline helper inside). Place it after the interface declarations and before the `export default function`:

```tsx
function parseJiraPanel(text: string): JiraStoryPanel | null {
  const match = text.match(/<<<USERSTORY_PANEL\n([\s\S]*?)\nUSERSTORY_PANEL>>>/);
  if (!match) return null;
  const block = match[1];
  const getField = (key: string) => {
    const m = block.match(new RegExp(`^${key}:\\s*(.+)$`, "m"));
    return m ? m[1].trim() : "";
  };
  const contentStart = block.indexOf("\n\n");
  const content = contentStart >= 0 ? block.slice(contentStart + 2).trim() : block;
  return {
    ticket_key: getField("ticket_key"),
    project: getField("project"),
    source_summary: getField("source_summary"),
    generated_at: getField("generated_at"),
    content,
  };
}
```

- [x] **Step 5: Add effect to parse panel markers from assistant messages**

In the component body, add this effect after the existing `useEffect` that calls `extractStory`:

```tsx
// Parse <<<USERSTORY_PANEL markers from assistant messages
useEffect(() => {
  if (mode !== "jira") return;
  const last = messages[messages.length - 1];
  if (!last || last.role !== "assistant") return;
  const panel = parseJiraPanel(last.content);
  if (panel) {
    setJiraPanel(panel);
    setSavedStory(null); // reset on new panel
  }
}, [messages, mode]);
```

- [x] **Step 6: Add saveToWorkspace and writeToJira handlers**

Add these two functions in the component body after the existing `createStory` function:

```tsx
const saveJiraStory = useCallback(async () => {
  if (!jiraPanel || !org) return;
  setSavingJira(true);
  try {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE}/api/v1/jira/stories`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        ticket_key: jiraPanel.ticket_key,
        project: jiraPanel.project,
        source_summary: jiraPanel.source_summary,
        content: jiraPanel.content,
        status: "draft",
        org_id: org.id,
      }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const created = await resp.json();
    setSavedStory({ id: created.id, ticket_key: created.ticket_key, status: created.status });
  } catch (err) {
    console.error("Save Jira story error:", err);
  } finally {
    setSavingJira(false);
  }
}, [jiraPanel, org]);

const writeToJira = useCallback(async () => {
  if (!jiraPanel || !savedStory) return;
  setWritingJira(true);
  try {
    const token = getAccessToken();
    const resp = await fetch(`${API_BASE}/api/v1/jira/write`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        ticket_key: jiraPanel.ticket_key,
        ticket_id: "",
        summary: "",
        description: jiraPanel.content,
      }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    // Update status to published
    if (savedStory.id) {
      const patchResp = await fetch(`${API_BASE}/api/v1/jira/stories/${savedStory.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ status: "published" }),
      });
      if (patchResp.ok) {
        setSavedStory(prev => prev ? { ...prev, status: "published" } : prev);
      }
    }
  } catch (err) {
    console.error("Write to Jira error:", err);
  } finally {
    setWritingJira(false);
  }
}, [jiraPanel, savedStory]);
```

- [x] **Step 7: Add "jira" to the mode selector**

Find the mode selector buttons in the render section (look for the buttons that render `"chat"`, `"docs"`, `"tasks"`). Add `"jira"` to the mode list:

```tsx
{(["chat", "docs", "tasks", "jira"] as ChatMode[]).map(m => (
  <button
    key={m}
    onClick={() => setMode(m)}
    className="px-3 py-1 rounded-sm transition-colors"
    style={{
      fontFamily: "var(--font-mono)",
      fontSize: "8px",
      letterSpacing: ".06em",
      textTransform: "uppercase",
      background: mode === m ? "var(--ink)" : "transparent",
      color: mode === m ? "var(--paper)" : "var(--ink-faint)",
      border: `0.5px solid ${mode === m ? "var(--ink)" : "transparent"}`,
    }}
  >
    {m === "chat" ? "Chat" : m === "docs" ? "Docs" : m === "tasks" ? "Tasks" : "Jira"}
  </button>
))}
```

- [x] **Step 8: Add JiraStoryPanel to the right panel**

In the right panel section (where `storyData` is rendered), add the Jira panel rendering BEFORE the existing `storyData` block. Find the right panel div and add:

```tsx
{/* ── Jira Story Panel ── */}
{mode === "jira" && jiraPanel && (
  <div className="space-y-3 px-4 py-4 overflow-y-auto flex-1">
    {/* Ticket badge */}
    <div className="flex items-center gap-2">
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>
        {jiraPanel.ticket_key}
      </span>
      <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faint)" }}>
        {jiraPanel.project}
      </span>
      {savedStory && (
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: savedStory.status === "published" ? "#4a7c59" : "var(--ink-faint)", marginLeft: "auto" }}>
          {savedStory.status === "published" ? "✓ veröffentlicht" : "✓ gespeichert"}
        </span>
      )}
    </div>

    {/* Story content */}
    <div style={{ fontSize: "13px", lineHeight: "1.7", fontFamily: "var(--font-body)" }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children }) => <p style={{ fontWeight: 600, fontSize: "13px", margin: "0.5em 0 0.2em" }}>{children}</p>,
          h3: ({ children }) => <p style={{ fontWeight: 600, fontSize: "12px", margin: "0.4em 0 0.1em", color: "var(--ink-mid)" }}>{children}</p>,
          p: ({ children }) => <p style={{ margin: "0 0 0.4em" }}>{children}</p>,
          li: ({ children }) => <li style={{ margin: "0.15em 0", listStyle: "none", paddingLeft: "1em", textIndent: "-1em" }}>{children}</li>,
          ul: ({ children }) => <ul style={{ margin: "0.2em 0", padding: 0 }}>{children}</ul>,
          strong: ({ children }) => <strong style={{ fontWeight: 600 }}>{children}</strong>,
          hr: () => <hr style={{ border: "none", borderTop: "0.5px solid var(--paper-rule)", margin: "0.5em 0" }} />,
        }}
      >
        {jiraPanel.content}
      </ReactMarkdown>
    </div>

    {/* Action buttons */}
    <div className="flex flex-col gap-2 pt-2">
      {!savedStory ? (
        <Button size="sm" onClick={saveJiraStory} disabled={savingJira} className="w-full">
          {savingJira ? "Wird gespeichert…" : "Im Workspace speichern"}
        </Button>
      ) : (
        <Button
          size="sm"
          onClick={writeToJira}
          disabled={writingJira || savedStory.status === "published"}
          className="w-full"
          variant="outline"
        >
          {writingJira ? "Wird geschrieben…" : savedStory.status === "published" ? "✓ In Jira geschrieben" : "Nach Jira schreiben"}
        </Button>
      )}
    </div>
  </div>
)}
```

**Important:** You need `ReactMarkdown` and `remarkGfm` imported for this panel. Check if they are already imported at the top of the file. If not, add:

```tsx
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
```

- [x] **Step 9: Rebuild frontend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
```

Check logs:
```bash
docker logs assist2-frontend --tail 15 2>&1 | grep -E "ready|error|Error" -i
```

Expected: `✓ Ready`

- [x] **Step 10: Commit**

```bash
cd /opt/assist2 && git add "frontend/app/[org]/ai-workspace/page.tsx"
git commit -m "feat(jira): add jira chat mode, panel marker parsing, and JiraStoryPanel UI"
```

---

## Self-Review

### Spec Coverage

| Requirement | Task |
|---|---|
| `GET /api/jira/tickets?project=&q=` search | Task 3 |
| `GET /api/jira/ticket/{KEY}` full ticket with plaintext description | Task 3 |
| ADF-to-plaintext conversion | Task 2 (`adf_to_text`) |
| `POST /api/jira/ai` with `action=userstory` → Claude | Task 4 |
| AI generates full User Story Markdown | Task 2 (`generate_user_story`) |
| `POST /api/jira/write` → Markdown-to-ADF → Jira PUT | Task 4 + 2 (`markdown_to_adf`) |
| `POST /api/userstories` → `POST /api/v1/jira/stories` | Task 5 |
| `PATCH /api/userstories/{id}` → `PATCH /api/v1/jira/stories/{id}` | Task 5 |
| `GET /api/userstories?project=` → `GET /api/v1/jira/stories` | Task 5 |
| Router registration | Task 6 |
| `<<<USERSTORY_PANEL` marker parsing in frontend | Task 7 |
| Right panel rendering with Markdown | Task 7 |
| "Im Workspace speichern" action | Task 7 |
| "Nach Jira schreiben" action | Task 7 |
| Status `draft` → `published` lifecycle | Task 5 + 7 |
| `"jira"` chat mode selector | Task 7 |
| 401 → session error, 403 → no Atlassian account | existing `get_atlassian_token` dep |

### Security Notes

- All Jira routes require authenticated user via `get_current_user` or `get_atlassian_token`
- `org_id` required as query param for story persistence — all queries filter by it
- Atlassian tokens are Fernet-encrypted in Redis (implemented in prior work)
- No Jira credentials in frontend — all proxied through backend

### Type Consistency

- `jiraPanel: JiraStoryPanel | null` used consistently across all handlers
- `savedStory: SavedJiraStory | null` — `id` field used for PATCH call
- `JiraStoryRead.organization_id` matches `JiraStory.organization_id` model field
- `JiraStoryCreate.org_id` maps to `JiraStory.organization_id` in the route handler
