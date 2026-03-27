"""Unit tests for POST /api/v1/ai/transcribe — whisper proxied, mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile


def make_whisper_response(status_code: int, text: str = "Hallo Welt") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value={"text": text})
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_transcribe_success():
    """Whisper responds 200 → endpoint returns {text: '...'}."""
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake-audio-bytes")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_whisper_response(200, "Hallo Welt")
        )
        result = await transcribe(file=mock_file, current_user=mock_user)

    assert result == {"text": "Hallo Welt"}


@pytest.mark.asyncio
async def test_transcribe_whisper_down():
    """Whisper not reachable → ConnectError → 503 HTTPException."""
    import httpx
    from fastapi import HTTPException
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"audio")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(HTTPException) as exc_info:
            await transcribe(file=mock_file, current_user=mock_user)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_transcribe_whisper_error_status():
    """Whisper returns 500 → raise_for_status raises → 503 HTTPException."""
    from fastapi import HTTPException
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"audio")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_whisper_response(500)
        )
        with pytest.raises(HTTPException) as exc_info:
            await transcribe(file=mock_file, current_user=mock_user)

    assert exc_info.value.status_code == 503
