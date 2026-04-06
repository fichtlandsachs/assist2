# backend/tests/unit/test_dispatch_tasks.py
import uuid
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

    with patch("app.tasks.sync_dispatcher.create_async_engine") as mock_engine_factory, \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_mailbox_task") as mock_task:

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_engine_factory.return_value = mock_engine
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

    with patch("app.tasks.sync_dispatcher.create_async_engine") as mock_engine_factory, \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_mailbox_task") as mock_task:

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_engine_factory.return_value = mock_engine
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

    with patch("app.tasks.sync_dispatcher.create_async_engine") as mock_engine_factory, \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.sync_calendar_task") as mock_task:

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_engine_factory.return_value = mock_engine
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.tasks.sync_dispatcher import _dispatch_calendar
        result = await _dispatch_calendar()

    assert result["dispatched"] == 1
    mock_task.delay.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_rag_index_triggers_confluence_and_jira():
    """_dispatch_rag_index must call index_confluence_space for each active org."""
    from app.tasks.sync_dispatcher import _dispatch_rag_index

    mock_org_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    mock_org_slug = "test-org"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [(mock_org_id, mock_org_slug)]
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.sync_dispatcher.create_async_engine") as mock_engine_factory, \
         patch("app.tasks.sync_dispatcher.async_sessionmaker") as mock_sm, \
         patch("app.tasks.sync_dispatcher.index_org_documents") as mock_nextcloud, \
         patch("app.tasks.sync_dispatcher.index_confluence_space") as mock_confluence:

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_engine_factory.return_value = mock_engine
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _dispatch_rag_index()

    mock_nextcloud.delay.assert_called_once_with(str(mock_org_id), mock_org_slug)
    mock_confluence.delay.assert_called_once_with(str(mock_org_id))
