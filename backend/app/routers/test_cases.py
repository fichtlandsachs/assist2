import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.test_case import TestCase
from app.core.story_filter import active_stories
from app.models.user_story import UserStory, StoryStatus
from app.schemas.test_case import TestCaseCreate, TestCaseRead, TestCaseUpdate
from app.core.exceptions import NotFoundException
from app.tasks.rag_tasks import index_story_knowledge
from app.models.organization import Organization

router = APIRouter()

# Status order: editing is locked once story reaches "testing" or beyond
_LOCKED_STATUSES = {StoryStatus.testing, StoryStatus.done, StoryStatus.archived}


def _assert_editable(story: UserStory) -> None:
    """Raise 409 if the story's status is at or beyond 'testing'."""
    if story.status in _LOCKED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Testfälle können nicht bearbeitet werden — Story hat Status '{story.status.value}'.",
        )


@router.get(
    "/user-stories/{story_id}/test-cases",
    response_model=List[TestCaseRead],
    summary="List test cases for a user story",
)
async def list_test_cases(
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[TestCaseRead]:
    stmt = active_stories().where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    stmt = (
        select(TestCase)
        .where(TestCase.story_id == story_id)
        .order_by(TestCase.is_ai_generated.desc(), TestCase.created_at.asc())
    )
    result = await db.execute(stmt)
    test_cases = result.scalars().all()
    return [TestCaseRead.model_validate(tc) for tc in test_cases]


@router.post(
    "/user-stories/{story_id}/test-cases",
    response_model=TestCaseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a test case for a user story",
)
async def create_test_case(
    story_id: uuid.UUID,
    data: TestCaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestCaseRead:
    stmt = active_stories().where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")
    _assert_editable(story)

    test_case = TestCase(
        organization_id=story.organization_id,
        story_id=story_id,
        created_by_id=current_user.id,
        title=data.title,
        description=data.description,
        steps=data.steps,
        expected_result=data.expected_result,
        is_ai_generated=False,
    )
    db.add(test_case)
    await db.commit()
    await db.refresh(test_case)
    return TestCaseRead.model_validate(test_case)


@router.patch(
    "/test-cases/{test_case_id}",
    response_model=TestCaseRead,
    summary="Update a test case",
)
async def update_test_case(
    test_case_id: uuid.UUID,
    data: TestCaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TestCaseRead:
    stmt = select(TestCase).where(TestCase.id == test_case_id)
    result = await db.execute(stmt)
    test_case = result.scalar_one_or_none()
    if test_case is None:
        raise NotFoundException("Test case not found")

    # Load story for status check — result field (pass/fail) is always editable
    fields = data.model_dump(exclude_unset=True)
    content_fields = {k for k in fields if k != "result" and k != "notes"}
    if content_fields:
        stmt2 = active_stories().where(UserStory.id == test_case.story_id)
        res2 = await db.execute(stmt2)
        story = res2.scalar_one_or_none()
        if story:
            _assert_editable(story)

    for field, value in fields.items():
        setattr(test_case, field, value)

    await db.commit()
    await db.refresh(test_case)

    # Re-index story knowledge when a test case is marked passed
    from app.models.test_case import TestResult as _TestResult
    if data.result == _TestResult.passed:
        org_result = await db.execute(
            select(Organization).where(Organization.id == test_case.organization_id)
        )
        org = org_result.scalar_one_or_none()
        org_slug = org.slug if org else str(test_case.organization_id)
        index_story_knowledge.delay(
            str(test_case.story_id), str(test_case.organization_id), org_slug
        )

    return TestCaseRead.model_validate(test_case)


@router.delete(
    "/test-cases/{test_case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a test case",
)
async def delete_test_case(
    test_case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    stmt = select(TestCase).where(TestCase.id == test_case_id)
    result = await db.execute(stmt)
    test_case = result.scalar_one_or_none()
    if test_case is None:
        raise NotFoundException("Test case not found")

    stmt2 = active_stories().where(UserStory.id == test_case.story_id)
    res2 = await db.execute(stmt2)
    story = res2.scalar_one_or_none()
    if story:
        _assert_editable(story)

    await db.delete(test_case)
    await db.commit()
