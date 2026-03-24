#!/usr/bin/env python
"""
One-time migration: provision all existing assist2 users into Authentik.

Usage (run inside backend container):
  python -m scripts.migrate_to_authentik

What it does:
1. Reads all active local users without authentik_id
2. For each: checks if Authentik user exists (by email)
3. If not: creates Authentik user with a random temporary password
4. Stores the authentik_id in the local users table

After running: execute `make migrate` to apply migration 0016 (drop user_sessions).
"""
import asyncio
import logging
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services.authentik_client import AuthentikClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

settings = get_settings()


async def migrate_users() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    AsyncSession_ = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    client = AuthentikClient()

    async with AsyncSession_() as session:
        result = await session.execute(
            select(User).where(
                User.deleted_at.is_(None),
                User.authentik_id.is_(None),
                User.is_active == True,
            )
        )
        users = result.scalars().all()
        logger.info(f"Found {len(users)} users without authentik_id")

        migrated = 0
        skipped = 0
        errors = 0

        for user in users:
            try:
                # Check if already exists in Authentik
                existing = await client.get_user_by_email(user.email)
                if existing:
                    authentik_id = str(existing["pk"])
                    logger.info(f"  Found existing Authentik user: {user.email} → {authentik_id}")
                else:
                    # Create with random temp password — user must reset
                    temp_password = secrets.token_urlsafe(20)
                    authentik_id = await client.create_user(
                        email=user.email,
                        password=temp_password,
                        display_name=user.display_name,
                    )
                    logger.info(f"  Created Authentik user: {user.email} → {authentik_id}")

                user.authentik_id = authentik_id
                await session.commit()
                migrated += 1

            except Exception as e:
                logger.error(f"  ERROR migrating {user.email}: {e}")
                await session.rollback()
                errors += 1

        logger.info(f"\nMigration complete: {migrated} migrated, {skipped} skipped, {errors} errors")
        if errors > 0:
            logger.warning("Some users failed — re-run script to retry. Do NOT run migration 0016 until errors=0.")
            sys.exit(1)
        else:
            logger.info("All users migrated. You can now run: make migrate (applies migration 0016)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_users())
