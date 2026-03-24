import uuid
from math import ceil
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User

from .schemas import (
    AIDeliveryRequest,
    AIDeliveryResponse,
    PaginatedResponse,
    StatusTransitionRequest,
    StoryCreate,
    StoryFilter,
    StoryList,
    StoryPriority,
    StoryRead,
    StoryStatus,
    StoryUpdate,
    TestCaseCreate,
    TestCaseRead,
    TestCaseUpdate,
)
from .service import story_service, test_case_service

router = APIRouter(
    prefix="/api/v1/organizations/{org_id}/stories",
    tags=["user-story"],
)


# ---------------------------------------------------------------------------
# Stories
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=StoryList,
    summary="List User Stories",
)
async def list_stories(
    org_id: uuid.UUID,
    status: StoryStatus | None = Query(None),
    priority: StoryPriority | None = Query(None),
    assignee_id: uuid.UUID | None = Query(None),
    group_id: uuid.UUID | None = Query(None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_permission("story:read")),
    db: AsyncSession = Depends(get_db),
) -> StoryList:
    filters = StoryFilter(
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        group_id=group_id,
        page=page,
        page_size=page_size,
    )
    stories, total = await story_service.list(db, org_id, filters)
    pages = ceil(total / page_size) if total > 0 else 0
    return PaginatedResponse(
        items=[StoryRead.model_validate(s) for s in stories],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post(
    "",
    response_model=StoryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create User Story",
)
async def create_story(
    org_id: uuid.UUID,
    data: StoryCreate,
    current_user: User = Depends(require_permission("story:create")),
    db: AsyncSession = Depends(get_db),
) -> StoryRead:
    story = await story_service.create(db, org_id, data, reporter_id=current_user.id)
    return StoryRead.model_validate(story)


@router.get(
    "/{story_id}",
    response_model=StoryRead,
    summary="Get User Story",
)
async def get_story(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    current_user: User = Depends(require_permission("story:read")),
    db: AsyncSession = Depends(get_db),
) -> StoryRead:
    story = await story_service.get(db, org_id, story_id)
    return StoryRead.model_validate(story)


@router.patch(
    "/{story_id}",
    response_model=StoryRead,
    summary="Update User Story",
)
async def update_story(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    data: StoryUpdate,
    current_user: User = Depends(require_permission("story:update")),
    db: AsyncSession = Depends(get_db),
) -> StoryRead:
    story = await story_service.update(db, org_id, story_id, data)
    return StoryRead.model_validate(story)


@router.delete(
    "/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete User Story",
)
async def delete_story(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    current_user: User = Depends(require_permission("story:delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await story_service.delete(db, org_id, story_id)


@router.post(
    "/{story_id}/transition",
    response_model=StoryRead,
    summary="Transition Story Status",
)
async def transition_story_status(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    data: StatusTransitionRequest,
    current_user: User = Depends(require_permission("story:update")),
    db: AsyncSession = Depends(get_db),
) -> StoryRead:
    story = await story_service.transition_status(
        db, org_id, story_id, data.status.value, user_id=current_user.id
    )
    return StoryRead.model_validate(story)


@router.post(
    "/{story_id}/ai-delivery",
    response_model=AIDeliveryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI Delivery Workflow",
)
async def trigger_ai_delivery(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    data: AIDeliveryRequest,
    current_user: User = Depends(require_permission("workflow:execute")),
    db: AsyncSession = Depends(get_db),
) -> AIDeliveryResponse:
    return await story_service.trigger_ai_delivery(db, org_id, story_id, user_id=current_user.id)


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


@router.get(
    "/{story_id}/test-cases",
    response_model=list[TestCaseRead],
    summary="List Test Cases for a Story",
)
async def list_test_cases(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    current_user: User = Depends(require_permission("story:read")),
    db: AsyncSession = Depends(get_db),
) -> list[TestCaseRead]:
    test_cases = await test_case_service.list(db, org_id, story_id)
    return [TestCaseRead.model_validate(tc) for tc in test_cases]


@router.post(
    "/{story_id}/test-cases",
    response_model=TestCaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Test Case",
)
async def create_test_case(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    data: TestCaseCreate,
    current_user: User = Depends(require_permission("story:update")),
    db: AsyncSession = Depends(get_db),
) -> TestCaseRead:
    test_case = await test_case_service.create(db, org_id, story_id, data, user_id=current_user.id)
    return TestCaseRead.model_validate(test_case)


@router.patch(
    "/{story_id}/test-cases/{tc_id}",
    response_model=TestCaseRead,
    summary="Update Test Case",
)
async def update_test_case(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    tc_id: uuid.UUID,
    data: TestCaseUpdate,
    current_user: User = Depends(require_permission("story:update")),
    db: AsyncSession = Depends(get_db),
) -> TestCaseRead:
    test_case = await test_case_service.update(db, org_id, tc_id, data)
    return TestCaseRead.model_validate(test_case)


@router.delete(
    "/{story_id}/test-cases/{tc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Test Case",
)
async def delete_test_case(
    org_id: uuid.UUID,
    story_id: uuid.UUID,
    tc_id: uuid.UUID,
    current_user: User = Depends(require_permission("story:delete")),
    db: AsyncSession = Depends(get_db),
) -> None:
    await test_case_service.delete(db, org_id, tc_id)
