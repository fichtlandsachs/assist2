"""
Story Readiness Router
======================
Endpoints for Karl's "Assigned User Story Evaluation" feature.

GET  /story-readiness/my-stories          → dashboard data for current user
POST /story-readiness/evaluate            → trigger batch evaluation
GET  /story-readiness/{story_id}/history  → versioned history for one story
POST /story-readiness/{story_id}/evaluate → evaluate a single story
"""
from __future__ import annotations

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.epic import Epic
from app.models.membership import Membership
from app.models.story_readiness import StoryReadinessEvaluation
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.story_readiness import (
    EvaluateMyStoriesRequest,
    EvaluateMyStoriesResponse,
    MyReadinessResponse,
    StoryReadinessEvaluationRead,
    StoryWithReadiness,
)
from app.services.story_readiness_service import (
    evaluate_assigned_user_stories,
    evaluate_story_readiness,
    get_latest_readiness_for_stories,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/story-readiness", tags=["Story Readiness"])

# ── Helpers ───────────────────────────────────────────────────────────────────

def _ev_to_read(ev: StoryReadinessEvaluation) -> StoryReadinessEvaluationRead:
    return StoryReadinessEvaluationRead(
        id=ev.id,
        story_id=ev.story_id,
        organization_id=ev.organization_id,
        evaluated_for_user_id=ev.evaluated_for_user_id,
        readiness_score=ev.readiness_score,
        readiness_state=ev.readiness_state.value,
        open_topics=ev.open_topics or [],
        missing_inputs=ev.missing_inputs or [],
        required_preparatory_work=ev.required_preparatory_work or [],
        dependencies=ev.dependencies or [],
        blockers=ev.blockers or [],
        risks=ev.risks or [],
        recommended_next_steps=ev.recommended_next_steps or [],
        summary=ev.summary,
        model_used=ev.model_used,
        confidence=float(ev.confidence) if ev.confidence is not None else None,
        error_message=ev.error_message,
        created_at=ev.created_at,
    )


async def _assert_member(org_id: uuid.UUID, user: User, db: AsyncSession) -> None:
    r = await db.execute(
        select(Membership).where(
            Membership.organization_id == org_id,
            Membership.user_id == user.id,
        )
    )
    if r.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a member of this organisation")


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/my-stories", response_model=MyReadinessResponse)
async def get_my_story_readiness(
    org_id: uuid.UUID = Query(...),
    filter_state: Optional[str] = Query(None, description="blocked|not_ready|missing_inputs|high_priority"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns dashboard data: all assigned/created stories + their latest
    readiness evaluation. Stories are filtered by org and not done/archived.
    """
    await _assert_member(org_id, current_user, db)

    # Load stories
    stories_result = await db.execute(
        select(UserStory)
        .where(
            UserStory.organization_id == org_id,
            or_(
                UserStory.assignee_id == current_user.id,
                UserStory.created_by_id == current_user.id,
            ),
            UserStory.status.not_in(["done", "archived"]),
        )
        .order_by(desc(UserStory.created_at))
    )
    stories = stories_result.scalars().all()

    story_ids = [s.id for s in stories]

    # Load epics for context
    epic_ids = {s.epic_id for s in stories if s.epic_id}
    epic_map: dict[uuid.UUID, str] = {}
    if epic_ids:
        epic_res = await db.execute(select(Epic).where(Epic.id.in_(epic_ids)))
        for epic in epic_res.scalars().all():
            epic_map[epic.id] = epic.title

    # Load latest evaluations
    latest_evals = await get_latest_readiness_for_stories(story_ids, org_id, db)

    # Build response items
    items: list[StoryWithReadiness] = []
    for story in stories:
        ev = latest_evals.get(story.id)

        # Apply filter
        if filter_state:
            if filter_state == "blocked":
                if not ev or not ev.blockers:
                    continue
            elif filter_state == "not_ready":
                if not ev or ev.readiness_state.value not in ("not_ready", "partially_ready"):
                    continue
            elif filter_state == "missing_inputs":
                if not ev or not ev.missing_inputs:
                    continue
            elif filter_state == "high_priority":
                if story.priority.value not in ("high", "critical"):
                    continue

        items.append(StoryWithReadiness(
            story_id=story.id,
            title=story.title,
            status=story.status.value,
            priority=story.priority.value,
            story_points=story.story_points,
            epic_id=story.epic_id,
            epic_title=epic_map.get(story.epic_id) if story.epic_id else None,
            latest_evaluation=_ev_to_read(ev) if ev else None,
        ))

    # Dashboard counters
    all_evals = [latest_evals.get(sid) for sid in story_ids]
    implementation_ready = sum(
        1 for ev in all_evals if ev and ev.readiness_state.value == "implementation_ready"
    )
    blocked = sum(1 for ev in all_evals if ev and ev.blockers)
    missing_inputs_count = sum(1 for ev in all_evals if ev and ev.missing_inputs)
    not_ready = sum(
        1 for ev in all_evals if ev and ev.readiness_state.value in ("not_ready", "partially_ready")
    )

    return MyReadinessResponse(
        total_stories=len(stories),
        implementation_ready=implementation_ready,
        blocked=blocked,
        missing_inputs_count=missing_inputs_count,
        not_ready=not_ready,
        stories=items,
    )


@router.post("/evaluate", response_model=EvaluateMyStoriesResponse, status_code=202)
async def evaluate_my_stories(
    body: EvaluateMyStoriesRequest,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger readiness evaluation for all assigned stories (or a subset)."""
    await _assert_member(org_id, current_user, db)

    evaluations, failed = await evaluate_assigned_user_stories(
        user_id=current_user.id,
        org_id=org_id,
        db=db,
        story_ids=body.story_ids,
    )

    return EvaluateMyStoriesResponse(
        evaluated=len(evaluations),
        failed=failed,
        results=[_ev_to_read(ev) for ev in evaluations],
    )


@router.get("/{story_id}/history", response_model=list[StoryReadinessEvaluationRead])
async def get_story_readiness_history(
    story_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    limit: int = Query(default=10, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return versioned evaluation history for a single story (newest first)."""
    await _assert_member(org_id, current_user, db)

    # Verify story belongs to org
    story_res = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.organization_id == org_id,
        )
    )
    if story_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Story not found")

    rows = await db.execute(
        select(StoryReadinessEvaluation)
        .where(
            StoryReadinessEvaluation.story_id == story_id,
            StoryReadinessEvaluation.organization_id == org_id,
        )
        .order_by(desc(StoryReadinessEvaluation.created_at))
        .limit(limit)
    )
    return [_ev_to_read(ev) for ev in rows.scalars().all()]


@router.post("/{story_id}/evaluate", response_model=StoryReadinessEvaluationRead, status_code=201)
async def evaluate_single_story(
    story_id: uuid.UUID,
    org_id: uuid.UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate a single story on demand."""
    await _assert_member(org_id, current_user, db)

    story_res = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.organization_id == org_id,
        )
    )
    story = story_res.scalar_one_or_none()
    if story is None:
        raise HTTPException(status_code=404, detail="Story not found")

    ev = await evaluate_story_readiness(story, current_user.id, org_id, db)
    await db.commit()
    return _ev_to_read(ev)
