"""
Admin Config Service — manages SystemConfig and ConfigHistory persistence.

All learning/optimization behaviour in the platform is gated through configs
returned by this service. Safe defaults are returned when no DB row exists,
so the system degrades gracefully to "no learning" mode out-of-the-box.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_config import CONFIG_TYPES, ConfigHistory, SystemConfig
from app.schemas.admin_config import DEFAULTS, ConfigSectionRead, MergedConfigRead

logger = logging.getLogger(__name__)


class AdminConfigService:
    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def get_merged_config(
        self, org_id: uuid.UUID, db: AsyncSession
    ) -> MergedConfigRead:
        """Return all 6 config sections for the org, falling back to defaults."""
        stmt = select(SystemConfig).where(SystemConfig.organization_id == org_id)
        result = await db.execute(stmt)
        rows: list[SystemConfig] = list(result.scalars().all())

        by_type = {r.config_type: r for r in rows}
        sections: dict[str, ConfigSectionRead] = {}

        for ct in CONFIG_TYPES:
            if ct in by_type:
                row = by_type[ct]
                payload = {**DEFAULTS[ct], **row.config_payload}
                sections[ct] = ConfigSectionRead(
                    config_type=ct,
                    config_payload=payload,
                    version=row.version,
                    updated_at=row.updated_at,
                )
            else:
                sections[ct] = ConfigSectionRead(
                    config_type=ct,
                    config_payload=dict(DEFAULTS[ct]),
                    version=0,
                    updated_at=datetime.now(timezone.utc),
                )

        return MergedConfigRead(organization_id=org_id, sections=sections)

    async def get_section(
        self, org_id: uuid.UUID, config_type: str, db: AsyncSession
    ) -> ConfigSectionRead:
        """Return a single config section, defaulting if not yet saved."""
        stmt = select(SystemConfig).where(
            SystemConfig.organization_id == org_id,
            SystemConfig.config_type == config_type,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            return ConfigSectionRead(
                config_type=config_type,
                config_payload=dict(DEFAULTS.get(config_type, {})),
                version=0,
                updated_at=datetime.now(timezone.utc),
            )

        return ConfigSectionRead(
            config_type=config_type,
            config_payload={**DEFAULTS.get(config_type, {}), **row.config_payload},
            version=row.version,
            updated_at=row.updated_at,
        )

    async def get_history(
        self, org_id: uuid.UUID, config_type: str, db: AsyncSession, limit: int = 50
    ) -> list[ConfigHistory]:
        """Return ConfigHistory entries for a given org + config_type."""
        stmt = (
            select(ConfigHistory)
            .join(SystemConfig, ConfigHistory.config_id == SystemConfig.id)
            .where(
                SystemConfig.organization_id == org_id,
                SystemConfig.config_type == config_type,
            )
            .order_by(ConfigHistory.timestamp.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def upsert_config(
        self,
        org_id: uuid.UUID,
        config_type: str,
        payload: dict,
        changed_by_id: uuid.UUID,
        db: AsyncSession,
    ) -> ConfigSectionRead:
        """Upsert a config section, increment version, write audit history."""
        if config_type not in CONFIG_TYPES:
            raise ValueError(f"Unknown config_type: {config_type}")

        stmt = select(SystemConfig).where(
            SystemConfig.organization_id == org_id,
            SystemConfig.config_type == config_type,
        )
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            # First-time write
            row = SystemConfig(
                organization_id=org_id,
                config_type=config_type,
                config_payload=payload,
                version=1,
            )
            db.add(row)
            await db.flush()
            previous = None
        else:
            previous = dict(row.config_payload)
            row.config_payload = payload
            row.version += 1
            row.updated_at = datetime.now(timezone.utc)

        history_entry = ConfigHistory(
            config_id=row.id,
            changed_by_id=changed_by_id,
            previous_value=previous,
            new_value=payload,
        )
        db.add(history_entry)
        await db.commit()
        await db.refresh(row)

        logger.info(
            "system_config updated org=%s type=%s version=%d by=%s",
            org_id, config_type, row.version, changed_by_id,
        )

        return ConfigSectionRead(
            config_type=config_type,
            config_payload={**DEFAULTS.get(config_type, {}), **row.config_payload},
            version=row.version,
            updated_at=row.updated_at,
        )

    # ------------------------------------------------------------------
    # Convenience: read a specific field quickly
    # ------------------------------------------------------------------

    async def is_retrieval_only(self, org_id: uuid.UUID, db: AsyncSession) -> bool:
        section = await self.get_section(org_id, "llm_trigger", db)
        return bool(section.config_payload.get("retrieval_only", False))

    async def is_prompt_learning_enabled(self, org_id: uuid.UUID, db: AsyncSession) -> bool:
        section = await self.get_section(org_id, "prompt_learning", db)
        return bool(section.config_payload.get("enabled", False))

    async def get_sensitivity_mode(self, org_id: uuid.UUID, db: AsyncSession) -> str:
        section = await self.get_section(org_id, "learning_sensitivity", db)
        return section.config_payload.get("mode", "conservative")


admin_config_service = AdminConfigService()
