"""Celery Beat dispatcher: checks intervals and dispatches sync tasks."""
import asyncio
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
from app.config import get_settings
from app.models.mail_connection import MailConnection
from app.models.calendar_connection import CalendarConnection, CalendarProvider
from app.tasks.mail_sync import sync_mailbox_task
from app.tasks.calendar_sync import sync_calendar_task
import app.models  # noqa: F401 — ensure all models registered with SQLAlchemy mapper


def _make_engine():
    return create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)


def _is_due(last_sync_at, interval_minutes: int, now: datetime) -> bool:
    """Return True if the connection is due for sync."""
    if last_sync_at is None:
        return True
    try:
        return (now - last_sync_at) >= timedelta(minutes=interval_minutes)
    except TypeError:
        return True  # naive timestamp — treat as overdue


async def _dispatch_mail() -> dict:
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    try:
        async with SessionLocal() as db:
            # System sweep: intentionally queries across all orgs.
            # Individual sync tasks (sync_mailbox_task) enforce tenant isolation.
            stmt = select(MailConnection).where(
                MailConnection.is_active.is_(True),
                MailConnection.imap_host.isnot(None),
            )
            result = await db.execute(stmt)
            connections = result.scalars().all()

            to_sync = [
                (str(c.id), str(c.organization_id))
                for c in connections
                if _is_due(c.last_sync_at, c.sync_interval_minutes, now)
            ]
    finally:
        await engine.dispose()

    for conn_id, org_id in to_sync:
        sync_mailbox_task.delay(conn_id, org_id)

    return {"dispatched": len(to_sync)}


@celery.task(name="sync_dispatcher.dispatch_mail_sync")
def dispatch_mail_sync_task():
    """Dispatch mail sync for all connections whose interval has elapsed."""
    return asyncio.run(_dispatch_mail())


async def _dispatch_calendar() -> dict:
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    try:
        async with SessionLocal() as db:
            # System sweep: intentionally queries across all orgs.
            # Individual sync tasks (sync_calendar_task) enforce tenant isolation.
            stmt = select(CalendarConnection).where(
                CalendarConnection.is_active.is_(True),
                CalendarConnection.provider == CalendarProvider.google,
                CalendarConnection.access_token_enc.isnot(None),
            )
            result = await db.execute(stmt)
            connections = result.scalars().all()

            to_sync = [
                (str(c.id), str(c.organization_id))
                for c in connections
                if _is_due(c.last_sync_at, c.sync_interval_minutes, now)
            ]
    finally:
        await engine.dispose()

    for conn_id, org_id in to_sync:
        sync_calendar_task.delay(conn_id, org_id)

    return {"dispatched": len(to_sync)}


@celery.task(name="sync_dispatcher.dispatch_calendar_sync")
def dispatch_calendar_sync_task():
    """Dispatch calendar sync for all connections whose interval has elapsed."""
    return asyncio.run(_dispatch_calendar())
