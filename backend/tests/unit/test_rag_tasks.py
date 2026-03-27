"""Unit tests for rag_tasks.index_org_documents — all IO mocked."""
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid


@pytest.mark.asyncio
async def test_index_skips_unchanged_file():
    """File with same SHA256 hash already in DB → skip embedding call."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"
    pdf_bytes = b"pdf-bytes"
    real_hash = hashlib.sha256(pdf_bytes).hexdigest()

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=real_hash)

    prefix = f"/remote.php/dav/files/admin/Organizations/{org_slug}/"
    file_list = [{"href": f"{prefix}doc.pdf", "content_type": "application/pdf"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = pdf_bytes

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


@pytest.mark.asyncio
async def test_index_skips_on_download_failure():
    """Download failure for one file → skip it, continue processing others."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"
    prefix = f"/remote.php/dav/files/admin/Organizations/{org_slug}/"

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

    file_list = [
        {"href": f"{prefix}broken.pdf", "content_type": "application/pdf"},
        {"href": f"{prefix}good.txt", "content_type": "text/plain"},
    ]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._extract_text", return_value="text"), \
         patch("app.tasks.rag_tasks._chunk_text", return_value=["chunk"]), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.side_effect = [Exception("connection refused"), b"good-bytes"]
        mock_embed.return_value = [[0.1] * 1536]

        await _index_org_documents_async(org_id, org_slug, mock_db)

    # embed called once for the good file
    mock_embed.assert_called_once()


@pytest.mark.asyncio
async def test_index_deletes_old_chunks_before_insert():
    """Changed file → old chunks deleted, new chunks inserted and committed."""
    from app.tasks.rag_tasks import _index_org_documents_async

    org_id = str(uuid.uuid4())
    org_slug = "test-org"
    href = f"/remote.php/dav/files/admin/Organizations/{org_slug}/doc.txt"

    mock_db = AsyncMock()
    # Return a different hash → file has changed
    mock_db.execute = AsyncMock()
    mock_db.execute.return_value.scalar_one_or_none = MagicMock(return_value="oldhash")

    file_list = [{"href": href, "content_type": "text/plain"}]

    with patch("app.tasks.rag_tasks._list_org_files", new_callable=AsyncMock) as mock_list, \
         patch("app.tasks.rag_tasks._download_file", new_callable=AsyncMock) as mock_dl, \
         patch("app.tasks.rag_tasks._sha256", return_value="newhash"), \
         patch("app.tasks.rag_tasks._extract_text", return_value="new content"), \
         patch("app.tasks.rag_tasks._chunk_text", return_value=["new chunk"]), \
         patch("app.tasks.rag_tasks._embed_chunks", new_callable=AsyncMock) as mock_embed:

        mock_list.return_value = file_list
        mock_dl.return_value = b"new-bytes"
        mock_embed.return_value = [[0.5] * 1536]

        await _index_org_documents_async(org_id, org_slug, mock_db)

    # Verify the delete statement was executed (second execute call, after SELECT)
    assert mock_db.execute.call_count >= 2  # SELECT + DELETE
    mock_db.commit.assert_called_once()
    # Verify db.add was called for new chunks
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_embed_chunks_batches_single_call():
    """_embed_chunks sends all chunks in one API call, not N sequential calls."""
    from app.tasks.rag_tasks import _embed_chunks

    chunks = ["chunk one", "chunk two", "chunk three"]
    fake_response = {
        "data": [
            {"index": 0, "embedding": [0.1] * 1536},
            {"index": 1, "embedding": [0.2] * 1536},
            {"index": 2, "embedding": [0.3] * 1536},
        ]
    }

    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_response
    mock_resp.raise_for_status = MagicMock()

    with patch("app.tasks.rag_tasks.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_resp
        )
        result = await _embed_chunks(chunks)

    # Only one HTTP call made
    post_call = mock_http.return_value.__aenter__.return_value.post
    assert post_call.call_count == 1
    # Input was the full list
    call_json = post_call.call_args.kwargs["json"]
    assert call_json["input"] == chunks
    assert len(result) == 3
