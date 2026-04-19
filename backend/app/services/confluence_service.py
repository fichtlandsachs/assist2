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


def _confluence_api_base(url: str) -> str:
    """Normalize a Confluence base URL.

    Atlassian Cloud stores the org URL as https://<slug>.atlassian.net but the
    Confluence REST API lives under /wiki.  Append /wiki when missing so that
    API calls land at the correct path regardless of how the URL was saved.
    """
    url = url.rstrip("/")
    if "atlassian.net" in url and not url.endswith("/wiki"):
        url = f"{url}/wiki"
    return url


def is_configured(
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
) -> bool:
    return _resolve_credentials(base_url, user, token) is not None


async def get_space_key_for_page(
    page_id: str,
    base_url: str,
    user: str,
    token: str,
) -> str:
    """Return the space key of the given Confluence page."""
    b = _confluence_api_base(base_url)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{b}/rest/api/content/{page_id}",
            headers=_make_headers(b, user, token),
            params={"expand": "space"},
        )
        resp.raise_for_status()
        return resp.json()["space"]["key"]


async def get_spaces(
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
) -> list[dict]:
    """Return list of {key, name} for all accessible spaces.

    Tries Confluence REST API v2 first (current Cloud API), falls back to v1.
    """
    creds = _resolve_credentials(base_url, user, token)
    if not creds:
        return []
    b, u, t = creds
    b = _confluence_api_base(b)
    headers = _make_headers(b, u, t)

    import re as _re

    async def _fetch_v2_spaces(client: httpx.AsyncClient, space_type: str | None = None) -> list[dict]:
        """Fetch one page-type of spaces from v2 API (global or personal)."""
        collected: list[dict] = []
        cursor: str | None = None
        while True:
            params: dict = {"limit": 250}
            if cursor:
                params["cursor"] = cursor
            if space_type:
                params["type"] = space_type
            resp = await client.get(f"{b}/api/v2/spaces", headers=headers, params=params)
            if resp.status_code == 404:
                raise ValueError("v2 not available")
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            collected.extend(
                {"key": sp["key"], "name": sp["name"]}
                for sp in results
                if sp.get("key")
            )
            next_url = data.get("_links", {}).get("next")
            if not next_url or not results:
                break
            m = _re.search(r"[?&]cursor=([^&]+)", next_url)
            cursor = m.group(1) if m else None
            if not cursor:
                break
        return collected

    # ── Try v2 (Confluence Cloud current API) ──────────────────────────────
    spaces: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # Fetch global and personal spaces separately — the v2 API
            # defaults to global-only when no type is specified on some tenants.
            global_spaces = await _fetch_v2_spaces(client, "global")
            personal_spaces = await _fetch_v2_spaces(client, "personal")
            spaces = global_spaces + personal_spaces
        if spaces:
            return spaces
    except Exception:
        pass

    # ── Fallback: v1 ──────────────────────────────────────────────────────
    async def _fetch_v1_spaces(client: httpx.AsyncClient, space_type: str | None = None) -> list[dict]:
        collected: list[dict] = []
        start = 0
        limit = 100
        while True:
            params: dict = {"limit": limit, "start": start}
            if space_type:
                params["type"] = space_type
            resp = await client.get(f"{b}/rest/api/space", headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            collected.extend(
                {"key": sp["key"], "name": sp["name"]}
                for sp in results
                if sp.get("key")
            )
            if not data.get("_links", {}).get("next") or len(results) < limit:
                break
            start += limit
        return collected

    async with httpx.AsyncClient(timeout=15) as client:
        global_spaces = await _fetch_v1_spaces(client, "global")
        personal_spaces = await _fetch_v1_spaces(client, "personal")
        spaces = global_spaces + personal_spaces
    return spaces


async def get_pages_in_space(
    space_key: str,
    base_url: str | None = None,
    user: str | None = None,
    token: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return list of {id, title} for pages in the given space (up to *limit*)."""
    creds = _resolve_credentials(base_url, user, token)
    if not creds:
        return []
    b, u, t = creds
    b = _confluence_api_base(b)
    headers = _make_headers(b, u, t)

    collected: list[dict] = []
    start = 0
    page_size = min(limit, 50)

    async with httpx.AsyncClient(timeout=15) as client:
        while len(collected) < limit:
            resp = await client.get(
                f"{b}/rest/api/content",
                headers=headers,
                params={
                    "spaceKey": space_key,
                    "type": "page",
                    "limit": page_size,
                    "start": start,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                break
            for p in results:
                collected.append({"id": p["id"], "title": p["title"]})
                if len(collected) >= limit:
                    break
            if not data.get("_links", {}).get("next") or len(results) < page_size:
                break
            start += len(results)

    return collected


def _docs_to_html(
    title: str,
    docs: dict,
    features: list | None = None,
    test_cases: list | None = None,
) -> str:
    """Render a story as a Confluence page.

    Sections (in order):
      1. Einleitung        — story description + DoD als Stichpunkte am Ende
      2. Business Value
      3. Zusammenfassung
      4. Akzeptanzkriterien
      5. Technische Details
      6. Weitere Informationen
      7. Workarounds
      8. Aufgaben          — Development | Test | Quality / Compliance
      9. Changelog
    """
    import json as _json

    def _p(text: str) -> str:
        return f"<p>{text}</p>"

    def _ul(lines: list[str]) -> str:
        items = "".join(f"<li>{l}</li>" for l in lines if l.strip())
        return f"<ul>{items}</ul>" if items else ""

    def _criteria_lines(raw: str) -> list[str]:
        return [
            line.lstrip("- •*0123456789.").strip()
            for line in raw.strip().splitlines()
            if line.strip()
        ]

    def _doccontrol_table(docs: dict) -> str:
        rows = [
            ("Zielgruppe", docs.get("target_audience") or "—"),
            ("Version",    docs.get("doc_version") or "1.0"),
            ("Datum",      docs.get("created_at") or "—"),
            ("Ersteller",  docs.get("creator_name") or "—"),
        ]
        row_html = "".join(
            f'<tr><th style="width:130px;background:#f4f5f7;padding:4px 8px;border:1px solid #dfe1e6;">{k}</th>'
            f'<td style="padding:4px 8px;border:1px solid #dfe1e6;">{v}</td></tr>'
            for k, v in rows
        )
        return (
            '<table style="border-collapse:collapse;font-size:12px;margin-bottom:16px;">'
            f"{row_html}</table>"
        )

    def _parse_dod_items(dod_raw: str | list | None) -> list[dict]:
        if not dod_raw:
            return []
        try:
            items = _json.loads(dod_raw) if isinstance(dod_raw, str) else dod_raw
            if isinstance(items, list):
                return items
        except Exception:
            pass
        return []

    parts: list[str] = [f"<h1>{title}</h1>", _doccontrol_table(docs)]

    # ── Einleitung (description + DoD-Stichpunkte) ──────────────────────────
    parts.append("<h2>Einleitung</h2>")
    description = docs.get("description") or ""
    dod_items = _parse_dod_items(docs.get("definition_of_done"))
    if description:
        parts.append(_p(description))
    if dod_items:
        dod_lines = []
        for item in dod_items:
            if isinstance(item, dict):
                text = item.get("text") or item.get("title") or str(item)
            else:
                text = str(item)
            dod_lines.append(text)
        if dod_lines:
            parts.append("<p><strong>Definition of Done:</strong></p>")
            parts.append(_ul(dod_lines))
    if not description and not dod_items:
        parts.append('<p><em>no data</em></p>')

    # ── Remaining content sections ───────────────────────────────────────────
    SECTIONS: list[tuple[str, str | None]] = [
        ("Business Value",        docs.get("business_value")),
        ("Zusammenfassung",       docs.get("summary")),
        ("Akzeptanzkriterien",    docs.get("acceptance_criteria")),
        ("Technische Details",    docs.get("technical_notes")),
        ("Weitere Informationen", docs.get("doc_additional_info")),
        ("Workarounds",           docs.get("doc_workarounds")),
    ]

    for heading, content in SECTIONS:
        parts.append(f"<h2>{heading}</h2>")
        if not content:
            parts.append('<p><em>no data</em></p>')
        elif heading == "Akzeptanzkriterien":
            parts.append(_ul(_criteria_lines(content)))
        else:
            parts.append(_p(content))

    # ── Aufgaben (Development | Test | Quality / Compliance) ────────────────
    parts.append("<h2>Aufgaben</h2>")

    # Development — Features
    parts.append("<h3>Development</h3>")
    if features:
        feat_lines = []
        for f in features:
            title_f = getattr(f, "title", None) or (f.get("title") if isinstance(f, dict) else "") or "–"
            desc_f = getattr(f, "description", None) or (f.get("description") if isinstance(f, dict) else "") or ""
            status_f = getattr(f, "status", None) or (f.get("status") if isinstance(f, dict) else "") or ""
            label = f"<strong>{title_f}</strong>"
            if status_f:
                label += f" <em>({status_f})</em>"
            if desc_f:
                label += f" – {desc_f}"
            feat_lines.append(label)
        parts.append(_ul(feat_lines) or '<p><em>Keine Features vorhanden</em></p>')
    else:
        parts.append('<p><em>Keine Features vorhanden</em></p>')

    # Test — Test Cases
    parts.append("<h3>Test</h3>")
    if test_cases:
        tc_lines = []
        for tc in test_cases:
            title_tc = getattr(tc, "title", None) or (tc.get("title") if isinstance(tc, dict) else "") or "–"
            expected = getattr(tc, "expected_result", None) or (tc.get("expected_result") if isinstance(tc, dict) else "") or ""
            label = f"<strong>{title_tc}</strong>"
            if expected:
                label += f" – {expected}"
            tc_lines.append(label)
        parts.append(_ul(tc_lines) or '<p><em>Keine Testfälle vorhanden</em></p>')
    else:
        parts.append('<p><em>Keine Testfälle vorhanden</em></p>')

    # Quality / Compliance — DoD-Items mit Status
    parts.append("<h3>Quality / Compliance</h3>")
    if dod_items:
        qc_lines = []
        for item in dod_items:
            if isinstance(item, dict):
                checked = item.get("passed") or item.get("checked") or item.get("done")
                text = item.get("text") or item.get("title") or str(item)
                qc_lines.append(f"{'✓' if checked else '○'} {text}")
            else:
                qc_lines.append(str(item))
        parts.append(_ul(qc_lines) or '<p><em>Keine DoD-Kriterien vorhanden</em></p>')
    else:
        parts.append('<p><em>Keine DoD-Kriterien vorhanden</em></p>')

    # ── Changelog ───────────────────────────────────────────────────────────
    parts.append("<h2>Changelog</h2>")
    if docs.get("changelog_entry"):
        parts.append(
            '<ac:structured-macro ac:name="code">'
            '<ac:parameter ac:name="language">markdown</ac:parameter>'
            f'<ac:plain-text-body><![CDATA[{docs["changelog_entry"]}]]></ac:plain-text-body>'
            '</ac:structured-macro>'
        )
    else:
        parts.append('<p><em>no data</em></p>')

    return "\n".join(parts)


async def find_page_by_title(
    space_key: str,
    title: str,
    base_url: str,
    user: str,
    token: str,
) -> dict | None:
    """Find a Confluence page by exact title in a space. Returns {id, version, url} or None."""
    b = _confluence_api_base(base_url)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{b}/rest/api/content",
            headers=_make_headers(b, user, token),
            params={
                "title": title,
                "spaceKey": space_key,
                "type": "page",
                "expand": "version",
                "limit": 1,
            },
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    if not results:
        return None
    page = results[0]
    web_ui = page.get("_links", {}).get("webui", "")
    return {
        "id": page["id"],
        "version": page["version"]["number"],
        "url": f"{b}{web_ui}",
    }


async def get_page_content_text(
    page_id: str,
    base_url: str,
    user: str,
    token: str,
) -> str:
    """Fetch Confluence page body as plain text (strips HTML tags)."""
    import re as _re
    b = _confluence_api_base(base_url)
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{b}/rest/api/content/{page_id}",
            headers=_make_headers(b, user, token),
            params={"expand": "body.storage"},
        )
        resp.raise_for_status()
        html = resp.json().get("body", {}).get("storage", {}).get("value", "")
    # Strip HTML tags for plain-text comparison
    text = _re.sub(r"<[^>]+>", " ", html)
    text = _re.sub(r"\s+", " ", text).strip()
    return text


async def get_page_info(
    page_id: str,
    base_url: str,
    user: str,
    token: str,
) -> dict:
    """Return {id, title, version, parent_id} for a Confluence page."""
    b = _confluence_api_base(base_url)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{b}/rest/api/content/{page_id}",
            headers=_make_headers(b, user, token),
            params={"expand": "version,ancestors"},
        )
        resp.raise_for_status()
        data = resp.json()
    ancestors = data.get("ancestors", [])
    parent_id = ancestors[-1]["id"] if ancestors else None
    return {
        "id": data["id"],
        "title": data["title"],
        "version": data.get("version", {}).get("number", 1),
        "parent_id": parent_id,
    }


async def ensure_hierarchy_page(
    space_key: str,
    title: str,
    parent_id: str | None,
    description: str,
    base_url: str,
    user: str,
    token: str,
) -> str:
    """Find or create a Confluence page with *title* in *space_key*. Returns the page ID.

    If the page does not exist it is created under *parent_id* (when given) with
    a simple HTML body built from *description*.
    """
    b = _confluence_api_base(base_url)
    headers = _make_headers(b, user, token)

    # Try to find an existing page by exact title in the space
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{b}/rest/api/content",
            headers=headers,
            params={"title": title, "spaceKey": space_key, "type": "page", "limit": 1},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
    if results:
        return results[0]["id"]

    # Page not found — create it
    html_body = f"<h1>{title}</h1>"
    if description:
        html_body += f"<p>{description}</p>"
    payload: dict = {
        "type": "page",
        "title": title,
        "space": {"key": space_key},
        "body": {"storage": {"value": html_body, "representation": "storage"}},
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{b}/rest/api/content",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def update_page(
    page_id: str,
    title: str,
    docs: dict,
    version_number: int,
    base_url: str,
    user: str,
    token: str,
    features: list | None = None,
    test_cases: list | None = None,
    parent_id: str | None = None,
) -> str:
    """Update an existing Confluence page. Returns the full URL.

    When *parent_id* is given the page is moved to that parent in the same
    request (Confluence accepts ancestor changes in a regular PUT).
    """
    b = _confluence_api_base(base_url)
    body = _docs_to_html(title, docs, features=features, test_cases=test_cases)
    payload = {
        "type": "page",
        "title": title,
        "version": {"number": version_number + 1},
        "body": {"storage": {"value": body, "representation": "storage"}},
    }
    if parent_id:
        payload["ancestors"] = [{"id": parent_id}]
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(
            f"{b}/rest/api/content/{page_id}",
            headers=_make_headers(b, user, token),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        web_ui = data.get("_links", {}).get("webui", "")
        return f"{b}{web_ui}"


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
    b = _confluence_api_base(b)
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
            headers=_make_headers(b, user, token),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        web_ui = data.get("_links", {}).get("webui", "")
        return f"{b}{web_ui}"


async def _resolve_story_parent(
    space_key: str,
    project_name: str | None,
    project_description: str | None,
    epic_title: str | None,
    epic_description: str | None,
    default_parent_page_id: str | None,
    base_url: str,
    user: str,
    token: str,
) -> str | None:
    """
    Resolve (and create if missing) the parent page for a story page.

    Hierarchy: default_parent → [Project] → [Epic] → story

    Returns the ID of the immediate parent page that the story should live under,
    or None if neither project, epic nor default parent is configured.
    """
    parent_id = default_parent_page_id

    if project_name:
        parent_id = await ensure_hierarchy_page(
            space_key=space_key,
            title=project_name,
            parent_id=default_parent_page_id,
            description=project_description or f"Dokumentation für das Projekt {project_name}",
            base_url=base_url,
            user=user,
            token=token,
        )

    if epic_title:
        parent_id = await ensure_hierarchy_page(
            space_key=space_key,
            title=epic_title,
            parent_id=parent_id,
            description=epic_description or f"Dokumentation für das Epic {epic_title}",
            base_url=base_url,
            user=user,
            token=token,
        )

    return parent_id


async def publish_story_page(
    space_key: str,
    story_title: str,
    docs: dict,
    project_name: str | None,
    base_url: str,
    user: str,
    token: str,
    existing_page_url: str | None = None,
    default_parent_page_id: str | None = None,
    features: list | None = None,
    test_cases: list | None = None,
    project_description: str | None = None,
    epic_title: str | None = None,
    epic_description: str | None = None,
) -> str:
    """
    Publish story documentation to Confluence.

    Hierarchy: default_parent → [Project] → [Epic] → story_title

    - Project and Epic pages are found by title or created with their descriptions.
    - If the story already has a Confluence page the page is updated in-place.
      When the project/epic assignment has changed, the page is also moved to the
      correct parent in the same PUT request (Confluence accepts ancestor changes
      alongside content updates).
    - When no existing page exists a new one is created.

    Returns the full URL of the story page.
    """
    import re as _re
    b = _confluence_api_base(base_url)

    # Always resolve the desired parent chain for the current epic/project state
    desired_parent_id = await _resolve_story_parent(
        space_key=space_key,
        project_name=project_name,
        project_description=project_description,
        epic_title=epic_title,
        epic_description=epic_description,
        default_parent_page_id=default_parent_page_id,
        base_url=base_url,
        user=user,
        token=token,
    )

    # ── Update existing page (and move it if necessary) ───────────────────────
    if existing_page_url:
        match = _re.search(r"/pages/(\d+)", existing_page_url)
        if match:
            page_id = match.group(1)
            try:
                page_info = await get_page_info(page_id, base_url, user, token)
                version_number = page_info["version"]
                # Pass desired_parent_id unconditionally — when it matches the
                # current parent Confluence treats it as a no-op for positioning.
                return await update_page(
                    page_id, story_title, docs, version_number,
                    base_url, user, token,
                    features=features,
                    test_cases=test_cases,
                    parent_id=desired_parent_id,
                )
            except Exception:
                pass  # fall through to create a fresh page

    # ── Create new story page ─────────────────────────────────────────────────
    html_body = _docs_to_html(story_title, docs, features=features, test_cases=test_cases)
    story_payload: dict = {
        "type": "page",
        "title": story_title,
        "space": {"key": space_key},
        "body": {"storage": {"value": html_body, "representation": "storage"}},
    }
    if desired_parent_id:
        story_payload["ancestors"] = [{"id": desired_parent_id}]

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{b}/rest/api/content",
            headers=_make_headers(b, user, token),
            json=story_payload,
        )
        if not resp.is_success:
            import logging as _logging
            _logging.getLogger(__name__).error(
                "Confluence create page failed %s: %s | ancestors=%s space=%s title=%s",
                resp.status_code, resp.text[:500], story_payload.get("ancestors"), space_key, story_title,
            )
        resp.raise_for_status()
        data = resp.json()
        web_ui = data.get("_links", {}).get("webui", "")
        return f"{b}{web_ui}"


async def update_process_page(
    page_id: str,
    process_name: str,
    changes: list[dict],
    base_url: str,
    user: str,
    token: str,
) -> None:
    """
    AI-driven update of a Confluence process page.

    Fetches the current page content, sends it to the LLM together with the
    pending change deltas, and writes the AI-rewritten version back to
    Confluence. The page changelog is extended with the applied changes.

    ``changes`` is a list of dicts with keys ``section_anchor`` (optional)
    and ``delta_text``.
    """
    import re as _re
    import openai as openai_sdk
    from app.config import get_settings

    b = _confluence_api_base(base_url)
    headers = _make_headers(b, user, token)

    # ── Fetch current page ──────────────────────────────────────────────────
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{b}/rest/api/content/{page_id}",
            headers=headers,
            params={"expand": "body.storage,version"},
        )
        resp.raise_for_status()
        page_data = resp.json()

    title = page_data.get("title", process_name)
    version_number = page_data.get("version", {}).get("number", 1)
    current_html = page_data.get("body", {}).get("storage", {}).get("value", "")

    # Strip plain text for the AI prompt
    plain_text = _re.sub(r"<[^>]+>", " ", current_html)
    plain_text = _re.sub(r"\s+", " ", plain_text).strip()

    # ── Build AI prompt ─────────────────────────────────────────────────────
    changes_block = "\n".join(
        f"- Abschnitt: {c.get('section_anchor') or '(kein Abschnitt angegeben)'}\n  Änderung: {c.get('delta_text') or '(kein Text)'}"
        for c in changes
    )

    system_prompt = (
        "Du bist ein technischer Redakteur für Prozessdokumentation. "
        "Deine Aufgabe ist es, eine bestehende Confluence-Prozessseite zu aktualisieren. "
        "Antworte NUR mit dem aktualisierten HTML-Inhalt im Confluence Storage Format. "
        "Kein Markdown, keine Erklärungen, nur valides HTML."
    )

    user_prompt = f"""Aktualisiere die folgende Prozessdokumentation basierend auf den Änderungen.

AKTUELLER PROZESSTEXT:
{plain_text[:8000]}

AUSSTEHENDE ÄNDERUNGEN:
{changes_block}

REGELN:
1. Passe die betroffenen Abschnitte intelligent an — schreibe sie um, ergänze oder streiche Inhalte.
2. Wenn ein Abschnitt nicht existiert, füge ihn sinnvoll ein.
3. Füge am Ende der Seite einen Changelog-Eintrag hinzu:
   <h2>Änderungshistorie</h2> mit dem heutigen Datum und einer Zusammenfassung der Änderungen.
4. Erhalte alle anderen Abschnitte unverändert.
5. Antworte nur mit dem vollständigen aktualisierten HTML (Confluence Storage Format)."""

    settings = get_settings()
    ai_client = openai_sdk.OpenAI(
        base_url=f"{settings.LITELLM_URL}/v1",
        api_key=settings.LITELLM_API_KEY or "sk-heykarl",
        timeout=120,
        max_retries=0,
    )

    response = ai_client.chat.completions.create(
        model="claude-sonnet-4-6",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
    )
    updated_html = response.choices[0].message.content or ""
    # Strip markdown fences if the model wrapped the response
    updated_html = _re.sub(r"^```[a-z]*\n?", "", updated_html.strip())
    updated_html = _re.sub(r"\n?```$", "", updated_html.strip())

    # ── Write updated page back ─────────────────────────────────────────────
    payload = {
        "type": "page",
        "title": title,
        "version": {"number": version_number + 1},
        "body": {"storage": {"value": updated_html, "representation": "storage"}},
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(
            f"{b}/rest/api/content/{page_id}",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
    logger.info("update_process_page: updated page %s (%s)", page_id, title)
