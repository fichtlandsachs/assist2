"""
AI Story Service — wraps all LLM calls with context analysis, complexity
scoring, dynamic routing and optional multi-stage pipeline.

Existing callers (routers) are unchanged — same function signatures,
same return types. The new context engine is injected transparently.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

import anthropic
from pydantic import BaseModel

from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity
from app.ai.pipeline import ProviderClient, execute_pipeline
from app.ai.router import RouteDecision, route_request
from app.config import get_settings
from app.schemas.user_story import AISuggestRequest, AISuggestion, AITestCaseSuggestion, StorySplitItem, AIDoDSuggestion
from app.schemas.feature import AIFeatureSuggestion

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Learning config helper (reads admin config at call-time)
# ---------------------------------------------------------------------------

async def _get_rejected_suggestions(
    org_id: "uuid.UUID", suggestion_type: str, db: "AsyncSession"
) -> list[str]:
    """Return up to 20 recently rejected suggestion texts for this org+type."""
    try:
        from sqlalchemy import select as _select
        from app.models.suggestion_feedback import SuggestionFeedback
        result = await db.execute(
            _select(SuggestionFeedback.suggestion_text)
            .where(
                SuggestionFeedback.organization_id == org_id,
                SuggestionFeedback.suggestion_type == suggestion_type,
                SuggestionFeedback.feedback == "rejected",
            )
            .order_by(SuggestionFeedback.created_at.desc())
            .limit(20)
        )
        return [row[0] for row in result.fetchall()]
    except Exception as e:
        logger.warning("Failed to load rejected suggestions: %s", e)
        return []


def _build_rejection_block(rejected: list[str]) -> str:
    if not rejected:
        return ""
    lines = "\n".join(f"- {t}" for t in rejected)
    return f"""--- Von der Organisation abgelehnte Vorschläge (nicht wiederholen) ---
{lines}
----------------------------------------------------------------------

"""


async def _get_learning_flags(org_id, db) -> dict:
    """Return key learning flags for the given org. Falls back to safe defaults."""
    try:
        from app.services.admin_config_service import admin_config_service
        import uuid as _uuid
        oid = org_id if isinstance(org_id, _uuid.UUID) else _uuid.UUID(str(org_id))
        merged = await admin_config_service.get_merged_config(oid, db)
        llm = merged.sections.get("llm_trigger")
        pl = merged.sections.get("prompt_learning")
        ls = merged.sections.get("learning_sensitivity")
        return {
            "retrieval_only": llm.config_payload.get("retrieval_only", False) if llm else False,
            "prompt_learning": pl.config_payload.get("enabled", False) if pl else False,
            "sensitivity": ls.config_payload.get("mode", "conservative") if ls else "conservative",
        }
    except Exception:
        return {"retrieval_only": False, "prompt_learning": False, "sensitivity": "conservative"}


# ---------------------------------------------------------------------------
# Schemas that live here (used by the docs endpoint)
# ---------------------------------------------------------------------------

class DocsGenerateRequest(BaseModel):
    title: str
    description: str | None = None
    acceptance_criteria: str | None = None


class DocsGenerateResponse(BaseModel):
    changelog_entry: str
    pdf_outline: list[str]
    summary: str
    technical_notes: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_client(task_category: str, ai_settings: dict | None = None, complexity: str = "medium") -> tuple[ProviderClient, str]:
    """All AI calls route through LiteLLM (OpenAI-compatible gateway).

    Returns (ProviderClient → LiteLLM, provider_name_for_route_request).

    provider_name controls which model map route_request() uses:
      "ionos"     → ionos-fast / ionos-quality / ionos-reasoning  (default)
      "anthropic" → claude-haiku / claude-sonnet  (org override with claude-* model)
    """
    import openai as openai_sdk

    settings = get_settings()

    litellm = openai_sdk.OpenAI(
        base_url=f"{settings.LITELLM_URL}/v1",
        api_key=settings.LITELLM_API_KEY or "sk-assist2",
        timeout=90,
        max_retries=0,
    )
    client = ProviderClient("openai", litellm)

    # Respect org-level model override — detect provider from model name prefix
    model_override = (ai_settings or {}).get("model_override", "")
    if model_override.startswith("claude"):
        return client, "anthropic"
    if model_override.startswith("gpt") or model_override.startswith("openai"):
        return client, "openai"

    # Default: workspace uses IONOS exclusively
    return client, "ionos"


def _log_decision(fn: str, decision: RouteDecision, usage: dict, elapsed_ms: int) -> None:
    logger.info(
        "ai_call fn=%s model=%s complexity=%s pipeline=%s "
        "in_tokens=%d out_tokens=%d elapsed_ms=%d",
        fn,
        decision.model,
        decision.complexity_level,
        decision.pipeline,
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        elapsed_ms,
    )


def _parse_json(raw: str) -> dict:
    """
    Robust JSON parser — strips markdown fences, then parses.
    If parsing fails due to truncation (max_tokens hit), attempts to recover
    by closing unclosed structures before raising.
    """
    text = raw.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Recovery: try to close truncated JSON by trimming to last complete value
    # Walk backwards and close any open objects/arrays/strings
    recovered = _recover_truncated_json(text)
    if recovered is not None:
        logger.warning("LLM response was truncated — recovered partial JSON")
        return recovered

    raise ValueError(f"LLM returned invalid JSON (truncated?)\nRaw: {raw[:400]}")


def _recover_truncated_json(text: str) -> dict | None:
    """
    Best-effort recovery for truncated JSON objects.
    Strips to the last complete top-level key-value pair, then closes the object.
    """
    # Find the outermost { ... }
    start = text.find("{")
    if start == -1:
        return None

    # Walk backwards from the end to find a position where we can close cleanly.
    # Strategy: strip trailing incomplete fragments and close the object.
    snippet = text[start:]

    # Remove any trailing incomplete string (unclosed quote)
    # Find last complete comma-separated entry
    for cutoff in range(len(snippet) - 1, 0, -1):
        candidate = snippet[:cutoff].rstrip().rstrip(",") + "\n}"
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# get_story_suggestions
# ---------------------------------------------------------------------------

async def get_story_suggestions(
    data: AISuggestRequest,
    ai_settings: dict | None = None,
    org_id: uuid.UUID | None = None,
    db: "AsyncSession | None" = None,
) -> AISuggestion:
    """
    Analyze a User Story draft and return improvement suggestions.

    Routing:
      low     → haiku/gpt-4o-mini, single stage  (clear, simple story)
      medium  → sonnet/gpt-4o,     single stage  (typical case)
      high    → sonnet/gpt-4o,     multi-stage   (missing fields, risk keywords, complex AC)
    """
    model_override = (ai_settings or {}).get("model_override", "")

    # 0. Context analysis (heuristic, no LLM)
    ctx = analyze_context(data.title, data.description, data.acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("story", ai_settings)
    decision = route_request(complexity, "suggest", provider=provider, model_override=model_override)

    logger.debug("get_story_suggestions context=%s score=%s", ctx, complexity)

    # 1. RAG retrieval (org-scoped, optional)
    rag_context_block: str | None = None
    rag_source: str = "llm"
    rag_sources: list = []
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(
                f"{data.title} {data.description}",
                org_id,
                db,
                min_score=0.75,
                source_types=["jira", "confluence", "karl_story"],
            )
            if rag.mode == "direct" and rag.context:
                from app.schemas.user_story import Source as RagSource
                return AISuggestion(
                    title=None,
                    description=None,
                    acceptance_criteria=None,
                    explanation=rag.context,
                    dor_issues=[],
                    quality_score=None,
                    source="rag_direct",
                    sources=[
                        RagSource(
                            title=c.source_title or c.source_type,
                            url=c.source_url or "",
                            type=c.source_type,
                        )
                        for c in rag.chunks if c.source_title or c.source_url
                    ],
                )
            if rag.mode == "context" and rag.chunks:
                rag_context_block = "\n".join(
                    [f"[{c.source_type.upper()}]\n{c.text}" for c in rag.chunks]
                )
                rag_source = "rag_context"
                from app.schemas.user_story import Source as RagSource
                rag_sources = [
                    RagSource(
                        title=c.source_title or c.source_type,
                        url=c.source_url or "",
                        type=c.source_type,
                    )
                    for c in rag.chunks if c.source_title or c.source_url
                ]
        except Exception as e:
            logger.warning("RAG retrieval error (skipping): %s", e)

    # 2. Build prompt (with optional RAG context)
    prompt = _build_suggest_prompt(data, rag_context=rag_context_block)

    # 3. Execute via pipeline (single or multi)
    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("get_story_suggestions", decision, usage, elapsed_ms)

    # 4. Parse and return
    parsed = _parse_json(raw)
    return AISuggestion(**parsed, source=rag_source, sources=rag_sources)


def _build_suggest_prompt(data: AISuggestRequest, rag_context: str | None = None) -> str:
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Nextcloud) ---
{rag_context}
---------------------------------

"""
    return f"""{context_section}Analysiere diese User Story und gib Verbesserungsvorschläge zurück.

Aktuelle Story:
Titel: {data.title or "(leer)"}
Beschreibung: {data.description or "(leer)"}
Akzeptanzkriterien: {data.acceptance_criteria or "(leer)"}

Du bist ein erfahrener Scrum Master. Prüfe die Story gegen die Definition of Ready (DoR):
- Hat die Story einen klaren Titel?
- Ist die Beschreibung im Format "Als [Rolle] möchte ich [Funktion], damit [Nutzen]"?
- Sind die Akzeptanzkriterien konkret, testbar und vollständig?
- Ist die Story klein genug für einen Sprint?
- Sind Abhängigkeiten bekannt?

Antworte NUR mit einem JSON-Objekt (kein Markdown, kein Text davor oder danach):
{{
  "title": "Verbesserte Version des Titels oder null wenn gut",
  "description": "Verbesserte Beschreibung im Format 'Als [Rolle] möchte ich [Funktion], damit [Nutzen]' oder null wenn gut",
  "acceptance_criteria": "Verbesserte Akzeptanzkriterien als nummerierte Liste oder null wenn gut",
  "explanation": "Kurze Erklärung der wichtigsten Verbesserungen",
  "dor_issues": ["Liste der fehlenden DoR-Kriterien"],
  "quality_score": 75
}}"""


# ---------------------------------------------------------------------------
# generate_story_docs
# ---------------------------------------------------------------------------

async def generate_story_docs(
    data: DocsGenerateRequest, ai_settings: dict | None = None
) -> DocsGenerateResponse:
    """
    Generate technical documentation for a User Story.

    Routing:
      low    → haiku/gpt-4o-mini, single stage
      medium → sonnet/gpt-4o,     single stage
      high   → sonnet/gpt-4o,     multi-stage
    """
    model_override = (ai_settings or {}).get("model_override", "")

    ctx = analyze_context(data.title, data.description, data.acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("dev", ai_settings)
    decision = route_request(complexity, "docs", provider=provider, model_override=model_override)

    logger.debug("generate_story_docs context=%s score=%s", ctx, complexity)

    prompt = _build_docs_prompt(data)

    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("generate_story_docs", decision, usage, elapsed_ms)

    parsed = _parse_json(raw)
    return DocsGenerateResponse(**parsed)


# ---------------------------------------------------------------------------
# generate_test_case_suggestions
# ---------------------------------------------------------------------------

async def generate_test_case_suggestions(
    title: str,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AITestCaseSuggestion]:
    """
    Derive concrete test cases from a story's acceptance criteria.

    Routing:
      low    → haiku/gpt-4o-mini, single stage  (few, clear AC)
      medium → sonnet/gpt-4o,     single stage
      high   → sonnet/gpt-4o,     multi-stage   (many/complex AC)
    """
    model_override = (ai_settings or {}).get("model_override", "")

    ctx = analyze_context(title, "", acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("story", ai_settings)
    decision = route_request(complexity, "suggest", provider=provider, model_override=model_override)

    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(f"{title} {acceptance_criteria or ''}", org_id, db)
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[{c.source_type.upper()}]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_test_case_suggestions (skipping): %s", e)

    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "test_case", db)
        rejection_block = _build_rejection_block(rejected)

    prompt = _build_test_cases_prompt(title, acceptance_criteria, rag_context=rag_context_block, rejection_block=rejection_block)

    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("generate_test_case_suggestions", decision, usage, elapsed_ms)

    parsed = _parse_json(raw)
    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    if isinstance(parsed, list):
        return [AITestCaseSuggestion(**item, sources=sources_payload) for item in parsed]
    items = parsed.get("suggestions", [])
    return [AITestCaseSuggestion(**item, sources=sources_payload) for item in items]


def _build_test_cases_prompt(
    title: str,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
    rejection_block: str = "",
) -> str:
    ac_text = acceptance_criteria or "(keine Akzeptanzkriterien angegeben)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{rejection_block}{context_section}Du bist ein erfahrener QA-Ingenieur. Leite aus den folgenden Akzeptanzkriterien konkrete Testfälle ab.

User Story: {title}
Akzeptanzkriterien:
{ac_text}

Generiere 3–6 aussagekräftige Testfälle. Jeder Testfall soll einen Normalfall, Grenzfall oder Fehlerfall abdecken.

Antworte NUR mit einem JSON-Array (kein Markdown, kein Text davor oder danach):
[
  {{
    "title": "Kurzer, präziser Testfall-Titel",
    "steps": "1. Schritt\\n2. Schritt\\n3. Schritt",
    "expected_result": "Was genau erwartet wird"
  }}
]"""


# ---------------------------------------------------------------------------
# split_story
# ---------------------------------------------------------------------------

async def split_story(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
) -> list[StorySplitItem]:
    """
    Suggest how to split a User Story into 2–5 smaller, independent stories.
    Always uses high-complexity routing for best quality.
    """
    model_override = (ai_settings or {}).get("model_override", "")

    ctx = analyze_context(title, description or "", acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("story", ai_settings)
    base = route_request(complexity, "suggest", provider=provider, model_override=model_override)
    # Force high quality for splits regardless of input complexity
    decision = RouteDecision(
        model=base.model,
        max_tokens=4096,
        temperature=0.4,
        pipeline="single",
        complexity_level="high",
        task_type="suggest",
    )

    prompt = _build_split_prompt(title, description, acceptance_criteria)

    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("split_story", decision, usage, elapsed_ms)

    parsed = _parse_json(raw)
    if isinstance(parsed, list):
        return [StorySplitItem(**item) for item in parsed]
    items = parsed.get("stories", parsed.get("items", []))
    return [StorySplitItem(**item) for item in items]


def _build_split_prompt(title: str, description: str | None, acceptance_criteria: str | None) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    return f"""Du bist ein erfahrener Scrum Master. Teile diese User Story nach dem INVEST-Prinzip in 2–5 kleinere, unabhängige Stories auf.

Original Story:
Titel: {title}
Beschreibung: {desc}
Akzeptanzkriterien: {ac}

Regeln:
- Jede Sub-Story ist eigenständig implementier- und testbar
- Teile an natürlichen Grenzen: Happy Path vs. Edge Cases, UI vs. Backend, verschiedene Nutzerrollen, oder verschiedene Akzeptanzkriterien-Gruppen
- Story Points: realistisch schätzen (1–8 pro Story)
- Beschreibung im Format "Als [Rolle] möchte ich [Funktion], damit [Nutzen]"

Antworte NUR mit einem JSON-Array (kein Markdown):
[
  {{
    "title": "Präziser Titel der Sub-Story",
    "description": "Als [Rolle] möchte ich [Funktion], damit [Nutzen]",
    "acceptance_criteria": "1. Kriterium\\n2. Kriterium\\n3. Kriterium",
    "story_points": 3
  }}
]"""


def _build_docs_prompt(data: DocsGenerateRequest) -> str:
    return f"""Generiere technische Dokumentation für diese User Story.

Story:
Titel: {data.title}
Beschreibung: {data.description or "(keine)"}
Akzeptanzkriterien: {data.acceptance_criteria or "(keine)"}

Antworte NUR mit einem JSON-Objekt:
{{
  "changelog_entry": "### Feature: {data.title}\\n- Kurze Beschreibung was geändert wurde",
  "pdf_outline": ["Einleitung", "Feature-Übersicht", "Technische Details", "Akzeptanzkriterien", "Testfälle"],
  "summary": "Kurze Zusammenfassung des Features für nicht-technische Stakeholder (2-3 Sätze)",
  "technical_notes": "Technische Implementierungshinweise für Entwickler"
}}"""


# ---------------------------------------------------------------------------
# generate_dod_suggestions
# ---------------------------------------------------------------------------

async def generate_dod_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AIDoDSuggestion]:
    """
    Suggest Definition of Done criteria and relevant KPIs for a User Story.
    Uses low/medium complexity routing — fast response.
    """
    model_override = (ai_settings or {}).get("model_override", "")

    ctx = analyze_context(title, description or "", acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("story", ai_settings)
    decision = route_request(complexity, "suggest", provider=provider, model_override=model_override)

    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(f"{title} {description or ''}", org_id, db)
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[{c.source_type.upper()}]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_dod_suggestions (skipping): %s", e)

    # Load rejected DoD suggestions for this org
    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "dod", db)
        rejection_block = _build_rejection_block(rejected)

    prompt = _build_dod_prompt(title, description, acceptance_criteria, rag_context=rag_context_block, rejection_block=rejection_block)

    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("generate_dod_suggestions", decision, usage, elapsed_ms)

    parsed = _parse_json(raw)
    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    if isinstance(parsed, list):
        items = parsed
    else:
        items = parsed.get("suggestions", [])
    return [AIDoDSuggestion(**item, sources=sources_payload) for item in items]


def _build_dod_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
    rejection_block: str = "",
) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{rejection_block}{context_section}Du bist ein erfahrener Scrum Master. Schlage konkrete Definition-of-Done-Kriterien und messbare KPIs für diese User Story vor.

User Story:
Titel: {title}
Beschreibung: {desc}
Akzeptanzkriterien: {ac}

Schlage 6–10 spezifische DoD-Kriterien vor. Beziehe dich auf typische Kategorien wie:
- Qualität (Code Review, Linting, keine kritischen Bugs)
- Tests (Unit Tests, Integration Tests, Testabdeckung ≥ X%)
- Dokumentation (API-Docs, README, Changelogs)
- Performance (Ladezeit ≤ X ms, Antwortzeit ≤ X ms)
- Sicherheit (OWASP, Input-Validierung, Auth-Check)
- Deployment (CI/CD grün, Staging deployed, Smoke Test)
- Fachlich (Abnahme durch PO, AC erfüllt)

Passe die Kriterien an die Story an. Nenne messbare Schwellwerte wo sinnvoll.

Antworte NUR mit einem JSON-Array (kein Markdown):
[
  {{
    "text": "Konkretes DoD-Kriterium oder KPI",
    "category": "Kategorie (z.B. Tests, Qualität, Deployment)"
  }}
]"""


# ---------------------------------------------------------------------------
# generate_feature_suggestions
# ---------------------------------------------------------------------------

async def generate_feature_suggestions(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    ai_settings: dict | None = None,
    org_id: "uuid.UUID | None" = None,
    db: "AsyncSession | None" = None,
) -> list[AIFeatureSuggestion]:
    """
    Suggest concrete, implementable features (sub-functions) for a User Story.
    Features are the technical building blocks that together fulfil the story.
    """
    model_override = (ai_settings or {}).get("model_override", "")

    ctx = analyze_context(title, description or "", acceptance_criteria)
    complexity = score_complexity(ctx)
    client, provider = _make_client("dev", ai_settings)
    decision = route_request(complexity, "suggest", provider=provider, model_override=model_override)

    # RAG retrieval
    rag_chunks: list = []
    rag_context_block: str | None = None
    if org_id is not None and db is not None:
        try:
            from app.services.rag_service import retrieve
            rag = await retrieve(
                f"{title} {description or ''} {acceptance_criteria or ''}", org_id, db
            )
            if rag.mode in ("direct", "context") and rag.chunks:
                rag_context_block = "\n".join([f"[{c.source_type.upper()}]\n{c.text}" for c in rag.chunks])
                rag_chunks = rag.chunks
        except Exception as e:
            logger.warning("RAG retrieval error in generate_feature_suggestions (skipping): %s", e)

    rejection_block = ""
    if org_id is not None and db is not None:
        rejected = await _get_rejected_suggestions(org_id, "feature", db)
        rejection_block = _build_rejection_block(rejected)

    prompt = _build_feature_suggestions_prompt(title, description, acceptance_criteria, rag_context=rag_context_block, rejection_block=rejection_block)

    t0 = time.monotonic()
    raw, usage = execute_pipeline(client, prompt, decision)
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    _log_decision("generate_feature_suggestions", decision, usage, elapsed_ms)

    sources_payload = [
        {"title": c.source_title or "", "url": c.source_url or "", "type": c.source_type}
        for c in rag_chunks if c.source_url
    ]
    parsed = _parse_json(raw)
    if isinstance(parsed, list):
        return [AIFeatureSuggestion(**item, sources=sources_payload) for item in parsed]
    items = parsed.get("features", parsed.get("suggestions", []))
    return [AIFeatureSuggestion(**item, sources=sources_payload) for item in items]


def _build_feature_suggestions_prompt(
    title: str,
    description: str | None,
    acceptance_criteria: str | None,
    rag_context: str | None = None,
    rejection_block: str = "",
) -> str:
    desc = description or "(keine)"
    ac = acceptance_criteria or "(keine)"
    context_section = ""
    if rag_context:
        context_section = f"""--- Org-Wissen (aus Karl / Nextcloud) ---
{rag_context}
-----------------------------------------

"""
    return f"""{rejection_block}{context_section}Du bist ein erfahrener Senior Developer und Product Owner. Analysiere diese User Story und schlage konkrete, implementierbare Features (Teilfunktionen) vor.

User Story:
Titel: {title}
Beschreibung: {desc}
Akzeptanzkriterien: {ac}

Ein "Feature" ist eine abgeschlossene, eigenständig implementierbare Teilfunktion der Story.
Beispiele für eine Login-Story: "Login-Formular UI", "JWT-Token-Generierung", "Passwort-Hashing", "Session-Management"

Regeln:
- 3–6 konkrete Features vorschlagen
- Jedes Feature soll eigenständig implementier- und testbar sein
- Klarer, technischer Fokus (Frontend-Komponente ODER Backend-Service ODER Datenbankschicht)
- Realistische Story Points: 1–8 pro Feature
- Priorität: low | medium | high | critical

Antworte NUR mit einem JSON-Array (kein Markdown, kein Text davor oder danach):
[
  {{
    "title": "Konkreter Feature-Titel",
    "description": "Kurze technische Beschreibung was zu implementieren ist",
    "priority": "medium",
    "story_points": 3
  }}
]"""
