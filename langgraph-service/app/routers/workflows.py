from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Header

from app.config import get_settings
from app.schemas.evaluation import (
    EvaluateRequest,
    EvaluationResult,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)
from app.workflows.evaluate import run_evaluation
from app.workflows.duplicate_check import run_duplicate_check

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if x_api_key != settings.langgraph_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.post("/workflows/evaluate", response_model=EvaluationResult)
def evaluate_story(
    request: EvaluateRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> EvaluationResult:
    """
    Execute story evaluation workflow synchronously.
    Called by Backend only — not publicly exposed.
    """
    _verify_api_key(x_api_key)
    logger.info("evaluate_story run_id=%s story_id=%s", request.run_id, request.story_id)
    return run_evaluation(request)


@router.post("/workflows/check-duplicates", response_model=DuplicateCheckResponse)
def check_duplicates(
    request: DuplicateCheckRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> DuplicateCheckResponse:
    """
    Execute duplicate detection workflow synchronously.
    Candidates come pre-fetched from the Backend's pgvector search.
    Called by Backend only — not publicly exposed.
    """
    _verify_api_key(x_api_key)
    logger.info(
        "check_duplicates story_id=%s candidates=%d",
        request.story_id,
        len(request.candidates),
    )
    return run_duplicate_check(request)
