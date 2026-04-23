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

        scheme = parsed.scheme.lower()
        host = parsed.netloc.lower().split(":")[0]

        if scheme not in ("http", "https"):
            return None
        if host not in self.allowed_domains:
            return None

        path = parsed.path.rstrip("/") or "/"

        qs_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered: dict[str, str] = {}
        for k, v in qs_pairs:
            if k in self.dropped_params:
                continue
            if k.startswith("utm_"):
                continue
            filtered[k] = v

        for k, v in self.required_params.items():
            filtered[k] = v

        sorted_qs = urlencode(sorted(filtered.items()))

        canonical = urlunparse((
            "https",
            host,
            path,
            "",
            sorted_qs,
            "",
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
