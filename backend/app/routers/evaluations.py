from __future__ import annotations
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.evaluation_run import EvaluationRun
from app.models.membership import Membership
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.evaluation import (
    StartEvaluationResponse, EvaluationRunRead, EvaluationResultRead,
    EvaluationStatusEnum, AmpelEnum,
)
from app.services.evaluation_service import start_evaluation, get_latest_evaluation
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)
router = APIRouter()


def _run_to_read(run: EvaluationRun) -> EvaluationRunRead:
    result = None
    if run.result_json:
        result = EvaluationResultRead.model_validate(run.result_json)
    return EvaluationRunRead(
        id=run.id,
        story_id=run.story_id,
        org_id=run.organization_id,
        status=EvaluationStatusEnum(run.status.value),
        score=float(run.score) if run.score is not None else None,
        ampel=AmpelEnum(run.ampel.value) if run.ampel else None,
        knockout=run.knockout,
        confidence=float(run.confidence) if run.confidence is not None else None,
        result=result,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


async def _get_story_and_verify_membership(
    story_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> UserStory:
    result = await db.execute(select(UserStory).where(UserStory.id == story_id))
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("Story not found")
    membership = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == story.organization_id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")
    return story


@router.post("/evaluations/stories/{story_id}/evaluate", response_model=StartEvaluationResponse)
async def trigger_evaluation(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartEvaluationResponse:
    """Start story evaluation. Blocks until LangGraph workflow completes."""
    story = await _get_story_and_verify_membership(story_id, current_user, db)

    run = await start_evaluation(
        story_id=story_id,
        org_id=story.organization_id,
        triggered_by_id=current_user.id,
        db=db,
    )

    run_read = _run_to_read(run)
    return StartEvaluationResponse(
        run_id=run.id,
        status=run_read.status,
        result=run_read.result,
    )


@router.get("/evaluations/stories/{story_id}/latest")
async def get_latest(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return most recent completed evaluation for a story."""
    story = await _get_story_and_verify_membership(story_id, current_user, db)

    run = await get_latest_evaluation(
        story_id=story_id,
        org_id=story.organization_id,
        db=db,
    )
    if run is None:
        return {"result": None}
    return _run_to_read(run)


@router.get("/evaluations/{run_id}/status")
async def get_run_status(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll evaluation run status by run_id."""
    result = await db.execute(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.organization_id.in_(
                select(Membership.organization_id).where(
                    Membership.user_id == current_user.id
                )
            ),
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundException("Evaluation run not found")
    return _run_to_read(run)
