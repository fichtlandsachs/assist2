# app/services/crawl/sap_source_config.py
"""Predefined configuration for SAP S/4HANA Utilities documentation source."""
from __future__ import annotations

SAP_S4HANA_UTILITIES_CONFIG: dict = {
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
