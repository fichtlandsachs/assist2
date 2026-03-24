import logging
import uuid
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.services.n8n_client import n8n_client

from .models import TestCase, UserStory
from .schemas import (
    AIDeliveryResponse,
    StoryCreate,
    StoryFilter,
    StoryUpdate,
    TestCaseCreate,
    TestCaseUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid status transitions
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["ready", "cancelled"],
    "ready": ["in_progress", "draft"],
    "in_progress": ["in_review", "draft"],
    "in_review": ["done", "in_progress"],
    "done": [],
    "cancelled": [],
}


# ---------------------------------------------------------------------------
# StoryService
# ---------------------------------------------------------------------------


class StoryService:
    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: StoryCreate,
        reporter_id: uuid.UUID,
    ) -> UserStory:
        """Create a new User Story for an organization."""
        story = UserStory(
            organization_id=org_id,
            title=data.title,
            description=data.description,
            status="draft",
            priority=data.priority.value,
            story_points=data.story_points,
            assignee_id=data.assignee_id,
            reporter_id=reporter_id,
            group_id=data.group_id,
            acceptance_criteria=data.acceptance_criteria or [],
        )
        db.add(story)
        await db.commit()
        await db.refresh(story)
        logger.info(f"Story created: {story.id} in org {org_id}")
        return story

    async def get(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
    ) -> UserStory:
        """Load a story, enforcing tenant isolation."""
        stmt = select(UserStory).where(
            UserStory.organization_id == org_id,
            UserStory.id == story_id,
        )
        result = await db.execute(stmt)
        story = result.scalar_one_or_none()
        if not story:
            raise NotFoundException(detail="Story not found")
        return story

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        filters: StoryFilter,
    ) -> tuple[list[UserStory], int]:
        """Return paginated list of stories with filters, always filtered by org."""
        base_stmt = select(UserStory).where(UserStory.organization_id == org_id)

        if filters.status is not None:
            base_stmt = base_stmt.where(UserStory.status == filters.status.value)
        if filters.priority is not None:
            base_stmt = base_stmt.where(UserStory.priority == filters.priority.value)
        if filters.assignee_id is not None:
            base_stmt = base_stmt.where(UserStory.assignee_id == filters.assignee_id)
        if filters.group_id is not None:
            base_stmt = base_stmt.where(UserStory.group_id == filters.group_id)

        # Count total
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        # Paginate
        offset = (filters.page - 1) * filters.page_size
        paginated_stmt = (
            base_stmt
            .order_by(UserStory.created_at.desc())
            .offset(offset)
            .limit(filters.page_size)
        )
        result = await db.execute(paginated_stmt)
        stories = list(result.scalars().all())

        return stories, total

    async def update(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
        data: StoryUpdate,
    ) -> UserStory:
        """Update a story, enforcing tenant isolation.
        Validates status transitions and optionally triggers workflow."""
        story = await self.get(db, org_id, story_id)

        update_data = data.model_dump(exclude_unset=True)

        # Validate status transition if status is being changed
        if "status" in update_data:
            new_status = update_data["status"]
            if isinstance(new_status, str):
                new_status_val = new_status
            else:
                new_status_val = new_status.value

            allowed = VALID_TRANSITIONS.get(story.status, [])
            if new_status_val not in allowed:
                raise BadRequestException(
                    detail=f"Invalid transition: {story.status} → {new_status_val}. "
                    f"Allowed: {allowed or 'none (terminal state)'}"
                )
            update_data["status"] = new_status_val

        if "priority" in update_data and hasattr(update_data["priority"], "value"):
            update_data["priority"] = update_data["priority"].value

        for key, value in update_data.items():
            setattr(story, key, value)

        story.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(story)
        logger.info(f"Story updated: {story.id}")
        return story

    async def delete(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
    ) -> None:
        """Delete a story (hard delete), enforcing tenant isolation."""
        story = await self.get(db, org_id, story_id)
        await db.delete(story)
        await db.commit()
        logger.info(f"Story deleted: {story_id} from org {org_id}")

    async def transition_status(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
        new_status: str,
        user_id: uuid.UUID,
    ) -> UserStory:
        """Validate and apply a status transition, triggering workflow events."""
        story = await self.get(db, org_id, story_id)

        allowed = VALID_TRANSITIONS.get(story.status, [])
        if new_status not in allowed:
            raise BadRequestException(
                detail=f"Invalid transition: {story.status} → {new_status}. "
                f"Allowed: {allowed or 'none (terminal state)'}"
            )

        old_status = story.status
        story.status = new_status
        story.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(story)

        # Trigger workflow event
        try:
            await n8n_client.trigger_workflow(
                "story-lifecycle",
                {
                    "event": "story.status_changed",
                    "story_id": str(story.id),
                    "organization_id": str(org_id),
                    "status_from": old_status,
                    "status_to": new_status,
                    "user_id": str(user_id),
                    "story": {
                        "id": str(story.id),
                        "title": story.title,
                        "description": story.description,
                        "priority": story.priority,
                        "story_points": story.story_points,
                        "acceptance_criteria": story.acceptance_criteria,
                    },
                },
            )
        except Exception as exc:
            logger.warning(
                f"Failed to trigger story-lifecycle workflow for story {story_id}: {exc}"
            )

        logger.info(f"Story {story_id} transitioned: {old_status} → {new_status}")
        return story

    async def trigger_ai_delivery(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> AIDeliveryResponse:
        """Trigger the ai-delivery workflow for a story."""
        story = await self.get(db, org_id, story_id)

        if story.status not in ("ready", "draft"):
            raise BadRequestException(
                detail=f"AI Delivery can only be triggered for stories in 'draft' or 'ready' status. "
                f"Current status: {story.status}"
            )

        process_id = f"proc_{uuid.uuid4().hex[:12]}"

        try:
            await n8n_client.trigger_workflow(
                "ai-delivery",
                {
                    "event": "story.ai_delivery_requested",
                    "process_id": process_id,
                    "story_id": str(story_id),
                    "organization_id": str(org_id),
                    "user_id": str(user_id),
                },
            )
        except Exception as exc:
            logger.error(f"Failed to trigger ai-delivery for story {story_id}: {exc}")
            raise

        logger.info(f"AI Delivery triggered for story {story_id}, process_id={process_id}")

        return AIDeliveryResponse(
            execution_id=process_id,
            process_id=process_id,
            story_id=story_id,
            status="triggered",
            triggered_at=datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# TestCaseService
# ---------------------------------------------------------------------------


class TestCaseService:
    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
        data: TestCaseCreate,
        user_id: uuid.UUID,
    ) -> TestCase:
        """Create a test case for a story, enforcing tenant isolation."""
        # Verify story belongs to org
        story_stmt = select(UserStory).where(
            UserStory.organization_id == org_id,
            UserStory.id == story_id,
        )
        story_result = await db.execute(story_stmt)
        if not story_result.scalar_one_or_none():
            raise NotFoundException(detail="Story not found")

        test_case = TestCase(
            organization_id=org_id,
            story_id=story_id,
            title=data.title,
            description=data.description,
            type=data.type.value,
            status="pending",
            steps=data.steps,
            expected_result=data.expected_result,
            created_by=user_id,
        )
        db.add(test_case)
        await db.commit()
        await db.refresh(test_case)
        logger.info(f"TestCase created: {test_case.id} for story {story_id}")
        return test_case

    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        story_id: uuid.UUID,
    ) -> list[TestCase]:
        """List test cases for a story, enforcing tenant isolation."""
        stmt = select(TestCase).where(
            TestCase.organization_id == org_id,
            TestCase.story_id == story_id,
        ).order_by(TestCase.created_at.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        test_case_id: uuid.UUID,
        data: TestCaseUpdate,
    ) -> TestCase:
        """Update a test case, enforcing tenant isolation."""
        stmt = select(TestCase).where(
            TestCase.organization_id == org_id,
            TestCase.id == test_case_id,
        )
        result = await db.execute(stmt)
        test_case = result.scalar_one_or_none()
        if not test_case:
            raise NotFoundException(detail="TestCase not found")

        update_data = data.model_dump(exclude_unset=True)
        if "status" in update_data and hasattr(update_data["status"], "value"):
            update_data["status"] = update_data["status"].value

        for key, value in update_data.items():
            setattr(test_case, key, value)

        test_case.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(test_case)
        return test_case

    async def delete(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        test_case_id: uuid.UUID,
    ) -> None:
        """Delete a test case, enforcing tenant isolation."""
        stmt = select(TestCase).where(
            TestCase.organization_id == org_id,
            TestCase.id == test_case_id,
        )
        result = await db.execute(stmt)
        test_case = result.scalar_one_or_none()
        if not test_case:
            raise NotFoundException(detail="TestCase not found")

        await db.delete(test_case)
        await db.commit()
        logger.info(f"TestCase deleted: {test_case_id}")


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

story_service = StoryService()
test_case_service = TestCaseService()
