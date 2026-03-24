"""Unit tests for StirlingPDFClient — all httpx calls are mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_mock_response(status_code: int, content: bytes = b"%PDF-fake") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_html_to_pdf_success():
    """html_to_pdf returns PDF bytes on success."""
    from app.services.stirling_client import StirlingPDFClient
    client = StirlingPDFClient()
    html = "<html><body><h1>Test</h1></body></html>"

    with patch("app.services.stirling_client.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(200, b"%PDF-1.4 fake-pdf-bytes")
        )
        result = await client.html_to_pdf(html)

    assert result == b"%PDF-1.4 fake-pdf-bytes"


@pytest.mark.asyncio
async def test_html_to_pdf_raises_on_error():
    """html_to_pdf raises HTTPStatusError on non-200 response."""
    from app.services.stirling_client import StirlingPDFClient
    import httpx
    client = StirlingPDFClient()

    with patch("app.services.stirling_client.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(500)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.html_to_pdf("<html></html>")


@pytest.mark.asyncio
async def test_overlay_pdfs_success():
    """overlay_pdfs returns merged PDF bytes."""
    from app.services.stirling_client import StirlingPDFClient
    client = StirlingPDFClient()

    with patch("app.services.stirling_client.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(200, b"%PDF-merged")
        )
        result = await client.overlay_pdfs(b"%PDF-content", b"%PDF-letterhead")

    assert result == b"%PDF-merged"


@pytest.mark.asyncio
async def test_overlay_pdfs_raises_on_error():
    """overlay_pdfs raises HTTPStatusError on non-200 response."""
    from app.services.stirling_client import StirlingPDFClient
    import httpx
    client = StirlingPDFClient()

    with patch("app.services.stirling_client.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(500)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.overlay_pdfs(b"%PDF-base", b"%PDF-overlay")
