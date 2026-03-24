"""
Confluence REST API integration.

Credentials are resolved in this order:
  1. Explicit (base_url, user, token) arguments — used when org-level settings exist
  2. ENV vars CONFLUENCE_BASE_URL / CONFLUENCE_USER / CONFLUENCE_API_TOKEN — global fallback

All functions are async via httpx.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _make_headers(base_url: str, user: str, token: str) -> dict:
    creds = base64.b64encode(f"{user}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _resolve_credentials(
    base_url: str | None,
    user: str | None,
    token: str | None,
) -> tuple[str, str, str] | None:
    """Return (base_url, user, token) from args or ENV, or None if unconfigured."""
    if base_url and user and token:
        return base_url, user, token
    s = get_settings()
    if s.CONFLUENCE_BASE_URL and s.CONFLUENCE_USER and s.CONFLUENCE_API_TOKEN:
        return s.CONFLUENCE_BASE_URL, s.CONFLUENCE_USER, s.CONFLUENCE_API_TOKEN
    return None


def is_configured(
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
) -> bool:
    return _resolve_credentials(base_url, user, token) is not None


async def get_spaces(
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
) -> list[dict]:
    """Return list of {key, name} for all accessible spaces."""
    creds = _resolve_credentials(base_url, user, token)
    if not creds:
        return []
    b, u, t = creds
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{b}/rest/api/space",
            headers=_make_headers(b, u, t),
            params={"limit": 50, "type": "global"},
        )
        resp.raise_for_status()
        return [
            {"key": sp["key"], "name": sp["name"]}
            for sp in resp.json().get("results", [])
        ]


def _docs_to_html(title: str, docs: dict) -> str:
    outline_items = "".join(
        f"<li>{item}</li>" for item in docs.get("pdf_outline", [])
    )
    return f"""
<h1>{title}</h1>

<h2>Zusammenfassung</h2>
<p>{docs.get("summary", "")}</p>

<h2>Changelog-Eintrag</h2>
<ac:structured-macro ac:name="code"><ac:parameter ac:name="language">markdown</ac:parameter>
<ac:plain-text-body><![CDATA[{docs.get("changelog_entry", "")}]]></ac:plain-text-body>
</ac:structured-macro>

<h2>Dokumentgliederung</h2>
<ol>{outline_items}</ol>

<h2>Technische Hinweise</h2>
<p>{docs.get("technical_notes", "")}</p>
"""


async def publish_page(
    space_key: str,
    title: str,
    docs: dict,
    parent_page_id: str | None = None,
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
) -> str:
    """Create a Confluence page. Returns the full URL of the created page."""
    creds = _resolve_credentials(base_url, user, token)
    if not creds:
        raise ValueError("Confluence ist nicht konfiguriert.")
    b, u, t = creds
    body = _docs_to_html(title, docs)

    payload: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    if parent_page_id:
        payload["ancestors"] = [{"id": parent_page_id}]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{b}/rest/api/content",
            headers=_make_headers(b, u, t),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        web_ui = data.get("_links", {}).get("webui", "")
        return f"{b}{web_ui}"
