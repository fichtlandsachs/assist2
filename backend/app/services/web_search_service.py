"""Web search service — 5 provider implementations with cost tracking.

Supported providers:
  brave      Free tier 2 000 req/mo, then ~$3/1 000 · best for budget
  tavily     $10/1 000 searches · best results for AI pipelines
  bing       ~$3–7/1 000 searches · broad index
  google     $5/1 000 (100 free/day) + Custom Search Engine ID required
  perplexity $5/1 000 · AI-native, returns synthesized answer + citations

Usage:
    result = await web_search(query, settings, org_id, user_id, db)
    if result:
        # result.text — markdown-formatted results
        # result.provider — which provider was used
        # result.cost_usd — cost in USD for this call
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass

import httpx

from app.database import AsyncSessionLocal
from app.models.web_search_log import WebSearchLog
from app.services.system_settings_service import RuntimeSettings

logger = logging.getLogger(__name__)

# ── Cost table (USD per single search call) ────────────────────────────────────
_COST_PER_SEARCH: dict[str, float] = {
    "brave":      0.003,
    "tavily":     0.010,
    "bing":       0.003,
    "google":     0.005,
    "perplexity": 0.005,
}

_TIMEOUT = httpx.Timeout(10.0)


@dataclass
class WebSearchResult:
    text: str       # markdown-formatted result block ready for LLM injection
    provider: str
    cost_usd: float


# ── Provider implementations ───────────────────────────────────────────────────

async def _brave(query: str, api_key: str) -> tuple[str, int]:
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(url, headers=headers, params={"q": query, "count": 5})
        r.raise_for_status()
        data = r.json()
    results = data.get("web", {}).get("results", [])
    lines = [f"**[Brave]** Web-Suchergebnisse für: *{query}*\n"]
    for item in results[:5]:
        title = item.get("title", "")
        url_ = item.get("url", "")
        desc = item.get("description", "")
        lines.append(f"- [{title}]({url_})\n  {desc}")
    return "\n".join(lines), len(results)


async def _tavily(query: str, api_key: str) -> tuple[str, int]:
    url = "https://api.tavily.com/search"
    payload = {"api_key": api_key, "query": query, "max_results": 5, "include_answer": True}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    lines = [f"**[Tavily]** Web-Suchergebnisse für: *{query}*\n"]
    if answer := data.get("answer"):
        lines.append(f"*Zusammenfassung:* {answer}\n")
    for item in data.get("results", [])[:5]:
        title = item.get("title", "")
        url_ = item.get("url", "")
        content = item.get("content", "")[:200]
        lines.append(f"- [{title}]({url_})\n  {content}")
    return "\n".join(lines), len(data.get("results", []))


async def _bing(query: str, api_key: str) -> tuple[str, int]:
    url = "https://api.bing.microsoft.com/v7.0/search"
    headers = {"Ocp-Apim-Subscription-Key": api_key}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(url, headers=headers, params={"q": query, "count": 5, "mkt": "de-DE"})
        r.raise_for_status()
        data = r.json()
    items = data.get("webPages", {}).get("value", [])
    lines = [f"**[Bing]** Web-Suchergebnisse für: *{query}*\n"]
    for item in items[:5]:
        title = item.get("name", "")
        url_ = item.get("url", "")
        snippet = item.get("snippet", "")
        lines.append(f"- [{title}]({url_})\n  {snippet}")
    return "\n".join(lines), len(items)


async def _google(query: str, api_key: str, cx: str) -> tuple[str, int]:
    url = "https://www.googleapis.com/customsearch/v1"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(url, params={"q": query, "key": api_key, "cx": cx, "num": 5})
        r.raise_for_status()
        data = r.json()
    items = data.get("items", [])
    lines = [f"**[Google]** Web-Suchergebnisse für: *{query}*\n"]
    for item in items[:5]:
        title = item.get("title", "")
        url_ = item.get("link", "")
        snippet = item.get("snippet", "")
        lines.append(f"- [{title}]({url_})\n  {snippet}")
    return "\n".join(lines), len(items)


async def _perplexity(query: str, api_key: str) -> tuple[str, int]:
    url = "https://api.perplexity.ai/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "sonar",
        "messages": [{"role": "user", "content": query}],
        "return_citations": True,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    lines = [f"**[Perplexity]** Recherche zu: *{query}*\n", content]
    if citations:
        lines.append("\n*Quellen:*")
        for i, cite in enumerate(citations[:5], 1):
            lines.append(f"{i}. {cite}")
    return "\n".join(lines), len(citations)


# ── Public entry point ─────────────────────────────────────────────────────────

async def web_search(
    query: str,
    settings: RuntimeSettings,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> WebSearchResult | None:
    """Run a web search using the configured provider.

    Returns None if web search is disabled or the provider key is missing.
    Logs cost to ``web_search_logs`` regardless of caller context.
    """
    if not settings.WEB_SEARCH_ENABLED:
        return None
    provider = settings.WEB_SEARCH_PROVIDER or "brave"
    api_key = settings.WEB_SEARCH_API_KEY
    if not api_key:
        logger.warning("web_search: provider=%s but WEB_SEARCH_API_KEY is empty", provider)
        return None

    try:
        if provider == "brave":
            text, count = await _brave(query, api_key)
        elif provider == "tavily":
            text, count = await _tavily(query, api_key)
        elif provider == "bing":
            text, count = await _bing(query, api_key)
        elif provider == "google":
            if not settings.WEB_SEARCH_GOOGLE_CX:
                logger.warning("web_search: google provider requires WEB_SEARCH_GOOGLE_CX")
                return None
            text, count = await _google(query, api_key, settings.WEB_SEARCH_GOOGLE_CX)
        elif provider == "perplexity":
            text, count = await _perplexity(query, api_key)
        else:
            logger.warning("web_search: unknown provider=%s", provider)
            return None
    except httpx.HTTPStatusError as exc:
        logger.warning("web_search error (provider=%s status=%s): %s", provider, exc.response.status_code, exc)
        return None
    except Exception as exc:
        logger.warning("web_search error (provider=%s): %s", provider, exc)
        return None

    cost_usd = _COST_PER_SEARCH.get(provider, 0.005)

    # Async fire-and-forget cost log (fresh session, non-blocking)
    try:
        async with AsyncSessionLocal() as log_db:
            log_db.add(WebSearchLog(
                organization_id=org_id,
                created_by_id=user_id,
                provider=provider,
                query=query,
                result_count=count,
                cost_usd=cost_usd,
            ))
            await log_db.commit()
    except Exception as exc:
        logger.warning("web_search: cost log failed (non-fatal): %s", exc)

    return WebSearchResult(text=text, provider=provider, cost_usd=cost_usd)
