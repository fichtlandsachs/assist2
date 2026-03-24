import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.workflow import (
    TriggerRequest,
    WorkflowCreate,
    WorkflowDefinitionRead,
    WorkflowExecutionDetail,
    WorkflowExecutionRead,
)
from app.services.workflow_service import workflow_service

router = APIRouter()


@router.get(
    "/organizations/{org_id}/workflows",
    response_model=List[WorkflowDefinitionRead],
    summary="List workflows",
)
async def list_workflows(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("workflow:read")),
) -> List[WorkflowDefinitionRead]:
    """List all workflow definitions for an organization."""
    workflows = await workflow_service.list(db, org_id)
    return [WorkflowDefinitionRead.model_validate(w) for w in workflows]


@router.post(
    "/organizations/{org_id}/workflows",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a workflow",
)
async def create_workflow(
    org_id: uuid.UUID,
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("workflow:create")),
) -> WorkflowDefinitionRead:
    """Create a new workflow definition."""
    workflow = await workflow_service.create(db, org_id, data, current_user.id)
    return WorkflowDefinitionRead.model_validate(workflow)


@router.post(
    "/organizations/{org_id}/workflows/{workflow_id}/trigger",
    response_model=WorkflowExecutionRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a workflow",
)
async def trigger_workflow(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    data: TriggerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("workflow:execute")),
) -> WorkflowExecutionRead:
    """Trigger a workflow execution."""
    execution = await workflow_service.trigger(db, org_id, workflow_id, data, current_user.id)
    return WorkflowExecutionRead.model_validate(execution)


@router.get(
    "/organizations/{org_id}/workflows/{workflow_id}/executions",
    response_model=List[WorkflowExecutionRead],
    summary="List workflow executions",
)
async def list_executions(
    org_id: uuid.UUID,
    workflow_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("workflow:read")),
) -> List[WorkflowExecutionRead]:
    """List all executions for a specific workflow."""
    executions = await workflow_service.list_executions(db, org_id, workflow_id)
    return [WorkflowExecutionRead.model_validate(e) for e in executions]


@router.get(
    "/organizations/{org_id}/workflows/executions/{execution_id}",
    response_model=WorkflowExecutionDetail,
    summary="Get execution details",
)
async def get_execution(
    org_id: uuid.UUID,
    execution_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("workflow:read")),
) -> WorkflowExecutionDetail:
    """Get detailed information about a workflow execution."""
    execution = await workflow_service.get_execution(db, org_id, execution_id)
    return WorkflowExecutionDetail.model_validate(execution)
