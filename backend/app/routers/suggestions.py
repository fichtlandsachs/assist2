"""Suggestion feedback endpoint."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.membership import Membership
from app.models.user import User
from app.models.suggestion_feedback import SuggestionFeedback

router = APIRouter()

VALID_TYPES = {"dod", "test_case", "feature", "story"}


class FeedbackCreate(BaseModel):
    suggestion_type: str    # "dod" | "test_case" | "feature" | "story"
    suggestion_text: str
    feedback: str = "rejected"
    organization_id: uuid.UUID


@router.post(
    "/suggestions/feedback",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record user feedback on an AI suggestion",
)
async def create_suggestion_feedback(
    data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if data.suggestion_type not in VALID_TYPES:
        raise HTTPException(status_code=422, detail=f"Invalid suggestion_type: {data.suggestion_type}")
    membership_result = await db.execute(
        select(Membership).where(
            Membership.organization_id == data.organization_id,
            Membership.user_id == current_user.id,
            Membership.status == "active",
        )
    )
    if not membership_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Kein Zugriff auf diese Organisation")
    record = SuggestionFeedback(
        organization_id=data.organization_id,
        suggestion_type=data.suggestion_type,
        suggestion_text=data.suggestion_text[:1000],
        feedback=data.feedback,
    )
    db.add(record)
    await db.commit()
