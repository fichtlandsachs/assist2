"""Unit tests for rag_tasks.index_org_documents — all IO mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.mark.asyncio
async def test_index_skips_unchanged_file():
    """File with same SHA256 hash already in DB → skip embedding call."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()
    # Simulate existing hash match
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value="abc123")

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/doc.pdf",
                  "content_type": "application/pdf"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._sha256", return_value="abc123"), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = b"pdf-bytes"

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_index_processes_new_pdf():
    """New PDF (hash mismatch) → text extracted, chunks embedded, stored."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()
    # No existing hash → file is new
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/doc.pdf",
                  "content_type": "application/pdf"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._sha256", return_value="newhash"), \
         patch("app.tasks.rag_tasks._extract_text", return_value="Dokument Inhalt"), \
         patch("app.tasks.rag_tasks._chunk_text", return_value=["Chunk 1", "Chunk 2"]), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = b"pdf-bytes"
        mock_embed.return_value = [[0.1] * 1536, [0.2] * 1536]

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_called_once_with(["Chunk 1", "Chunk 2"])
    assert mock_db.add.called  # DocumentChunk rows added


@pytest.mark.asyncio
async def test_index_skips_unsupported_filetype():
    """File with unsupported extension (e.g. .xlsx) → skip without error."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"

    mock_db = AsyncMock()

    file_list = [{"href": f"/remote.php/dav/files/admin/Organizations/{org_slug}/data.xlsx",
                  "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list

        await _index_org_documents_async(org_id, org_slug, mock_db)

    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_chunk_text_splits_correctly():
    """_chunk_text splits text into chunks with overlap."""
    from app.tasks.rag_tasks import _chunk_text

    # ~600 words → should produce 2 chunks (CHUNK_SIZE=2000 chars, each word ~6 chars)
    word = "lorem "
    text = word * 600  # ~3600 chars
    chunks = _chunk_text(text)

    assert len(chunks) >= 2
    assert all(len(c) > 0 for c in chunks)
