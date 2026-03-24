import logging
import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.workflow import WorkflowDefinition, WorkflowExecution
from app.schemas.workflow import TriggerRequest, WorkflowCreate
from app.services.n8n_client import n8n_client

logger = logging.getLogger(__name__)


class WorkflowService:
    async def list(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> List[WorkflowDefinition]:
        """List all workflow definitions for an organization."""
        result = await db.execute(
            select(WorkflowDefinition)
            .where(
                WorkflowDefinition.organization_id == org_id,
                WorkflowDefinition.is_active == True,
            )
            .order_by(WorkflowDefinition.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        workflow_id: uuid.UUID,
    ) -> WorkflowDefinition:
        """Get a workflow definition by ID, enforcing tenant isolation."""
        result = await db.execute(
            select(WorkflowDefinition).where(
                WorkflowDefinition.id == workflow_id,
                WorkflowDefinition.organization_id == org_id,
            )
        )
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise NotFoundException(detail="Workflow not found")
        return workflow

    async def create(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        data: WorkflowCreate,
        user_id: uuid.UUID,
    ) -> WorkflowDefinition:
        """Create a new workflow definition for an organization."""
        workflow = WorkflowDefinition(
            organization_id=org_id,
            name=data.name,
            slug=data.slug,
            version=1,
            description=data.description,
            trigger_type=data.trigger_type,
            n8n_workflow_id=data.n8n_workflow_id,
            definition=data.definition,
            is_active=True,
            created_by=user_id,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)
        return workflow

    async def trigger(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        workflow_id: uuid.UUID,
        data: TriggerRequest,
        user_id: uuid.UUID,
    ) -> WorkflowExecution:
        """
        Trigger a workflow execution.
        Creates an execution record, sends a request to n8n, and updates the status.
        """
        workflow = await self.get_by_id(db, org_id, workflow_id)

        if not workflow.is_active:
            raise NotFoundException(detail="Workflow is not active")

        # Create execution record with pending status
        execution = WorkflowExecution(
            organization_id=org_id,
            definition_id=workflow.id,
            definition_version=workflow.version,
            n8n_execution_id="pending",
            status="pending",
            triggered_by=user_id,
            trigger_type="manual",
            input_snapshot=data.input,
            context_snapshot={
                "organization_id": str(org_id),
                "user_id": str(user_id),
                "workflow_slug": workflow.slug,
            },
        )
        db.add(execution)
        await db.flush()

        # Trigger n8n workflow
        try:
            n8n_response = await n8n_client.trigger_workflow(
                workflow.n8n_workflow_id,
                {
                    "execution_id": str(execution.id),
                    "organization_id": str(org_id),
                    "user_id": str(user_id),
                    "input": data.input,
                },
            )
            n8n_execution_id = n8n_response.get("executionId", str(execution.id))
            execution.n8n_execution_id = str(n8n_execution_id)
            execution.status = "running"
        except Exception as e:
            logger.error(f"Failed to trigger n8n workflow: {e}")
            execution.status = "failed"
            execution.error_message = str(e)
            execution.n8n_execution_id = str(execution.id)

        await db.commit()
        await db.refresh(execution)
        return execution

    async def list_executions(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        workflow_id: uuid.UUID,
    ) -> List[WorkflowExecution]:
        """List executions for a specific workflow, enforcing tenant isolation."""
        result = await db.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == org_id,
                WorkflowExecution.definition_id == workflow_id,
            )
            .order_by(WorkflowExecution.started_at.desc())
        )
        return list(result.scalars().all())

    async def get_execution(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        execution_id: uuid.UUID,
    ) -> WorkflowExecution:
        """Get a workflow execution by ID, enforcing tenant isolation."""
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.organization_id == org_id,
            )
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise NotFoundException(detail="Workflow execution not found")
        return execution


workflow_service = WorkflowService()
