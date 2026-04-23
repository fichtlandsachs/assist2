# app/services/crawl/extraction_service.py
"""Clean content extraction from documentation HTML pages."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    ".help-content",
    ".content",
    "#content",
    "#main-content",
]
EXCLUDE_SELECTORS = [
    "header",
    "footer",
    "nav",
    ".cookie-banner",
    ".search-widget",
    ".related-links",
    ".feedback-section",
    '[role="navigation"]',
    '[role="search"]',
]


@dataclass
class ExtractedPage:
    canonical_url: str
    title: str
    main_heading: str
    breadcrumb: list[str]
    headings: list[tuple[int, str]]
    plain_text: str
    structured_sections: list[dict]
    language: str
    extraction_quality_score: float
    fetch_method: str


class ExtractionService:
    def __init__(
        self,
        content_selectors: list[str] = CONTENT_SELECTORS,
        exclude_selectors: list[str] = EXCLUDE_SELECTORS,
        min_content_length: int = 100,
    ) -> None:
        self.content_selectors = content_selectors if content_selectors else CONTENT_SELECTORS
        self.exclude_selectors = exclude_selectors if exclude_selectors else EXCLUDE_SELECTORS
        self.min_content_length = min_content_length

    def extract(self, html: str, canonical_url: str, fetch_method: str) -> ExtractedPage:
        soup = BeautifulSoup(html, "lxml")

        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"].strip()

        lang_tag = soup.find("html", lang=True)
        lang = lang_tag.get("lang", "en") if lang_tag else "en"

        breadcrumb = self._extract_breadcrumb(soup)

        for sel in self.exclude_selectors:
            for el in soup.select(sel):
                el.decompose()

        content_el = self._find_content(soup)
        if not content_el:
            logger.warning("No main content found for %s", canonical_url)
            content_el = soup.body or soup

        headings: list[tuple[int, str]] = []
        main_heading = ""
        for level in range(1, 5):
            for h in content_el.find_all(f"h{level}"):
                text = h.get_text(" ", strip=True)
                if text:
                    headings.append((level, text))
                    if level == 1 and not main_heading:
                        main_heading = text

        sections = self._extract_sections(content_el)

        plain_text = content_el.get_text(" ", strip=True)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        quality_score = self._compute_quality(plain_text, headings, sections)

        return ExtractedPage(
            canonical_url=canonical_url,
            title=title or main_heading or canonical_url,
            main_heading=main_heading,
            breadcrumb=breadcrumb,
            headings=headings,
            plain_text=plain_text,
            structured_sections=sections,
            language=lang,
            extraction_quality_score=quality_score,
            fetch_method=fetch_method,
        )

    def _find_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        for sel in self.content_selectors:
            el = soup.select_one(sel)
            if el and len(el.get_text(strip=True)) >= self.min_content_length:
                return el
        return None

    def _extract_breadcrumb(self, soup: BeautifulSoup) -> list[str]:
        crumbs: list[str] = []
        for item in soup.select('[itemtype*="BreadcrumbList"] [itemprop="name"]'):
            text = item.get_text(strip=True)
            if text:
                crumbs.append(text)
        if crumbs:
            return crumbs
        nav = soup.find("nav", {"aria-label": lambda x: x and "breadcrumb" in x.lower()})
        if nav:
            for a in nav.find_all(["a", "span", "li"]):
                text = a.get_text(strip=True)
                if text and text not in crumbs:
                    crumbs.append(text)
        return crumbs

    def _extract_sections(self, content: Tag) -> list[dict]:
        sections: list[dict] = []
        current: dict = {"heading": "", "level": 0, "body": []}

        for child in content.children:
            if not hasattr(child, "name") or not child.name:
                continue
            if child.name in ("h1", "h2", "h3", "h4"):
                if current["body"] or current["heading"]:
                    sections.append({
                        "heading": current["heading"],
                        "level": current["level"],
                        "body_text": " ".join(current["body"]).strip(),
                    })
                current = {
                    "heading": child.get_text(" ", strip=True),
                    "level": int(child.name[1]),
                    "body": [],
                }
            elif child.name in ("p", "ul", "ol", "table", "pre", "blockquote", "dl"):
                text = child.get_text(" ", strip=True)
                if text:
                    current["body"].append(text)

        if current["body"] or current["heading"]:
            sections.append({
                "heading": current["heading"],
                "level": current["level"],
                "body_text": " ".join(current["body"]).strip(),
            })

        return sections

    def _compute_quality(
        self,
        plain_text: str,
        headings: list[tuple[int, str]],
        sections: list[dict],
    ) -> float:
        score = 0.0
        if len(plain_text) >= 500:
            score += 0.4
        elif len(plain_text) >= 200:
            score += 0.2
        if headings:
            score += 0.2
        if sections:
            score += 0.2
        if len(plain_text) >= 1000:
            score += 0.2
        return min(1.0, score)
