"""
Story Readiness Service
=======================
Evaluates all User Stories assigned to (or created by) a given user and
produces a structured readiness assessment for each story.

Karl distinguishes between:
  - explicitly documented information
  - context-inferred information
  - unknown / missing information

No information is invented. If data is absent it is flagged as missing.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity
from app.ai.pipeline import ProviderClient, execute_pipeline
from app.ai.router import route_request
from app.models.epic import Epic
from app.models.story_readiness import ReadinessState, StoryReadinessEvaluation
from app.models.user_story import UserStory
from app.schemas.story_readiness import StoryReadinessResult

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ── Score → State mapping ─────────────────────────────────────────────────────

def _score_to_state(score: int) -> ReadinessState:
    if score >= 81:
        return ReadinessState.implementation_ready
    if score >= 61:
        return ReadinessState.mostly_ready
    if score >= 41:
        return ReadinessState.partially_ready
    return ReadinessState.not_ready


# ── Context collection ────────────────────────────────────────────────────────

async def collect_story_context(story: UserStory, db: AsyncSession) -> dict:
    """
    Gather all available context for a story. Never invents data;
    marks absent fields explicitly as None / empty.
    """
    epic_title: Optional[str] = None
    epic_description: Optional[str] = None
    if story.epic_id:
        result = await db.execute(select(Epic).where(Epic.id == story.epic_id))
        epic = result.scalar_one_or_none()
        if epic:
            epic_title = epic.title
            epic_description = getattr(epic, "description", None)

    dod_items: list[str] = []
    if story.definition_of_done:
        try:
            raw = json.loads(story.definition_of_done)
            if isinstance(raw, list):
                dod_items = [
                    item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    for item in raw
                ]
        except (json.JSONDecodeError, AttributeError):
            pass

    return {
        "title": story.title,
        "description": story.description or "",
        "acceptance_criteria": story.acceptance_criteria or "",
        "status": story.status.value,
        "priority": story.priority.value,
        "story_points": story.story_points,
        "dor_passed": story.dor_passed,
        "quality_score": story.quality_score,
        "epic_title": epic_title,
        "epic_description": epic_description,
        "definition_of_done": dod_items,
        "jira_ticket_key": story.jira_ticket_key,
    }


# ── Prompt builder ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """Du bist Karl, ein erfahrener Product-Owner-Assistent.
Du analysierst User Stories auf ihre Umsetzungsreife.
Du erfindest KEINE Informationen.
Du unterscheidest klar zwischen:
- explizit dokumentiert (source: "documented")
- aus Kontext abgeleitet (source: "inferred")
- unbekannt / nicht vorhanden (source: "unknown")
Wenn Informationen fehlen, nennst du sie explizit als fehlend.
Antworte ausschließlich mit einem validen JSON-Objekt, ohne Markdown.
"""

def _build_evaluation_prompt(ctx: dict) -> str:
    epic_block = ""
    if ctx.get("epic_title"):
        epic_block = f"""
Epic-Kontext:
  Titel: {ctx['epic_title']}
  Beschreibung: {ctx.get('epic_description') or '(nicht vorhanden)'}
"""

    dod_block = ""
    if ctx.get("definition_of_done"):
        dod_block = "\nDefinition of Done:\n" + "\n".join(f"  - {d}" for d in ctx["definition_of_done"])

    return f"""Bewerte folgende User Story auf ihre Umsetzungsreife.

## Story-Daten

Titel: {ctx['title']}
Status: {ctx['status']} | Priorität: {ctx['priority']} | Story Points: {ctx.get('story_points') or 'nicht geschätzt'}
DoR bestanden: {ctx['dor_passed']} | Qualitäts-Score (vorher): {ctx.get('quality_score') or 'nicht bewertet'}

Beschreibung:
{ctx['description'] or '(KEINE BESCHREIBUNG VORHANDEN)'}

Akzeptanzkriterien:
{ctx['acceptance_criteria'] or '(KEINE AKZEPTANZKRITERIEN VORHANDEN)'}
{epic_block}{dod_block}

## Bewertungsauftrag

Analysiere die Story entlang dieser Dimensionen:
1. Verständlichkeit und Zielklarheit (hat die Story das „Als … möchte ich … damit …"-Muster? Ist das Ziel klar?)
2. Qualität und Vollständigkeit der Akzeptanzkriterien
3. Offene fachliche und technische Fragen
4. Abhängigkeiten und Vorbedingungen
5. Notwendige Zuarbeiten anderer Rollen oder Teams
6. Blockers (was verhindert den Start?)
7. Risiken (was könnte die Umsetzung gefährden?)

Berechne dann einen Readiness-Score (0-100):
- 0-40: not_ready
- 41-60: partially_ready
- 61-80: mostly_ready
- 81-100: implementation_ready

## Pflichtformat (reines JSON, kein Markdown)

{{
  "readiness_score": <integer 0-100>,
  "readiness_state": "<not_ready|partially_ready|mostly_ready|implementation_ready>",
  "open_topics": [
    {{"topic": "<Thema>", "source": "<documented|inferred|unknown>", "detail": "<optional Erläuterung>"}}
  ],
  "missing_inputs": [
    {{"input": "<was fehlt>", "importance": "<high|medium|low>"}}
  ],
  "required_preparatory_work": [
    {{"task": "<Aufgabe>", "owner": "<Rolle oder null>", "urgency": "<high|medium|low>"}}
  ],
  "dependencies": [
    {{"name": "<Name>", "type": "<technical|business|team|external>", "status": "<resolved|pending|unknown>"}}
  ],
  "blockers": [
    {{"description": "<Beschreibung>", "severity": "<critical|major|minor>"}}
  ],
  "risks": [
    {{"description": "<Beschreibung>", "probability": "<high|medium|low>", "impact": "<high|medium|low>"}}
  ],
  "recommended_next_steps": [
    {{"step": "<Schritt>", "priority": <1-10>, "responsible": "<Rolle oder null>"}}
  ],
  "summary": "<2-3 Sätze Gesamtzusammenfassung>",
  "confidence": <0.0-1.0>
}}
"""


# ── LLM call ──────────────────────────────────────────────────────────────────

async def _call_llm(ctx: dict) -> tuple[StoryReadinessResult, str, int, int]:
    """Return (result, model_used, input_tokens, output_tokens)."""
    story_context = analyze_context(
        title=ctx["title"],
        description=ctx["description"],
        acceptance_criteria=ctx["acceptance_criteria"],
    )
    complexity = score_complexity(story_context)

    settings = None
    try:
        from app.config import get_settings as _gs
        settings = _gs()
    except Exception:
        pass

    route = route_request(task_type="evaluation", complexity=complexity)
    client = ProviderClient(settings=settings)
    prompt = _build_evaluation_prompt(ctx)

    raw, input_tok, output_tok = await execute_pipeline(
        client=client,
        route=route,
        system_prompt=_SYSTEM_PROMPT,
        user_prompt=prompt,
    )

    # Robust JSON extraction
    result = _parse_result(raw)
    return result, route.model, input_tok, output_tok


def _parse_result(raw: str) -> StoryReadinessResult:
    """Extract and validate JSON from LLM response."""
    text = raw.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:] if lines[0].startswith("```") else lines)
        if text.endswith("```"):
            text = text[:-3].rstrip()

    # Find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in LLM response: {text[:200]}")

    data = json.loads(text[start:end])

    # Clamp and validate score
    score = max(0, min(100, int(data.get("readiness_score", 50))))
    state = data.get("readiness_state", _score_to_state(score).value)
    # Normalise state to enum value
    valid_states = {"not_ready", "partially_ready", "mostly_ready", "implementation_ready"}
    if state not in valid_states:
        state = _score_to_state(score).value

    return StoryReadinessResult(
        readiness_score=score,
        readiness_state=state,
        open_topics=data.get("open_topics", []),
        missing_inputs=data.get("missing_inputs", []),
        required_preparatory_work=data.get("required_preparatory_work", []),
        dependencies=data.get("dependencies", []),
        blockers=data.get("blockers", []),
        risks=data.get("risks", []),
        recommended_next_steps=data.get("recommended_next_steps", []),
        summary=data.get("summary", ""),
        confidence=float(data.get("confidence", 0.7)),
    )


# ── Persistence ───────────────────────────────────────────────────────────────

async def _persist_evaluation(
    story: UserStory,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    result: StoryReadinessResult,
    ctx: dict,
    model_used: str,
    db: AsyncSession,
    error_message: Optional[str] = None,
) -> StoryReadinessEvaluation:
    """Persist a new (versioned) readiness evaluation row."""
    ev = StoryReadinessEvaluation(
        organization_id=org_id,
        story_id=story.id,
        evaluated_for_user_id=user_id,
        triggered_by_id=user_id,
        readiness_score=result.readiness_score,
        readiness_state=ReadinessState(result.readiness_state),
        open_topics=[t.model_dump() for t in result.open_topics],
        missing_inputs=[m.model_dump() for m in result.missing_inputs],
        required_preparatory_work=[p.model_dump() for p in result.required_preparatory_work],
        dependencies=[d.model_dump() for d in result.dependencies],
        blockers=[b.model_dump() for b in result.blockers],
        risks=[r.model_dump() for r in result.risks],
        recommended_next_steps=[s.model_dump() for s in result.recommended_next_steps],
        summary=result.summary,
        confidence=result.confidence,
        model_used=model_used,
        story_snapshot={
            "title": ctx["title"],
            "description": ctx["description"][:500] if ctx["description"] else None,
            "acceptance_criteria": ctx["acceptance_criteria"][:500] if ctx["acceptance_criteria"] else None,
            "status": ctx["status"],
            "priority": ctx["priority"],
            "story_points": ctx["story_points"],
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
        error_message=error_message,
    )
    db.add(ev)
    await db.flush()
    return ev


# ── Public API ────────────────────────────────────────────────────────────────

async def evaluate_story_readiness(
    story: UserStory,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> StoryReadinessEvaluation:
    """
    Evaluate readiness for a single story and persist the result.
    Always creates a new versioned row — old evaluations are retained.
    """
    ctx = await collect_story_context(story, db)

    model_used = "unknown"
    error_message = None

    try:
        result, model_used, _, _ = await _call_llm(ctx)
    except Exception as exc:
        logger.exception("Readiness LLM call failed for story %s: %s", story.id, exc)
        # Persist a failed evaluation with default/empty data
        result = StoryReadinessResult(
            readiness_score=0,
            readiness_state="not_ready",
            summary=f"Bewertung fehlgeschlagen: {exc}",
        )
        error_message = str(exc)

    ev = await _persist_evaluation(
        story=story,
        user_id=user_id,
        org_id=org_id,
        result=result,
        ctx=ctx,
        model_used=model_used,
        db=db,
        error_message=error_message,
    )
    return ev


async def evaluate_assigned_user_stories(
    user_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
    story_ids: Optional[list[uuid.UUID]] = None,
) -> tuple[list[StoryReadinessEvaluation], int]:
    """
    Evaluate all stories assigned to (or created by) the user.

    Returns (evaluations, failed_count).
    If story_ids is provided, only those stories are evaluated.
    """
    query = (
        select(UserStory)
        .where(
            UserStory.organization_id == org_id,
            or_(
                UserStory.assignee_id == user_id,
                UserStory.created_by_id == user_id,
            ),
        )
        .where(UserStory.status.not_in(["done", "archived"]))
    )
    if story_ids:
        query = query.where(UserStory.id.in_(story_ids))

    result = await db.execute(query)
    stories = result.scalars().all()

    evaluations: list[StoryReadinessEvaluation] = []
    failed = 0

    for story in stories:
        try:
            ev = await evaluate_story_readiness(story, user_id, org_id, db)
            evaluations.append(ev)
        except Exception as exc:
            logger.exception("Failed to evaluate story %s: %s", story.id, exc)
            failed += 1

    await db.commit()
    return evaluations, failed


async def get_latest_readiness_for_stories(
    story_ids: list[uuid.UUID],
    org_id: uuid.UUID,
    db: AsyncSession,
) -> dict[uuid.UUID, StoryReadinessEvaluation]:
    """Return the most recent evaluation per story_id."""
    if not story_ids:
        return {}

    # Subquery: latest created_at per story
    from sqlalchemy import func
    sub = (
        select(
            StoryReadinessEvaluation.story_id,
            func.max(StoryReadinessEvaluation.created_at).label("latest"),
        )
        .where(
            StoryReadinessEvaluation.story_id.in_(story_ids),
            StoryReadinessEvaluation.organization_id == org_id,
        )
        .group_by(StoryReadinessEvaluation.story_id)
        .subquery()
    )

    rows = await db.execute(
        select(StoryReadinessEvaluation)
        .join(
            sub,
            (StoryReadinessEvaluation.story_id == sub.c.story_id)
            & (StoryReadinessEvaluation.created_at == sub.c.latest),
        )
    )
    return {ev.story_id: ev for ev in rows.scalars().all()}
