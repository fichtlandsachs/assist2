# app/services/crawl/discovery_service.py
"""URL discovery via sitemap.xml and HTML link following."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from typing import Optional

import httpx

from app.services.crawl.url_canonicalizer import UrlCanonicalizer

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "heyKarl-DocBot/1.0 (compatible; +https://heykarl.de/bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class DiscoveryService:
    def __init__(
        self,
        canonicalizer: UrlCanonicalizer,
        seed_urls: list[str],
        allowed_prefixes: list[str],
        crawl_delay: float = 1.0,
        max_pages: int = 10_000,
    ) -> None:
        self.canonicalizer = canonicalizer
        self.seed_urls = seed_urls
        self.allowed_prefixes = allowed_prefixes
        self.crawl_delay = crawl_delay
        self.max_pages = max_pages

    async def discover_all(self) -> list[str]:
        """Return sorted list of unique canonical URLs to ingest."""
        discovered: set[str] = set()

        async with httpx.AsyncClient(
            headers=_HEADERS,
            timeout=30,
            follow_redirects=True,
        ) as client:
            sitemap_urls = await self._find_sitemaps(client)
            if sitemap_urls:
                for sitemap_url in sitemap_urls:
                    await self._parse_sitemap(client, sitemap_url, discovered)

            crawl_queue = list(self.seed_urls)
            visited_raw: set[str] = set()
            while crawl_queue and len(discovered) < self.max_pages:
                url = crawl_queue.pop(0)
                if url in visited_raw:
                    continue
                visited_raw.add(url)

                in_scope, canon = self.canonicalizer.is_in_scope(url)
                if not in_scope or not canon:
                    continue
                if canon in discovered:
                    continue

                discovered.add(canon)
                logger.debug("Discovered: %s", canon)

                try:
                    await asyncio.sleep(self.crawl_delay)
                    resp = await client.get(url, timeout=20)
                    if resp.status_code != 200:
                        continue
                    ct = resp.headers.get("content-type", "")
                    if "text/html" not in ct:
                        continue
                    links = self._extract_links(resp.text, url)
                    for link in links:
                        if link not in visited_raw:
                            in_s, _ = self.canonicalizer.is_in_scope(link)
                            if in_s:
                                crawl_queue.append(link)
                except Exception as exc:
                    logger.warning("Discovery error for %s: %s", url, exc)

        return sorted(discovered)

    async def _find_sitemaps(self, client: httpx.AsyncClient) -> list[str]:
        sitemaps: list[str] = []
        for seed in self.seed_urls:
            parsed = urlparse(seed)
            base = f"{parsed.scheme}://{parsed.netloc}"
            try:
                resp = await client.get(f"{base}/robots.txt", timeout=10)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        if line.lower().startswith("sitemap:"):
                            sm_url = line.split(":", 1)[1].strip()
                            sitemaps.append(sm_url)
            except Exception:
                pass
            for path in ["/sitemap.xml", "/sitemap_index.xml"]:
                try:
                    resp = await client.get(f"{base}{path}", timeout=10)
                    if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                        sitemaps.append(f"{base}{path}")
                except Exception:
                    pass
        return list(dict.fromkeys(sitemaps))

    async def _parse_sitemap(
        self,
        client: httpx.AsyncClient,
        sitemap_url: str,
        discovered: set[str],
    ) -> None:
        try:
            resp = await client.get(sitemap_url, timeout=20)
            if resp.status_code != 200:
                return
            root = ET.fromstring(resp.text)
            tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

            if tag == "sitemapindex":
                for loc_el in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    child_url = loc_el.text.strip() if loc_el.text else ""
                    if child_url:
                        await asyncio.sleep(0.5)
                        await self._parse_sitemap(client, child_url, discovered)
            else:
                for loc_el in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    raw = loc_el.text.strip() if loc_el.text else ""
                    if raw:
                        in_scope, canon = self.canonicalizer.is_in_scope(raw)
                        if in_scope and canon:
                            discovered.add(canon)
        except Exception as exc:
            logger.warning("Sitemap parse error %s: %s", sitemap_url, exc)

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute = urljoin(base_url, href)
            absolute = absolute.split("#")[0]
            links.append(absolute)
        return links
