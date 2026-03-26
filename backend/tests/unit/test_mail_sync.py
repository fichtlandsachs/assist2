# backend/tests/unit/test_mail_sync.py
"""Unit tests for mail_sync task internals."""
import email
import email.header
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
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

def _make_mock_engine():
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    return mock_engine


@pytest.mark.asyncio
async def test_run_sync_connection_not_found():
    from app.tasks.mail_sync import _run_sync

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    with patch("app.tasks.mail_sync._make_engine", return_value=_make_mock_engine()), \
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

    with patch("app.tasks.mail_sync._make_engine", return_value=_make_mock_engine()), \
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

    with patch("app.tasks.mail_sync._make_engine", return_value=_make_mock_engine()), \
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
