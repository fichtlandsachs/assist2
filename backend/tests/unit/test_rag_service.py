"""Unit tests for rag_service.retrieve — LiteLLM and DB mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


def make_db_row(chunk_text: str, score: float) -> MagicMock:
    row = MagicMock()
    row.chunk_text = chunk_text
    row.score = score
    return row


@pytest.mark.asyncio
async def test_retrieve_direct_mode():
    """Score >= 0.92 → mode='direct', direct_answer set."""
    from app.services.rag_service import retrieve, RagResult

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Direktantwort Text", 0.95)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "direct"
    assert result.direct_answer == "Direktantwort Text"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_context_mode():
    """Score 0.50-0.92 → mode='context', chunks filled."""
    from app.services.rag_service import retrieve, RagResult

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[
            make_db_row("Chunk 1", 0.75),
            make_db_row("Chunk 2", 0.60),
        ]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "context"
    assert len(result.chunks) == 2
    assert result.direct_answer is None


@pytest.mark.asyncio
async def test_retrieve_none_mode():
    """Score < 0.50 → mode='none'."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Irrelevant", 0.30)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"
    assert result.chunks == []


@pytest.mark.asyncio
async def test_retrieve_empty_db():
    """No chunks in DB → mode='none'."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(return_value=[])

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_litellm_error_fallback():
    """LiteLLM not reachable → returns mode='none', no exception raised."""
    import httpx
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.side_effect = httpx.ConnectError("LiteLLM down")
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_db_error_fallback():
    """DB error → returns mode='none', no exception raised."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("DB failure"))

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1536
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"
