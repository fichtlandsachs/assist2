# app/services/crawl/seed_sources.py
"""Seed predefined external sources into the database."""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource
from app.services.crawl.sap_source_config import SAP_S4HANA_UTILITIES_CONFIG


async def seed_sap_utilities_source() -> None:
    """Insert the SAP Utilities source if not already present."""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(ExternalSource).where(
                ExternalSource.source_key == SAP_S4HANA_UTILITIES_CONFIG["source_key"]
            )
        )
        if existing.scalar_one_or_none():
            print(f"Source '{SAP_S4HANA_UTILITIES_CONFIG['source_key']}' already exists.")
            return

        cfg = SAP_S4HANA_UTILITIES_CONFIG
        source = ExternalSource(
            source_key=cfg["source_key"],
            display_name=cfg["display_name"],
            source_type=cfg["source_type"],
            base_url=cfg["base_url"],
            visibility_scope=cfg["visibility_scope"],
            config_json=cfg["config"],
        )
        db.add(source)
        await db.commit()
        print(f"Seeded source: {cfg['source_key']}")


if __name__ == "__main__":
    asyncio.run(seed_sap_utilities_source())
