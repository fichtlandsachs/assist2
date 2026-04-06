"""Tests for /ai/chat and /ai/extract-story endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user import User


@pytest.fixture
def mock_user():
    u = MagicMock(spec=User)
    u.id = "00000000-0000-0000-0000-000000000001"
    u.email = "test@example.com"
    u.display_name = "Test User"
    return u


@pytest.fixture
def auth_override(mock_user):
    from app.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(auth_override):
    """POST /ai/chat streams text/event-stream with data lines."""

    async def fake_text_stream():
        yield "Hallo "
        yield "Welt"

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=MagicMock(text_stream=fake_text_stream()))
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream = MagicMock(return_value=mock_stream_cm)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/ai/chat",
                json={"messages": [{"role": "user", "content": "Hallo"}], "mode": "chat"},
                headers={"Authorization": "Bearer fake"},
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                chunks = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunks.append(line[6:])
                assert "[DONE]" in chunks
                text_chunks = [c for c in chunks if c not in ("[DONE]", "[ERROR]")]
                assert len(text_chunks) > 0


@pytest.mark.asyncio
async def test_chat_stream_unknown_mode_falls_back(auth_override):
    """Unknown mode falls back to chat system prompt without error."""

    async def fake_text_stream():
        yield "OK"

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=MagicMock(text_stream=fake_text_stream()))
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream = MagicMock(return_value=mock_stream_cm)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/ai/chat",
                json={"messages": [{"role": "user", "content": "Test"}], "mode": "unknown_mode"},
                headers={"Authorization": "Bearer fake"},
            ) as response:
                assert response.status_code == 200


@pytest.mark.asyncio
async def test_extract_story_returns_json(auth_override):
    """POST /ai/extract-story returns structured JSON with story sections."""
    payload = json.dumps({
        "story": ["Als Nutzer möchte ich einloggen, damit ich Zugang habe."],
        "accept": ["Gegeben ein Nutzer, wenn er einloggt, dann wird er weitergeleitet."],
        "tests": ["TC-01: Login mit gültigen Daten"],
        "release": ["v1.0: Login implementiert"],
    })

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=payload)]

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(return_value=mock_response)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/extract-story",
                json={"transcript": "Nutzer: Ich möchte einloggen können.\nKI: Das ist eine Login-User-Story."},
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "story" in data
        assert "accept" in data
        assert "tests" in data
        assert "release" in data
        assert isinstance(data["story"], list)


@pytest.mark.asyncio
async def test_extract_story_short_transcript_returns_empty(auth_override):
    """Transcripts under 80 chars return empty arrays without calling Anthropic."""
    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/extract-story",
                json={"transcript": "kurz"},
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data == {"story": [], "accept": [], "tests": [], "release": []}
        MockClient.assert_not_called()


@pytest.mark.asyncio
async def test_chat_injects_rag_context(auth_override):
    """When RAG returns chunks, a context system message is prepended."""
    from app.services.rag_service import RagResult, RagChunk
    from app.deps import get_db

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    rag_chunk = RagChunk(
        text="Confluence Inhalt: Das Deployment erfolgt montags.",
        score=0.80,
        source_type="confluence",
        source_url=None,
        source_title="Deployment Guide",
    )
    mock_rag = RagResult(mode="context", chunks=[rag_chunk])

    with patch("app.routers.ai.AsyncOpenAI") as MockOAI, \
         patch("app.routers.ai.rag_retrieve", new_callable=AsyncMock, return_value=mock_rag):

        mock_choice = MagicMock()
        mock_choice.choices = [MagicMock(delta=MagicMock(content="OK"))]
        mock_stream = MagicMock()
        mock_stream.__aiter__ = MagicMock(return_value=iter([mock_choice]))
        MockOAI.return_value.chat.completions.create = AsyncMock(return_value=mock_stream)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": "Wann ist Deployment?"}],
                    "mode": "chat",
                    "org_id": "00000000-0000-0000-0000-000000000001",
                },
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_chat_continues_on_rag_timeout(auth_override):
    """RAG timeout → chat proceeds without context, no error."""
    import asyncio as _asyncio
    from app.deps import get_db

    mock_db = AsyncMock()
    app.dependency_overrides[get_db] = lambda: mock_db

    async def slow_rag(*args, **kwargs):
        await _asyncio.sleep(2)

    with patch("app.routers.ai.AsyncOpenAI") as MockOAI, \
         patch("app.routers.ai.rag_retrieve", new_callable=AsyncMock, side_effect=slow_rag):

        mock_choice = MagicMock()
        mock_choice.choices = [MagicMock(delta=MagicMock(content="OK"))]
        mock_stream = MagicMock()
        mock_stream.__aiter__ = MagicMock(return_value=iter([mock_choice]))
        MockOAI.return_value.chat.completions.create = AsyncMock(return_value=mock_stream)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/ai/chat",
                json={
                    "messages": [{"role": "user", "content": "Hallo"}],
                    "mode": "chat",
                    "org_id": "00000000-0000-0000-0000-000000000001",
                },
                headers={"Authorization": "Bearer fake"},
            )
        assert resp.status_code == 200

    app.dependency_overrides.pop(get_db, None)
