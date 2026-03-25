import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.mail_connection import MailConnection, MailProvider
from app.models.calendar_connection import CalendarConnection, CalendarProvider


@pytest_asyncio.fixture
async def mail_conn(db: AsyncSession, test_user, test_org) -> MailConnection:
    conn = MailConnection(
        organization_id=test_org.id,
        user_id=test_user.id,
        provider=MailProvider.imap,
        email_address="test@example.com",
        imap_host="imap.example.com",
        imap_port=993,
        sync_interval_minutes=15,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


@pytest_asyncio.fixture
async def calendar_conn(db: AsyncSession, test_user, test_org) -> CalendarConnection:
    conn = CalendarConnection(
        organization_id=test_org.id,
        user_id=test_user.id,
        provider=CalendarProvider.google,
        email_address="test@example.com",
        sync_interval_minutes=30,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return conn


@pytest.mark.asyncio
async def test_patch_mail_connection_interval(
    client: AsyncClient, auth_headers: dict, mail_conn: MailConnection, test_org
):
    resp = await client.patch(
        f"/api/v1/inbox/connections/{mail_conn.id}",
        params={"org_id": str(test_org.id)},
        json={"sync_interval_minutes": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sync_interval_minutes"] == 5


@pytest.mark.asyncio
async def test_patch_calendar_connection_interval(
    client: AsyncClient, auth_headers: dict, calendar_conn: CalendarConnection, test_org
):
    resp = await client.patch(
        f"/api/v1/calendar/connections/{calendar_conn.id}",
        params={"org_id": str(test_org.id)},
        json={"sync_interval_minutes": 60},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sync_interval_minutes"] == 60


@pytest.mark.asyncio
async def test_patch_mail_connection_not_found(client: AsyncClient, auth_headers: dict, test_org):
    resp = await client.patch(
        f"/api/v1/inbox/connections/{uuid.uuid4()}",
        params={"org_id": str(test_org.id)},
        json={"sync_interval_minutes": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_patch_mail_connection_wrong_org(
    client: AsyncClient, auth_headers: dict, mail_conn: MailConnection
):
    """Cannot update a connection by providing the wrong org_id — returns 404."""
    wrong_org_id = uuid.uuid4()
    resp = await client.patch(
        f"/api/v1/inbox/connections/{mail_conn.id}",
        params={"org_id": str(wrong_org_id)},
        json={"sync_interval_minutes": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404
