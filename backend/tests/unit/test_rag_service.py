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
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "direct"
    assert result.context == "Direktantwort Text"
    assert len(result.chunks) == 1
    assert result.chunks[0].text == "Direktantwort Text"


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
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "context"
    assert len(result.chunks) == 2
    assert result.context is None


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
        mock_embed.return_value = [0.1] * 1024
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
        mock_embed.return_value = [0.1] * 1024
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
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_direct_mode_at_boundary():
    """Score exactly 0.92 → mode='direct' (boundary is inclusive)."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Grenzwert Text", 0.92)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "direct"
    assert result.context == "Grenzwert Text"


@pytest.mark.asyncio
async def test_retrieve_context_mode_at_boundary():
    """Score exactly 0.50 → mode='context' (boundary is inclusive)."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Kontext Text", 0.50)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "context"
    assert len(result.chunks) == 1


@pytest.mark.asyncio
async def test_retrieve_none_just_below_context_threshold():
    """Score just below 0.50 → mode='none'."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[make_db_row("Irrelevant", 0.499)]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "none"


@pytest.mark.asyncio
async def test_retrieve_context_truncates_to_max_chunks():
    """5 qualifying context-range rows → only MAX_CHUNKS (3) returned."""
    from app.services.rag_service import retrieve

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.fetchall = MagicMock(
        return_value=[
            make_db_row("Chunk 1", 0.80),
            make_db_row("Chunk 2", 0.75),
            make_db_row("Chunk 3", 0.70),
            make_db_row("Chunk 4", 0.65),
            make_db_row("Chunk 5", 0.60),
        ]
    )

    with patch("app.services.rag_service._embed_query", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = [0.1] * 1024
        result = await retrieve("test query", uuid.uuid4(), mock_db)

    assert result.mode == "context"
    assert len(result.chunks) == 3
