import uuid
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.schemas.calendar import (
    CalendarConnectionCreate,
    CalendarConnectionRead,
    CalendarEventCreate,
    CalendarEventRead,
)
from app.core.exceptions import NotFoundException

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
