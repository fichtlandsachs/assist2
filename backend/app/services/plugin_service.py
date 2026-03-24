import uuid
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictException, NotFoundException
from app.models.plugin import OrganizationPluginActivation, Plugin
from app.schemas.plugin import PluginActivateRequest, PluginConfigUpdate


class PluginService:
    async def list_available(self, db: AsyncSession) -> List[Plugin]:
        """List all available (active) plugins."""
        result = await db.execute(
            select(Plugin).where(Plugin.is_active == True).order_by(Plugin.name)
        )
        return list(result.scalars().all())

    async def list_for_org(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> List[OrganizationPluginActivation]:
        """List all plugin activations for an organization."""
        result = await db.execute(
            select(OrganizationPluginActivation)
            .where(OrganizationPluginActivation.organization_id == org_id)
            .options(selectinload(OrganizationPluginActivation.plugin))
            .order_by(OrganizationPluginActivation.activated_at.desc())
        )
        return list(result.scalars().all())

    async def activate(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        plugin_id: uuid.UUID,
        data: PluginActivateRequest,
        user_id: uuid.UUID,
    ) -> OrganizationPluginActivation:
        """Activate a plugin for an organization."""
        # Verify plugin exists
        plugin_result = await db.execute(
            select(Plugin).where(Plugin.id == plugin_id, Plugin.is_active == True)
        )
        plugin = plugin_result.scalar_one_or_none()
        if not plugin:
            raise NotFoundException(detail="Plugin not found or inactive")

        # Check if already activated
        existing_result = await db.execute(
            select(OrganizationPluginActivation).where(
                OrganizationPluginActivation.organization_id == org_id,
                OrganizationPluginActivation.plugin_id == plugin_id,
            )
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Re-enable if disabled
            existing.is_enabled = True
            if data.config is not None:
                existing.config = data.config
            await db.commit()
            await db.refresh(existing)
            return existing

        activation = OrganizationPluginActivation(
            organization_id=org_id,
            plugin_id=plugin_id,
            is_enabled=True,
            config=data.config,
            activated_by=user_id,
        )
        db.add(activation)
        await db.commit()
        await db.refresh(activation)
        return activation

    async def update_config(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        plugin_id: uuid.UUID,
        config: Dict[str, Any],
    ) -> OrganizationPluginActivation:
        """Update the configuration for an org's plugin activation."""
        result = await db.execute(
            select(OrganizationPluginActivation).where(
                OrganizationPluginActivation.organization_id == org_id,
                OrganizationPluginActivation.plugin_id == plugin_id,
            )
        )
        activation = result.scalar_one_or_none()

        if not activation:
            raise NotFoundException(detail="Plugin activation not found")

        activation.config = config
        await db.commit()
        await db.refresh(activation)
        return activation

    async def deactivate(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        plugin_id: uuid.UUID,
    ) -> None:
        """Deactivate a plugin for an organization."""
        result = await db.execute(
            select(OrganizationPluginActivation).where(
                OrganizationPluginActivation.organization_id == org_id,
                OrganizationPluginActivation.plugin_id == plugin_id,
            )
        )
        activation = result.scalar_one_or_none()

        if not activation:
            raise NotFoundException(detail="Plugin activation not found")

        activation.is_enabled = False
        await db.commit()


plugin_service = PluginService()
