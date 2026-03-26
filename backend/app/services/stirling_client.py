"""HTTP client for Stirling PDF REST API."""
import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class StirlingPDFClient:
    """Wraps Stirling PDF REST API calls."""

    def __init__(self) -> None:
        cfg = get_settings()
        self._base_url = cfg.STIRLING_PDF_URL
        self._auth = (cfg.STIRLING_PDF_USERNAME, cfg.STIRLING_PDF_PASSWORD) if cfg.STIRLING_PDF_PASSWORD else None

    async def html_to_pdf(self, html: str) -> bytes:
        """
        Convert an HTML string to PDF.
        POST /api/v1/misc/html-to-pdf (multipart: fileInput = HTML file)
        Returns raw PDF bytes.
        """
        url = f"{self._base_url}/api/v1/convert/html/pdf"
        html_bytes = html.encode("utf-8")
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    url,
                    files={"fileInput": ("input.html", html_bytes, "text/html")},
                    auth=self._auth,
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
                    auth=self._auth,
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
