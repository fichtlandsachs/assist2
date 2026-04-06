"""Confluence integration endpoints."""
import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User

router = APIRouter()


class ConfluenceIndexRequest(BaseModel):
    org_id: uuid.UUID


@router.post(
    "/confluence/index",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Confluence space indexing for org",
)
async def trigger_confluence_index(
    data: ConfluenceIndexRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    from app.tasks.rag_tasks import index_confluence_space
    index_confluence_space.delay(str(data.org_id))
    return {"message": "Confluence-Indexierung gestartet"}
