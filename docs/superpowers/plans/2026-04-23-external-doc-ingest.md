# External Documentation Ingest Worker – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Production-grade SAP S/4HANA Utilities documentation ingest worker — crawl, extract, chunk, embed, and index into the shared RAG knowledge base.

**Architecture:**
- New DB tables: `external_sources`, `external_source_runs`, `external_source_pages` (crawl management layer)
- Reuse existing `document_chunks` + pgvector for final embedded chunks
- Add `is_global: bool` to `document_chunks` for shared/org-agnostic visibility
- Add `source_type = "external_docs"` to SourceType enum
- Celery task orchestrates full runs; admin API via `/api/v1/superadmin/knowledge-sources/external`
- Modular services: canonicalizer → discovery → fetch → extract → chunk → embed

**Tech Stack:** FastAPI, Celery + Redis, SQLAlchemy async, pgvector, httpx, BeautifulSoup4, Playwright (headless fallback), LiteLLM (ionos-embed, 1024-dim).

---

### Task 1: Migration 0062 — DB schema

**Files:**
- Create: `backend/migrations/versions/0062_external_sources.py`

- [ ] **Step 1: Write migration**

```python
"""external source ingest tables + is_global on document_chunks

Revision ID: 0062
Revises: 0061
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add is_global to document_chunks (shared/global visibility)
    op.add_column(
        "document_chunks",
        sa.Column("is_global", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_document_chunks_is_global", "document_chunks", ["is_global"])

    # 2. external_sources
    op.create_table(
        "external_sources",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_key", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False, server_default="external_docs"),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("config_json", JSONB(), nullable=False, server_default="'{}'::jsonb"),
        sa.Column("visibility_scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_external_sources_source_key", "external_sources", ["source_key"])
    op.create_index("ix_external_sources_enabled", "external_sources", ["is_enabled"])

    # 3. external_source_runs
    op.create_table(
        "external_source_runs",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("run_type", sa.String(20), nullable=False),  # initial, refresh, retry
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),  # pending, running, completed, failed, cancelled
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stats_json", JSONB(), nullable=False, server_default="'{}'::jsonb"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_external_source_runs_status", "external_source_runs", ["status"])

    # 4. external_source_pages
    op.create_table(
        "external_source_pages",
        sa.Column("id", PGUUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", PGUUID(as_uuid=True), sa.ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("raw_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # pending, fetched, extracted, chunked, embedded, failed, skipped
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("fetch_method", sa.String(20), nullable=True),  # http, rendered
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("etag", sa.String(256), nullable=True),
        sa.Column("last_modified", sa.String(128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("metadata_json", JSONB(), nullable=False, server_default="'{}'::jsonb"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_esp_source_canonical",
        "external_source_pages",
        ["source_id", "canonical_url"],
        unique=True,
    )
    op.create_index("ix_esp_status", "external_source_pages", ["status"])
    op.create_index("ix_esp_content_hash", "external_source_pages", ["content_hash"])


def downgrade() -> None:
    op.drop_table("external_source_pages")
    op.drop_table("external_source_runs")
    op.drop_table("external_sources")
    op.drop_index("ix_document_chunks_is_global", table_name="document_chunks")
    op.drop_column("document_chunks", "is_global")
```

- [ ] **Step 2: Run migration**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```

Expected: `Running upgrade 0061 -> 0062`

- [ ] **Step 3: Verify**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec db psql -U assist2 -c "\dt external*"
docker compose -f docker-compose.yml exec db psql -U assist2 -c "\d document_chunks" | grep is_global
```

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2 && git add backend/migrations/versions/0062_external_sources.py
git commit -m "feat: migration 0062 – external sources tables + is_global on document_chunks"
```

---

### Task 2: ORM Models

**Files:**
- Create: `backend/app/models/external_source.py`
- Modify: `backend/app/models/document_chunk.py` (add is_global + external_docs source_type)

- [ ] **Step 1: Update document_chunk.py**

In `backend/app/models/document_chunk.py`, add `external_docs = "external_docs"` to SourceType enum and add `is_global` column to DocumentChunk:

```python
class SourceType(str, enum.Enum):
    nextcloud = "nextcloud"
    karl_story = "karl_story"
    jira = "jira"
    confluence = "confluence"
    user_action = "user_action"
    external_docs = "external_docs"   # ← add this
```

Add to DocumentChunk class after `zone_id`:
```python
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 2: Create external_source.py**

```python
# app/models/external_source.py
"""ORM models for external documentation source management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, SmallInteger,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ExternalSource(Base):
    __tablename__ = "external_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="external_docs")
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    visibility_scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    runs: Mapped[list["ExternalSourceRun"]] = relationship(
        "ExternalSourceRun", back_populates="source", cascade="all, delete-orphan"
    )
    pages: Mapped[list["ExternalSourcePage"]] = relationship(
        "ExternalSourcePage", back_populates="source", cascade="all, delete-orphan"
    )


class ExternalSourceRun(Base):
    __tablename__ = "external_source_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    triggered_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    source: Mapped["ExternalSource"] = relationship("ExternalSource", back_populates="runs")


class ExternalSourcePage(Base):
    __tablename__ = "external_source_pages"
    __table_args__ = (
        UniqueConstraint("source_id", "canonical_url", name="uq_esp_source_canonical"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    discovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    fetch_method: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    etag: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    last_modified: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    source: Mapped["ExternalSource"] = relationship("ExternalSource", back_populates="pages")
```

- [ ] **Step 3: Import models in `__init__.py`**

Add to `backend/app/models/__init__.py`:
```python
from app.models.external_source import ExternalSource, ExternalSourceRun, ExternalSourcePage  # noqa: F401
```

- [ ] **Step 4: Restart backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml restart backend
docker logs assist2-backend --tail 20
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2 && git add backend/app/models/external_source.py backend/app/models/document_chunk.py backend/app/models/__init__.py
git commit -m "feat: ORM models – ExternalSource, ExternalSourceRun, ExternalSourcePage + is_global"
```

---

### Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/external_source.py`

- [ ] **Step 1: Write schemas**

```python
# app/schemas/external_source.py
"""Pydantic v2 schemas for external source management API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, HttpUrl


class CrawlPolicy(BaseModel):
    max_concurrency: int = 3
    request_delay_seconds: float = 1.0
    request_timeout_seconds: int = 30
    max_retries: int = 3
    respect_robots_txt: bool = True
    user_agent: str = "heyKarl-DocBot/1.0 (compatible; +https://heykarl.de/bot)"
    thin_content_threshold: int = 200  # chars; below this → rendered fallback


class ExtractionPolicy(BaseModel):
    content_selectors: list[str] = ["article", "main", ".content", "#content", ".help-content"]
    exclude_selectors: list[str] = ["header", "footer", "nav", ".cookie-banner", ".search-widget"]
    min_content_length: int = 100


class ChunkingPolicy(BaseModel):
    target_chunk_tokens: int = 800
    overlap_tokens: int = 120
    max_chunk_tokens: int = 1200
    heading_split_levels: list[int] = [1, 2, 3]


class EmbeddingPolicy(BaseModel):
    model: str = "ionos-embed"
    batch_size: int = 32
    dimensions: int = 1024


class RefreshPolicy(BaseModel):
    schedule_cron: str = "0 3 * * 0"  # weekly Sunday 03:00 UTC
    use_etag: bool = True
    use_last_modified: bool = True
    force_reindex_on_hash_change: bool = True


class SourceConfig(BaseModel):
    allowed_domains: list[str]
    include_url_prefixes: list[str]
    required_query_params: dict[str, str] = {}
    dropped_query_params: list[str] = []
    seed_urls: list[str] = []
    crawl_policy: CrawlPolicy = CrawlPolicy()
    extraction_policy: ExtractionPolicy = ExtractionPolicy()
    chunking_policy: ChunkingPolicy = ChunkingPolicy()
    embedding_policy: EmbeddingPolicy = EmbeddingPolicy()
    refresh_policy: RefreshPolicy = RefreshPolicy()
    metadata_defaults: dict[str, str] = {}


class ExternalSourceCreate(BaseModel):
    source_key: str
    display_name: str
    base_url: str
    visibility_scope: str = "global"
    config: SourceConfig


class ExternalSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_key: str
    display_name: str
    source_type: str
    base_url: str
    config_json: dict[str, Any]
    visibility_scope: str
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class ExternalSourceRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    run_type: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    stats_json: dict[str, Any]
    error_summary: Optional[str] = None
    triggered_by: Optional[str] = None
    created_at: datetime


class ExternalSourcePageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    raw_url: str
    canonical_url: str
    status: str
    discovered_at: Optional[datetime] = None
    fetched_at: Optional[datetime] = None
    extracted_at: Optional[datetime] = None
    last_changed_at: Optional[datetime] = None
    http_status: Optional[int] = None
    fetch_method: Optional[str] = None
    content_hash: Optional[str] = None
    is_active: bool
    error_detail: Optional[str] = None
    metadata_json: dict[str, Any]


class IngestStartResponse(BaseModel):
    run_id: uuid.UUID
    status: str
    message: str


class PreviewResponse(BaseModel):
    canonical_url: str
    title: str
    breadcrumb: list[str]
    headings: list[str]
    plain_text_preview: str  # first 500 chars
    chunk_count: int
    fetch_method: str
    extraction_quality_score: float
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2 && git add backend/app/schemas/external_source.py
git commit -m "feat: external source Pydantic schemas"
```

---

### Task 4: URL Canonicalizer + Discovery Service

**Files:**
- Create: `backend/app/services/crawl/__init__.py`
- Create: `backend/app/services/crawl/url_canonicalizer.py`
- Create: `backend/app/services/crawl/discovery_service.py`

- [ ] **Step 1: Create package `__init__.py`**

Empty file at `backend/app/services/crawl/__init__.py`.

- [ ] **Step 2: url_canonicalizer.py**

```python
# app/services/crawl/url_canonicalizer.py
"""Deterministic URL normalization and canonicalization."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse


class UrlCanonicalizer:
    def __init__(
        self,
        required_params: dict[str, str],
        dropped_params: set[str],
        allowed_prefixes: list[str],
        allowed_domains: list[str],
    ) -> None:
        self.required_params = required_params
        self.dropped_params = dropped_params
        self.allowed_prefixes = [p.rstrip("/") for p in allowed_prefixes]
        self.allowed_domains = [d.lower() for d in allowed_domains]

    def canonicalize(self, raw_url: str) -> str | None:
        """Return canonical URL or None if URL should be rejected."""
        try:
            parsed = urlparse(raw_url)
        except Exception:
            return None

        # Normalize scheme and host
        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower().split(":")[0]  # strip port

        if scheme not in ("http", "https"):
            return None
        if host not in self.allowed_domains:
            return None

        # Remove fragment
        path = parsed.path.rstrip("/") or "/"

        # Process query params
        qs_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered: dict[str, str] = {}
        for k, v in qs_pairs:
            # Drop unwanted params
            if k in self.dropped_params:
                continue
            # Drop utm_* pattern
            if k.startswith("utm_"):
                continue
            filtered[k] = v

        # Merge required params (override if present, add if missing)
        for k, v in self.required_params.items():
            filtered[k] = v

        # Sort params deterministically
        sorted_qs = urlencode(sorted(filtered.items()))

        canonical = urlunparse((
            "https",  # always https
            host,
            path,
            "",  # params
            sorted_qs,
            "",  # no fragment
        ))
        return canonical

    def is_allowed(self, canonical_url: str) -> bool:
        """Check if canonical URL is within allowed prefixes."""
        return any(canonical_url.startswith(prefix) for prefix in self.allowed_prefixes)

    def is_in_scope(self, raw_url: str) -> tuple[bool, str | None]:
        """Returns (in_scope, canonical_url). canonical_url is None if rejected."""
        canon = self.canonicalize(raw_url)
        if not canon:
            return False, None
        return self.is_allowed(canon), canon
```

- [ ] **Step 3: discovery_service.py**

```python
# app/services/crawl/discovery_service.py
"""URL discovery via sitemap.xml and HTML link following."""
from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse

import httpx

from app.services.crawl.url_canonicalizer import UrlCanonicalizer

logger = logging.getLogger(__name__)

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
_SITEMAP_INDEX_NS = {"si": "http://www.sitemaps.org/schemas/sitemap/0.9"}
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
            # 1. Try sitemap discovery from each seed
            sitemap_urls = await self._find_sitemaps(client)
            if sitemap_urls:
                for sitemap_url in sitemap_urls:
                    await self._parse_sitemap(client, sitemap_url, discovered)

            # 2. HTML crawl starting from seeds (complement or fallback)
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
        """Check robots.txt and common sitemap paths."""
        sitemaps: list[str] = []
        for seed in self.seed_urls:
            parsed = urlparse(seed)
            base = f"{parsed.scheme}://{parsed.netloc}"
            # robots.txt
            try:
                resp = await client.get(f"{base}/robots.txt", timeout=10)
                if resp.status_code == 200:
                    for line in resp.text.splitlines():
                        if line.lower().startswith("sitemap:"):
                            sm_url = line.split(":", 1)[1].strip()
                            sitemaps.append(sm_url)
            except Exception:
                pass
            # common paths
            for path in ["/sitemap.xml", "/sitemap_index.xml"]:
                try:
                    resp = await client.get(f"{base}{path}", timeout=10)
                    if resp.status_code == 200 and "xml" in resp.headers.get("content-type", ""):
                        sitemaps.append(f"{base}{path}")
                except Exception:
                    pass
        return list(dict.fromkeys(sitemaps))  # deduplicate preserving order

    async def _parse_sitemap(
        self,
        client: httpx.AsyncClient,
        sitemap_url: str,
        discovered: set[str],
    ) -> None:
        """Recursively parse sitemap/sitemap index."""
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
                # urlset
                for loc_el in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                    raw = loc_el.text.strip() if loc_el.text else ""
                    if raw:
                        in_scope, canon = self.canonicalizer.is_in_scope(raw)
                        if in_scope and canon:
                            discovered.add(canon)
        except Exception as exc:
            logger.warning("Sitemap parse error %s: %s", sitemap_url, exc)

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract href links from HTML text."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        links: list[str] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            absolute = urljoin(base_url, href)
            # Strip fragment
            absolute = absolute.split("#")[0]
            links.append(absolute)
        return links
```

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/crawl/
git commit -m "feat: URL canonicalizer and discovery service"
```

---

### Task 5: Fetch + Extraction Services

**Files:**
- Create: `backend/app/services/crawl/fetch_service.py`
- Create: `backend/app/services/crawl/extraction_service.py`

- [ ] **Step 1: fetch_service.py**

```python
# app/services/crawl/fetch_service.py
"""HTTP fetch with retry/backoff and optional rendered fallback."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

THIN_CONTENT_THRESHOLD = 200  # chars of body text

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
    fetch_method: str  # "http" or "rendered"
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
        """Fetch URL with retry. Falls back to rendered if content is thin."""
        result = await self._http_fetch(url, canonical_url, etag, last_modified)
        if result.error:
            return result

        if allow_rendered and self._is_thin(result.html):
            logger.info("Thin content detected for %s, escalating to rendered fetch", url)
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
                        content_hash="",  # unchanged
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
        """Headless browser fetch using Playwright."""
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
        """Return True if HTML body text is below threshold."""
        if not html:
            return True
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(" ", strip=True)
            return len(text) < self.thin_threshold
        except Exception:
            return len(html) < self.thin_threshold * 5
```

- [ ] **Step 2: extraction_service.py**

```python
# app/services/crawl/extraction_service.py
"""Clean content extraction from SAP help.sap.com HTML."""
from __future__ import annotations

import logging
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
    ".breadcrumb-nav",  # keep breadcrumb text but not nav structure
]


@dataclass
class ExtractedPage:
    canonical_url: str
    title: str
    main_heading: str
    breadcrumb: list[str]
    headings: list[tuple[int, str]]  # (level, text)
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
        self.content_selectors = content_selectors
        self.exclude_selectors = exclude_selectors
        self.min_content_length = min_content_length

    def extract(self, html: str, canonical_url: str, fetch_method: str) -> ExtractedPage:
        soup = BeautifulSoup(html, "lxml")

        # Title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        # Prefer og:title or first h1
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            title = og["content"].strip()

        # Language
        language = soup.find("html", lang=True)
        lang = language.get("lang", "en") if language else "en"

        # Breadcrumb
        breadcrumb = self._extract_breadcrumb(soup)

        # Remove excluded elements
        for sel in self.exclude_selectors:
            for el in soup.select(sel):
                el.decompose()

        # Find main content
        content_el = self._find_content(soup)

        if not content_el:
            logger.warning("No main content found for %s", canonical_url)
            content_el = soup.body or soup

        # Extract headings
        headings: list[tuple[int, str]] = []
        main_heading = ""
        for level in range(1, 5):
            for h in content_el.find_all(f"h{level}"):
                text = h.get_text(" ", strip=True)
                if text:
                    headings.append((level, text))
                    if level == 1 and not main_heading:
                        main_heading = text

        # Structured sections
        sections = self._extract_sections(content_el)

        # Plain text
        plain_text = content_el.get_text(" ", strip=True)
        # Collapse multiple spaces
        import re
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
        # Try schema.org breadcrumb
        for item in soup.select('[itemtype*="BreadcrumbList"] [itemprop="name"]'):
            text = item.get_text(strip=True)
            if text:
                crumbs.append(text)
        if crumbs:
            return crumbs
        # Try aria-label breadcrumb nav
        nav = soup.find("nav", {"aria-label": lambda x: x and "breadcrumb" in x.lower()})
        if nav:
            for a in nav.find_all(["a", "span", "li"]):
                text = a.get_text(strip=True)
                if text and text not in crumbs:
                    crumbs.append(text)
        return crumbs

    def _extract_sections(self, content: Tag) -> list[dict]:
        """Build a list of {heading, level, body_text} sections."""
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
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/crawl/fetch_service.py backend/app/services/crawl/extraction_service.py
git commit -m "feat: fetch service (HTTP + rendered fallback) and extraction service"
```

---

### Task 6: Chunking + Embedding Index Service

**Files:**
- Create: `backend/app/services/crawl/chunking_service.py`
- Create: `backend/app/services/crawl/embedding_index_service.py`

- [ ] **Step 1: chunking_service.py**

```python
# app/services/crawl/chunking_service.py
"""Structure-aware chunking for extracted documentation pages."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

APPROX_CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    chunk_uid: str
    chunk_index: int
    total_chunks: int
    text: str
    section_path: list[str]
    metadata: dict


class ChunkingService:
    def __init__(
        self,
        target_tokens: int = 800,
        overlap_tokens: int = 120,
        max_tokens: int = 1200,
    ) -> None:
        self.target_chars = target_tokens * APPROX_CHARS_PER_TOKEN
        self.overlap_chars = overlap_tokens * APPROX_CHARS_PER_TOKEN
        self.max_chars = max_tokens * APPROX_CHARS_PER_TOKEN

    def chunk_page(
        self,
        canonical_url: str,
        page_title: str,
        sections: list[dict],
        plain_text: str,
        source_metadata: dict,
    ) -> list[Chunk]:
        """Split page content into structured chunks with metadata."""
        raw_chunks = self._split_sections(sections, plain_text)
        chunks: list[Chunk] = []
        for i, (section_path, text) in enumerate(raw_chunks):
            uid = self._chunk_uid(canonical_url, i, text)
            meta = {
                **source_metadata,
                "canonical_url": canonical_url,
                "page_title": page_title,
                "section_path": " > ".join(section_path) if section_path else page_title,
                "chunk_index": i,
                "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            }
            chunks.append(Chunk(
                chunk_uid=uid,
                chunk_index=i,
                total_chunks=0,  # filled after
                text=text,
                section_path=section_path,
                metadata=meta,
            ))

        total = len(chunks)
        for c in chunks:
            c.total_chunks = total
            c.metadata["total_chunks_for_page"] = total

        return chunks

    def _split_sections(
        self, sections: list[dict], plain_text: str
    ) -> list[tuple[list[str], str]]:
        """Yield (section_path, text) pairs respecting target_chars."""
        if not sections:
            return list(self._split_text([], plain_text))

        result: list[tuple[list[str], str]] = []
        heading_stack: list[str] = []

        for section in sections:
            heading = section.get("heading", "")
            level = section.get("level", 0)
            body = section.get("body_text", "")

            # Trim heading stack to current level
            heading_stack = heading_stack[: max(0, level - 1)]
            if heading:
                heading_stack = heading_stack + [heading]

            # Section text = heading + body
            section_text = f"{heading}\n\n{body}".strip() if heading else body
            if not section_text:
                continue

            result.extend(self._split_text(list(heading_stack), section_text))

        return result if result else list(self._split_text([], plain_text))

    def _split_text(
        self, section_path: list[str], text: str
    ):
        """Split text into target_chars chunks with overlap."""
        if len(text) <= self.max_chars:
            yield section_path, text
            return

        # Split on paragraph boundaries first
        paragraphs = re.split(r"\n\n+", text)
        buffer = ""
        for para in paragraphs:
            if len(buffer) + len(para) + 2 > self.target_chars and buffer:
                yield section_path, buffer.strip()
                # overlap: keep last overlap_chars of buffer
                buffer = buffer[-self.overlap_chars:] + "\n\n" + para
            else:
                buffer = (buffer + "\n\n" + para).lstrip()

        if buffer.strip():
            yield section_path, buffer.strip()

    def _chunk_uid(self, canonical_url: str, index: int, text: str) -> str:
        raw = f"{canonical_url}|{index}|{hashlib.md5(text[:200].encode()).hexdigest()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
```

- [ ] **Step 2: embedding_index_service.py**

```python
# app/services/crawl/embedding_index_service.py
"""Embed chunks and upsert into document_chunks (pgvector)."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import httpx
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document_chunk import DocumentChunk, SourceType
from app.services.crawl.chunking_service import Chunk

logger = logging.getLogger(__name__)


class EmbeddingIndexService:
    def __init__(self, batch_size: int = 32) -> None:
        self.batch_size = batch_size

    async def embed_and_upsert(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        page_canonical_url: str,
        chunks: list[Chunk],
        source_key: str,
        visibility: str = "global",
    ) -> int:
        """Embed chunks and upsert into document_chunks. Returns count upserted."""
        if not chunks:
            return 0

        settings = get_settings()
        texts = [c.text for c in chunks]
        embeddings = await self._batch_embed(texts, settings)

        if len(embeddings) != len(chunks):
            logger.error("Embedding count mismatch: %d texts vs %d embeddings", len(texts), len(embeddings))
            raise RuntimeError("Embedding batch size mismatch")

        # Delete stale chunks for this page
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.source_ref == page_canonical_url,
                DocumentChunk.source_type == SourceType.external_docs,
            )
        )

        # Insert new chunks
        for chunk, embedding in zip(chunks, embeddings):
            dc = DocumentChunk(
                id=uuid.uuid4(),
                org_id=None,  # global shared → no org restriction
                source_ref=page_canonical_url,
                source_type=SourceType.external_docs,
                source_url=chunk.metadata.get("canonical_url"),
                source_title=chunk.metadata.get("page_title"),
                file_hash=chunk.chunk_uid,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.text,
                embedding=embedding,
                zone_id=None,  # zone_id=NULL + is_global=True → accessible to all
                is_global=True,
            )
            db.add(dc)

        await db.commit()
        logger.info("Upserted %d chunks for %s", len(chunks), page_canonical_url)
        return len(chunks)

    async def delete_page_chunks(self, db: AsyncSession, canonical_url: str) -> None:
        """Remove all chunks for a page (used when page is removed)."""
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.source_ref == canonical_url,
                DocumentChunk.source_type == SourceType.external_docs,
            )
        )
        await db.commit()

    async def _batch_embed(
        self, texts: list[str], settings
    ) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.LITELLM_URL}/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.LITELLM_API_KEY}"},
                    json={"model": "ionos-embed", "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                # Sort by index (API may reorder)
                data.sort(key=lambda x: x["index"])
                results.extend([item["embedding"] for item in data])
        return results
```

- [ ] **Step 3: Handle org_id=None**

The `DocumentChunk.org_id` column has a FK to organizations. Since we need `org_id=NULL` for global docs, we need to make it nullable. Read `backend/app/models/document_chunk.py` and update:

```python
    org_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
```

Also write migration 0063 to allow NULL org_id:

```python
"""allow null org_id on document_chunks for global shared content

Revision ID: 0063
Revises: 0062
Create Date: 2026-04-23
"""
from alembic import op

revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("document_chunks", "org_id", nullable=True)


def downgrade() -> None:
    # Note: this will fail if any rows have org_id=NULL
    op.alter_column("document_chunks", "org_id", nullable=False)
```

Run migration: `alembic upgrade head`

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/crawl/chunking_service.py backend/app/services/crawl/embedding_index_service.py backend/migrations/versions/0063_document_chunk_nullable_org.py backend/app/models/document_chunk.py
git commit -m "feat: chunking + embedding index service; allow nullable org_id for global chunks"
```

---

### Task 7: Ingest Run Service + SAP Source Config

**Files:**
- Create: `backend/app/services/crawl/ingest_run_service.py`
- Create: `backend/app/services/crawl/sap_source_config.py`

- [ ] **Step 1: sap_source_config.py**

```python
# app/services/crawl/sap_source_config.py
"""Predefined configuration for SAP S/4HANA Utilities documentation source."""
from __future__ import annotations

SAP_S4HANA_UTILITIES_CONFIG = {
    "source_key": "sap_s4hana_utilities_en_2025_001_shared",
    "display_name": "SAP S/4HANA Utilities Documentation (EN, 2025.001)",
    "source_type": "external_docs",
    "base_url": "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/",
    "visibility_scope": "global",
    "config": {
        "allowed_domains": ["help.sap.com"],
        "include_url_prefixes": [
            "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/"
        ],
        "required_query_params": {
            "locale": "en-US",
            "state": "PRODUCTION",
            "version": "2025.001",
        },
        "dropped_query_params": ["q", "search", "sort", "page"],
        "seed_urls": [
            "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/?locale=en-US&state=PRODUCTION&version=2025.001"
        ],
        "crawl_policy": {
            "max_concurrency": 2,
            "request_delay_seconds": 1.5,
            "request_timeout_seconds": 30,
            "max_retries": 3,
            "respect_robots_txt": True,
            "user_agent": "heyKarl-DocBot/1.0 (compatible; +https://heykarl.de/bot)",
            "thin_content_threshold": 200,
        },
        "extraction_policy": {
            "content_selectors": [
                "article", "main", '[role="main"]',
                ".help-content", ".content", "#content",
                ".ltr", ".innerContent",
            ],
            "exclude_selectors": [
                "header", "footer", "nav", ".cookie-banner",
                ".search-widget", ".related-links", ".feedback-section",
                '[role="navigation"]', '[role="search"]',
                ".sap-icon--navigation-right-arrow",
            ],
            "min_content_length": 100,
        },
        "chunking_policy": {
            "target_chunk_tokens": 800,
            "overlap_tokens": 120,
            "max_chunk_tokens": 1200,
            "heading_split_levels": [1, 2, 3],
        },
        "embedding_policy": {
            "model": "ionos-embed",
            "batch_size": 32,
            "dimensions": 1024,
        },
        "refresh_policy": {
            "schedule_cron": "0 3 * * 0",
            "use_etag": True,
            "use_last_modified": True,
            "force_reindex_on_hash_change": True,
        },
        "metadata_defaults": {
            "source_type": "external_docs",
            "visibility": "global",
            "vendor": "SAP",
            "product": "SAP_S4HANA_ON-PREMISE",
            "module": "Utilities",
            "collection_id": "021b182b0c47416c8fafed67ebfd78a9",
            "locale": "en-US",
            "state": "PRODUCTION",
            "version": "2025.001",
            "source_key": "sap_s4hana_utilities_en_2025_001_shared",
        },
    },
}
```

- [ ] **Step 2: ingest_run_service.py**

```python
# app/services/crawl/ingest_run_service.py
"""Orchestrates a complete or refresh ingest run for an external source."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource, ExternalSourcePage, ExternalSourceRun
from app.services.crawl.chunking_service import ChunkingService
from app.services.crawl.discovery_service import DiscoveryService
from app.services.crawl.embedding_index_service import EmbeddingIndexService
from app.services.crawl.extraction_service import ExtractionService
from app.services.crawl.fetch_service import FetchService
from app.services.crawl.url_canonicalizer import UrlCanonicalizer

logger = logging.getLogger(__name__)


class IngestRunService:
    def __init__(self, source: ExternalSource) -> None:
        self.source = source
        cfg = source.config_json
        crawl_cfg = cfg.get("crawl_policy", {})
        chunk_cfg = cfg.get("chunking_policy", {})
        embed_cfg = cfg.get("embedding_policy", {})
        extract_cfg = cfg.get("extraction_policy", {})

        self.canonicalizer = UrlCanonicalizer(
            required_params=cfg.get("required_query_params", {}),
            dropped_params=set(cfg.get("dropped_query_params", [])),
            allowed_prefixes=cfg.get("include_url_prefixes", [source.base_url]),
            allowed_domains=cfg.get("allowed_domains", []),
        )
        self.discovery = DiscoveryService(
            canonicalizer=self.canonicalizer,
            seed_urls=cfg.get("seed_urls", [source.base_url]),
            allowed_prefixes=cfg.get("include_url_prefixes", []),
            crawl_delay=crawl_cfg.get("request_delay_seconds", 1.0),
        )
        self.fetcher = FetchService(
            timeout=crawl_cfg.get("request_timeout_seconds", 30),
            max_retries=crawl_cfg.get("max_retries", 3),
            delay_between_requests=crawl_cfg.get("request_delay_seconds", 1.0),
            thin_threshold=crawl_cfg.get("thin_content_threshold", 200),
        )
        self.extractor = ExtractionService(
            content_selectors=extract_cfg.get("content_selectors", []),
            exclude_selectors=extract_cfg.get("exclude_selectors", []),
            min_content_length=extract_cfg.get("min_content_length", 100),
        )
        self.chunker = ChunkingService(
            target_tokens=chunk_cfg.get("target_chunk_tokens", 800),
            overlap_tokens=chunk_cfg.get("overlap_tokens", 120),
            max_tokens=chunk_cfg.get("max_chunk_tokens", 1200),
        )
        self.embedder = EmbeddingIndexService(
            batch_size=embed_cfg.get("batch_size", 32),
        )
        self.metadata_defaults = cfg.get("metadata_defaults", {})

    async def run_initial(self, run_id: uuid.UUID) -> dict:
        """Full discovery + ingest of all pages."""
        stats = {
            "discovered": 0, "fetched": 0, "rendered": 0,
            "extracted": 0, "chunked": 0, "embedded": 0,
            "skipped_unchanged": 0, "failed": 0,
        }
        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if not run:
                raise ValueError(f"Run {run_id} not found")
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

        try:
            logger.info("Starting discovery for source %s", self.source.source_key)
            canonical_urls = await self.discovery.discover_all()
            stats["discovered"] = len(canonical_urls)
            logger.info("Discovered %d URLs", len(canonical_urls))

            # Persist discovered pages
            async with AsyncSessionLocal() as db:
                for canon_url in canonical_urls:
                    await self._upsert_page_record(db, canon_url)
                await db.commit()

            # Process each page
            semaphore = asyncio.Semaphore(2)  # max_concurrency
            tasks = [
                self._process_page(canon_url, stats, semaphore, is_refresh=False)
                for canon_url in canonical_urls
            ]
            await asyncio.gather(*tasks)

        except Exception as exc:
            logger.exception("Run %s failed: %s", run_id, exc)
            async with AsyncSessionLocal() as db:
                run = await db.get(ExternalSourceRun, run_id)
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_summary = str(exc)
                    run.stats_json = stats
                    await db.commit()
            raise

        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "completed"
                run.finished_at = datetime.now(timezone.utc)
                run.stats_json = stats
                await db.commit()

        logger.info("Run %s complete: %s", run_id, stats)
        return stats

    async def run_refresh(self, run_id: uuid.UUID) -> dict:
        """Refresh run: check existing pages for changes, discover new ones."""
        stats = {
            "discovered": 0, "fetched": 0, "rendered": 0,
            "extracted": 0, "chunked": 0, "embedded": 0,
            "skipped_unchanged": 0, "failed": 0,
        }
        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "running"
                run.started_at = datetime.now(timezone.utc)
                await db.commit()

            # Get existing pages
            result = await db.execute(
                select(ExternalSourcePage).where(
                    ExternalSourcePage.source_id == self.source.id,
                    ExternalSourcePage.is_active == True,  # noqa: E712
                )
            )
            existing_pages = result.scalars().all()

        # Discover new URLs
        canonical_urls = await self.discovery.discover_all()
        stats["discovered"] = len(canonical_urls)

        existing_map = {p.canonical_url: p for p in existing_pages}
        all_urls = set(canonical_urls) | set(existing_map.keys())

        semaphore = asyncio.Semaphore(2)
        tasks = [
            self._process_page(
                url, stats, semaphore, is_refresh=True,
                existing_page=existing_map.get(url),
            )
            for url in all_urls
        ]
        await asyncio.gather(*tasks)

        async with AsyncSessionLocal() as db:
            run = await db.get(ExternalSourceRun, run_id)
            if run:
                run.status = "completed"
                run.finished_at = datetime.now(timezone.utc)
                run.stats_json = stats
                await db.commit()

        return stats

    async def _process_page(
        self,
        canonical_url: str,
        stats: dict,
        semaphore: asyncio.Semaphore,
        is_refresh: bool,
        existing_page: Optional[ExternalSourcePage] = None,
    ) -> None:
        async with semaphore:
            try:
                etag = existing_page.etag if existing_page else None
                last_mod = existing_page.last_modified if existing_page else None

                fetch_result = await self.fetcher.fetch(
                    canonical_url, canonical_url, etag=etag, last_modified=last_mod
                )
                stats["fetched"] += 1
                if fetch_result.fetch_method == "rendered":
                    stats["rendered"] += 1

                if fetch_result.http_status == 304:
                    stats["skipped_unchanged"] += 1
                    return

                if fetch_result.error or fetch_result.http_status >= 400:
                    stats["failed"] += 1
                    await self._mark_page_failed(canonical_url, fetch_result.error or f"HTTP {fetch_result.http_status}")
                    return

                # Check hash for change detection
                if is_refresh and existing_page and existing_page.content_hash == fetch_result.content_hash:
                    stats["skipped_unchanged"] += 1
                    return

                # Extract
                extracted = self.extractor.extract(fetch_result.html, canonical_url, fetch_result.fetch_method)
                stats["extracted"] += 1

                # Chunk
                chunks = self.chunker.chunk_page(
                    canonical_url=canonical_url,
                    page_title=extracted.title,
                    sections=extracted.structured_sections,
                    plain_text=extracted.plain_text,
                    source_metadata=self.metadata_defaults,
                )
                stats["chunked"] += len(chunks)

                # Embed + index
                async with AsyncSessionLocal() as db:
                    count = await self.embedder.embed_and_upsert(
                        db=db,
                        source_id=self.source.id,
                        page_canonical_url=canonical_url,
                        chunks=chunks,
                        source_key=self.source.source_key,
                    )
                    stats["embedded"] += count

                    # Update page record
                    await self._update_page_record(
                        db, canonical_url, fetch_result, extracted.extraction_quality_score
                    )

            except Exception as exc:
                logger.warning("Failed to process %s: %s", canonical_url, exc)
                stats["failed"] += 1
                await self._mark_page_failed(canonical_url, str(exc))

    async def _upsert_page_record(self, db: AsyncSession, canonical_url: str) -> None:
        result = await db.execute(
            select(ExternalSourcePage).where(
                ExternalSourcePage.source_id == self.source.id,
                ExternalSourcePage.canonical_url == canonical_url,
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            db.add(ExternalSourcePage(
                source_id=self.source.id,
                raw_url=canonical_url,
                canonical_url=canonical_url,
                status="pending",
                discovered_at=datetime.now(timezone.utc),
            ))

    async def _update_page_record(
        self, db: AsyncSession, canonical_url: str, fetch_result, quality_score: float
    ) -> None:
        result = await db.execute(
            select(ExternalSourcePage).where(
                ExternalSourcePage.source_id == self.source.id,
                ExternalSourcePage.canonical_url == canonical_url,
            )
        )
        page = result.scalar_one_or_none()
        if not page:
            page = ExternalSourcePage(
                source_id=self.source.id,
                raw_url=canonical_url,
                canonical_url=canonical_url,
                discovered_at=datetime.now(timezone.utc),
            )
            db.add(page)

        page.status = "embedded"
        page.fetched_at = fetch_result.fetched_at
        page.extracted_at = datetime.now(timezone.utc)
        page.http_status = fetch_result.http_status
        page.fetch_method = fetch_result.fetch_method
        page.content_hash = fetch_result.content_hash
        page.etag = fetch_result.etag
        page.last_modified = fetch_result.last_modified
        page.last_changed_at = datetime.now(timezone.utc)
        page.metadata_json = {"quality_score": quality_score}
        await db.commit()

    async def _mark_page_failed(self, canonical_url: str, error: str) -> None:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ExternalSourcePage).where(
                    ExternalSourcePage.source_id == self.source.id,
                    ExternalSourcePage.canonical_url == canonical_url,
                )
            )
            page = result.scalar_one_or_none()
            if page:
                page.status = "failed"
                page.error_detail = error
                await db.commit()
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/crawl/ingest_run_service.py backend/app/services/crawl/sap_source_config.py
git commit -m "feat: ingest run service and SAP S/4HANA Utilities source config"
```

---

### Task 8: Celery Tasks + Admin API Router

**Files:**
- Create: `backend/app/tasks/external_ingest_tasks.py`
- Create: `backend/app/routers/external_sources.py`
- Modify: `backend/app/main.py` (mount router)
- Modify: `backend/app/celery_app.py` (include task module)

- [ ] **Step 1: external_ingest_tasks.py**

```python
# app/tasks/external_ingest_tasks.py
"""Celery tasks for external documentation source ingest."""
from __future__ import annotations

import asyncio
import logging
import uuid

from app.celery_app import celery
from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource, ExternalSourceRun

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(name="external_ingest.run_initial", bind=True, max_retries=1)
def run_initial_ingest(self, source_id: str, run_id: str) -> dict:
    """Full initial ingest for an external source."""
    from app.services.crawl.ingest_run_service import IngestRunService

    async def _inner():
        async with AsyncSessionLocal() as db:
            source = await db.get(ExternalSource, uuid.UUID(source_id))
            if not source:
                raise ValueError(f"Source {source_id} not found")
        svc = IngestRunService(source)
        return await svc.run_initial(uuid.UUID(run_id))

    try:
        return _run_async(_inner())
    except Exception as exc:
        logger.exception("Initial ingest failed: %s", exc)
        self.retry(countdown=300, exc=exc)


@celery.task(name="external_ingest.run_refresh", bind=True, max_retries=2)
def run_refresh_ingest(self, source_id: str, run_id: str) -> dict:
    """Refresh ingest for an external source."""
    from app.services.crawl.ingest_run_service import IngestRunService

    async def _inner():
        async with AsyncSessionLocal() as db:
            source = await db.get(ExternalSource, uuid.UUID(source_id))
            if not source:
                raise ValueError(f"Source {source_id} not found")
        svc = IngestRunService(source)
        return await svc.run_refresh(uuid.UUID(run_id))

    try:
        return _run_async(_inner())
    except Exception as exc:
        logger.exception("Refresh ingest failed: %s", exc)
        self.retry(countdown=300, exc=exc)
```

- [ ] **Step 2: external_sources.py router**

```python
# app/routers/external_sources.py
"""Admin API for managing external documentation sources."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.external_source import ExternalSource, ExternalSourcePage, ExternalSourceRun
from app.models.user import User
from app.routers.superadmin import get_admin_user
from app.schemas.external_source import (
    ExternalSourceCreate,
    ExternalSourcePageRead,
    ExternalSourceRead,
    ExternalSourceRunRead,
    IngestStartResponse,
    PreviewResponse,
    SourceConfig,
)

router = APIRouter(prefix="/knowledge-sources/external", tags=["external-sources-admin"])


def _source_to_read(source: ExternalSource) -> ExternalSourceRead:
    return ExternalSourceRead(
        id=source.id,
        source_key=source.source_key,
        display_name=source.display_name,
        source_type=source.source_type,
        base_url=source.base_url,
        config_json=source.config_json,
        visibility_scope=source.visibility_scope,
        is_enabled=source.is_enabled,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


@router.post("", response_model=ExternalSourceRead, status_code=status.HTTP_201_CREATED)
async def create_source(
    body: ExternalSourceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> ExternalSourceRead:
    existing = await db.execute(
        select(ExternalSource).where(ExternalSource.source_key == body.source_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Source key already exists")

    source = ExternalSource(
        source_key=body.source_key,
        display_name=body.display_name,
        base_url=body.base_url,
        visibility_scope=body.visibility_scope,
        config_json=body.config.model_dump(),
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return _source_to_read(source)


@router.get("", response_model=list[ExternalSourceRead])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourceRead]:
    result = await db.execute(
        select(ExternalSource).order_by(ExternalSource.created_at.desc())
    )
    return [_source_to_read(s) for s in result.scalars().all()]


@router.get("/{source_id}", response_model=ExternalSourceRead)
async def get_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> ExternalSourceRead:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_to_read(source)


@router.post("/{source_id}/ingest", response_model=IngestStartResponse)
async def start_ingest(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source or not source.is_enabled:
        raise HTTPException(status_code=404, detail="Source not found or disabled")

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="initial",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_initial_ingest
    run_initial_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message="Initial ingest started",
    )


@router.post("/{source_id}/refresh", response_model=IngestStartResponse)
async def start_refresh(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source or not source.is_enabled:
        raise HTTPException(status_code=404, detail="Source not found or disabled")

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="refresh",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_refresh_ingest
    run_refresh_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message="Refresh ingest started",
    )


@router.post("/{source_id}/disable", status_code=status.HTTP_204_NO_CONTENT)
async def disable_source(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> None:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_enabled = False
    await db.commit()


@router.get("/{source_id}/runs", response_model=list[ExternalSourceRunRead])
async def list_runs(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourceRunRead]:
    result = await db.execute(
        select(ExternalSourceRun)
        .where(ExternalSourceRun.source_id == source_id)
        .order_by(desc(ExternalSourceRun.created_at))
        .limit(50)
    )
    runs = result.scalars().all()
    return [ExternalSourceRunRead.model_validate(r) for r in runs]


@router.get("/{source_id}/pages", response_model=list[ExternalSourcePageRead])
async def list_pages(
    source_id: uuid.UUID,
    page_status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourcePageRead]:
    stmt = select(ExternalSourcePage).where(ExternalSourcePage.source_id == source_id)
    if page_status:
        stmt = stmt.where(ExternalSourcePage.status == page_status)
    stmt = stmt.order_by(ExternalSourcePage.canonical_url).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return [ExternalSourcePageRead.model_validate(p) for p in result.scalars().all()]


@router.get("/{source_id}/failures", response_model=list[ExternalSourcePageRead])
async def list_failures(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_admin_user),
) -> list[ExternalSourcePageRead]:
    result = await db.execute(
        select(ExternalSourcePage)
        .where(
            ExternalSourcePage.source_id == source_id,
            ExternalSourcePage.status == "failed",
        )
        .order_by(desc(ExternalSourcePage.updated_at))
        .limit(200)
    )
    return [ExternalSourcePageRead.model_validate(p) for p in result.scalars().all()]


@router.post("/{source_id}/retry-failures", response_model=IngestStartResponse)
async def retry_failures(
    source_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
) -> IngestStartResponse:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    result = await db.execute(
        select(ExternalSourcePage).where(
            ExternalSourcePage.source_id == source_id,
            ExternalSourcePage.status == "failed",
        )
    )
    pages = result.scalars().all()
    for page in pages:
        page.status = "pending"
    await db.commit()

    run = ExternalSourceRun(
        source_id=source_id,
        run_type="retry",
        status="pending",
        triggered_by=admin.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    from app.tasks.external_ingest_tasks import run_refresh_ingest
    run_refresh_ingest.delay(str(source_id), str(run.id))

    return IngestStartResponse(
        run_id=run.id,
        status="pending",
        message=f"Retrying {len(pages)} failed pages",
    )


@router.get("/{source_id}/preview", response_model=PreviewResponse)
async def preview_page(
    source_id: uuid.UUID,
    page_url: str = Query(...),
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    source = await db.get(ExternalSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.services.crawl.extraction_service import ExtractionService
    from app.services.crawl.fetch_service import FetchService
    from app.services.crawl.chunking_service import ChunkingService
    from app.services.crawl.url_canonicalizer import UrlCanonicalizer

    cfg = source.config_json
    canon = UrlCanonicalizer(
        required_params=cfg.get("required_query_params", {}),
        dropped_params=set(cfg.get("dropped_query_params", [])),
        allowed_prefixes=cfg.get("include_url_prefixes", []),
        allowed_domains=cfg.get("allowed_domains", []),
    )
    canonical_url = canon.canonicalize(page_url) or page_url

    fetcher = FetchService()
    fetch_result = await fetcher.fetch(page_url, canonical_url)
    if fetch_result.error:
        raise HTTPException(status_code=422, detail=f"Fetch failed: {fetch_result.error}")

    extractor = ExtractionService()
    extracted = extractor.extract(fetch_result.html, canonical_url, fetch_result.fetch_method)

    chunker = ChunkingService()
    chunks = chunker.chunk_page(
        canonical_url=canonical_url,
        page_title=extracted.title,
        sections=extracted.structured_sections,
        plain_text=extracted.plain_text,
        source_metadata={},
    )

    return PreviewResponse(
        canonical_url=canonical_url,
        title=extracted.title,
        breadcrumb=extracted.breadcrumb,
        headings=[f"H{level}: {text}" for level, text in extracted.headings[:10]],
        plain_text_preview=extracted.plain_text[:500],
        chunk_count=len(chunks),
        fetch_method=fetch_result.fetch_method,
        extraction_quality_score=extracted.extraction_quality_score,
    )
```

- [ ] **Step 3: Register task module in celery_app.py**

In `backend/app/celery_app.py`, add `"app.tasks.external_ingest_tasks"` to the `include` list.

- [ ] **Step 4: Mount router in main.py**

In `backend/app/main.py`, find where superadmin routers are mounted. Add:

```python
from app.routers.external_sources import router as external_sources_router
# Mount under superadmin prefix:
app.include_router(
    external_sources_router,
    prefix="/api/v1/superadmin",
    dependencies=[],
)
```

- [ ] **Step 5: Restart backend and worker**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml restart backend worker
sleep 10
docker logs assist2-backend --tail 30
docker logs assist2-worker --tail 10
```

Expected: no errors.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2 && git add backend/app/tasks/external_ingest_tasks.py backend/app/routers/external_sources.py backend/app/celery_app.py backend/app/main.py
git commit -m "feat: external ingest Celery tasks and admin API router"
```

---

### Task 9: RAG Service — Global Visibility Filter

**Files:**
- Modify: `backend/app/services/rag_service.py`

- [ ] **Step 1: Read rag_service.py**

Read the full RAG retrieval query in `backend/app/services/rag_service.py` to understand the WHERE clause.

- [ ] **Step 2: Add is_global filter**

Find the SQL query in `retrieve()` and add an `OR document_chunks.is_global = TRUE` clause so globally shared content is returned for any org query.

The WHERE clause should change from:
```python
WHERE org_id = :org_id AND (zone conditions)
```
To:
```python
WHERE (org_id = :org_id AND (zone conditions)) OR is_global = TRUE
```

Make this a minimal, surgical change. If the query is raw SQL text, wrap the existing conditions in parens and OR-append the global clause. If it's SQLAlchemy ORM, use `or_()`.

- [ ] **Step 3: Restart and verify**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml restart backend
docker logs assist2-backend --tail 20
```

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/rag_service.py
git commit -m "feat: RAG service includes globally shared chunks (is_global=True)"
```

---

### Task 10: Seed SAP Source + Tests

**Files:**
- Create: `backend/app/services/crawl/seed_sources.py`
- Create: `backend/tests/test_external_ingest/test_canonicalizer.py`
- Create: `backend/tests/test_external_ingest/test_extraction.py`
- Create: `backend/tests/test_external_ingest/test_chunking.py`

- [ ] **Step 1: seed_sources.py**

```python
# app/services/crawl/seed_sources.py
"""Seed predefined external sources into the database."""
from __future__ import annotations

import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.external_source import ExternalSource
from app.services.crawl.sap_source_config import SAP_S4HANA_UTILITIES_CONFIG


async def seed_sap_utilities_source() -> None:
    """Insert the SAP Utilities source if not already present."""
    async with AsyncSessionLocal() as db:
        existing = await db.execute(
            select(ExternalSource).where(
                ExternalSource.source_key == SAP_S4HANA_UTILITIES_CONFIG["source_key"]
            )
        )
        if existing.scalar_one_or_none():
            print(f"Source '{SAP_S4HANA_UTILITIES_CONFIG['source_key']}' already exists.")
            return

        cfg = SAP_S4HANA_UTILITIES_CONFIG
        source = ExternalSource(
            source_key=cfg["source_key"],
            display_name=cfg["display_name"],
            source_type=cfg["source_type"],
            base_url=cfg["base_url"],
            visibility_scope=cfg["visibility_scope"],
            config_json=cfg["config"],
        )
        db.add(source)
        await db.commit()
        print(f"Seeded source: {cfg['source_key']}")


if __name__ == "__main__":
    asyncio.run(seed_sap_utilities_source())
```

- [ ] **Step 2: test_canonicalizer.py**

```python
# tests/test_external_ingest/test_canonicalizer.py
"""Unit tests for URL canonicalization."""
import pytest

from app.services.crawl.url_canonicalizer import UrlCanonicalizer

BASE_PREFIX = "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/"

REQUIRED_PARAMS = {"locale": "en-US", "state": "PRODUCTION", "version": "2025.001"}
DROPPED_PARAMS = {"q", "search", "sort", "page"}
ALLOWED_DOMAINS = ["help.sap.com"]
ALLOWED_PREFIXES = [BASE_PREFIX]


@pytest.fixture
def canon():
    return UrlCanonicalizer(
        required_params=REQUIRED_PARAMS,
        dropped_params=DROPPED_PARAMS,
        allowed_prefixes=ALLOWED_PREFIXES,
        allowed_domains=ALLOWED_DOMAINS,
    )


def test_drops_q_param(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=utilities"
    result = canon.canonicalize(raw)
    assert result is not None
    assert "q=" not in result


def test_preserves_required_params(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001"
    result = canon.canonicalize(raw)
    assert "locale=en-US" in result
    assert "state=PRODUCTION" in result
    assert "version=2025.001" in result


def test_adds_missing_required_params(canon):
    raw = BASE_PREFIX + "page.html"
    result = canon.canonicalize(raw)
    assert "locale=en-US" in result
    assert "state=PRODUCTION" in result


def test_removes_fragment(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001#section-1"
    result = canon.canonicalize(raw)
    assert "#" not in result


def test_rejects_out_of_scope_url(canon):
    raw = "https://example.com/page"
    result = canon.canonicalize(raw)
    assert result is None or not canon.is_allowed(result or "")


def test_rejects_other_sap_collection(canon):
    raw = "https://help.sap.com/docs/OTHER_PRODUCT/different_collection/page.html?locale=en-US&state=PRODUCTION&version=2025.001"
    in_scope, _ = canon.is_in_scope(raw)
    assert not in_scope


def test_duplicate_urls_converge(canon):
    """Two raw URLs with different q= param produce same canonical."""
    raw1 = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=a"
    raw2 = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&q=b"
    c1 = canon.canonicalize(raw1)
    c2 = canon.canonicalize(raw2)
    assert c1 == c2


def test_params_sorted_deterministically(canon):
    raw1 = BASE_PREFIX + "page.html?version=2025.001&locale=en-US&state=PRODUCTION"
    raw2 = BASE_PREFIX + "page.html?state=PRODUCTION&version=2025.001&locale=en-US"
    c1 = canon.canonicalize(raw1)
    c2 = canon.canonicalize(raw2)
    assert c1 == c2


def test_drops_utm_params(canon):
    raw = BASE_PREFIX + "page.html?locale=en-US&state=PRODUCTION&version=2025.001&utm_source=email"
    result = canon.canonicalize(raw)
    assert "utm_" not in result
```

- [ ] **Step 3: test_chunking.py**

```python
# tests/test_external_ingest/test_chunking.py
"""Unit tests for structure-aware chunking."""
import pytest

from app.services.crawl.chunking_service import ChunkingService


@pytest.fixture
def chunker():
    return ChunkingService(target_tokens=100, overlap_tokens=20, max_tokens=150)


def test_single_section_single_chunk(chunker):
    sections = [{"heading": "Intro", "level": 1, "body_text": "Short content."}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, "Short content.", {})
    assert len(chunks) == 1
    assert "Intro" in chunks[0].text


def test_section_path_in_metadata(chunker):
    sections = [{"heading": "Features", "level": 1, "body_text": "Feature list."}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, "Feature list.", {})
    assert chunks[0].metadata["section_path"] == "Features"


def test_chunk_uid_is_deterministic(chunker):
    sections = [{"heading": "X", "level": 1, "body_text": "Y"}]
    chunks1 = chunker.chunk_page("http://x.com/p", "Page", sections, "Y", {})
    chunks2 = chunker.chunk_page("http://x.com/p", "Page", sections, "Y", {})
    assert chunks1[0].chunk_uid == chunks2[0].chunk_uid


def test_long_text_splits(chunker):
    long_text = ("word " * 200).strip()
    sections = [{"heading": "Long", "level": 1, "body_text": long_text}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, long_text, {})
    assert len(chunks) > 1


def test_total_chunks_metadata(chunker):
    long_text = ("word " * 200).strip()
    sections = [{"heading": "A", "level": 1, "body_text": long_text}]
    chunks = chunker.chunk_page("http://x.com/p", "Page", sections, long_text, {})
    for c in chunks:
        assert c.metadata["total_chunks_for_page"] == len(chunks)
```

- [ ] **Step 4: test_extraction.py**

```python
# tests/test_external_ingest/test_extraction.py
"""Unit tests for HTML content extraction."""
import pytest

from app.services.crawl.extraction_service import ExtractionService


SAMPLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>SAP Test Page</title></head>
<body>
  <header>Global Navigation</header>
  <nav>Breadcrumb Nav</nav>
  <main>
    <h1>Main Feature</h1>
    <p>First paragraph about the feature.</p>
    <h2>Sub-section</h2>
    <p>Sub-section content here.</p>
    <ul><li>Item A</li><li>Item B</li></ul>
  </main>
  <footer>Footer content</footer>
</body>
</html>
"""


@pytest.fixture
def extractor():
    return ExtractionService()


def test_extracts_title(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "SAP Test Page" in page.title or "Main Feature" in page.title


def test_extracts_main_heading(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert page.main_heading == "Main Feature"


def test_excludes_header_footer(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "Global Navigation" not in page.plain_text
    assert "Footer content" not in page.plain_text


def test_includes_body_content(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert "First paragraph" in page.plain_text
    assert "Sub-section content" in page.plain_text


def test_extracts_sections(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    headings_text = [h for _, h in page.headings]
    assert "Main Feature" in headings_text
    assert "Sub-section" in headings_text


def test_language_detection(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert page.language == "en"


def test_quality_score_non_zero(extractor):
    page = extractor.extract(SAMPLE_HTML, "http://x.com/p", "http")
    assert page.extraction_quality_score > 0
```

- [ ] **Step 5: Run tests**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend pytest tests/test_external_ingest/ -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 6: Seed SAP source**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend python -m app.services.crawl.seed_sources
```

Expected: `Seeded source: sap_s4hana_utilities_en_2025_001_shared`

- [ ] **Step 7: Commit**

```bash
cd /opt/assist2 && git add backend/app/services/crawl/seed_sources.py backend/tests/test_external_ingest/
git commit -m "feat: seed SAP source + unit tests (canonicalizer, extraction, chunking)"
```

---

### Task 11: Install Dependencies + Verify End-to-End

- [ ] **Step 1: Check requirements.txt**

Read `backend/requirements.txt`. Check if `beautifulsoup4`, `lxml`, `playwright` are present. If not, add:
```
beautifulsoup4>=4.12.0
lxml>=5.0.0
playwright>=1.40.0  # optional; rendered fetch fallback
```

Run inside container:
```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml exec backend pip install beautifulsoup4 lxml 2>&1 | tail -5
```

- [ ] **Step 2: Rebuild image with new deps**

If requirements.txt was modified:
```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend worker
```

- [ ] **Step 3: Smoke test preview endpoint**

```bash
# Use admin token
TOKEN="<admin_token>"
SOURCE_ID="<uuid_from_list_sources>"

curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/superadmin/knowledge-sources/external/$SOURCE_ID/preview?page_url=https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/266dce53118d4308e10000000a174cb4.html?locale=en-US%26state=PRODUCTION%26version=2025.001" \
  | python3 -m json.tool
```

Expected: JSON with title, breadcrumb, headings, plain_text_preview, chunk_count.

- [ ] **Step 4: Final commit**

```bash
cd /opt/assist2 && git add backend/requirements.txt
git commit -m "feat: add beautifulsoup4 + lxml dependencies for external doc ingest"
```
