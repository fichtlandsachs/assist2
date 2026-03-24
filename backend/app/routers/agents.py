import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate, InvokeRequest, InvokeResponse
from app.core.exceptions import NotFoundException

router = APIRouter()


@router.get(
    "/organizations/{org_id}/agents",
    response_model=List[AgentRead],
    summary="List agents",
)
async def list_agents(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:read")),
) -> List[AgentRead]:
    """List all agents for an organization."""
    result = await db.execute(
        select(Agent)
        .where(Agent.organization_id == org_id)
        .order_by(Agent.name)
    )
    agents = result.scalars().all()
    return [AgentRead.model_validate(a) for a in agents]


@router.post(
    "/organizations/{org_id}/agents",
    response_model=AgentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an agent",
)
async def create_agent(
    org_id: uuid.UUID,
    data: AgentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:create")),
) -> AgentRead:
    """Create a new AI agent for an organization."""
    agent = Agent(
        organization_id=org_id,
        name=data.name,
        role=data.role,
        model=data.model,
        config=data.config,
        system_prompt_ref=data.system_prompt_ref,
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return AgentRead.model_validate(agent)


@router.get(
    "/organizations/{org_id}/agents/{agent_id}",
    response_model=AgentRead,
    summary="Get an agent",
)
async def get_agent(
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:read")),
) -> AgentRead:
    """Get a specific agent by ID."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundException(detail="Agent not found")
    return AgentRead.model_validate(agent)


@router.patch(
    "/organizations/{org_id}/agents/{agent_id}",
    response_model=AgentRead,
    summary="Update an agent",
)
async def update_agent(
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: AgentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:update")),
) -> AgentRead:
    """Update an agent's configuration."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundException(detail="Agent not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(agent, field, value)

    await db.commit()
    await db.refresh(agent)
    return AgentRead.model_validate(agent)


@router.delete(
    "/organizations/{org_id}/agents/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an agent",
)
async def delete_agent(
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:delete")),
) -> None:
    """Delete an agent."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundException(detail="Agent not found")

    await db.delete(agent)
    await db.commit()


@router.post(
    "/organizations/{org_id}/agents/{agent_id}/invoke",
    response_model=InvokeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Invoke an agent",
)
async def invoke_agent(
    org_id: uuid.UUID,
    agent_id: uuid.UUID,
    data: InvokeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("agent:invoke")),
) -> InvokeResponse:
    """Invoke an AI agent asynchronously."""
    result = await db.execute(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.organization_id == org_id,
            Agent.is_active == True,
        )
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundException(detail="Agent not found or inactive")

    # Generate invocation ID and enqueue via Celery
    invocation_id = str(uuid.uuid4())

    # In a full implementation, this would enqueue a Celery task:
    # invoke_agent_task.delay(
    #     agent_id=str(agent_id),
    #     invocation_id=invocation_id,
    #     input_data=data.input,
    #     user_id=str(current_user.id),
    # )

    return InvokeResponse(invocation_id=invocation_id, status="running")
