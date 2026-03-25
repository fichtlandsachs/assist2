import uuid
from typing import List, Optional
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.organization import Organization
from app.models.calendar_connection import CalendarConnection, CalendarProvider
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar import (
    CalendarConnectionCreate,
    CalendarConnectionRead,
    CalendarConnectionUpdate,
    CalendarEventCreate,
    CalendarEventRead,
)
from app.core.exceptions import NotFoundException
from app.core.security import encrypt_value
from app.config import get_settings
from app.tasks.calendar_sync import sync_calendar_task

router = APIRouter()


@router.get(
    "/calendar/connections",
    response_model=List[CalendarConnectionRead],
    summary="List calendar connections for an organization",
)
async def list_calendar_connections(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CalendarConnectionRead]:
    """List all calendar connections for the given organization."""
    stmt = (
        select(CalendarConnection)
        .where(CalendarConnection.organization_id == org_id)
        .order_by(CalendarConnection.created_at.desc())
    )
    result = await db.execute(stmt)
    connections = result.scalars().all()
    return [CalendarConnectionRead.model_validate(c) for c in connections]


@router.post(
    "/calendar/connections",
    response_model=CalendarConnectionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a calendar connection",
)
async def create_calendar_connection(
    org_id: uuid.UUID,
    data: CalendarConnectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarConnectionRead:
    """Create a new calendar connection (manual, no OAuth)."""
    connection = CalendarConnection(
        organization_id=org_id,
        user_id=current_user.id,
        provider=data.provider,
        email_address=data.email_address,
        display_name=data.display_name,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return CalendarConnectionRead.model_validate(connection)


@router.delete(
    "/calendar/connections/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a calendar connection",
)
async def delete_calendar_connection(
    connection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a calendar connection."""
    stmt = select(CalendarConnection).where(CalendarConnection.id == connection_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Calendar connection not found")
    await db.delete(connection)
    await db.commit()


@router.patch(
    "/calendar/connections/{connection_id}",
    response_model=CalendarConnectionRead,
    summary="Update a calendar connection",
)
async def update_calendar_connection(
    connection_id: uuid.UUID,
    org_id: uuid.UUID,
    data: CalendarConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarConnectionRead:
    """Update sync interval or other settings for a calendar connection."""
    stmt = select(CalendarConnection).where(
        CalendarConnection.id == connection_id,
        CalendarConnection.organization_id == org_id,
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Calendar connection not found")
    if data.sync_interval_minutes is not None:
        connection.sync_interval_minutes = data.sync_interval_minutes
    if data.display_name is not None:
        connection.display_name = data.display_name
    if data.is_active is not None:
        connection.is_active = data.is_active
    await db.commit()
    await db.refresh(connection)
    return CalendarConnectionRead.model_validate(connection)


@router.get(
    "/calendar/events",
    response_model=List[CalendarEventRead],
    summary="List calendar events",
)
async def list_calendar_events(
    org_id: uuid.UUID,
    connection_id: Optional[uuid.UUID] = None,
    from_dt: Optional[datetime] = None,
    to_dt: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CalendarEventRead]:
    """List calendar events for an organization with optional filters."""
    stmt = select(CalendarEvent).where(CalendarEvent.organization_id == org_id)
    if connection_id is not None:
        stmt = stmt.where(CalendarEvent.connection_id == connection_id)
    if from_dt is not None:
        stmt = stmt.where(CalendarEvent.start_at >= from_dt)
    if to_dt is not None:
        stmt = stmt.where(CalendarEvent.start_at <= to_dt)
    stmt = stmt.order_by(CalendarEvent.start_at.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()
    return [CalendarEventRead.model_validate(e) for e in events]


@router.post(
    "/calendar/events",
    response_model=CalendarEventRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a calendar event (manual)",
)
async def create_calendar_event(
    org_id: uuid.UUID,
    connection_id: uuid.UUID,
    data: CalendarEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarEventRead:
    """Manually create a calendar event."""
    # Verify connection belongs to org
    stmt = select(CalendarConnection).where(
        CalendarConnection.id == connection_id,
        CalendarConnection.organization_id == org_id,
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Calendar connection not found")

    event = CalendarEvent(
        organization_id=org_id,
        connection_id=connection_id,
        external_id=str(uuid.uuid4()),  # Placeholder external ID for manual events
        title=data.title,
        description=data.description,
        location=data.location,
        start_at=data.start_at,
        end_at=data.end_at,
        all_day=data.all_day,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return CalendarEventRead.model_validate(event)


@router.delete(
    "/calendar/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a calendar event",
)
async def delete_calendar_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a calendar event."""
    stmt = select(CalendarEvent).where(CalendarEvent.id == event_id)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    if event is None:
        raise NotFoundException("Calendar event not found")
    await db.delete(event)
    await db.commit()


# ── Google OAuth2 ──────────────────────────────────────────────────────────────

@router.get(
    "/calendar/connections/google/authorize",
    summary="Start Google Calendar OAuth2 flow",
)
async def google_calendar_authorize(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the Google OAuth2 authorization URL for calendar access."""
    settings = get_settings()
    base_url = settings.APP_BASE_URL.rstrip("/")
    redirect_uri = f"{base_url}/api/v1/calendar/connections/google/callback"
    state = f"{org_id}:{current_user.id}"

    params = urlencode({
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{params}"
    return {"url": auth_url}


@router.get(
    "/calendar/connections/google/callback",
    summary="Handle Google Calendar OAuth2 callback",
)
async def google_calendar_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Exchange OAuth2 code for tokens and create a CalendarConnection."""
    settings = get_settings()

    # Parse state
    try:
        org_id_str, user_id_str = state.split(":", 1)
        org_id = uuid.UUID(org_id_str)
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        return RedirectResponse(url="/calendar?error=oauth_failed", status_code=302)

    # Verify org exists to prevent IDOR
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()
    if org is None:
        return RedirectResponse(url="/", status_code=302)

    error_redirect = f"/{org.slug}/calendar?error=oauth_failed"
    success_redirect = f"/{org.slug}/calendar"

    base_url = settings.APP_BASE_URL.rstrip("/")
    redirect_uri = f"{base_url}/api/v1/calendar/connections/google/callback"

    # Exchange code for tokens
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token", "")
            expires_in = token_data.get("expires_in", 3600)
            token_expires_at = datetime.now(timezone.utc).replace(microsecond=0)
            from datetime import timedelta
            token_expires_at = token_expires_at + timedelta(seconds=expires_in)

            # Fetch user info to get email
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
            email_address = userinfo.get("email", "")
    except Exception:
        return RedirectResponse(url=error_redirect, status_code=302)

    # Create CalendarConnection with encrypted tokens
    connection = CalendarConnection(
        organization_id=org_id,
        user_id=user_id,
        provider=CalendarProvider.google,
        email_address=email_address,
        display_name=userinfo.get("name") or email_address,
        access_token_enc=encrypt_value(access_token),
        refresh_token_enc=encrypt_value(refresh_token) if refresh_token else None,
        token_expires_at=token_expires_at,
        is_active=True,
    )
    db.add(connection)
    await db.commit()

    return RedirectResponse(url=success_redirect, status_code=302)


# ── Sync trigger ───────────────────────────────────────────────────────────────

@router.post(
    "/calendar/connections/{connection_id}/sync",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger calendar sync",
)
async def trigger_calendar_sync(
    connection_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Enqueue a Celery task to sync the calendar connection."""
    stmt = select(CalendarConnection).where(
        CalendarConnection.id == connection_id,
        CalendarConnection.organization_id == org_id,
    )
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Calendar connection not found")
    sync_calendar_task.delay(str(connection_id), str(org_id))
    return {"status": "queued", "connection_id": str(connection_id)}
