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

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context_analyzer import analyze_context
from app.ai.complexity_scorer import score_complexity
from app.ai.pipeline import execute_pipeline
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
        "target_audience": getattr(story, "target_audience", None) or "",
        "doc_version": getattr(story, "doc_version", None) or "",
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

_SYSTEM_PROMPT = """Du bist Karl, ein Product-Owner-Assistent. Analysiere User Stories auf Umsetzungsreife.
Erfinde KEINE Informationen. Unterscheide: documented|inferred|unknown.
Antworte ausschließlich mit einem validen JSON-Objekt, kein Markdown."""


def _story_content_hash(ctx: dict) -> str:
    """Short hash of the story fields that drive the evaluation. Used for cache invalidation."""
    relevant = {
        "title": ctx.get("title") or "",
        "description": ctx.get("description") or "",
        "acceptance_criteria": ctx.get("acceptance_criteria") or "",
        "target_audience": ctx.get("target_audience") or "",
        "dod": ctx.get("definition_of_done") or [],
    }
    raw = json.dumps(relevant, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _build_evaluation_prompt(ctx: dict) -> str:
    epic_block = ""
    if ctx.get("epic_title"):
        epic_block = f"\nEpic: {ctx['epic_title']}"
        if ctx.get("epic_description"):
            epic_block += f" — {ctx['epic_description']}"
        epic_block += "\n"

    dod_block = ""
    if ctx.get("definition_of_done"):
        dod_block = "\nDoD: " + " | ".join(ctx["definition_of_done"]) + "\n"

    ta_display = ctx.get("target_audience") or "(FEHLT)"
    dv_display = ctx.get("doc_version") or "(FEHLT)"

    return f"""Bewerte diese User Story auf Umsetzungsreife.

## Story

Titel: {ctx['title']}
Status: {ctx['status']} | Priorität: {ctx['priority']} | Points: {ctx.get('story_points') or '–'}
Zielgruppe: {ta_display} | Version: {dv_display}

Beschreibung:
{ctx['description'] or '(FEHLT)'}

Akzeptanzkriterien:
{ctx['acceptance_criteria'] or '(FEHLT)'}
{epic_block}{dod_block}
## Dimensionen

1. Zielgruppe — konkret/spezifisch? Fehlt→max 60. Vage→max 70.
2. „Als…möchte…damit…"-Format und Zielklarheit
3. Businessnutzen — echter Outcome (messbar, wer profitiert wie) oder nur Output? Fehlt→max 55. Output/vage→max 70.
4. Akzeptanzkriterien — messbar und testbar?
5. Offene fachliche/technische Fragen
6. Abhängigkeiten und Vorbedingungen
7. Benötigte Zuarbeiten anderer Teams/Rollen
8. Blockers (verhindert Start)
9. Risiken (gefährdet Umsetzung)

Score 0–100: not_ready(0–40)|partially_ready(41–60)|mostly_ready(61–80)|implementation_ready(81–100)
Constraints: Zielgruppe fehlt→≤60 | vage→≤70 | Businessnutzen fehlt→≤55 | Output/vage→≤70

## JSON

{{
  "readiness_score": <0-100>,
  "readiness_state": "<not_ready|partially_ready|mostly_ready|implementation_ready>",
  "open_topics": [{{"topic":"...","source":"documented|inferred|unknown","detail":"..."}}],
  "missing_inputs": [{{"input":"...","importance":"high|medium|low"}}],
  "required_preparatory_work": [{{"task":"...","owner":"...","urgency":"high|medium|low"}}],
  "dependencies": [{{"name":"...","type":"technical|business|team|external","status":"resolved|pending|unknown"}}],
  "blockers": [{{"description":"...","severity":"critical|major|minor"}}],
  "risks": [{{"description":"...","probability":"high|medium|low","impact":"high|medium|low"}}],
  "recommended_next_steps": [{{"step":"...","priority":<1-10>,"responsible":"..."}}],
  "summary": "...",
  "confidence": <0.0-1.0>
}}
"""


# ── LLM call ──────────────────────────────────────────────────────────────────

async def _call_llm(ctx: dict, user_id: uuid.UUID) -> tuple[StoryReadinessResult, str, int, int]:
    """Return (result, model_used, input_tokens, output_tokens).

    *user_id* is forwarded to the LLM provider as the ``user`` attribution
    field so that LiteLLM / IONOS can track usage per triggering user.
    """
    story_context = analyze_context(
        title=ctx["title"],
        description=ctx["description"],
        acceptance_criteria=ctx["acceptance_criteria"],
        target_audience=ctx.get("target_audience"),
    )
    complexity = score_complexity(story_context)

    from app.services.ai_story_service import _make_client
    client, provider = _make_client("story")
    decision = route_request(complexity, "evaluate", provider=provider)
    user_prompt = _build_evaluation_prompt(ctx)
    full_prompt = f"{_SYSTEM_PROMPT}\n\n{user_prompt}"

    raw, usage = await execute_pipeline(client, full_prompt, decision, user=str(user_id))

    # Robust JSON extraction
    result = _parse_result(raw)
    return result, decision.model, usage["input_tokens"], usage["output_tokens"]


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

    # Hard-enforce structural constraints regardless of LLM score
    missing = [m.get("input", "").lower() for m in data.get("missing_inputs", [])]
    missing_str = " ".join(missing)

    # Zielgruppe constraint — highest priority (same level as Dokumentensteuerung)
    missing_zielgruppe = any(
        k in missing_str for k in ("zielgruppe", "target_audience", "zielgruppen")
    )
    if missing_zielgruppe and score > 60:
        score = 60  # missing Zielgruppe caps at partially_ready

    # Businessnutzen constraint
    vague_nutzen = any(
        k in missing_str for k in ("businessnutzen", "outcome", "nutzen", "mehrwert")
    )
    if vague_nutzen and score > 70:
        score = 70  # vague/missing Businessnutzen caps at mostly_ready boundary

    state = data.get("readiness_state", _score_to_state(score).value)
    # Normalise state to enum value
    valid_states = {"not_ready", "partially_ready", "mostly_ready", "implementation_ready"}
    if state not in valid_states:
        state = _score_to_state(score).value
    # Re-derive state from capped score to stay consistent
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
            "content_hash": _story_content_hash(ctx),
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
    force_refresh: bool = False,
) -> StoryReadinessEvaluation:
    """
    Evaluate readiness for a single story and persist the result.
    Always creates a new versioned row — old evaluations are retained.

    If force_refresh=False and the story content hasn't changed since the last
    evaluation, the cached result is returned without an LLM call.
    """
    ctx = await collect_story_context(story, db)
    current_hash = _story_content_hash(ctx)

    if not force_refresh:
        # Check for a cached evaluation with the same content hash
        cached_res = await db.execute(
            select(StoryReadinessEvaluation)
            .where(
                StoryReadinessEvaluation.story_id == story.id,
                StoryReadinessEvaluation.organization_id == org_id,
                StoryReadinessEvaluation.error_message.is_(None),
            )
            .order_by(StoryReadinessEvaluation.created_at.desc())
            .limit(1)
        )
        latest = cached_res.scalar_one_or_none()
        if latest and (latest.story_snapshot or {}).get("content_hash") == current_hash:
            logger.debug("Cache hit for story %s (hash=%s)", story.id, current_hash)
            return latest

    model_used = "unknown"
    error_message = None

    try:
        result, model_used, _, _ = await _call_llm(ctx, user_id)
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
