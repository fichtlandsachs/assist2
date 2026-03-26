# backend/tests/unit/test_calendar_sync.py
"""Unit tests for calendar_sync task internals."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


# ── Helper: mock engine that supports await engine.dispose() ───────────────────

def _make_mock_engine():
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    return mock_engine


# ── _parse_event_dt ────────────────────────────────────────────────────────────

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


def test_parse_event_dt_invalid_datetime_string():
    from app.tasks.calendar_sync import _parse_event_dt
    assert _parse_event_dt({"dateTime": "not-a-date"}) is None


def test_parse_event_dt_invalid_date_string():
    from app.tasks.calendar_sync import _parse_event_dt
    assert _parse_event_dt({"date": "15/06/2024"}) is None


def test_parse_event_dt_naive_datetime_gets_utc():
    """A dateTime string without tzinfo should be treated as UTC."""
    from app.tasks.calendar_sync import _parse_event_dt
    obj = {"dateTime": "2024-06-15T10:00:00"}
    dt = _parse_event_dt(obj)
    assert dt is not None
    assert dt.tzinfo == timezone.utc


# ── _event_status ──────────────────────────────────────────────────────────────

def test_event_status_tentative():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status("tentative") == EventStatus.tentative


def test_event_status_cancelled():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status("cancelled") == EventStatus.cancelled


def test_event_status_confirmed():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status("confirmed") == EventStatus.confirmed


def test_event_status_none_defaults_confirmed():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status(None) == EventStatus.confirmed


def test_event_status_unknown_defaults_confirmed():
    from app.tasks.calendar_sync import _event_status
    from app.models.calendar_event import EventStatus
    assert _event_status("unknown_value") == EventStatus.confirmed


# ── _run_sync: error paths ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_sync_connection_not_found():
    from app.tasks.calendar_sync import _run_sync

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "not found" in result["detail"]


@pytest.mark.asyncio
async def test_run_sync_non_google_provider_rejected():
    """Non-Google provider connections return an error."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    mock_conn = MagicMock()
    mock_conn.provider = "outlook"  # not CalendarProvider.google
    mock_conn.access_token_enc = "some_token"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "google" in result["detail"].lower()


@pytest.mark.asyncio
async def test_run_sync_no_access_token_returns_error():
    """Missing access_token_enc returns an error without crashing."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    mock_conn = MagicMock()
    mock_conn.provider = CalendarProvider.google
    mock_conn.access_token_enc = None  # no token stored

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm:
        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(uuid.uuid4()), str(uuid.uuid4()))

    assert result["status"] == "error"
    assert "access token" in result["detail"].lower()


# ── _run_sync: token refresh path ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_run_sync_token_refresh_called_when_expiring_soon():
    """When access token expires within 5 minutes, refresh is called before API request."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    now = datetime.now(timezone.utc)
    conn_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_conn = MagicMock()
    mock_conn.provider = CalendarProvider.google
    mock_conn.access_token_enc = "enc_old_token"
    mock_conn.refresh_token_enc = "enc_refresh"
    mock_conn.token_expires_at = now + timedelta(minutes=2)  # within 5 min threshold
    mock_conn.organization_id = org_id

    mock_db = AsyncMock()
    mock_result_conn = MagicMock()
    mock_result_conn.scalar_one_or_none.return_value = mock_conn
    # Return the same mock for all db.execute calls (connection lookup + update)
    mock_db.execute = AsyncMock(return_value=mock_result_conn)
    mock_db.commit = AsyncMock()

    mock_refresh_resp = MagicMock()
    mock_refresh_resp.raise_for_status = MagicMock()
    mock_refresh_resp.json = MagicMock(return_value={"access_token": "new_token", "expires_in": 3600})

    mock_events_resp = MagicMock()
    mock_events_resp.raise_for_status = MagicMock()
    mock_events_resp.json = MagicMock(return_value={"items": []})

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock(return_value=mock_refresh_resp)
    mock_http_client.get = AsyncMock(return_value=mock_events_resp)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm, \
         patch("app.tasks.calendar_sync.decrypt_value", return_value="decrypted_refresh_token"), \
         patch("app.tasks.calendar_sync.encrypt_value", return_value="new_enc_token"), \
         patch("app.tasks.calendar_sync.httpx.AsyncClient", return_value=mock_http_client):

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(conn_id), str(org_id))

    # Token refresh POST must have been called
    mock_http_client.post.assert_called_once()
    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_run_sync_no_refresh_when_token_valid():
    """When access token is still valid (>5 min), no refresh is triggered."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    now = datetime.now(timezone.utc)
    conn_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_conn = MagicMock()
    mock_conn.provider = CalendarProvider.google
    mock_conn.access_token_enc = "enc_valid_token"
    mock_conn.refresh_token_enc = "enc_refresh"
    mock_conn.token_expires_at = now + timedelta(minutes=30)  # still valid
    mock_conn.organization_id = org_id

    mock_db = AsyncMock()
    mock_result_conn = MagicMock()
    mock_result_conn.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result_conn)
    mock_db.commit = AsyncMock()

    mock_events_resp = MagicMock()
    mock_events_resp.raise_for_status = MagicMock()
    mock_events_resp.json = MagicMock(return_value={"items": []})

    mock_http_client = AsyncMock()
    mock_http_client.post = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_events_resp)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm, \
         patch("app.tasks.calendar_sync.decrypt_value", return_value="decrypted_access_token"), \
         patch("app.tasks.calendar_sync.encrypt_value", return_value="enc"), \
         patch("app.tasks.calendar_sync.httpx.AsyncClient", return_value=mock_http_client):

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(conn_id), str(org_id))

    # No token refresh should have happened
    mock_http_client.post.assert_not_called()
    assert result["status"] == "ok"


# ── _run_sync: success path with events ───────────────────────────────────────

@pytest.mark.asyncio
async def test_run_sync_ok_returns_counts():
    """Successful sync with zero items returns ok status with counts."""
    from app.tasks.calendar_sync import _run_sync
    from app.models.calendar_connection import CalendarProvider

    now = datetime.now(timezone.utc)
    conn_id = uuid.uuid4()
    org_id = uuid.uuid4()

    mock_conn = MagicMock()
    mock_conn.provider = CalendarProvider.google
    mock_conn.access_token_enc = "enc_token"
    mock_conn.refresh_token_enc = None  # no refresh token → no refresh attempted
    mock_conn.token_expires_at = now + timedelta(hours=1)
    mock_conn.organization_id = org_id

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conn
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()

    mock_events_resp = MagicMock()
    mock_events_resp.raise_for_status = MagicMock()
    mock_events_resp.json = MagicMock(return_value={"items": []})

    mock_http_client = AsyncMock()
    mock_http_client.get = AsyncMock(return_value=mock_events_resp)
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.tasks.calendar_sync._make_engine", return_value=_make_mock_engine()), \
         patch("app.tasks.calendar_sync.async_sessionmaker") as mock_sm, \
         patch("app.tasks.calendar_sync.decrypt_value", return_value="access_token"), \
         patch("app.tasks.calendar_sync.httpx.AsyncClient", return_value=mock_http_client):

        mock_sm.return_value.return_value.__aenter__ = AsyncMock(return_value=mock_db)
        mock_sm.return_value.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await _run_sync(str(conn_id), str(org_id))

    assert result["status"] == "ok"
    assert "new_events" in result
    assert "total_fetched" in result
    assert result["total_fetched"] == 0
    assert result["connection_id"] == str(conn_id)
