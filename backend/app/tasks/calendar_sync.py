"""Celery task: sync Google Calendar events for a CalendarConnection."""
import asyncio
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
from app.config import get_settings
from app.core.security import decrypt_value, encrypt_value
from app.models.calendar_connection import CalendarConnection, CalendarProvider
from app.models.calendar_event import CalendarEvent, EventStatus
import app.models  # ensure all models registered with SQLAlchemy mapper


def _make_engine():
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)


async def _refresh_access_token(conn: CalendarConnection, client: httpx.AsyncClient) -> str:
    """Refresh the Google OAuth2 access token and update the connection object in-place."""
    settings = get_settings()
    refresh_token = decrypt_value(conn.refresh_token_enc)
    resp = await client.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )
    resp.raise_for_status()
    token_data = resp.json()
    new_access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 3600)
    conn.access_token_enc = encrypt_value(new_access_token)
    conn.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return new_access_token


def _parse_event_dt(dt_obj: Optional[dict]) -> Optional[datetime]:
    """Parse a Google Calendar dateTime or date object to a UTC datetime."""
    if not dt_obj:
        return None
    if "dateTime" in dt_obj:
        try:
            dt = datetime.fromisoformat(dt_obj["dateTime"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None
    if "date" in dt_obj:
        try:
            d = datetime.strptime(dt_obj["date"], "%Y-%m-%d")
            return d.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def _event_status(google_status: Optional[str]) -> EventStatus:
    if google_status == "tentative":
        return EventStatus.tentative
    if google_status == "cancelled":
        return EventStatus.cancelled
    return EventStatus.confirmed


async def _run_sync(connection_id: str, org_id: str) -> dict:
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # Load connection
        stmt = select(CalendarConnection).where(CalendarConnection.id == uuid.UUID(connection_id))
        result = await db.execute(stmt)
        conn = result.scalar_one_or_none()
        if conn is None:
            await engine.dispose()
            return {"status": "error", "detail": "connection not found"}

        if conn.provider != CalendarProvider.google:
            await engine.dispose()
            return {"status": "error", "detail": "only google provider is supported"}

        if not conn.access_token_enc:
            await engine.dispose()
            return {"status": "error", "detail": "no access token stored"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            # Refresh token if expiring within 5 minutes
            now = datetime.now(timezone.utc)
            needs_refresh = (
                conn.refresh_token_enc
                and conn.token_expires_at is not None
                and conn.token_expires_at <= now + timedelta(minutes=5)
            )

            if needs_refresh:
                try:
                    access_token = await _refresh_access_token(conn, client)
                except Exception as e:
                    await engine.dispose()
                    return {"status": "error", "detail": f"token refresh failed: {e}"}
            else:
                access_token = decrypt_value(conn.access_token_enc)

            # Fetch events from Google Calendar API
            time_min = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            time_max = (now + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")

            try:
                events_resp = await client.get(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params={
                        "timeMin": time_min,
                        "timeMax": time_max,
                        "maxResults": 250,
                        "singleEvents": "true",
                        "orderBy": "startTime",
                    },
                )
                events_resp.raise_for_status()
                events_data = events_resp.json()
            except Exception as e:
                await engine.dispose()
                return {"status": "error", "detail": f"Google API error: {e}"}

        google_events: List[dict] = events_data.get("items", [])
        upserted = 0

        for item in google_events:
            external_id = item.get("id", "")
            if not external_id:
                continue

            start_dt = _parse_event_dt(item.get("start"))
            end_dt = _parse_event_dt(item.get("end"))
            if start_dt is None or end_dt is None:
                continue

            all_day = "date" in (item.get("start") or {}) and "dateTime" not in (item.get("start") or {})
            title = item.get("summary") or "(No title)"
            description = item.get("description")
            location = item.get("location")
            organizer_email = (item.get("organizer") or {}).get("email")
            attendees = item.get("attendees") or []
            attendees_json = json.dumps(
                [{"email": a.get("email"), "displayName": a.get("displayName"), "responseStatus": a.get("responseStatus")} for a in attendees]
            ) if attendees else None
            ev_status = _event_status(item.get("status"))

            # Upsert: check if event already exists
            existing_stmt = select(CalendarEvent).where(
                CalendarEvent.external_id == external_id,
                CalendarEvent.connection_id == uuid.UUID(connection_id),
            )
            existing_result = await db.execute(existing_stmt)
            existing_event = existing_result.scalar_one_or_none()

            if existing_event is not None:
                # Update existing event
                existing_event.title = title
                existing_event.description = description
                existing_event.location = location
                existing_event.start_at = start_dt
                existing_event.end_at = end_dt
                existing_event.all_day = all_day
                existing_event.status = ev_status
                existing_event.organizer_email = organizer_email
                existing_event.attendees_json = attendees_json
            else:
                # Insert new event
                new_event = CalendarEvent(
                    organization_id=uuid.UUID(org_id),
                    connection_id=uuid.UUID(connection_id),
                    external_id=external_id,
                    title=title,
                    description=description,
                    location=location,
                    start_at=start_dt,
                    end_at=end_dt,
                    all_day=all_day,
                    status=ev_status,
                    organizer_email=organizer_email,
                    attendees_json=attendees_json,
                )
                db.add(new_event)
                upserted += 1

        # Update last_sync_at and potentially refreshed token
        await db.execute(
            update(CalendarConnection)
            .where(CalendarConnection.id == uuid.UUID(connection_id))
            .values(
                last_sync_at=datetime.now(timezone.utc),
                access_token_enc=conn.access_token_enc,
                token_expires_at=conn.token_expires_at,
            )
        )
        await db.commit()

    await engine.dispose()
    return {"status": "ok", "new_events": upserted, "total_fetched": len(google_events), "connection_id": connection_id}


@celery.task(name="calendar_sync.sync_calendar")
def sync_calendar_task(connection_id: str, org_id: str):
    """Sync Google Calendar events for a single CalendarConnection."""
    return asyncio.run(_run_sync(connection_id, org_id))


async def _run_sync_all() -> dict:
    """Load all active Google Calendar connections and dispatch individual sync tasks."""
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        stmt = select(CalendarConnection).where(
            CalendarConnection.is_active == True,  # noqa: E712
            CalendarConnection.provider == CalendarProvider.google,
            CalendarConnection.access_token_enc != None,  # noqa: E711
        )
        result = await db.execute(stmt)
        connections = result.scalars().all()
        connection_pairs = [(str(c.id), str(c.organization_id)) for c in connections]

    await engine.dispose()

    dispatched = 0
    for conn_id, org_id in connection_pairs:
        sync_calendar_task.delay(conn_id, org_id)
        dispatched += 1

    return {"status": "ok", "dispatched": dispatched}


@celery.task(name="calendar_sync.sync_calendar_all")
def sync_calendar_all_task():
    """Sync all active Google Calendar connections."""
    return asyncio.run(_run_sync_all())
