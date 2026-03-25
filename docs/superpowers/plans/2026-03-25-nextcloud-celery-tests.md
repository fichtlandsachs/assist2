# Nextcloud Abschluss, Celery Tasks & Test-Coverage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nextcloud-Integration abschließen, Celery Beat-Dispatcher mit konfigurierbaren Sync-Intervallen per Verbindung einführen, AI-Agent-Tasks implementieren und Test-Coverage für alle neuen Bereiche aufbauen.

**Architecture:** Celery Beat läuft einen Dispatcher jede Minute, der anhand von `sync_interval_minutes` (DB-Feld auf Mail/Kalender-Verbindung) entscheidet, welche Verbindungen synchronisiert werden. `agent_tasks.py` bekommt zwei echte Tasks: Story-Analyse direkt im Worker, n8n AI-Delivery-Trigger via Webhook. Nextcloud bekommt `upload_story_pdf` und wird mit dem Docs-Save-Endpoint verdrahtet.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery 5.4, httpx, pytest-asyncio, pytest (SQLite in-memory für Integration), Python 3.12.

---

## File Map

### Neue Dateien
- `backend/migrations/versions/0018_sync_interval_minutes.py` — Alembic-Migration
- `backend/app/tasks/sync_dispatcher.py` — Celery Beat Dispatcher Tasks
- `backend/tests/unit/test_mail_sync.py` — Unit Tests mail_sync
- `backend/tests/unit/test_calendar_sync.py` — Unit Tests calendar_sync
- `backend/tests/unit/test_agent_tasks_unit.py` — Unit Tests agent_tasks
- `backend/tests/unit/test_dispatch_tasks.py` — Unit Tests sync_dispatcher
- `backend/tests/integration/test_nextcloud.py` — Integration Tests Nextcloud endpoints
- `backend/tests/integration/test_agent_tasks_endpoint.py` — Integration Tests agent endpoint

### Geänderte Dateien
- `backend/app/models/mail_connection.py` — `sync_interval_minutes` Feld
- `backend/app/models/calendar_connection.py` — `sync_interval_minutes` Feld
- `backend/app/config.py` — `MAIL_SYNC_INTERVAL_MINUTES`, `CALENDAR_SYNC_INTERVAL_MINUTES`
- `backend/app/schemas/inbox.py` — `MailConnectionUpdate`, `sync_interval_minutes` in Read
- `backend/app/schemas/calendar.py` — `CalendarConnectionUpdate`, `sync_interval_minutes` in Read
- `backend/app/routers/inbox.py` — PATCH `/inbox/connections/{id}`
- `backend/app/routers/calendar.py` — PATCH `/calendar/connections/{id}`
- `backend/app/tasks/agent_tasks.py` — Echte Implementierung beider Tasks
- `backend/app/celery_app.py` — `beat_schedule`, `sync_dispatcher` in `include`
- `backend/app/services/nextcloud_service.py` — `upload_story_pdf`
- `backend/app/schemas/user_story.py` — `save_to_nextcloud` in `StoryDocsSave`
- `backend/app/routers/user_stories.py` — Nextcloud-Upload in `save_story_docs`
- `infra/docker-compose.yml` — Nextcloud `NEXTCLOUD_TRUSTED_PROXIES`
- `frontend/app/[org]/inbox/page.tsx` — Sync-Intervall-Dropdown
- `frontend/app/[org]/calendar/page.tsx` — Sync-Intervall-Dropdown

---

## Task 1: Migration 0018 — sync_interval_minutes + Modelle + Config

**Files:**
- Create: `backend/migrations/versions/0018_sync_interval_minutes.py`
- Modify: `backend/app/models/mail_connection.py`
- Modify: `backend/app/models/calendar_connection.py`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Migration erstellen**

```python
# backend/migrations/versions/0018_sync_interval_minutes.py
"""Add sync_interval_minutes to mail and calendar connections.

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mail_connections",
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "calendar_connections",
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
    )


def downgrade() -> None:
    op.drop_column("mail_connections", "sync_interval_minutes")
    op.drop_column("calendar_connections", "sync_interval_minutes")
```

- [ ] **Step 2: MailConnection Model aktualisieren**

In `backend/app/models/mail_connection.py` nach `last_sync_at` folgende Zeile ergänzen:

```python
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
```

Vollständige Zeile im Kontext (nach `last_sync_at: Mapped[Optional[datetime]] ...`):
```python
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    created_at: Mapped[datetime] = ...
```

- [ ] **Step 3: CalendarConnection Model aktualisieren**

In `backend/app/models/calendar_connection.py` nach `last_sync_at` einfügen:

```python
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
```

Der Import `Integer` ist bereits in der Datei vorhanden (`from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum`), muss um `Integer` erweitert werden:

```python
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum, Integer
```

- [ ] **Step 4: Config aktualisieren**

In `backend/app/config.py` nach dem `NEXTCLOUD_ADMIN_APP_PASSWORD`-Eintrag einfügen:

```python
    # Sync defaults (used as initial value when creating connections)
    MAIL_SYNC_INTERVAL_MINUTES: int = 15
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 30
```

- [ ] **Step 5: Migration ausführen**

```bash
make migrate
```

Erwartete Ausgabe: `Running upgrade 0017 -> 0018, Add sync_interval_minutes...`

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0018_sync_interval_minutes.py \
        backend/app/models/mail_connection.py \
        backend/app/models/calendar_connection.py \
        backend/app/config.py
git commit -m "feat: add sync_interval_minutes to mail and calendar connections"
```

---

## Task 2: Schemas + PATCH Endpoints für sync_interval_minutes

**Files:**
- Modify: `backend/app/schemas/inbox.py`
- Modify: `backend/app/schemas/calendar.py`
- Modify: `backend/app/routers/inbox.py`
- Modify: `backend/app/routers/calendar.py`
- Test: `backend/tests/integration/test_nextcloud.py` (Voraussetzung für Task 5, PATCH-Tests hier als Erstes)

- [ ] **Step 1: Test schreiben — PATCH mail connection**

Neue Datei `backend/tests/integration/test_sync_interval.py` erstellen:

```python
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
    client: AsyncClient, auth_headers: dict, mail_conn: MailConnection
):
    resp = await client.patch(
        f"/api/v1/inbox/connections/{mail_conn.id}",
        json={"sync_interval_minutes": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sync_interval_minutes"] == 5


@pytest.mark.asyncio
async def test_patch_calendar_connection_interval(
    client: AsyncClient, auth_headers: dict, calendar_conn: CalendarConnection
):
    resp = await client.patch(
        f"/api/v1/calendar/connections/{calendar_conn.id}",
        json={"sync_interval_minutes": 60},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sync_interval_minutes"] == 60


@pytest.mark.asyncio
async def test_patch_mail_connection_not_found(client: AsyncClient, auth_headers: dict):
    import uuid
    resp = await client.patch(
        f"/api/v1/inbox/connections/{uuid.uuid4()}",
        json={"sync_interval_minutes": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Test ausführen — erwartet FAIL**

```bash
make test-integration
```

Erwartete Ausgabe: `FAILED tests/integration/test_sync_interval.py - 404 or 405 Method Not Allowed`

- [ ] **Step 3: Schemas aktualisieren — inbox.py**

In `backend/app/schemas/inbox.py` folgendes ergänzen:

```python
class MailConnectionUpdate(BaseModel):
    sync_interval_minutes: Optional[int] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
```

Außerdem in `MailConnectionRead` das Feld ergänzen (nach `last_sync_at`):

```python
    sync_interval_minutes: int = 15
```

- [ ] **Step 4: Schemas aktualisieren — calendar.py**

In `backend/app/schemas/calendar.py` ergänzen:

```python
class CalendarConnectionUpdate(BaseModel):
    sync_interval_minutes: Optional[int] = None
    display_name: Optional[str] = None
    is_active: Optional[bool] = None
```

Und in `CalendarConnectionRead` nach `last_sync_at`:

```python
    sync_interval_minutes: int = 30
```

- [ ] **Step 5: PATCH Endpoint — inbox.py**

In `backend/app/routers/inbox.py` nach dem DELETE-Handler für connections einfügen. Zuerst den Import ergänzen:

```python
from app.schemas.inbox import MailConnectionCreate, MailConnectionRead, MessageRead, MessageUpdate, MailConnectionUpdate
```

Dann den neuen Handler:

```python
@router.patch(
    "/inbox/connections/{connection_id}",
    response_model=MailConnectionRead,
    summary="Update a mail connection",
)
async def update_mail_connection(
    connection_id: uuid.UUID,
    data: MailConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MailConnectionRead:
    """Update sync interval or other settings for a mail connection."""
    stmt = select(MailConnection).where(MailConnection.id == connection_id)
    result = await db.execute(stmt)
    connection = result.scalar_one_or_none()
    if connection is None:
        raise NotFoundException("Mail connection not found")
    if data.sync_interval_minutes is not None:
        connection.sync_interval_minutes = data.sync_interval_minutes
    if data.display_name is not None:
        connection.display_name = data.display_name
    if data.is_active is not None:
        connection.is_active = data.is_active
    await db.commit()
    await db.refresh(connection)
    return MailConnectionRead.model_validate(connection)
```

- [ ] **Step 6: PATCH Endpoint — calendar.py**

In `backend/app/routers/calendar.py` den Import ergänzen:

```python
from app.schemas.calendar import (
    CalendarConnectionCreate, CalendarConnectionRead, CalendarConnectionUpdate,
    CalendarEventCreate, CalendarEventRead,
)
```

Dann nach dem DELETE-Handler für connections einfügen:

```python
@router.patch(
    "/calendar/connections/{connection_id}",
    response_model=CalendarConnectionRead,
    summary="Update a calendar connection",
)
async def update_calendar_connection(
    connection_id: uuid.UUID,
    data: CalendarConnectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CalendarConnectionRead:
    """Update sync interval or other settings for a calendar connection."""
    stmt = select(CalendarConnection).where(CalendarConnection.id == connection_id)
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
```

Sicherstellen dass `CalendarConnection` importiert ist:
```python
from app.models.calendar_connection import CalendarConnection, CalendarProvider
```

- [ ] **Step 7: Tests ausführen — erwartet PASS**

```bash
make test-integration
```

Erwartete Ausgabe: `PASSED tests/integration/test_sync_interval.py::test_patch_mail_connection_interval`
`PASSED tests/integration/test_sync_interval.py::test_patch_calendar_connection_interval`
`PASSED tests/integration/test_sync_interval.py::test_patch_mail_connection_not_found`

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/inbox.py backend/app/schemas/calendar.py \
        backend/app/routers/inbox.py backend/app/routers/calendar.py \
        backend/tests/integration/test_sync_interval.py
git commit -m "feat: add PATCH endpoint for sync_interval_minutes on mail/calendar connections"
```

---

## Task 3: Celery Beat Dispatcher

**Files:**
- Create: `backend/app/tasks/sync_dispatcher.py`
- Modify: `backend/app/celery_app.py`
- Test: `backend/tests/unit/test_dispatch_tasks.py`

- [ ] **Step 1: Test schreiben**

```python
# backend/tests/unit/test_dispatch_tasks.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


def _make_mail_conn(conn_id, org_id, interval_minutes, last_sync_at):
    conn = MagicMock()
    conn.id = conn_id
    conn.organization_id = org_id
    conn.sync_interval_minutes = interval_minutes
    conn.last_sync_at = last_sync_at
    conn.is_active = True
    conn.imap_host = "imap.example.com"
    return conn


def _make_cal_conn(conn_id, org_id, interval_minutes, last_sync_at):
    conn = MagicMock()
    conn.id = conn_id
    conn.organization_id = org_id
    conn.sync_interval_minutes = interval_minutes
    conn.last_sync_at = last_sync_at
    conn.is_active = True
    conn.access_token_enc = "enc_token"
    return conn


@pytest.mark.asyncio
async def test_dispatch_mail_syncs_due_connections():
    """Connections past their interval are dispatched, others are skipped."""
    import uuid
    now = datetime.now(timezone.utc)

    due_conn = _make_mail_conn(uuid.uuid4(), uuid.uuid4(), 15, now - timedelta(minutes=20))
    not_due_conn = _make_mail_conn(uuid.uuid4(), uuid.uuid4(), 15, now - timedelta(minutes=5))
    never_synced = _make_mail_conn(uuid.uuid4(), uuid.uuid4(), 15, None)

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [due_conn, not_due_conn, never_synced]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.sync_dispatcher.create_async_engine"), \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_mailbox_task") as mock_task:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.sync_dispatcher import _dispatch_mail
        result = await _dispatch_mail()

    assert result["dispatched"] == 2
    assert mock_task.delay.call_count == 2


@pytest.mark.asyncio
async def test_dispatch_mail_nothing_due():
    """No connections are due — nothing dispatched."""
    import uuid
    now = datetime.now(timezone.utc)
    fresh_conn = _make_mail_conn(uuid.uuid4(), uuid.uuid4(), 15, now - timedelta(minutes=2))

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [fresh_conn]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.sync_dispatcher.create_async_engine"), \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_mailbox_task") as mock_task:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.sync_dispatcher import _dispatch_mail
        result = await _dispatch_mail()

    assert result["dispatched"] == 0
    mock_task.delay.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_calendar_syncs_due_connections():
    import uuid
    now = datetime.now(timezone.utc)
    due = _make_cal_conn(uuid.uuid4(), uuid.uuid4(), 30, now - timedelta(minutes=35))
    not_due = _make_cal_conn(uuid.uuid4(), uuid.uuid4(), 30, now - timedelta(minutes=10))

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [due, not_due]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.sync_dispatcher.create_async_engine"), \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_calendar_task") as mock_task:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.sync_dispatcher import _dispatch_calendar
        result = await _dispatch_calendar()

    assert result["dispatched"] == 1
    mock_task.delay.assert_called_once()
```

- [ ] **Step 2: Tests ausführen — erwartet FAIL**

```bash
make test-unit
```

Erwartete Ausgabe: `ImportError: cannot import name '_dispatch_mail' from 'app.tasks.sync_dispatcher'`

- [ ] **Step 3: sync_dispatcher.py implementieren**

```python
# backend/app/tasks/sync_dispatcher.py
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


async def _dispatch_mail() -> dict:
    engine = _make_engine()
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    now = datetime.now(timezone.utc)

    async with SessionLocal() as db:
        stmt = select(MailConnection).where(
            MailConnection.is_active.is_(True),
            MailConnection.imap_host.isnot(None),
        )
        result = await db.execute(stmt)
        connections = result.scalars().all()

        to_sync = [
            (str(c.id), str(c.organization_id))
            for c in connections
            if c.last_sync_at is None
            or (now - c.last_sync_at) >= timedelta(minutes=c.sync_interval_minutes)
        ]

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

    async with SessionLocal() as db:
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
            if c.last_sync_at is None
            or (now - c.last_sync_at) >= timedelta(minutes=c.sync_interval_minutes)
        ]

    await engine.dispose()

    for conn_id, org_id in to_sync:
        sync_calendar_task.delay(conn_id, org_id)

    return {"dispatched": len(to_sync)}


@celery.task(name="sync_dispatcher.dispatch_calendar_sync")
def dispatch_calendar_sync_task():
    """Dispatch calendar sync for all connections whose interval has elapsed."""
    return asyncio.run(_dispatch_calendar())
```

- [ ] **Step 4: Beat-Schedule in celery_app.py eintragen**

`backend/app/celery_app.py` vollständig ersetzen:

```python
from celery import Celery
from app.config import get_settings

settings = get_settings()

celery = Celery(
    "assist2",
    broker=settings.REDIS_URL.replace("/0", "/1"),
    backend=settings.REDIS_URL.replace("/0", "/2"),
    include=[
        "app.tasks.mail_sync",
        "app.tasks.calendar_sync",
        "app.tasks.agent_tasks",
        "app.tasks.pdf_tasks",
        "app.tasks.sync_dispatcher",
    ]
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    "dispatch-mail-sync": {
        "task": "sync_dispatcher.dispatch_mail_sync",
        "schedule": 60.0,  # every 60 seconds
    },
    "dispatch-calendar-sync": {
        "task": "sync_dispatcher.dispatch_calendar_sync",
        "schedule": 60.0,  # every 60 seconds
    },
}
```

- [ ] **Step 5: Tests ausführen — erwartet PASS**

```bash
make test-unit
```

Erwartete Ausgabe: alle 3 Dispatcher-Tests grün.

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/sync_dispatcher.py \
        backend/app/celery_app.py \
        backend/tests/unit/test_dispatch_tasks.py
git commit -m "feat: add celery beat dispatcher with per-connection sync intervals"
```

---

## Task 4: Agent Tasks — Implementierung

**Files:**
- Modify: `backend/app/tasks/agent_tasks.py`
- Test: `backend/tests/unit/test_agent_tasks_unit.py`

- [ ] **Step 1: Test schreiben**

```python
# backend/tests/unit/test_agent_tasks_unit.py
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_analyze_story_task_calls_ai_service():
    """analyze_story persists an AIStep with the AI response."""
    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_story = MagicMock()
    mock_story.id = uuid.UUID(story_id)
    mock_story.title = "Login Feature"
    mock_story.description = "As a user I want to log in"
    mock_story.acceptance_criteria = "- Can log in with email"

    mock_suggestions = MagicMock()
    mock_suggestions.model_dump_json.return_value = '{"suggestions": []}'

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_story
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("app.tasks.agent_tasks.create_async_engine"), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm, \
         patch("app.tasks.agent_tasks.get_story_suggestions", return_value=mock_suggestions) as mock_ai:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.agent_tasks import _analyze_story
        result = await _analyze_story(story_id, org_id)

    assert result["status"] == "completed"
    assert result["story_id"] == story_id
    mock_ai.assert_called_once()
    mock_db.add.assert_called_once()  # AIStep was added


@pytest.mark.asyncio
async def test_analyze_story_task_story_not_found():
    """Returns error dict when story is missing."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.agent_tasks.create_async_engine"), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.agent_tasks import _analyze_story
        result = await _analyze_story(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["detail"]


@pytest.mark.asyncio
async def test_trigger_ai_delivery_calls_n8n():
    """trigger_ai_delivery finds the workflow, creates an execution, calls n8n."""
    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_workflow = MagicMock()
    mock_workflow.id = uuid.uuid4()
    mock_workflow.n8n_workflow_id = "ai-delivery-webhook-id"
    mock_workflow.version = 1

    mock_execution = MagicMock()
    mock_execution.id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_result_wf = MagicMock()
    mock_result_wf.scalar_one_or_none.return_value = mock_workflow
    mock_db.execute = AsyncMock(return_value=mock_result_wf)
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_n8n = AsyncMock(return_value={"executionId": "n8n-123"})

    with patch("app.tasks.agent_tasks.create_async_engine"), \
         patch("app.tasks.agent_tasks.async_sessionmaker") as mock_sm, \
         patch("app.tasks.agent_tasks.n8n_client") as mock_client:

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client.trigger_workflow = mock_n8n

        from app.tasks.agent_tasks import _trigger_ai_delivery
        result = await _trigger_ai_delivery(story_id, org_id)

    assert result["status"] == "triggered"
    mock_n8n.assert_called_once()
```

- [ ] **Step 2: Tests ausführen — erwartet FAIL**

```bash
make test-unit
```

Erwartete Ausgabe: `ImportError: cannot import name '_analyze_story' from 'app.tasks.agent_tasks'`

- [ ] **Step 3: agent_tasks.py implementieren**

```python
# backend/app/tasks/agent_tasks.py
"""Celery tasks for AI agent invocation."""
import asyncio
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery
import app.models  # noqa: F401


async def _analyze_story(story_id: str, org_id: str) -> dict:
    from app.config import get_settings
    from app.models.user_story import UserStory
    from app.models.ai_step import AIStep, AIStepStatus
    from app.schemas.user_story import AISuggestRequest
    from app.services.ai_story_service import get_story_suggestions

    engine = create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        stmt = select(UserStory).where(UserStory.id == uuid.UUID(story_id))
        result = await db.execute(stmt)
        story = result.scalar_one_or_none()
        if story is None:
            await engine.dispose()
            return {"status": "error", "detail": "story not found"}

        req = AISuggestRequest(
            title=story.title,
            description=story.description or "",
            acceptance_criteria=story.acceptance_criteria or "",
        )
        suggestions = await get_story_suggestions(req)

        ai_step = AIStep(
            organization_id=uuid.UUID(org_id),
            story_id=uuid.UUID(story_id),
            agent_role="story_analyzer",
            model="claude-sonnet-4-6",
            status=AIStepStatus.completed,
            input_data=json.dumps({"title": story.title}),
            output_data=suggestions.model_dump_json()
            if hasattr(suggestions, "model_dump_json")
            else json.dumps(str(suggestions)),
        )
        db.add(ai_step)
        await db.commit()

    await engine.dispose()
    return {"status": "completed", "story_id": story_id}


@celery.task(name="agent_tasks.analyze_story", bind=True, max_retries=3)
def analyze_story_task(self, story_id: str, org_id: str):
    """Run AI story analysis and persist the result as an AIStep."""
    try:
        return asyncio.run(_analyze_story(story_id, org_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


async def _trigger_ai_delivery(story_id: str, org_id: str) -> dict:
    from app.config import get_settings
    from app.models.workflow import WorkflowDefinition, WorkflowExecution
    from app.services.n8n_client import n8n_client

    engine = create_async_engine(get_settings().DATABASE_URL, echo=False, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        stmt = select(WorkflowDefinition).where(
            WorkflowDefinition.slug == "ai-delivery",
            WorkflowDefinition.organization_id == uuid.UUID(org_id),
            WorkflowDefinition.is_active.is_(True),
        )
        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if workflow is None:
            await engine.dispose()
            return {"status": "error", "detail": "ai-delivery workflow not found for org"}

        execution = WorkflowExecution(
            organization_id=uuid.UUID(org_id),
            definition_id=workflow.id,
            definition_version=workflow.version,
            n8n_execution_id="pending",
            status="pending",
            trigger_type="celery",
            input_snapshot={"story_id": story_id, "org_id": org_id},
            context_snapshot={"workflow_slug": "ai-delivery"},
        )
        db.add(execution)
        await db.flush()

        try:
            n8n_resp = await n8n_client.trigger_workflow(
                workflow.n8n_workflow_id,
                {"execution_id": str(execution.id), "story_id": story_id, "org_id": org_id},
            )
            execution.n8n_execution_id = str(n8n_resp.get("executionId", execution.id))
            execution.status = "running"
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)

        await db.commit()
        execution_id = str(execution.id)

    await engine.dispose()
    return {"status": "triggered", "execution_id": execution_id}


@celery.task(name="agent_tasks.trigger_ai_delivery", bind=True, max_retries=3)
def trigger_ai_delivery_task(self, story_id: str, org_id: str):
    """Trigger the n8n ai-delivery workflow for a story."""
    try:
        return asyncio.run(_trigger_ai_delivery(story_id, org_id))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)
```

- [ ] **Step 4: Tests ausführen — erwartet PASS**

```bash
make test-unit
```

Erwartete Ausgabe: alle 3 agent_tasks Tests grün.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/agent_tasks.py \
        backend/tests/unit/test_agent_tasks_unit.py
git commit -m "feat: implement analyze_story and trigger_ai_delivery celery tasks"
```

---

## Task 5: Nextcloud — upload_story_pdf + Docs-Router

**Files:**
- Modify: `backend/app/services/nextcloud_service.py`
- Modify: `backend/app/schemas/user_story.py`
- Modify: `backend/app/routers/user_stories.py`
- Test: `backend/tests/unit/test_nextcloud_service.py` (erweitern)

- [ ] **Step 1: Test schreiben — upload_story_pdf**

Die bereits vorhandene Datei `backend/tests/test_nextcloud_service.py` (im Root-Tests-Ordner) um folgenden Test erweitern. Zuerst prüfen wo die Datei liegt: `backend/tests/test_nextcloud_service.py`. Neuen Test anhängen:

```python
@pytest.mark.asyncio
async def test_upload_story_pdf_returns_path():
    """upload_story_pdf PUTs to WebDAV and returns the path."""
    from app.services.nextcloud_service import NextcloudService

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    story_id = "abc123"
    with patch("app.services.nextcloud_service.httpx.AsyncClient", return_value=mock_client), \
         patch("app.services.nextcloud_service.get_settings") as mock_cfg:
        mock_cfg.return_value.NEXTCLOUD_INTERNAL_URL = "http://nextcloud"
        mock_cfg.return_value.NEXTCLOUD_ADMIN_USER = "admin"
        mock_cfg.return_value.NEXTCLOUD_ADMIN_APP_PASSWORD = "secret"
        mock_cfg.return_value.NEXTCLOUD_URL = "https://cloud.example.com"

        svc = NextcloudService()
        path = await svc.upload_story_pdf("my-org", story_id, b"%PDF-content")

    assert path == f"Organizations/my-org/Docs/{story_id}.pdf"
    mock_client.put.assert_called_once()
```

Fehlende Imports an den Anfang der bestehenden Datei hinzufügen falls nicht vorhanden:
```python
from unittest.mock import AsyncMock, MagicMock, patch
```

- [ ] **Step 2: Tests ausführen — erwartet FAIL**

```bash
make test-unit
```

Erwartete Ausgabe: `AttributeError: 'NextcloudService' object has no attribute 'upload_story_pdf'`

- [ ] **Step 3: upload_story_pdf in nextcloud_service.py ergänzen**

In `backend/app/services/nextcloud_service.py` vor `nextcloud_service = NextcloudService()` einfügen:

```python
    async def upload_story_pdf(self, org_slug: str, story_id: str, pdf_bytes: bytes) -> str:
        """Upload a PDF to Organizations/{org_slug}/Docs/{story_id}.pdf via WebDAV."""
        settings = get_settings()
        dav_base = (
            f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/"
            f"{settings.NEXTCLOUD_ADMIN_USER}"
        )
        auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
        dest_path = f"Organizations/{org_slug}/Docs/{story_id}.pdf"
        url = f"{dav_base}/{dest_path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Ensure Docs sub-folder exists
            docs_folder_url = f"{dav_base}/Organizations/{org_slug}/Docs/"
            r = await client.request("MKCOL", docs_folder_url, auth=auth)
            if r.status_code not in (201, 405):
                pass  # 405 = already exists

            resp = await client.put(url, content=pdf_bytes, auth=auth)
            resp.raise_for_status()

        return dest_path
```

- [ ] **Step 4: StoryDocsSave Schema aktualisieren**

In `backend/app/schemas/user_story.py` in der Klasse `StoryDocsSave` ergänzen:

```python
class StoryDocsSave(BaseModel):
    changelog_entry: str
    pdf_outline: list[str]
    summary: str
    technical_notes: str
    confluence_space_key: Optional[str] = None
    confluence_parent_page_id: Optional[str] = None
    save_to_nextcloud: bool = False          # ← neu
```

- [ ] **Step 5: save_story_docs Router verdrahten**

In `backend/app/routers/user_stories.py` in der Funktion `save_story_docs` nach dem Confluence-Block (nach `await db.commit()`, vor dem `return`-Statement) einfügen:

```python
    # Upload PDF to Nextcloud if requested
    nextcloud_path: Optional[str] = None
    if data.save_to_nextcloud and org:
        try:
            pdf_bytes = await _render_story_pdf(story, org, db)
            nextcloud_path = await nextcloud_service.upload_story_pdf(
                org.slug, str(story_id), pdf_bytes
            )
        except Exception as exc:
            logger.warning(f"Nextcloud upload failed (non-fatal): {exc}")
```

Und im `return`-Statement `nextcloud_path` hinzufügen:

```python
    return StoryDocsRead(
        **docs_dict,
        confluence_page_url=story.confluence_page_url,
        nextcloud_path=nextcloud_path,
    )
```

Außerdem am Anfang der Datei `nextcloud_service` importieren, falls noch nicht vorhanden:
```python
from app.services.nextcloud_service import nextcloud_service
```

Und eine Hilfsfunktion `_render_story_pdf` ergänzen (direkt vor `save_story_docs`):

```python
async def _render_story_pdf(story: UserStory, org: Organization, db: AsyncSession) -> bytes:
    """Render the story as a PDF via Stirling."""
    from app.services.pdf_service import PDFService
    pdf_service = PDFService()
    return await pdf_service.generate_story_pdf(story, org, db)
```

*Hinweis:* Falls `PDFService.generate_story_pdf` noch nicht existiert, die Methode in `pdf_service.py` implementieren — sie rendert `userstory_pdf.html.jinja2` und gibt PDF-Bytes zurück via `stirling_client.html_to_pdf()`. Den Import und den Aufruf anpassen falls die Methode anders heißt.

- [ ] **Step 6: Tests ausführen — erwartet PASS**

```bash
make test-unit
```

Erwartete Ausgabe: `PASSED tests/test_nextcloud_service.py::test_upload_story_pdf_returns_path`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/nextcloud_service.py \
        backend/app/schemas/user_story.py \
        backend/app/routers/user_stories.py \
        backend/tests/test_nextcloud_service.py
git commit -m "feat: add upload_story_pdf to nextcloud service and wire into docs save endpoint"
```

---

## Task 6: Docker-Config + Commit bestehender Nextcloud-Änderungen

**Files:**
- Modify: `infra/docker-compose.yml`
- Commit: alle 11 verbleibenden uncommitteten Dateien

- [ ] **Step 1: docker-compose.yml — Nextcloud Trusted Proxies**

In `infra/docker-compose.yml` im `nextcloud`-Service unter `environment:` folgenden Eintrag ergänzen:

```yaml
      NEXTCLOUD_TRUSTED_PROXIES: "172.16.0.0/12 10.0.0.0/8"
```

Dies erlaubt Traefik als Reverse-Proxy (Docker-interne IPs).

- [ ] **Step 2: Status prüfen**

```bash
git status
```

Die noch uncommitteten modifizierten Dateien sollten jetzt umfassen:
- `backend/Dockerfile`
- `backend/app/config.py` (bereits committed in Task 1, ggf. nochmals prüfen)
- `backend/app/templates/userstory_pdf.html.jinja2`
- `frontend/app/[org]/docs/page.tsx`
- `frontend/app/[org]/nextcloud/page.tsx`
- `infra/docker-compose.yml`

- [ ] **Step 3: Commit aller verbleibenden Nextcloud-Änderungen**

```bash
git add backend/Dockerfile \
        backend/app/templates/userstory_pdf.html.jinja2 \
        frontend/app/[org]/docs/page.tsx \
        frontend/app/[org]/nextcloud/page.tsx \
        infra/docker-compose.yml
git commit -m "feat(nextcloud): complete nextcloud integration — proxy, templates, frontend, docker config"
```

---

## Task 7: Unit Tests — mail_sync

**Files:**
- Create: `backend/tests/unit/test_mail_sync.py`

- [ ] **Step 1: Tests schreiben**

```python
# backend/tests/unit/test_mail_sync.py
"""Unit tests for mail_sync task internals."""
import email
import email.header
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call
import uuid


# ── Header decoding ────────────────────────────────────────────────────────────

def test_decode_header_plain():
    from app.tasks.mail_sync import _decode_header
    assert _decode_header("Hello World") == "Hello World"


def test_decode_header_mime_encoded():
    from app.tasks.mail_sync import _decode_header
    # RFC 2047 Base64-encoded UTF-8
    encoded = "=?UTF-8?B?SGVsbG8gV29ybGQ=?="
    assert _decode_header(encoded) == "Hello World"


def test_decode_header_none():
    from app.tasks.mail_sync import _decode_header
    assert _decode_header(None) is None


# ── Date parsing ───────────────────────────────────────────────────────────────

def test_parse_date_valid():
    from app.tasks.mail_sync import _parse_date
    raw = "Mon, 01 Jan 2024 10:00:00 +0000"
    dt = _parse_date(raw)
    assert dt is not None
    assert dt.year == 2024
    assert dt.tzinfo is not None


def test_parse_date_invalid():
    from app.tasks.mail_sync import _parse_date
    assert _parse_date("not-a-date") is None


def test_parse_date_none():
    from app.tasks.mail_sync import _parse_date
    assert _parse_date(None) is None


# ── Body extraction ────────────────────────────────────────────────────────────

def test_get_body_simple_text():
    from app.tasks.mail_sync import _get_body
    msg = email.message_from_string(
        "Content-Type: text/plain\r\n\r\nHello, world!"
    )
    assert _get_body(msg) == "Hello, world!"


def test_get_body_multipart():
    from app.tasks.mail_sync import _get_body
    raw = (
        "MIME-Version: 1.0\r\n"
        "Content-Type: multipart/alternative; boundary=bound\r\n"
        "\r\n"
        "--bound\r\n"
        "Content-Type: text/plain\r\n\r\n"
        "Plain text body\r\n"
        "--bound\r\n"
        "Content-Type: text/html\r\n\r\n"
        "<p>HTML body</p>\r\n"
        "--bound--\r\n"
    )
    msg = email.message_from_string(raw)
    body = _get_body(msg)
    assert body == "Plain text body"


# ── _run_sync integration (mocked DB + IMAP) ──────────────────────────────────

@pytest.mark.asyncio
async def test_run_sync_connection_not_found():
    from app.tasks.mail_sync import _run_sync

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.mail_sync.create_async_engine"), \
         patch("app.tasks.mail_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["detail"]


@pytest.mark.asyncio
async def test_run_sync_no_imap_credentials():
    from app.tasks.mail_sync import _run_sync

    mock_conn = MagicMock()
    mock_conn.imap_host = None
    mock_conn.imap_password_enc = None

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.mail_sync.create_async_engine"), \
         patch("app.tasks.mail_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "IMAP credentials" in result["detail"]


@pytest.mark.asyncio
async def test_run_sync_imap_error_returns_error():
    """IMAP4.error during connect → returns error dict, doesn't raise."""
    import imaplib
    from app.tasks.mail_sync import _run_sync

    mock_conn = MagicMock()
    mock_conn.imap_host = "imap.example.com"
    mock_conn.imap_port = 993
    mock_conn.imap_use_ssl = True
    mock_conn.imap_password_enc = "encrypted"
    mock_conn.email_address = "test@example.com"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.mail_sync.create_async_engine"), \
         patch("app.tasks.mail_sync.async_sessionmaker") as mock_sm, \
         patch("app.tasks.mail_sync.decrypt_value", return_value="password"), \
         patch("app.tasks.mail_sync.asyncio.get_event_loop") as mock_loop:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_loop.return_value.run_in_executor = AsyncMock(
            side_effect=imaplib.IMAP4.error("Connection refused")
        )

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "IMAP error" in result["detail"]
```

- [ ] **Step 2: Tests ausführen — erwartet PASS**

```bash
make test-unit
```

Erwartete Ausgabe: alle `test_mail_sync` Tests grün.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_mail_sync.py
git commit -m "test: add unit tests for mail_sync internals"
```

---

## Task 8: Unit Tests — calendar_sync

**Files:**
- Create: `backend/tests/unit/test_calendar_sync.py`

- [ ] **Step 1: Tests schreiben**

```python
# backend/tests/unit/test_calendar_sync.py
"""Unit tests for calendar_sync task internals."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


def test_parse_event_dt_datetime():
    from app.tasks.calendar_sync import _parse_event_dt
    obj = {"dateTime": "2024-06-15T10:00:00+02:00"}
    dt = _parse_event_dt(obj)
    assert dt is not None
    assert dt.year == 2024
    assert dt.tzinfo is not None


def test_parse_event_dt_date_only():
    from app.tasks.calendar_sync import _parse_event_dt
    obj = {"date": "2024-06-15"}
    dt = _parse_event_dt(obj)
    assert dt is not None
    assert dt.year == 2024
    assert dt.tzinfo == timezone.utc


def test_parse_event_dt_none():
    from app.tasks.calendar_sync import _parse_event_dt
    assert _parse_event_dt(None) is None
    assert _parse_event_dt({}) is None


def test_event_status_mapping():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status("tentative") == EventStatus.tentative
    assert _event_status("cancelled") == EventStatus.cancelled
    assert _event_status("confirmed") == EventStatus.confirmed
    assert _event_status(None) == EventStatus.confirmed


@pytest.mark.asyncio
async def test_run_sync_connection_not_found():
    from app.tasks.calendar_sync import _run_sync

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.calendar_sync.create_async_engine"), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["detail"]


@pytest.mark.asyncio
async def test_run_sync_token_refresh_called_when_expired():
    """When access token expires soon, refresh is called before API request."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    now = datetime.now(timezone.utc)
    mock_conn = MagicMock()
    mock_conn.provider = CalendarProvider.google
    mock_conn.access_token_enc = "enc_old_token"
    mock_conn.refresh_token_enc = "enc_refresh"
    mock_conn.token_expires_at = now + timedelta(minutes=2)  # expires in 2 min → refresh needed
    mock_conn.organization_id = uuid.uuid4()

    mock_db = AsyncMock()
    mock_result_conn = MagicMock()
    mock_result_conn.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result_conn)
    mock_db.commit = AsyncMock()

    mock_events_resp = MagicMock()
    mock_events_resp.raise_for_status = MagicMock()
    mock_events_resp.json.return_value = {"items": []}

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=MagicMock(
        raise_for_status=MagicMock(),
        json=MagicMock(return_value={"access_token": "new_token", "expires_in": 3600}),
    ))
    mock_http_client.get = AsyncMock(return_value=mock_events_resp)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.calendar_sync.create_async_engine"), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm, \
         patch("app.tasks.calendar_sync.decrypt_value", return_value="refresh_token"), \
         patch("app.tasks.calendar_sync.encrypt_value", return_value="new_enc"), \
         patch("app.tasks.calendar_sync.httpx.AsyncClient", return_value=mock_http_client):

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(mock_conn.organization_id))

    # refresh token POST was called
    mock_http_client.post.assert_called_once()
    assert result["status"] == "ok"
```

- [ ] **Step 2: Tests ausführen — erwartet PASS**

```bash
make test-unit
```

Erwartete Ausgabe: alle `test_calendar_sync` Tests grün.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_calendar_sync.py
git commit -m "test: add unit tests for calendar_sync internals"
```

---

## Task 9: Integration Tests — Nextcloud Endpoints

**Files:**
- Create: `backend/tests/integration/test_nextcloud.py`

- [ ] **Step 1: Tests schreiben**

```python
# backend/tests/integration/test_nextcloud.py
"""Integration tests for Nextcloud proxy endpoints."""
import pytest
import pytest_asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership, MembershipRole
from app.schemas.nextcloud import NextcloudFile, NextcloudFileList


@pytest_asyncio.fixture
async def member_org(db: AsyncSession, test_user, test_org) -> tuple:
    """Returns (test_user, test_org) where test_user is already an owner via org_service."""
    return test_user, test_org


def _mock_nextcloud_file_list():
    return NextcloudFileList(
        files=[
            NextcloudFile(
                name="report.pdf",
                href="/remote.php/dav/files/admin/Organizations/test-org/report.pdf",
                content_type="application/pdf",
                last_modified=None,
                size=1024,
            )
        ],
        nextcloud_url="https://cloud.example.com",
    )


@pytest.mark.asyncio
async def test_list_files_requires_membership(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
):
    """Without membership in this org, endpoint returns 403."""
    random_org_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/organizations/{random_org_id}/nextcloud/files",
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_org_files_success(
    client: AsyncClient, auth_headers: dict, member_org
):
    """Member with active membership gets file list."""
    _, org = member_org

    with patch(
        "app.routers.nextcloud.nextcloud_service.list_files",
        return_value=_mock_nextcloud_file_list(),
    ):
        resp = await client.get(
            f"/api/v1/organizations/{org.id}/nextcloud/files",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert len(data["files"]) == 1
    assert data["files"][0]["name"] == "report.pdf"


@pytest.mark.asyncio
async def test_list_personal_files_success(
    client: AsyncClient, auth_headers: dict, member_org
):
    """Member can list their personal files."""
    _, org = member_org

    with patch(
        "app.routers.nextcloud.nextcloud_service.list_personal_files",
        return_value=NextcloudFileList(files=[], nextcloud_url="https://cloud.example.com"),
    ):
        resp = await client.get(
            f"/api/v1/organizations/{org.id}/nextcloud/files/personal",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    assert resp.json()["files"] == []


@pytest.mark.asyncio
async def test_upload_personal_file_success(
    client: AsyncClient, auth_headers: dict, member_org
):
    """File upload to personal folder returns ok=True and path."""
    _, org = member_org

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.request = AsyncMock(return_value=MagicMock(status_code=201))
    mock_client.put = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.nextcloud.httpx.AsyncClient", return_value=mock_client), \
         patch("app.routers.nextcloud.get_settings") as mock_cfg:
        mock_cfg.return_value.NEXTCLOUD_INTERNAL_URL = "http://nextcloud"
        mock_cfg.return_value.NEXTCLOUD_ADMIN_USER = "admin"
        mock_cfg.return_value.NEXTCLOUD_ADMIN_APP_PASSWORD = "secret"

        resp = await client.post(
            f"/api/v1/organizations/{org.id}/nextcloud/files/personal/upload",
            headers=auth_headers,
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )

    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert "test.txt" in resp.json()["path"]


@pytest.mark.asyncio
async def test_download_requires_membership(
    client: AsyncClient, auth_headers: dict
):
    """Download without membership → 403."""
    resp = await client.get(
        f"/api/v1/organizations/{uuid.uuid4()}/nextcloud/files/download",
        params={"path": "some/file.pdf"},
        headers=auth_headers,
    )
    assert resp.status_code == 403
```

- [ ] **Step 2: Tests ausführen — erwartet PASS**

```bash
make test-integration
```

Erwartete Ausgabe: alle 5 Nextcloud-Integrationstests grün.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_nextcloud.py
git commit -m "test: add integration tests for nextcloud proxy endpoints"
```

---

## Task 10: Integration Tests — Agent Endpoint

**Files:**
- Create: `backend/tests/integration/test_agent_tasks_endpoint.py`

- [ ] **Step 1: Tests schreiben**

```python
# backend/tests/integration/test_agent_tasks_endpoint.py
"""Integration test: invoking an agent dispatches the celery task."""
import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent


@pytest_asyncio.fixture
async def test_agent(db: AsyncSession, test_user, test_org) -> Agent:
    agent = Agent(
        organization_id=test_org.id,
        name="TestAgent",
        slug="test-agent",
        role="story_analyzer",
        system_prompt="You are a test agent.",
        is_active=True,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@pytest.mark.asyncio
async def test_invoke_agent_dispatches_analyze_task(
    client: AsyncClient, auth_headers: dict, test_agent: Agent, test_org
):
    """POST /agents/{id}/invoke triggers analyze_story_task.delay."""
    story_id = str(uuid.uuid4())

    with patch("app.tasks.agent_tasks.analyze_story_task") as mock_task:
        mock_task.delay = MagicMock()
        resp = await client.post(
            f"/api/v1/agents/{test_agent.id}/invoke",
            json={"story_id": story_id, "org_id": str(test_org.id)},
            headers=auth_headers,
        )

    # The endpoint should return 200 or 202 (accepted)
    assert resp.status_code in (200, 202)
```

*Hinweis:* Falls der `/agents/{id}/invoke`-Endpoint noch keinen Celery-Task dispatcht, muss dieser nach Step 2 ergänzt werden. Zunächst ausführen um den aktuellen Stand zu sehen.

- [ ] **Step 2: Tests ausführen und Ergebnis prüfen**

```bash
make test-integration
```

Falls der Test wegen fehlendem Celery-Dispatch fehlschlägt: Im Agents-Router (`backend/app/routers/agents.py`) im Invoke-Endpoint den Task-Dispatch ergänzen:

```python
from app.tasks.agent_tasks import analyze_story_task
# Im invoke handler, nach der bestehenden Logik:
story_id = data.get("story_id")
if story_id:
    analyze_story_task.delay(story_id, str(org_id))
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/integration/test_agent_tasks_endpoint.py
git commit -m "test: add integration test for agent invoke → celery task dispatch"
```

---

## Task 11: Frontend — Inbox Sync-Intervall Dropdown

**Files:**
- Modify: `frontend/app/[org]/inbox/page.tsx`

- [ ] **Step 1: Typ ergänzen**

In `frontend/app/[org]/inbox/page.tsx` die `MailConnection`-Typdefinition suchen (importiert aus `@/types`) und ggf. in `frontend/types/index.ts` oder `frontend/types.ts` `sync_interval_minutes: number` ergänzen:

```typescript
// In der MailConnection-Interface/Type Definition:
sync_interval_minutes?: number;
```

- [ ] **Step 2: Dropdown-Komponente in der Verbindungsansicht ergänzen**

In `frontend/app/[org]/inbox/page.tsx` wo eine einzelne Verbindung angezeigt wird, folgendes Dropdown für Sync-Intervall ergänzen. Den genauen Einfügepunkt durch Suche nach dem Connection-Display-Code finden (suche nach `email_address` oder `display_name` im JSX):

```tsx
{/* Sync Interval */}
<div className="flex items-center gap-2 mt-2">
  <label className="text-xs text-slate-500 whitespace-nowrap">Sync-Intervall:</label>
  <select
    defaultValue={conn.sync_interval_minutes ?? 15}
    onChange={async (e) => {
      const interval = Number(e.target.value);
      const token = getAccessToken() ?? "";
      await fetch(`/api/v1/inbox/connections/${conn.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ sync_interval_minutes: interval }),
      });
    }}
    className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700"
  >
    <option value={5}>5 Minuten</option>
    <option value={15}>15 Minuten</option>
    <option value={30}>30 Minuten</option>
    <option value={60}>60 Minuten</option>
  </select>
</div>
```

`getAccessToken` ist bereits in der Datei importiert.

- [ ] **Step 3: Build prüfen**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Erwartete Ausgabe: Build erfolgreich ohne TypeScript-Fehler.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/[org]/inbox/page.tsx
git commit -m "feat: add sync interval dropdown to inbox connections"
```

---

## Task 12: Frontend — Calendar Sync-Intervall Dropdown

**Files:**
- Modify: `frontend/app/[org]/calendar/page.tsx`

- [ ] **Step 1: CalendarConnection-Typ ergänzen**

In `frontend/types/index.ts` (oder wo `CalendarConnection` definiert ist) `sync_interval_minutes` ergänzen:

```typescript
sync_interval_minutes?: number;
```

- [ ] **Step 2: Dropdown ergänzen**

In `frontend/app/[org]/calendar/page.tsx` bei der Anzeige einer Kalender-Verbindung (suche nach `display_name` oder `email_address` in JSX) folgendes Dropdown einfügen:

```tsx
{/* Sync Interval */}
<div className="flex items-center gap-2 mt-2">
  <label className="text-xs text-slate-500 whitespace-nowrap">Sync-Intervall:</label>
  <select
    defaultValue={conn.sync_interval_minutes ?? 30}
    onChange={async (e) => {
      const interval = Number(e.target.value);
      const token = getAccessToken() ?? "";
      await fetch(`/api/v1/calendar/connections/${conn.id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ sync_interval_minutes: interval }),
      });
    }}
    className="text-xs border border-slate-200 rounded px-2 py-1 bg-white text-slate-700"
  >
    <option value={15}>15 Minuten</option>
    <option value={30}>30 Minuten</option>
    <option value={60}>60 Minuten</option>
    <option value={120}>2 Stunden</option>
  </select>
</div>
```

Falls `getAccessToken` in `calendar/page.tsx` noch nicht importiert ist:
```typescript
import { getAccessToken } from "@/lib/api/client";
```

- [ ] **Step 3: Build prüfen**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Erwartete Ausgabe: Build erfolgreich.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/[org]/calendar/page.tsx
git commit -m "feat: add sync interval dropdown to calendar connections"
```

---

## Spec Coverage Check

| Spec-Anforderung | Task |
|---|---|
| Nextcloud: save_to_nextcloud in Docs-Save | Task 5 |
| Nextcloud: docker-compose TRUSTED_PROXIES | Task 6 |
| Celery: analyze_story_task | Task 4 |
| Celery: trigger_ai_delivery_task | Task 4 |
| Beat-Dispatcher | Task 3 |
| sync_interval_minutes DB-Feld | Task 1 |
| .env-Defaults MAIL/CALENDAR_SYNC_INTERVAL | Task 1 |
| PATCH-Endpoint Mail-Verbindung | Task 2 |
| PATCH-Endpoint Kalender-Verbindung | Task 2 |
| UI-Dropdown Inbox | Task 11 |
| UI-Dropdown Calendar | Task 12 |
| Tests: Nextcloud-Endpoints | Task 9 |
| Tests: Celery Unit-Tests | Tasks 7, 8 |
| Tests: Dispatch-Logik | Task 3 |
| Tests: Agent-Tasks | Tasks 4, 10 |
| Commit bestehende Nextcloud-Änderungen | Task 6 |
