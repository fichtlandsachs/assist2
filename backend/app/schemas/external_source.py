# app/schemas/external_source.py
"""Pydantic v2 schemas for external source management API."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class CrawlPolicy(BaseModel):
    max_concurrency: int = 3
    request_delay_seconds: float = 1.0
    request_timeout_seconds: int = 30
    max_retries: int = 3
    respect_robots_txt: bool = True
    user_agent: str = "heyKarl-DocBot/1.0 (compatible; +https://heykarl.de/bot)"
    thin_content_threshold: int = 200


class ExtractionPolicy(BaseModel):
    content_selectors: list[str] = ["article", "main", ".content", "#content"]
    exclude_selectors: list[str] = ["header", "footer", "nav", ".cookie-banner"]
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
    schedule_cron: str = "0 3 * * 0"
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
    plain_text_preview: str
    chunk_count: int
    fetch_method: str
    extraction_quality_score: float
