"""BCM context + Process Mapping Suggestion endpoints.

Minimalinvasive Erweiterung – baut auf der bestehenden capability_nodes /
initialization_status Infrastruktur auf.

BCM aktiv = initialization_status == "initialized"
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.organization import Organization, OrgInitializationStatus
from app.models.process_suggestion import ProcessMappingSuggestion, SuggestionStatus
from app.models.audit_log import AuditLog
from app.models.user import User

router = APIRouter(tags=["BCM"])

CONFIDENCE_AUTO_ASSIGN = 0.85
CONFIDENCE_SUGGEST = 0.50


# ── Schemas ────────────────────────────────────────────────────────────────────

class OrgBcmContext(BaseModel):
    """Session-init payload. Frontend nutzt skip_bcm_questions als einzigen Guard."""
    has_active_bcm: bool
    initialization_status: str
    bcm_last_updated: Optional[datetime]
    skip_bcm_questions: bool
    capability_map_version: int


class SuggestionCreate(BaseModel):
    process_name: str
    detected_context: Optional[str] = None
    suggested_node_id: Optional[uuid.UUID] = None
    suggested_node_title: Optional[str] = None
    confidence_score: float = 0.0
    source_reference: Optional[str] = None


class SuggestionDecision(BaseModel):
    action: str
    admin_note: Optional[str] = None
    target_node_id: Optional[uuid.UUID] = None
    new_process_name: Optional[str] = None

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"confirm", "reject", "rename", "reassign_capability", "create_process"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v


class SuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    process_name: str
    detected_context: Optional[str]
    suggested_node_id: Optional[uuid.UUID]
    suggested_node_title: Optional[str]
    confidence_score: float
    source_reference: Optional[str]
    status: SuggestionStatus
    admin_note: Optional[str]
    reviewed_by: Optional[uuid.UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_org(org_id: uuid.UUID, db: AsyncSession) -> Organization:
    result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organisation nicht gefunden.")
    return org


def _is_bcm_active(org: Organization) -> bool:
    return org.initialization_status == OrgInitializationStatus.initialized


async def _write_audit(
    db: AsyncSession,
    org_id: uuid.UUID,
    entity_id: uuid.UUID,
    action: str,
    actor_id: uuid.UUID,
    new_value: Optional[dict] = None,
    old_value: Optional[dict] = None,
) -> None:
    log = AuditLog(
        org_id=org_id,
        entity_type="bcm_suggestion",
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        actor_type="user",
        new_value=new_value,
        old_value=old_value,
    )
    db.add(log)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/api/v1/organizations/{org_id}/bcm/context", response_model=OrgBcmContext)
async def get_bcm_context(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> OrgBcmContext:
    """
    Liefert den BCM-State für eine Organisation.
    skip_bcm_questions=true wenn initialization_status == 'initialized'.
    Wird beim Session-Start vom Frontend/Chat abgerufen.
    """
    org = await _get_org(org_id, db)
    active = _is_bcm_active(org)
    return OrgBcmContext(
        has_active_bcm=active,
        initialization_status=org.initialization_status,
        bcm_last_updated=org.initialization_completed_at,
        skip_bcm_questions=active,
        capability_map_version=org.capability_map_version or 0,
    )


@router.get("/api/v1/organizations/{org_id}/bcm/suggestions", response_model=List[SuggestionRead])
async def list_suggestions(
    org_id: uuid.UUID,
    status_filter: str = Query("pending"),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> List[SuggestionRead]:
    """Admin-Inbox: listet Mapping-Vorschläge nach Status."""
    stmt = select(ProcessMappingSuggestion).where(ProcessMappingSuggestion.org_id == org_id)
    if status_filter != "all":
        try:
            sf = SuggestionStatus(status_filter)
            stmt = stmt.where(ProcessMappingSuggestion.status == sf)
        except ValueError:
            pass
    stmt = stmt.order_by(ProcessMappingSuggestion.created_at.desc())
    result = await db.execute(stmt)
    return [SuggestionRead.model_validate(s) for s in result.scalars().all()]


@router.post(
    "/api/v1/organizations/{org_id}/bcm/suggestions",
    response_model=SuggestionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_suggestion(
    org_id: uuid.UUID,
    data: SuggestionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuggestionRead:
    """
    Erzeugt einen Prozess-Zuordnungsvorschlag.
    Wird vom Chat/AI-Layer aufgerufen, kein Admin erforderlich.
    confidence_score steuert auto-assign vs. pending vs. admin-required.
    """
    org = await _get_org(org_id, db)
    if not _is_bcm_active(org):
        raise HTTPException(status_code=422, detail="Keine aktive BCM – Zuordnung nicht möglich.")

    score = data.confidence_score
    if score >= CONFIDENCE_AUTO_ASSIGN:
        sug_status = SuggestionStatus.confirmed
    else:
        sug_status = SuggestionStatus.pending

    suggestion = ProcessMappingSuggestion(
        org_id=org_id,
        process_name=data.process_name,
        detected_context=data.detected_context,
        suggested_node_id=data.suggested_node_id,
        suggested_node_title=data.suggested_node_title,
        confidence_score=score,
        source_reference=data.source_reference,
        status=sug_status,
    )
    if sug_status == SuggestionStatus.confirmed:
        suggestion.reviewed_by = current_user.id
        suggestion.reviewed_at = datetime.now(timezone.utc)

    db.add(suggestion)
    await db.flush()
    await _write_audit(
        db, org_id=org_id, entity_id=suggestion.id,
        action="process_suggestion_created",
        actor_id=current_user.id,
        new_value={
            "process_name": data.process_name,
            "status": sug_status,
            "confidence_score": score,
            "decision_type": "auto_decision",
        },
    )
    await db.commit()
    await db.refresh(suggestion)
    return SuggestionRead.model_validate(suggestion)


@router.patch(
    "/api/v1/organizations/{org_id}/bcm/suggestions/{suggestion_id}",
    response_model=SuggestionRead,
)
async def decide_suggestion(
    org_id: uuid.UUID,
    suggestion_id: uuid.UUID,
    decision: SuggestionDecision,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuggestionRead:
    """Org Admin bestätigt, lehnt ab oder ordnet Prozess neu zu."""
    result = await db.execute(
        select(ProcessMappingSuggestion).where(
            ProcessMappingSuggestion.id == suggestion_id,
            ProcessMappingSuggestion.org_id == org_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="Vorschlag nicht gefunden.")

    old_status = suggestion.status
    action = decision.action

    if action == "confirm":
        suggestion.status = SuggestionStatus.confirmed
    elif action == "reject":
        suggestion.status = SuggestionStatus.rejected
    else:
        suggestion.status = SuggestionStatus.reassigned

    if decision.new_process_name:
        suggestion.process_name = decision.new_process_name
    if decision.target_node_id:
        suggestion.suggested_node_id = decision.target_node_id
    if decision.admin_note:
        suggestion.admin_note = decision.admin_note

    suggestion.reviewed_by = current_user.id
    suggestion.reviewed_at = datetime.now(timezone.utc)

    await _write_audit(
        db, org_id=org_id, entity_id=suggestion_id,
        action="admin_decision",
        actor_id=current_user.id,
        old_value={"status": old_status},
        new_value={"status": suggestion.status, "action": action, "decision_type": "admin_decision"},
    )
    await db.commit()
    await db.refresh(suggestion)
    return SuggestionRead.model_validate(suggestion)


@router.post("/api/v1/organizations/{org_id}/bcm/suggestions/deduplicate")
async def deduplicate_suggestions(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """Fasst gleiche Prozessnamen (pending) zusammen, höchste Konfidenz gewinnt."""
    stmt = select(ProcessMappingSuggestion).where(
        ProcessMappingSuggestion.org_id == org_id,
        ProcessMappingSuggestion.status == SuggestionStatus.pending,
    )
    result = await db.execute(stmt)
    suggestions = result.scalars().all()

    seen: dict[str, ProcessMappingSuggestion] = {}
    to_delete: list[ProcessMappingSuggestion] = []
    for s in suggestions:
        key = s.process_name.lower().strip()
        if key not in seen or s.confidence_score > seen[key].confidence_score:
            if key in seen:
                to_delete.append(seen[key])
            seen[key] = s
        else:
            to_delete.append(s)

    for dup in to_delete:
        await db.delete(dup)
    await db.commit()
    return {"merged": len(to_delete)}
