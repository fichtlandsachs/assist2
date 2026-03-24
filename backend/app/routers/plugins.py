import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.user import User
from app.schemas.plugin import OrgPluginRead, PluginActivateRequest, PluginConfigUpdate, PluginRead
from app.services.plugin_service import plugin_service

router = APIRouter()


@router.get(
    "/plugins",
    response_model=List[PluginRead],
    summary="List all available plugins",
)
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PluginRead]:
    """List all available plugins in the marketplace."""
    plugins = await plugin_service.list_available(db)
    return [PluginRead.model_validate(p) for p in plugins]


@router.get(
    "/organizations/{org_id}/plugins",
    response_model=List[OrgPluginRead],
    summary="List organization's plugins",
)
async def list_org_plugins(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("plugin:read")),
) -> List[OrgPluginRead]:
    """List all plugins activated for an organization."""
    activations = await plugin_service.list_for_org(db, org_id)
    return [OrgPluginRead.model_validate(a) for a in activations]


@router.post(
    "/organizations/{org_id}/plugins/{plugin_id}/activate",
    response_model=OrgPluginRead,
    summary="Activate a plugin",
)
async def activate_plugin(
    org_id: uuid.UUID,
    plugin_id: uuid.UUID,
    data: PluginActivateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("plugin:activate")),
) -> OrgPluginRead:
    """Activate a plugin for the organization."""
    activation = await plugin_service.activate(db, org_id, plugin_id, data, current_user.id)
    return OrgPluginRead.model_validate(activation)


@router.patch(
    "/organizations/{org_id}/plugins/{plugin_id}/config",
    response_model=OrgPluginRead,
    summary="Update plugin configuration",
)
async def update_plugin_config(
    org_id: uuid.UUID,
    plugin_id: uuid.UUID,
    data: PluginConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("plugin:configure")),
) -> OrgPluginRead:
    """Update the configuration for an activated plugin."""
    activation = await plugin_service.update_config(db, org_id, plugin_id, data.config)
    return OrgPluginRead.model_validate(activation)


@router.delete(
    "/organizations/{org_id}/plugins/{plugin_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a plugin",
)
async def deactivate_plugin(
    org_id: uuid.UUID,
    plugin_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("plugin:deactivate")),
) -> None:
    """Deactivate a plugin for the organization."""
    await plugin_service.deactivate(db, org_id, plugin_id)
