from __future__ import annotations
import uuid
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user
from app.models.evaluation_run import EvaluationRun
from app.models.membership import Membership
from app.models.user import User
from app.core.story_filter import active_stories
from app.models.user_story import UserStory
from app.schemas.evaluation import (
    StartEvaluationResponse, EvaluationRunRead, EvaluationResultRead,
    EvaluationStatusEnum, AmpelEnum,
    DuplicateCandidate, DuplicateCheckResponse,
)
from app.services.embedding_service import find_similar_stories
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
    result = await db.execute(active_stories().where(UserStory.id == story_id))
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


@router.post(
    "/evaluations/stories/{story_id}/check-duplicates",
    response_model=DuplicateCheckResponse,
)
async def check_duplicates(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DuplicateCheckResponse:
    """
    1. pgvector similarity search for the story's embedding
    2. Load story details for each candidate
    3. Call LangGraph /workflows/check-duplicates for LLM-based classification
    4. Return {duplicates, similar}
    """
    settings = get_settings()

    story = await _get_story_and_verify_membership(story_id, current_user, db)

    # Step 1: vector search
    candidates_raw = await find_similar_stories(
        story_id=str(story_id),
        org_id=str(story.organization_id),
        db=db,
    )
    if not candidates_raw:
        return DuplicateCheckResponse(duplicates=[], similar=[])

    # Step 2: load story details for each candidate
    candidate_ids = [cid for cid, _ in candidates_raw]
    stories_result = await db.execute(
        select(UserStory).where(UserStory.id.in_(candidate_ids))
    )
    story_map = {s.id: s for s in stories_result.scalars().all()}

    candidates_payload = []
    for cid, sim in candidates_raw:
        s = story_map.get(cid)
        if s is None:
            continue
        candidates_payload.append({
            "story_id": str(cid),
            "title": s.title or "",
            "description": s.description or "",
            "acceptance_criteria": s.acceptance_criteria or "",
            "similarity_score": sim,
        })

    if not candidates_payload:
        return DuplicateCheckResponse(duplicates=[], similar=[])

    # Step 3: call LangGraph
    langgraph_payload = {
        "story_id": str(story_id),
        "org_id": str(story.organization_id),
        "title": story.title or "",
        "description": story.description or "",
        "acceptance_criteria": story.acceptance_criteria or "",
        "candidates": candidates_payload,
    }

    try:
        async with httpx.AsyncClient(timeout=float(settings.LANGGRAPH_TIMEOUT)) as client:
            response = await client.post(
                f"{settings.LANGGRAPH_BASE_URL}/workflows/check-duplicates",
                json=langgraph_payload,
                headers={"X-API-Key": settings.LANGGRAPH_API_KEY},
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        logger.error("check_duplicates: LangGraph timeout for story %s: %s", story_id, e)
        raise HTTPException(status_code=504, detail=f"LangGraph timeout: {e}")
    except httpx.HTTPStatusError as e:
        logger.error("check_duplicates: LangGraph error for story %s: %s", story_id, e)
        raise HTTPException(status_code=502, detail=f"LangGraph error: {e.response.status_code}")

    # Step 4: parse and return
    duplicates = [DuplicateCandidate(**d) for d in data.get("duplicates", [])]
    similar = [DuplicateCandidate(**s) for s in data.get("similar", [])]
    return DuplicateCheckResponse(duplicates=duplicates, similar=similar)
