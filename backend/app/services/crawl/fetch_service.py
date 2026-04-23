# app/services/crawl/fetch_service.py
"""HTTP fetch with retry/backoff and optional rendered fallback."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

THIN_CONTENT_THRESHOLD = 200

_HEADERS = {
    "User-Agent": "heyKarl-DocBot/1.0 (compatible; +https://heykarl.de/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class FetchResult:
    url: str
    canonical_url: str
    http_status: int
    content_type: str
    html: str
    fetch_method: str
    fetched_at: datetime
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_hash: str = ""
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if self.html and not self.content_hash:
            self.content_hash = hashlib.sha256(self.html.encode()).hexdigest()


class FetchService:
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        delay_between_requests: float = 1.0,
        thin_threshold: int = THIN_CONTENT_THRESHOLD,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.delay = delay_between_requests
        self.thin_threshold = thin_threshold

    async def fetch(
        self,
        url: str,
        canonical_url: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        allow_rendered: bool = True,
    ) -> FetchResult:
        result = await self._http_fetch(url, canonical_url, etag, last_modified)
        if result.error:
            return result
        if allow_rendered and self._is_thin(result.html):
            logger.info("Thin content for %s, trying rendered fetch", url)
            rendered = await self._rendered_fetch(url, canonical_url)
            if rendered and not rendered.error:
                return rendered
        return result

    async def _http_fetch(
        self,
        url: str,
        canonical_url: str,
        etag: Optional[str],
        last_modified: Optional[str],
    ) -> FetchResult:
        headers = dict(_HEADERS)
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

        for attempt in range(self.max_retries):
            try:
                await asyncio.sleep(self.delay if attempt == 0 else 2 ** attempt)
                async with httpx.AsyncClient(
                    headers=headers, timeout=self.timeout, follow_redirects=True
                ) as client:
                    resp = await client.get(url)
                    fetched_at = datetime.now(timezone.utc)

                if resp.status_code == 304:
                    return FetchResult(
                        url=url, canonical_url=canonical_url,
                        http_status=304, content_type="", html="",
                        fetch_method="http", fetched_at=fetched_at,
                        etag=resp.headers.get("etag"),
                        last_modified=resp.headers.get("last-modified"),
                        content_hash="",
                    )

                if resp.status_code >= 400:
                    return FetchResult(
                        url=url, canonical_url=canonical_url,
                        http_status=resp.status_code, content_type="",
                        html="", fetch_method="http", fetched_at=fetched_at,
                        error=f"HTTP {resp.status_code}",
                    )

                return FetchResult(
                    url=url, canonical_url=canonical_url,
                    http_status=resp.status_code,
                    content_type=resp.headers.get("content-type", ""),
                    html=resp.text,
                    fetch_method="http",
                    fetched_at=fetched_at,
                    etag=resp.headers.get("etag"),
                    last_modified=resp.headers.get("last-modified"),
                )
            except httpx.TimeoutException:
                logger.warning("Timeout fetching %s (attempt %d)", url, attempt + 1)
            except Exception as exc:
                logger.warning("Fetch error %s (attempt %d): %s", url, attempt + 1, exc)

        return FetchResult(
            url=url, canonical_url=canonical_url,
            http_status=0, content_type="", html="",
            fetch_method="http", fetched_at=datetime.now(timezone.utc),
            error="Max retries exceeded",
        )

    async def _rendered_fetch(self, url: str, canonical_url: str) -> Optional[FetchResult]:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
                try:
                    page = await browser.new_page()
                    await page.set_extra_http_headers({"User-Agent": _HEADERS["User-Agent"]})
                    await page.goto(url, timeout=60000, wait_until="networkidle")
                    html = await page.content()
                    fetched_at = datetime.now(timezone.utc)
                finally:
                    await browser.close()
            return FetchResult(
                url=url, canonical_url=canonical_url,
                http_status=200, content_type="text/html",
                html=html, fetch_method="rendered",
                fetched_at=fetched_at,
            )
        except ImportError:
            logger.warning("playwright not installed; skipping rendered fetch")
            return None
        except Exception as exc:
            logger.warning("Rendered fetch failed for %s: %s", url, exc)
            return None

    def _is_thin(self, html: str) -> bool:
        if not html:
            return True
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            return len(text) < self.thin_threshold
        except Exception:
            return len(html) < self.thin_threshold * 5
