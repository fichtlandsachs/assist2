"""Process registry and story process changes router."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models.process import Process
from app.models.story_process_change import StoryProcessChange, ProcessChangeStatus
from app.models.user_story import UserStory, StoryStatus, StoryPriority
from app.models.epic import Epic, EpicStatus
from app.models.user import User
from app.schemas.process import (
    ProcessCreate, ProcessUpdate, ProcessRead,
    StoryProcessChangeCreate, StoryProcessChangeUpdate, StoryProcessChangeRead,
    EpicProcessSummary,
)
from app.core.exceptions import NotFoundException

router = APIRouter()


# ── Process-request schemas ───────────────────────────────────────────────────

class ProcessRequestCreate(BaseModel):
    proposed_name: str
    capability_node_id: Optional[uuid.UUID] = None


class ProcessRequestDescribe(BaseModel):
    """Update the epic + story description after chat conversation."""
    epic_description: Optional[str] = None
    story_description: Optional[str] = None
    story_acceptance_criteria: Optional[str] = None


class ProcessRequestRead(BaseModel):
    id: uuid.UUID
    proposed_name: str
    capability_node_id: Optional[uuid.UUID]
    epic_id: Optional[uuid.UUID]
    story_id: Optional[uuid.UUID]
    status: str
    created_at: datetime


# ── Processes CRUD ────────────────────────────────────────────────────────────

@router.get("/processes", response_model=List[ProcessRead])
async def list_processes(
    org_id: uuid.UUID,
    capability_node_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProcessRead]:
    """
    List processes for an org.
    If capability_node_id is provided, return processes assigned to that node
    PLUS processes with no node assigned (global processes).
    If no capability filter, return all processes.
    """
    stmt = select(Process).where(Process.organization_id == org_id)
    if capability_node_id:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                Process.capability_node_id == capability_node_id,
                Process.capability_node_id.is_(None),
            )
        )
    stmt = stmt.order_by(Process.capability_node_id.is_(None), Process.name)
    result = await db.execute(stmt)
    return [ProcessRead.model_validate(p) for p in result.scalars().all()]


@router.post("/processes", response_model=ProcessRead, status_code=status.HTTP_201_CREATED)
async def create_process(
    org_id: uuid.UUID,
    data: ProcessCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessRead:
    process = Process(
        organization_id=org_id,
        name=data.name,
        confluence_page_id=data.confluence_page_id,
        capability_node_id=data.capability_node_id,
    )
    db.add(process)
    await db.commit()
    await db.refresh(process)
    return ProcessRead.model_validate(process)


# ── Process Request: auto-create Epic + Story stub ────────────────────────────

@router.post("/process-requests", response_model=ProcessRequestRead, status_code=201)
async def create_process_request(
    org_id: uuid.UUID,
    data: ProcessRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessRequestRead:
    """
    A user requests a new process that doesn't exist yet.
    We automatically:
    1. Create an Epic: "Neuer Prozess: <proposed_name>"
    2. Create a UserStory assigned to that Epic: "Prozess beschreiben: <proposed_name>"
    3. Store the ProcessRequest row linking both.
    The chat will then guide the user to fill in descriptions.
    """
    # 1. Create Epic
    epic_title = f"Neuer Prozess: {data.proposed_name}"
    epic = Epic(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=epic_title,
        description=None,
        status=EpicStatus.planning,
    )
    db.add(epic)
    await db.flush()

    # 2. Create UserStory stub assigned to Epic
    story_title = f"Prozess beschreiben: {data.proposed_name}"
    story = UserStory(
        organization_id=org_id,
        created_by_id=current_user.id,
        title=story_title,
        description=None,
        status=StoryStatus.draft,
        priority=StoryPriority.medium,
        epic_id=epic.id,
    )
    db.add(story)
    await db.flush()

    # 3. Create ProcessRequest
    from sqlalchemy import text
    req_id = uuid.uuid4()
    await db.execute(
        text("""
            INSERT INTO process_requests
              (id, organization_id, requested_by_id, capability_node_id,
               proposed_name, epic_id, story_id, status, created_at, updated_at)
            VALUES
              (:id, :org_id, :user_id, :cap_id,
               :name, :epic_id, :story_id, 'pending_description', now(), now())
        """),
        {
            "id": req_id,
            "org_id": org_id,
            "user_id": current_user.id,
            "cap_id": data.capability_node_id,
            "name": data.proposed_name,
            "epic_id": epic.id,
            "story_id": story.id,
        }
    )
    await db.commit()

    return ProcessRequestRead(
        id=req_id,
        proposed_name=data.proposed_name,
        capability_node_id=data.capability_node_id,
        epic_id=epic.id,
        story_id=story.id,
        status="pending_description",
        created_at=datetime.now(timezone.utc),
    )


@router.patch("/process-requests/{request_id}/describe")
async def describe_process_request(
    request_id: uuid.UUID,
    data: ProcessRequestDescribe,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Called by the chat when the user has provided epic/story descriptions.
    Updates the epic description and story description + acceptance criteria.
    """
    from sqlalchemy import text
    row = (await db.execute(
        text("SELECT epic_id, story_id FROM process_requests WHERE id = :id"),
        {"id": request_id}
    )).fetchone()
    if not row:
        raise HTTPException(404, "ProcessRequest not found")

    epic_id, story_id = row

    if epic_id and data.epic_description:
        epic = await db.get(Epic, epic_id)
        if epic:
            epic.description = data.epic_description

    if story_id:
        story = await db.get(UserStory, story_id)
        if story:
            if data.story_description:
                story.description = data.story_description
            if data.story_acceptance_criteria:
                story.acceptance_criteria = data.story_acceptance_criteria

    await db.execute(
        text("UPDATE process_requests SET status='described', updated_at=now() WHERE id=:id"),
        {"id": request_id}
    )
    await db.commit()

    return {
        "status": "described",
        "epic_id": str(epic_id) if epic_id else None,
        "story_id": str(story_id) if story_id else None,
    }


@router.patch("/processes/{process_id}", response_model=ProcessRead)
async def update_process(
    process_id: uuid.UUID,
    data: ProcessUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessRead:
    stmt = select(Process).where(Process.id == process_id)
    result = await db.execute(stmt)
    process = result.scalar_one_or_none()
    if process is None:
        raise NotFoundException("Prozess nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(process, field, value)
    await db.commit()
    await db.refresh(process)
    return ProcessRead.model_validate(process)


@router.delete("/processes/{process_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_process(
    process_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(Process).where(Process.id == process_id)
    result = await db.execute(stmt)
    process = result.scalar_one_or_none()
    if process is None:
        raise NotFoundException("Prozess nicht gefunden")
    await db.delete(process)
    await db.commit()


# ── Story Process Changes ─────────────────────────────────────────────────────

@router.get("/user-stories/{story_id}/process-changes", response_model=List[StoryProcessChangeRead])
async def list_story_process_changes(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[StoryProcessChangeRead]:
    stmt = (
        select(StoryProcessChange)
        .where(StoryProcessChange.story_id == story_id)
        .options(selectinload(StoryProcessChange.process))
        .order_by(StoryProcessChange.created_at)
    )
    result = await db.execute(stmt)
    return [StoryProcessChangeRead.model_validate(c) for c in result.scalars().all()]


@router.post(
    "/user-stories/{story_id}/process-changes",
    response_model=StoryProcessChangeRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_story_process_change(
    story_id: uuid.UUID,
    data: StoryProcessChangeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryProcessChangeRead:
    change = StoryProcessChange(
        story_id=story_id,
        process_id=data.process_id,
        section_anchor=data.section_anchor,
        delta_text=data.delta_text,
        status=ProcessChangeStatus.pending,
    )
    db.add(change)
    await db.commit()
    await db.refresh(change)
    # reload with process relationship
    stmt = (
        select(StoryProcessChange)
        .where(StoryProcessChange.id == change.id)
        .options(selectinload(StoryProcessChange.process))
    )
    result = await db.execute(stmt)
    return StoryProcessChangeRead.model_validate(result.scalar_one())


@router.patch(
    "/user-stories/{story_id}/process-changes/{change_id}",
    response_model=StoryProcessChangeRead,
)
async def update_story_process_change(
    story_id: uuid.UUID,
    change_id: uuid.UUID,
    data: StoryProcessChangeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoryProcessChangeRead:
    stmt = (
        select(StoryProcessChange)
        .where(StoryProcessChange.id == change_id, StoryProcessChange.story_id == story_id)
        .options(selectinload(StoryProcessChange.process))
    )
    result = await db.execute(stmt)
    change = result.scalar_one_or_none()
    if change is None:
        raise NotFoundException("Prozessänderung nicht gefunden")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(change, field, value)
    await db.commit()
    await db.refresh(change)
    return StoryProcessChangeRead.model_validate(change)


@router.delete(
    "/user-stories/{story_id}/process-changes/{change_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_story_process_change(
    story_id: uuid.UUID,
    change_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(StoryProcessChange).where(
        StoryProcessChange.id == change_id,
        StoryProcessChange.story_id == story_id,
    )
    result = await db.execute(stmt)
    change = result.scalar_one_or_none()
    if change is None:
        raise NotFoundException("Prozessänderung nicht gefunden")
    await db.delete(change)
    await db.commit()


# ── Epic Aggregation ──────────────────────────────────────────────────────────

@router.get("/epics/{epic_id}/process-changes", response_model=List[EpicProcessSummary])
async def get_epic_process_changes(
    epic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[EpicProcessSummary]:
    """Return pending process changes for all stories in this epic, grouped by process."""
    stories_stmt = select(UserStory.id).where(UserStory.epic_id == epic_id)
    stories_result = await db.execute(stories_stmt)
    story_ids = [row[0] for row in stories_result.all()]

    if not story_ids:
        return []

    changes_stmt = (
        select(StoryProcessChange)
        .where(
            StoryProcessChange.story_id.in_(story_ids),
            StoryProcessChange.status == ProcessChangeStatus.pending,
        )
        .options(selectinload(StoryProcessChange.process))
        .order_by(StoryProcessChange.created_at)
    )
    changes_result = await db.execute(changes_stmt)
    changes = changes_result.scalars().all()

    # Group by process
    grouped: dict[uuid.UUID, list[StoryProcessChange]] = {}
    processes: dict[uuid.UUID, Process] = {}
    for change in changes:
        pid = change.process_id
        if pid not in grouped:
            grouped[pid] = []
            processes[pid] = change.process
        grouped[pid].append(change)

    return [
        EpicProcessSummary(
            process=ProcessRead.model_validate(processes[pid]),
            pending_count=len(group),
            changes=[StoryProcessChangeRead.model_validate(c) for c in group],
        )
        for pid, group in grouped.items()
    ]


# ── Confluence Update Trigger ─────────────────────────────────────────────────

@router.post("/epics/{epic_id}/process-changes/publish", status_code=status.HTTP_202_ACCEPTED)
async def publish_epic_process_changes(
    epic_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Trigger AI-based update of all Confluence process pages affected by pending
    changes in this epic's stories.
    """
    from app.models.organization import Organization
    from app.services import org_integrations_service as integrations_svc
    from app.services import confluence_service

    org_stmt = select(Organization).where(Organization.id == org_id)
    org = (await db.execute(org_stmt)).scalar_one_or_none()
    if org is None:
        raise NotFoundException("Organisation nicht gefunden")

    creds = integrations_svc.get_confluence_credentials(org)
    if not creds or not confluence_service.is_configured(*creds):
        raise HTTPException(
            status_code=422,
            detail="Confluence ist nicht konfiguriert.",
        )
    b_url, b_user, b_token = creds

    # Load all pending changes for this epic
    stories_stmt = select(UserStory.id).where(UserStory.epic_id == epic_id)
    story_ids = [row[0] for row in (await db.execute(stories_stmt)).all()]

    if not story_ids:
        return {"updated": 0}

    changes_stmt = (
        select(StoryProcessChange)
        .where(
            StoryProcessChange.story_id.in_(story_ids),
            StoryProcessChange.status == ProcessChangeStatus.pending,
        )
        .options(selectinload(StoryProcessChange.process))
    )
    changes = (await db.execute(changes_stmt)).scalars().all()

    # Group by process
    grouped: dict[uuid.UUID, list[StoryProcessChange]] = {}
    processes: dict[uuid.UUID, Process] = {}
    for change in changes:
        pid = change.process_id
        if pid not in grouped:
            grouped[pid] = []
            processes[pid] = change.process
        grouped[pid].append(change)

    updated = 0
    for pid, group in grouped.items():
        proc = processes[pid]
        if not proc.confluence_page_id:
            continue
        try:
            await confluence_service.update_process_page(
                page_id=proc.confluence_page_id,
                process_name=proc.name,
                changes=[
                    {"section_anchor": c.section_anchor, "delta_text": c.delta_text}
                    for c in group
                ],
                base_url=b_url,
                user=b_user,
                token=b_token,
            )
            now = datetime.now(timezone.utc)
            for change in group:
                change.status = ProcessChangeStatus.released
                change.released_at = now
            updated += 1
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Confluence-Fehler für Prozess '{proc.name}': {exc}") from exc

    await db.commit()
    return {"updated": updated}
