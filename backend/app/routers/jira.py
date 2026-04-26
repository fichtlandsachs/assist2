"""Jira REST API proxy endpoints."""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import json as _json

from app.database import get_db
from app.deps import get_atlassian_token, get_current_user
from app.models.feature import Feature
from app.models.jira_story import JiraStory
from app.models.organization import Organization
from app.models.test_case import TestCase
from app.models.user import User
from app.core.story_filter import active_stories
from app.models.user_story import UserStory
from app.services import org_integrations_service as org_svc
from app.services.jira_service import jira_service
from app.tasks.rag_tasks import index_jira_ticket

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jira", tags=["Jira"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class JiraAIRequest(BaseModel):
    action: str  # "userstory"
    summary: str
    description: str = ""


class JiraCreateRequest(BaseModel):
    project_key: str
    summary: str
    description: str = ""
    issue_type: str = "Story"
    org_id: uuid.UUID | None = None


class JiraWriteRequest(BaseModel):
    ticket_key: str
    ticket_id: str = ""
    summary: str = ""
    description: str
    org_id: uuid.UUID | None = None


async def _resolve_jira_auth(
    org_id: uuid.UUID | None,
    current_user: User,
    db: AsyncSession,
) -> dict:
    """Return Jira auth info. Tries OAuth first, falls back to org basic auth.

    Returns either:
      {"type": "oauth", "access_token": ..., "cloud_id": ...}
      {"type": "basic", "base_url": ..., "user": ..., "api_token": ...}
    Raises 403 when neither is available.
    """
    from app.services.atlassian_token import atlassian_token_store
    data = await atlassian_token_store.get(current_user.id)
    if data:
        token = await atlassian_token_store.get_valid_token(current_user.id)
        return {"type": "oauth", "access_token": token, "cloud_id": data["cloud_id"]}

    if org_id:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one_or_none()
        if org:
            base_url = org_svc._get_section(org, "jira").get("base_url", "")
            user = org_svc._get_section(org, "jira").get("user", "")
            api_token = org_svc.get_jira_token(org)
            if base_url and user and api_token:
                return {"type": "basic", "base_url": base_url, "user": user, "api_token": api_token}

    raise HTTPException(
        status_code=403,
        detail="Kein Atlassian-Account verknüpft. Bitte OAuth oder API-Token in den Integrationseinstellungen konfigurieren.",
    )


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


class JiraSyncItem(BaseModel):
    item_type: str          # "story" | "feature" | "testcase"
    item_id: str            # UUID of the HeyKarl record
    jira_key: str
    jira_url: str
    heykarl_title: str
    jira_title: str
    title_changed: bool
    heykarl_description: str
    jira_description: str
    description_changed: bool

class JiraSyncPreviewResponse(BaseModel):
    items: list[JiraSyncItem]
    in_sync: bool

class JiraSyncApplyRequest(BaseModel):
    story_id: uuid.UUID
    org_id: uuid.UUID
    apply_ids: list[str]    # item_ids to overwrite in HeyKarl

class JiraPushStoryRequest(BaseModel):
    story_id: uuid.UUID
    project_key: str
    issue_type: str = "Story"
    feature_issue_type: str = "Feature"
    testcase_issue_type: str = "Testcase"
    dod_issue_type: str = "DefinitionOfDone"
    org_id: uuid.UUID


@router.post("/sync-preview", response_model=JiraSyncPreviewResponse)
async def sync_preview(
    body: JiraSyncApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JiraSyncPreviewResponse:
    """Fetch linked Jira tickets and return a diff against HeyKarl data."""
    auth = await _resolve_jira_auth(body.org_id, current_user, db)
    if auth["type"] != "basic":
        raise HTTPException(status_code=400, detail="Sync wird nur mit API-Token unterstützt")
    b, u, t = auth["base_url"], auth["user"], auth["api_token"]

    story_result = await db.execute(
        active_stories().where(UserStory.id == body.story_id, UserStory.organization_id == body.org_id)
    )
    story = story_result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story nicht gefunden")

    org_result = await db.execute(select(Organization).where(Organization.id == body.org_id))
    org = org_result.scalar_one_or_none()
    base_browse = org_svc._get_section(org, "jira").get("base_url", "").rstrip("/") if org else ""

    def browse(key: str) -> str:
        return f"{base_browse}/browse/{key}" if base_browse else ""

    def _diff(hk: str, ji: str) -> bool:
        return (hk or "").strip() != (ji or "").strip()

    items: list[JiraSyncItem] = []

    # Story
    if story.jira_ticket_key:
        jt = await jira_service.get_ticket_basic(b, u, t, story.jira_ticket_key)
        if jt:
            hk_desc = "\n\n".join(filter(None, [story.description or "", f"Akzeptanzkriterien:\n{story.acceptance_criteria}" if story.acceptance_criteria else ""]))
            items.append(JiraSyncItem(
                item_type="story", item_id=str(story.id), jira_key=jt["key"], jira_url=browse(jt["key"]),
                heykarl_title=story.title, jira_title=jt["summary"],
                title_changed=_diff(story.title, jt["summary"]),
                heykarl_description=hk_desc, jira_description=jt["description"],
                description_changed=_diff(hk_desc, jt["description"]),
            ))

    # Features
    feat_result = await db.execute(select(Feature).where(Feature.story_id == story.id))
    for feat in feat_result.scalars().all():
        if not feat.jira_ticket_key:
            continue
        jt = await jira_service.get_ticket_basic(b, u, t, feat.jira_ticket_key)
        if jt:
            items.append(JiraSyncItem(
                item_type="feature", item_id=str(feat.id), jira_key=jt["key"], jira_url=browse(jt["key"]),
                heykarl_title=feat.title, jira_title=jt["summary"],
                title_changed=_diff(feat.title, jt["summary"]),
                heykarl_description=feat.description or "", jira_description=jt["description"],
                description_changed=_diff(feat.description or "", jt["description"]),
            ))

    # Test cases
    tc_result = await db.execute(select(TestCase).where(TestCase.story_id == story.id))
    for tc in tc_result.scalars().all():
        if not tc.jira_ticket_key:
            continue
        jt = await jira_service.get_ticket_basic(b, u, t, tc.jira_ticket_key)
        if jt:
            hk_desc = "\n\n".join(filter(None, [f"Schritte:\n{tc.steps}" if tc.steps else "", f"Erwartetes Ergebnis:\n{tc.expected_result}" if tc.expected_result else ""]))
            items.append(JiraSyncItem(
                item_type="testcase", item_id=str(tc.id), jira_key=jt["key"], jira_url=browse(jt["key"]),
                heykarl_title=tc.title, jira_title=jt["summary"],
                title_changed=_diff(tc.title, jt["summary"]),
                heykarl_description=hk_desc, jira_description=jt["description"],
                description_changed=_diff(hk_desc, jt["description"]),
            ))

    changed = [i for i in items if i.title_changed or i.description_changed]
    return JiraSyncPreviewResponse(items=changed, in_sync=len(changed) == 0)


@router.post("/sync-apply")
async def sync_apply(
    body: JiraSyncApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Apply selected Jira changes back into HeyKarl."""
    auth = await _resolve_jira_auth(body.org_id, current_user, db)
    if auth["type"] != "basic":
        raise HTTPException(status_code=400, detail="Sync wird nur mit API-Token unterstützt")
    b, u, t = auth["base_url"], auth["user"], auth["api_token"]

    story_result = await db.execute(
        active_stories().where(UserStory.id == body.story_id, UserStory.organization_id == body.org_id)
    )
    story = story_result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story nicht gefunden")

    apply_set = set(body.apply_ids)
    updated = 0

    # Story
    if str(story.id) in apply_set and story.jira_ticket_key:
        jt = await jira_service.get_ticket_basic(b, u, t, story.jira_ticket_key)
        if jt:
            story.title = jt["summary"] or story.title
            # Split description back into description + acceptance_criteria heuristically
            desc_text = jt["description"]
            if "Akzeptanzkriterien:" in desc_text:
                parts = desc_text.split("Akzeptanzkriterien:", 1)
                story.description = parts[0].strip() or None
                story.acceptance_criteria = parts[1].strip() or None
            else:
                story.description = desc_text or None
            updated += 1

    # Features
    feat_result = await db.execute(select(Feature).where(Feature.story_id == story.id))
    for feat in feat_result.scalars().all():
        if str(feat.id) not in apply_set or not feat.jira_ticket_key:
            continue
        jt = await jira_service.get_ticket_basic(b, u, t, feat.jira_ticket_key)
        if jt:
            feat.title = jt["summary"] or feat.title
            feat.description = jt["description"] or feat.description
            updated += 1

    # Test cases
    tc_result = await db.execute(select(TestCase).where(TestCase.story_id == story.id))
    for tc in tc_result.scalars().all():
        if str(tc.id) not in apply_set or not tc.jira_ticket_key:
            continue
        jt = await jira_service.get_ticket_basic(b, u, t, tc.jira_ticket_key)
        if jt:
            tc.title = jt["summary"] or tc.title
            updated += 1

    await db.commit()
    return {"updated": updated}


@router.post("/push-story")
async def push_story_full(
    body: JiraPushStoryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create Jira tickets for a story plus all its features, test cases and DoD items."""
    auth = await _resolve_jira_auth(body.org_id, current_user, db)
    if auth["type"] != "basic":
        raise HTTPException(status_code=400, detail="Push-Story wird nur mit API-Token unterstützt")

    # Resolve browse base URL
    org_result = await db.execute(select(Organization).where(Organization.id == body.org_id))
    org = org_result.scalar_one_or_none()
    base_browse = ""
    if org:
        base_browse = org_svc._get_section(org, "jira").get("base_url", "").rstrip("/")

    def browse(key: str) -> str:
        return f"{base_browse}/browse/{key}" if base_browse else ""

    # Load story
    story_result = await db.execute(
        active_stories().where(UserStory.id == body.story_id, UserStory.organization_id == body.org_id)
    )
    story = story_result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story nicht gefunden")

    b, u, t = auth["base_url"], auth["user"], auth["api_token"]
    created: list[dict] = []
    errors: list[str] = []

    # ── 1. Create / update main story ticket ────────────────────────────────
    story_desc = "\n\n".join(filter(None, [
        story.description or "",
        f"**Akzeptanzkriterien:**\n{story.acceptance_criteria}" if story.acceptance_criteria else "",
    ]))
    try:
        if story.jira_ticket_key:
            await jira_service.write_ticket_basic(b, u, t, story.jira_ticket_key, story.title, story_desc)
            main_key = story.jira_ticket_key
        else:
            res = await jira_service.create_ticket_basic(b, u, t, body.project_key, story.title, story_desc, body.issue_type)
            main_key = res["key"]
            story.jira_ticket_key = main_key
            story.jira_ticket_url = browse(main_key)
        created.append({"type": "story", "key": main_key, "url": browse(main_key)})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Story-Ticket fehlgeschlagen: {exc}")

    async def _create_child(summary: str, description: str, issue_type: str, label: str) -> str | None:
        """Create a child issue under main_key.

        Tries to set parent field first (next-gen projects).  If Jira rejects
        it (classic project hierarchy rules), retries without parent and adds
        an issue link instead.
        """
        # Attempt 1: with parent field (next-gen / sub-task hierarchy)
        try:
            res = await jira_service.create_ticket_basic(
                b, u, t, body.project_key, summary, description, issue_type, parent_key=main_key
            )
            return res["key"]
        except Exception:
            pass  # fall through to attempt 2

        # Attempt 2: create without parent, then link
        try:
            res = await jira_service.create_ticket_basic(
                b, u, t, body.project_key, summary, description, issue_type
            )
        except Exception as exc:
            errors.append(f"{label}: Erstellen fehlgeschlagen: {exc}")
            return None

        child_key = res["key"]
        try:
            await jira_service.link_issues_basic(b, u, t, child_key, main_key)
        except Exception as exc:
            errors.append(f"{label}: Verknüpfung fehlgeschlagen: {exc}")
        return child_key

    # ── 2. Features ──────────────────────────────────────────────────────────
    feat_result = await db.execute(select(Feature).where(Feature.story_id == story.id))
    for feat in feat_result.scalars().all():
        if feat.jira_ticket_key:
            created.append({"type": "feature", "key": feat.jira_ticket_key, "title": feat.title, "url": feat.jira_ticket_url or browse(feat.jira_ticket_key), "existing": True})
            continue
        key = await _create_child(feat.title, feat.description or "", body.feature_issue_type, f"Feature '{feat.title}'")
        if key:
            feat.jira_ticket_key = key
            feat.jira_ticket_url = browse(key)
            created.append({"type": "feature", "key": key, "title": feat.title, "url": browse(key)})

    # ── 3. Test cases ────────────────────────────────────────────────────────
    tc_result = await db.execute(select(TestCase).where(TestCase.story_id == story.id))
    for tc in tc_result.scalars().all():
        if tc.jira_ticket_key:
            created.append({"type": "testcase", "key": tc.jira_ticket_key, "title": tc.title, "url": tc.jira_ticket_url or browse(tc.jira_ticket_key), "existing": True})
            continue
        desc_parts = [tc.title]
        if tc.steps:
            desc_parts.append(f"**Schritte:**\n{tc.steps}")
        if tc.expected_result:
            desc_parts.append(f"**Erwartetes Ergebnis:**\n{tc.expected_result}")
        key = await _create_child(tc.title, "\n\n".join(desc_parts), body.testcase_issue_type, f"Testfall '{tc.title}'")
        if key:
            tc.jira_ticket_key = key
            tc.jira_ticket_url = browse(key)
            created.append({"type": "testcase", "key": key, "title": tc.title, "url": browse(key)})

    # ── 4. DoD items (no persistent key — recreate only if not yet pushed) ───
    dod_items: list[dict] = []
    if story.definition_of_done:
        try:
            dod_items = _json.loads(story.definition_of_done)
        except Exception:
            pass
    for item in dod_items:
        text = item.get("text", "").strip()
        if not text:
            continue
        if item.get("jira_ticket_key"):
            created.append({"type": "dod", "key": item["jira_ticket_key"], "title": text, "url": item.get("jira_ticket_url", browse(item["jira_ticket_key"])), "existing": True})
            continue
        key = await _create_child(text, "", body.dod_issue_type, f"DoD '{text}'")
        if key:
            item["jira_ticket_key"] = key
            item["jira_ticket_url"] = browse(key)
            created.append({"type": "dod", "key": key, "title": text, "url": browse(key)})

    # Persist updated DoD with Jira keys
    if dod_items and any("jira_ticket_key" in i for i in dod_items):
        story.definition_of_done = _json.dumps(dod_items)

    await db.commit()
    return {"main_key": main_key, "main_url": browse(main_key), "created": created, "errors": errors}


@router.get("/issue-types")
async def get_issue_types(
    project_key: str = Query(...),
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return available issue types for a Jira project."""
    auth = await _resolve_jira_auth(org_id, current_user, db)
    if auth["type"] == "basic":
        types = await jira_service.get_issue_types_basic(
            base_url=auth["base_url"],
            user=auth["user"],
            api_token=auth["api_token"],
            project_key=project_key,
        )
    else:
        types = []  # OAuth path not implemented yet
    return {"issue_types": types}


@router.post("/create")
async def create_ticket(
    body: JiraCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new Jira issue and return {ticket_key}."""
    auth = await _resolve_jira_auth(body.org_id, current_user, db)
    try:
        if auth["type"] == "oauth":
            result = await jira_service.create_ticket(
                access_token=auth["access_token"],
                cloud_id=auth["cloud_id"],
                project_key=body.project_key,
                summary=body.summary,
                description_md=body.description,
                issue_type=body.issue_type,
            )
        else:
            result = await jira_service.create_ticket_basic(
                base_url=auth["base_url"],
                user=auth["user"],
                api_token=auth["api_token"],
                project_key=body.project_key,
                summary=body.summary,
                description_md=body.description,
                issue_type=body.issue_type,
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 400:
            try:
                body_json = exc.response.json()  # type: ignore[union-attr]
                msgs = list(body_json.get("errors", {}).values()) + body_json.get("errorMessages", [])
                detail = "; ".join(str(m) for m in msgs) if msgs else f"Ungültiger Projektschlüssel oder Issue-Typ: {body.project_key}"
            except Exception:
                detail = f"Ungültiger Projektschlüssel oder Issue-Typ: {body.project_key}"
            raise HTTPException(status_code=400, detail=detail)
        logger.error("Jira create error: %s", exc)
        raise HTTPException(status_code=502, detail="Jira Create fehlgeschlagen")
    # Build browse URL — always use the org's configured base_url regardless of auth type
    ticket_url = None
    if body.org_id:
        org_result = await db.execute(select(Organization).where(Organization.id == body.org_id))
        org = org_result.scalar_one_or_none()
        if org:
            base_url = org_svc._get_section(org, "jira").get("base_url", "").rstrip("/")
            if base_url:
                ticket_url = f"{base_url}/browse/{result['key']}"
    if not ticket_url and auth["type"] == "basic":
        ticket_url = f"{auth['base_url'].rstrip('/')}/browse/{result['key']}"
    return {"ticket_key": result["key"], "ticket_id": result["id"], "ticket_url": ticket_url}


@router.post("/write")
async def write_ticket(
    body: JiraWriteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Write a user story (Markdown) back to Jira as ADF description."""
    auth = await _resolve_jira_auth(body.org_id, current_user, db)
    try:
        if auth["type"] == "oauth":
            await jira_service.write_ticket(
                access_token=auth["access_token"],
                cloud_id=auth["cloud_id"],
                key=body.ticket_key.upper(),
                summary=body.summary,
                description_md=body.description,
            )
        else:
            await jira_service.write_ticket_basic(
                base_url=auth["base_url"],
                user=auth["user"],
                api_token=auth["api_token"],
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
    index_jira_ticket.delay(story.ticket_key, str(story.organization_id))
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
