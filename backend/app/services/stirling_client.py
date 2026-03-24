"""HTTP client for Stirling PDF REST API."""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class StirlingPDFClient:
    """Wraps Stirling PDF REST API calls."""

    def __init__(self) -> None:
        self._base_url = get_settings().STIRLING_PDF_URL

    async def html_to_pdf(self, html: str) -> bytes:
        """
        Convert an HTML string to PDF.
        POST /api/v1/misc/html-to-pdf (multipart: fileInput = HTML file)
        Returns raw PDF bytes.
        """
        url = f"{self._base_url}/api/v1/misc/html-to-pdf"
        html_bytes = html.encode("utf-8")
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    url,
                    files={"fileInput": ("input.html", html_bytes, "text/html")},
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as e:
                logger.error(f"Stirling PDF html_to_pdf failed: {e.response.status_code} {e.response.text[:200]}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Stirling PDF html_to_pdf connection error: {e}")
                raise

    async def overlay_pdfs(self, base_pdf: bytes, overlay_pdf: bytes) -> bytes:
        """
        Overlay two PDFs (e.g., apply a letterhead over the generated PDF).
        POST /api/v1/general/overlay-pdfs
        Returns merged PDF bytes.
        """
        url = f"{self._base_url}/api/v1/general/overlay-pdfs"
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    url,
                    files={
                        "fileInput": ("base.pdf", base_pdf, "application/pdf"),
                        "fileInput2": ("overlay.pdf", overlay_pdf, "application/pdf"),
                    },
                )
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as e:
                logger.error(f"Stirling PDF overlay_pdfs failed: {e.response.status_code} {e.response.text[:200]}")
                raise
            except httpx.RequestError as e:
                logger.error(f"Stirling PDF overlay_pdfs connection error: {e}")
                raise


stirling_client = StirlingPDFClient()
