# app/services/compliance_chat_service.py
"""
Compliance Chat Service.

Orchestrates the compliance dialogue:
  1. get_or_create_session   → find / initialize chat session for an assessment
  2. get_next_question       → pick next relevant question in plain language
  3. process_user_turn       → send user message to LLM, extract mappings,
                               update assessment items, generate assistant reply
  4. apply_mappings          → commit proposed score changes to AssessmentItems
  5. seed_chat_questions     → populate default ControlChatQuestion for all controls

The LLM system prompt enforces non-ISO language. All audit/governance logic
stays in the data layer; the chat surface is purely business/product language.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import openai as openai_sdk
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.compliance_assessment import (
    ComplianceAssessment, ComplianceAssessmentItem,
    ItemStatus, TrafficLight,
)
from app.models.control_chat_config import (
    ComplianceChatSession, ComplianceChatTurn, ComplianceChatMapping,
    ControlChatQuestion, SessionStatus, TurnRole,
)
from app.models.product_governance import ControlDefinition, ControlStatus
from app.models.user import User
from app.services.compliance_service import score_item, compute_assessment_summary

logger = logging.getLogger(__name__)


# ── System Prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_TEMPLATE = """\
Du bist ein intelligenter Produkt-, Risiko- und Governance-Assistent.

Deine Aufgabe ist es, wichtige Informationen über ein Produkt oder Projekt zu verstehen, 
um sicherzustellen, dass alle wesentlichen Aspekte durchdacht und bewertet sind.

Du sprichst mit Fachanwendern — Produktmanagern, Entwicklern, Einkäufern, Qualitätsmitarbeitern 
oder Führungskräften. Du klingst wie ein erfahrener Kollege oder Berater, nicht wie ein Auditor.

WICHTIGE VERHALTENSREGELN:
- Stelle immer nur 1–3 Fragen gleichzeitig, nie mehr.
- Knüpfe an das an, was der Nutzer gerade gesagt hat.
- Fasse bekannte Informationen kurz zusammen, bevor du weitergehst.
- Verwende KEINE der folgenden Begriffe oder ähnliche Formulierungen:
  * ISO 9001, ISO 27001, IEC, EN-Norm, Normkapitel
  * Kontrollziel, Pflichtkontrolle, Audit, Konformität
  * regulatorische Anforderung, normative Anforderung
  * Gate-Blocking-Control, Hard-Stop-Control
  * Compliance-Score, Assessment-Item
  * „wurde eine risikobasierte Bewertung durchgeführt?"
  * „sind gesetzliche und regulatorische Anforderungen identifiziert?"
- Spreche stattdessen in Begriffen wie:
  * wichtig für den Markteintritt
  * relevant für die Freigabe
  * noch nicht klar genug bewertet
  * hier fehlt noch ein belastbarer Nachweis
  * das könnte später teuer oder kritisch werden
  * dafür brauchen wir noch eine Bestätigung

GESPRÄCHSSTIL:
- Freundlich, direkt, fachkundig
- Kurze Antworten, gezielte Fragen
- Unsicherheiten benennen, aber nicht dramatisieren
- Bei klaren Antworten kurz bestätigen und weitergehen
- Bei unklaren Antworten sanft nachfragen

KONTEXT DES AKTUELLEN OBJEKTS:
{object_context}

BEKANNTE INFORMATIONEN AUS DEM BISHERIGEN GESPRÄCH:
{conversation_summary}

OFFENE BEREICHE, DIE NOCH NICHT AUSREICHEND GEKLÄRT SIND:
{open_areas}

AKTUELL RELEVANTE FRAGE(N) (intern, für deine Orientierung — nicht wörtlich übernehmen):
{current_questions}

AUFGABE FÜR DIESE ANTWORT:
{task_instruction}

Antworte immer auf Deutsch. Nutze Markdown sparsam, nur wenn es die Lesbarkeit verbessert.
"""

_MAPPING_EXTRACTION_PROMPT = """\
Du bist ein internes Analyse-System. Extrahiere aus der folgenden Nutzerantwort strukturierte Informationen.

NUTZERANTWORT:
{user_message}

OFFENE BEWERTUNGSBEREICHE (intern):
{open_controls_json}

AUFGABE:
Analysiere die Nutzerantwort und extrahiere für jeden relevanten Bereich:
1. Was kann bewertet werden (Score 0-3, wobei 3=gut beherrscht, 0=unklar/nicht bewertet)
2. Welche Kontextparameter lassen sich ableiten (z.B. Märkte, Kundengruppe, Technologie)
3. Ob Nachweise erwähnt wurden (vorhanden oder erforderlich)
4. Welche Bereiche noch offene Fragen haben

Antworte NUR als JSON in diesem Format:
{
  "control_mappings": [
    {
      "control_slug": "...",
      "proposed_score": 0-3,
      "rationale": "kurze Begründung auf Deutsch",
      "confidence": 0.0-1.0
    }
  ],
  "extracted_params": {
    "markets": [],
    "customer_type": "",
    "has_software": null,
    "criticality": "",
    "product_type": ""
  },
  "evidence_mentioned": [],
  "still_unclear": []
}
"""


# ── LLM caller ────────────────────────────────────────────────────────────────

def _get_llm_client():
    settings = get_settings()
    return openai_sdk.AsyncOpenAI(
        base_url=f"{settings.LITELLM_URL}/v1",
        api_key=settings.LITELLM_API_KEY or "sk-heykarl",
        timeout=60,
        max_retries=0,
    )


async def _call_llm(messages: list[dict], model: str = "ionos-fast", max_tokens: int = 800) -> str:
    client = _get_llm_client()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.4,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        logger.error("LLM call failed: %s", e)
        raise


# ── Session management ────────────────────────────────────────────────────────

async def get_or_create_session(
    db: AsyncSession,
    assessment: ComplianceAssessment,
    user: User,
) -> ComplianceChatSession:
    """Get active session or create a new one for this assessment."""
    session = await db.scalar(
        select(ComplianceChatSession).where(
            and_(
                ComplianceChatSession.assessment_id == assessment.id,
                ComplianceChatSession.status == SessionStatus.active.value,
            )
        )
    )
    if not session:
        session = ComplianceChatSession(
            assessment_id=assessment.id,
            org_id=assessment.org_id,
            user_id=user.id,
            status=SessionStatus.active.value,
            context_params=dict(assessment.context_params or {}),
        )
        db.add(session)
        await db.flush()

        # Initialize pending controls from open assessment items
        open_items = await _get_open_items(db, assessment.id)
        session.pending_control_ids = [str(i.control_id) for i in open_items[:20]]

        # Generate first question
        session.next_question = await _generate_opening_question(db, session, assessment)
        await db.flush()

    return session


async def _get_open_items(
    db: AsyncSession, assessment_id: uuid.UUID, limit: int = 30
) -> list[ComplianceAssessmentItem]:
    result = await db.execute(
        select(ComplianceAssessmentItem)
        .where(
            and_(
                ComplianceAssessmentItem.assessment_id == assessment_id,
                ComplianceAssessmentItem.score == 0,
            )
        )
        .order_by(
            ComplianceAssessmentItem.hard_stop.desc(),
            ComplianceAssessmentItem.default_weight.desc(),
        )
        .limit(limit)
    )
    return list(result.scalars().all())


async def _get_chat_question(
    db: AsyncSession, control_id: uuid.UUID
) -> Optional[ControlChatQuestion]:
    return await db.scalar(
        select(ControlChatQuestion).where(
            and_(
                ControlChatQuestion.control_id == control_id,
                ControlChatQuestion.is_active == True,
            )
        )
    )


# ── Question selection ────────────────────────────────────────────────────────

async def _generate_opening_question(
    db: AsyncSession,
    session: ComplianceChatSession,
    assessment: ComplianceAssessment,
) -> dict:
    """Build the first question grouping 2-3 high-priority open topics."""
    if not session.pending_control_ids:
        return {
            "text": "Gibt es noch offene Punkte, die du klären möchtest?",
            "type": "free_text",
            "control_ids": [],
        }

    # Grab top 3 open controls with chat config
    questions_text = []
    covered_ids = []
    for cid_str in session.pending_control_ids[:5]:
        try:
            cid = uuid.UUID(cid_str)
        except ValueError:
            continue
        cq = await _get_chat_question(db, cid)
        if cq:
            questions_text.append(cq.primary_question)
            covered_ids.append(cid_str)
        if len(covered_ids) >= 2:
            break

    if not questions_text:
        # Fallback: generic opener
        questions_text = [
            "Erzähl mir ein bisschen mehr über das Produkt: Wer nutzt es, wo wird es eingesetzt und was ist der Hauptnutzen für den Kunden?"
        ]

    combined = " Und außerdem: ".join(questions_text[:2])
    return {
        "text": combined,
        "type": "free_text",
        "control_ids": covered_ids[:2],
    }


async def get_next_question(
    db: AsyncSession,
    session: ComplianceChatSession,
    assessment: ComplianceAssessment,
) -> dict:
    """Select the next most relevant question based on session state."""
    if session.next_question:
        return session.next_question

    open_items = await _get_open_items(db, assessment.id)
    remaining = [
        i for i in open_items
        if str(i.control_id) not in session.addressed_control_ids
    ]

    if not remaining:
        return {
            "text": "Ich glaube, wir haben die wichtigsten Punkte besprochen. Gibt es noch etwas, das du für die Freigabe klären möchtest?",
            "type": "free_text",
            "control_ids": [],
            "is_closing": True,
        }

    # Pick top item
    item = remaining[0]
    cq = await _get_chat_question(db, item.control_id)
    question_text = cq.primary_question if cq else (
        item.what_to_check or
        f"Wie ist der Stand bei '{item.control_name}'?"
    )

    # Optionally bundle a second related question
    second_text = None
    if len(remaining) > 1:
        item2 = remaining[1]
        cq2 = await _get_chat_question(db, item2.control_id)
        if cq2 and cq2.question_priority <= 40:
            second_text = cq2.primary_question

    combined = question_text
    ids = [str(item.control_id)]
    if second_text and len(combined) < 120:
        combined += f" Außerdem: {second_text}"
        ids.append(str(remaining[1].control_id))

    return {"text": combined, "type": "free_text", "control_ids": ids}


# ── Main turn processing ──────────────────────────────────────────────────────

async def process_user_turn(
    db: AsyncSession,
    session: ComplianceChatSession,
    assessment: ComplianceAssessment,
    user_message: str,
    user: User,
) -> dict:
    """
    Handle one user turn:
    1. Store user turn
    2. Extract mapping from message via LLM
    3. Generate assistant reply via LLM
    4. Store assistant turn + mappings
    5. Update session state
    6. Return reply + meta
    """
    # 1. Store user turn
    turn_index = session.turn_count
    user_turn = ComplianceChatTurn(
        session_id=session.id,
        turn_index=turn_index,
        role=TurnRole.user.value,
        content=user_message,
        control_ids=session.next_question.get("control_ids", []) if session.next_question else [],
        extracted_params={},
    )
    db.add(user_turn)
    session.turn_count = turn_index + 2
    await db.flush()

    # 2. Build conversation history for LLM
    history = await _build_history(db, session.id)

    # 3. Identify open controls for mapping extraction
    open_items = await _get_open_items(db, assessment.id, limit=15)
    open_controls_json = json.dumps([
        {
            "slug": i.control_slug,
            "name": i.control_name,
            "category": i.category_name,
            "current_score": i.score,
            "hard_stop": i.hard_stop,
        }
        for i in open_items
    ], ensure_ascii=False)

    # 4. Extract mappings (structured, low-temperature call)
    mappings_data = await _extract_mappings(user_message, open_controls_json)

    # 5. Update session context params
    extracted_params = mappings_data.get("extracted_params", {})
    merged_params = {**session.context_params}
    for k, v in extracted_params.items():
        if v is not None and v != "" and v != []:
            merged_params[k] = v
    session.context_params = merged_params
    user_turn.extracted_params = extracted_params

    # 6. Determine which controls can now be marked addressed
    newly_addressed = []
    for cm in mappings_data.get("control_mappings", []):
        if cm.get("proposed_score", 0) >= 2:
            slug = cm["control_slug"]
            for item in open_items:
                if item.control_slug == slug:
                    newly_addressed.append(str(item.control_id))
                    break

    addressed = list(session.addressed_control_ids or [])
    addressed.extend(newly_addressed)
    session.addressed_control_ids = list(set(addressed))

    # 7. Store mapping rows
    for cm in mappings_data.get("control_mappings", []):
        ctrl = await db.scalar(
            select(ControlDefinition).where(ControlDefinition.slug == cm["control_slug"])
        )
        if ctrl:
            mapping = ComplianceChatMapping(
                session_id=session.id,
                turn_id=user_turn.id,
                control_id=ctrl.id,
                control_slug=cm["control_slug"],
                proposed_score=min(3, max(0, cm.get("proposed_score", 0))),
                rationale=cm.get("rationale"),
                trigger_params=extracted_params,
                confidence=cm.get("confidence", 0.7),
            )
            db.add(mapping)

    # 8. Build conversation summary (rolling)
    session.conversation_summary = _update_summary(
        session.conversation_summary, user_message, extracted_params
    )

    # 9. Generate next question
    remaining_open = [
        i for i in open_items
        if str(i.control_id) not in session.addressed_control_ids
    ]

    # 10. Build assistant reply via LLM
    open_areas = _format_open_areas(remaining_open[:5])
    next_qs = await get_next_question(db, session, assessment)
    session.next_question = next_qs

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        object_context=_format_object_context(assessment),
        conversation_summary=session.conversation_summary or "Noch kein Gesprächskontext.",
        open_areas=open_areas,
        current_questions=next_qs["text"],
        task_instruction=(
            "Antworte auf die letzte Nutzerantwort: bestätige kurz, was klar ist, "
            "benenne offen Gebliebenes in normaler Sprache, und stelle dann die nächste "
            "Frage bzw. die nächsten 1–2 Fragen aus 'AKTUELL RELEVANTE FRAGE(N)'."
        ),
    )

    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": user_message}
    ]

    assistant_reply = await _call_llm(messages, max_tokens=600)

    # 11. Store assistant turn
    assistant_turn = ComplianceChatTurn(
        session_id=session.id,
        turn_index=turn_index + 1,
        role=TurnRole.assistant.value,
        content=assistant_reply,
        control_ids=next_qs.get("control_ids", []),
        extracted_params={},
    )
    db.add(assistant_turn)
    await db.flush()

    # 12. Build fachanwender-friendly gap summary
    gap_summary = _build_gap_summary(open_items, session.addressed_control_ids)

    return {
        "reply": assistant_reply,
        "next_question": next_qs,
        "gap_summary": gap_summary,
        "addressed_count": len(session.addressed_control_ids),
        "remaining_count": len(remaining_open),
        "extracted_params": extracted_params,
        "session_id": str(session.id),
    }


async def _build_history(db: AsyncSession, session_id: uuid.UUID) -> list[dict]:
    result = await db.execute(
        select(ComplianceChatTurn)
        .where(ComplianceChatTurn.session_id == session_id)
        .order_by(ComplianceChatTurn.turn_index)
        .limit(20)
    )
    turns = result.scalars().all()
    history = []
    for t in turns:
        if t.role in (TurnRole.user.value, TurnRole.assistant.value):
            history.append({"role": t.role, "content": t.content})
    return history[-16:]  # Keep last 8 exchanges for context window


async def _extract_mappings(user_message: str, open_controls_json: str) -> dict:
    prompt = _MAPPING_EXTRACTION_PROMPT.format(
        user_message=user_message,
        open_controls_json=open_controls_json,
    )
    try:
        raw = await _call_llm(
            [{"role": "user", "content": prompt}],
            model="ionos-fast",
            max_tokens=1000,
        )
        # Extract JSON from response
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        logger.warning("Mapping extraction failed: %s", e)
    return {"control_mappings": [], "extracted_params": {}, "evidence_mentioned": [], "still_unclear": []}


def _update_summary(
    current: Optional[str], user_message: str, extracted: dict
) -> str:
    parts = []
    if current:
        parts.append(current)
    if extracted.get("markets"):
        parts.append(f"Zielmärkte: {', '.join(extracted['markets'])}")
    if extracted.get("customer_type"):
        parts.append(f"Kundengruppe: {extracted['customer_type']}")
    if extracted.get("criticality"):
        parts.append(f"Kritikalität: {extracted['criticality']}")
    if extracted.get("has_software") is True:
        parts.append("Software/Firmware beteiligt: ja")
    if extracted.get("product_type"):
        parts.append(f"Produktart: {extracted['product_type']}")
    return " | ".join(parts[-8:])  # Keep summary compact


def _format_object_context(assessment: ComplianceAssessment) -> str:
    ctx = assessment.context_params or {}
    parts = [f"Objekt: {assessment.object_name} ({assessment.object_type})"]
    for k, v in ctx.items():
        if v:
            parts.append(f"{k}: {v}")
    return ", ".join(parts)


def _format_open_areas(items: list[ComplianceAssessmentItem]) -> str:
    if not items:
        return "Keine offenen Bereiche mehr."
    return "\n".join([
        f"- {i.control_name} (Kategorie: {i.category_name or '–'})"
        + (" [KRITISCH]" if i.hard_stop else "")
        for i in items
    ])


def _build_gap_summary(
    all_items: list[ComplianceAssessmentItem],
    addressed_ids: list[str],
) -> list[dict]:
    """
    Build user-friendly gap list without governance language.
    Maps ControlChatQuestion.gap_label_template if available,
    otherwise generates a plain description.
    """
    gaps = []
    for item in all_items:
        if str(item.control_id) in addressed_ids:
            continue
        if item.score > 0:
            continue
        # Plain-language gap label
        label = _plain_gap_label(item)
        gaps.append({
            "control_id": str(item.control_id),
            "control_slug": item.control_slug,
            "label": label,
            "is_critical": item.hard_stop and item.blocks_gate,
            "gate_phases": item.gate_phases,
        })
    return gaps[:10]


def _plain_gap_label(item: ComplianceAssessmentItem) -> str:
    """Map control category / name to user-friendly gap label."""
    name = (item.control_name or "").lower()
    cat = (item.category_name or "").lower()

    if "markt" in name or "regulat" in name or "marktzugang" in cat:
        return "Für den Markteintritt fehlen noch belastbare Angaben zu Zielmärkten und Anforderungen."
    if "qualit" in name or "zuverlässig" in name:
        return "Das Ausfallrisiko und die Produktzuverlässigkeit sind noch nicht ausreichend bewertet."
    if "beschaff" in name or "lieferant" in name:
        return "Die Lieferkette wirkt noch zu abhängig von einzelnen Quellen — hier fehlt eine Absicherung."
    if "software" in name or "firmware" in name or "cyber" in name:
        return "Der Software- und Sicherheitsaspekt ist noch nicht abschließend bewertet."
    if "service" in name or "support" in name:
        return "Wie aufwendig Support und Installation werden, ist noch nicht klar genug durchdacht."
    if "wirtschaft" in name or "kosten" in name or "finanz" in name:
        return "Die wirtschaftliche Absicherung ist noch nicht vollständig durchgerechnet."
    if "nachweis" in name or "test" in name or "prüf" in name:
        return "Hier fehlen noch belastbare Nachweise oder Testergebnisse."
    if "risiko" in name or "risk" in name:
        return "Für eine Freigabe ist das Risiko noch nicht ausreichend bewertet."
    if item.hard_stop:
        return f"Wichtig für die Freigabe: '{item.control_name}' ist noch offen und muss vor der Freigabe geklärt werden."
    return f"Der Bereich '{item.control_name}' ist noch nicht ausreichend bewertet."


# ── Apply mappings ────────────────────────────────────────────────────────────

async def apply_pending_mappings(
    db: AsyncSession,
    session: ComplianceChatSession,
    assessment: ComplianceAssessment,
    user: User,
    min_confidence: float = 0.6,
) -> int:
    """
    Apply all un-applied mappings with sufficient confidence to
    AssessmentItems via the compliance_service.score_item().
    Returns count of applied mappings.
    """
    result = await db.execute(
        select(ComplianceChatMapping).where(
            and_(
                ComplianceChatMapping.session_id == session.id,
                ComplianceChatMapping.applied == False,
                ComplianceChatMapping.confidence >= min_confidence,
                ComplianceChatMapping.proposed_score > 0,
            )
        )
    )
    mappings = result.scalars().all()
    applied = 0

    for mapping in mappings:
        item = await db.scalar(
            select(ComplianceAssessmentItem).where(
                and_(
                    ComplianceAssessmentItem.assessment_id == assessment.id,
                    ComplianceAssessmentItem.control_id == mapping.control_id,
                )
            )
        )
        if item and item.score < mapping.proposed_score:
            await score_item(
                db, item, mapping.proposed_score,
                mapping.rationale, None, user
            )
            mapping.applied = True
            mapping.applied_at = datetime.now(timezone.utc)
            applied += 1

    if applied > 0:
        await compute_assessment_summary(db, assessment)

    await db.flush()
    return applied


# ── Seed chat questions ───────────────────────────────────────────────────────

# Default chat question configs for the 24 fixed controls (by slug pattern)
_DEFAULT_QUESTIONS: list[dict] = [
    {
        "slug_pattern": "market",
        "primary_question": "In welchen Ländern oder Märkten soll das Produkt verkauft werden? Gibt es Regionen, in denen ihr mit besonderen Anforderungen rechnet?",
        "answer_type": "free_text",
        "priority": 10,
        "always_ask": True,
        "gap_label": "Für den Markteintritt fehlen noch belastbare Angaben zu Zielmärkten und Anforderungen.",
        "risk_label": "Hier ist noch Risiko offen: Marktanforderungen sind nicht vollständig bekannt.",
        "followups": [
            {"trigger_condition": {"field": "markets", "op": "eq", "value": []},
             "question": "Gibt es schon eine grobe Vorstellung, welche Märkte zuerst adressiert werden sollen?"},
        ],
    },
    {
        "slug_pattern": "qualit",
        "primary_question": "Wie sicher seid ihr aktuell, dass das Produkt im Alltag stabil und zuverlässig läuft? Gab es in Tests oder Piloten schon auffällige Probleme?",
        "answer_type": "free_text",
        "priority": 15,
        "always_ask": True,
        "gap_label": "Das Ausfallrisiko und die Produktzuverlässigkeit sind noch nicht ausreichend bewertet.",
        "risk_label": "Noch offenes Risiko: Produktzuverlässigkeit im Feld nicht belegt.",
    },
    {
        "slug_pattern": "beschaff",
        "primary_question": "Gibt es Bauteile oder Lieferanten, von denen ihr stark abhängig seid? Wie schnell hättet ihr Ersatz, wenn ein wichtiger Lieferant ausfällt?",
        "answer_type": "free_text",
        "priority": 20,
        "gap_label": "Die Lieferkette wirkt noch zu abhängig von einzelnen Quellen.",
    },
    {
        "slug_pattern": "software",
        "primary_question": "Ist am Produkt Software, Firmware oder eine App beteiligt? Falls ja: Wie wird sichergestellt, dass diese sicher und aktuell bleibt?",
        "answer_type": "yes_no",
        "priority": 25,
        "gap_label": "Der Software- und Sicherheitsaspekt ist noch nicht abschließend bewertet.",
    },
    {
        "slug_pattern": "service",
        "primary_question": "Wie aufwendig wird Support und Installation voraussichtlich? Rechnet ihr damit, dass viele Kunden Rückfragen haben werden?",
        "answer_type": "free_text",
        "priority": 30,
        "gap_label": "Wie aufwendig Support und Installation werden, ist noch nicht ausreichend eingeschätzt.",
    },
    {
        "slug_pattern": "wirtschaft",
        "primary_question": "Ist das Produkt wirtschaftlich sauber durchgerechnet? Wo seht ihr aktuell das größte Kostenrisiko?",
        "answer_type": "free_text",
        "priority": 35,
        "gap_label": "Die wirtschaftliche Absicherung ist noch nicht vollständig durchgerechnet.",
    },
    {
        "slug_pattern": "risiko",
        "primary_question": "Wie kritisch wäre ein Ausfall für den Kunden? Gibt es Einsatzfälle, bei denen ein Fehler schnell teuer oder kritisch wird?",
        "answer_type": "free_text",
        "priority": 12,
        "always_ask": True,
        "gap_label": "Für eine Freigabe ist das Ausfallrisiko noch nicht ausreichend bewertet.",
    },
    {
        "slug_pattern": "nachweis",
        "primary_question": "Welche Tests, Freigaben oder Prüfergebnisse liegen schon vor? Gibt es Bereiche, bei denen ihr euch noch nicht sicher seid?",
        "answer_type": "free_text",
        "priority": 40,
        "gap_label": "Hier fehlen noch belastbare Nachweise oder Testergebnisse.",
    },
    {
        "slug_pattern": "cyber",
        "primary_question": "Gibt es Schnittstellen oder Funktionen, bei denen Datensicherheit oder Datenschutz eine Rolle spielt? Wurden diese schon überprüft?",
        "answer_type": "free_text",
        "priority": 18,
        "gap_label": "Datensicherheit und Datenschutz sind noch nicht ausreichend bewertet.",
    },
    {
        "slug_pattern": "umwelt",
        "primary_question": "Gibt es Umwelt- oder Entsorgungsanforderungen für das Produkt, z. B. bei Batterien, Elektronik oder Verpackung?",
        "answer_type": "free_text",
        "priority": 50,
        "gap_label": "Umwelt- und Entsorgungsanforderungen sind noch nicht vollständig bewertet.",
    },
]

_GENERIC_QUESTION = {
    "primary_question": "Was ist aus deiner Sicht noch der offenste oder riskanteste Punkt bei diesem Produkt vor einer Freigabe?",
    "answer_type": "free_text",
    "priority": 99,
    "gap_label": "Es gibt noch offene Bereiche, die vor einer Freigabe geklärt werden müssen.",
}


async def seed_chat_questions(db: AsyncSession) -> int:
    """
    For every ControlDefinition without a ControlChatQuestion, create a default one.
    Uses slug pattern matching from _DEFAULT_QUESTIONS, falls back to generic.
    Returns count of created entries.
    """
    result = await db.execute(select(ControlDefinition))
    all_controls = result.scalars().all()
    created = 0

    for ctrl in all_controls:
        existing = await _get_chat_question(db, ctrl.id)
        if existing:
            continue

        # Find matching template by slug pattern
        template = _GENERIC_QUESTION
        for tpl in _DEFAULT_QUESTIONS:
            if tpl["slug_pattern"] in ctrl.slug.lower() or tpl["slug_pattern"] in (ctrl.control_objective or "").lower():
                template = tpl
                break

        cq = ControlChatQuestion(
            control_id=ctrl.id,
            primary_question=template["primary_question"],
            answer_type=template.get("answer_type", "free_text"),
            question_priority=template.get("priority", 99),
            always_ask=template.get("always_ask", False),
            gap_label_template=template.get("gap_label"),
            risk_label_template=template.get("risk_label"),
            followup_questions=template.get("followups", []),
            forbidden_terms=[
                "ISO 9001", "Normkapitel", "Audit", "regulatorische Anforderung",
                "Kontrollziel", "Gate-Blocking", "Hard-Stop-Control",
                "Assessment-Item", "Compliance-Score",
            ],
            score_mapping_rules=[
                {"match_type": "sentiment", "match_value": "positive", "score": 3},
                {"match_type": "keyword", "match_value": "noch nicht", "score": 1},
                {"match_type": "keyword", "match_value": "unklar", "score": 1},
                {"match_type": "keyword", "match_value": "offen", "score": 1},
                {"match_type": "keyword", "match_value": "vorhanden", "score": 2},
                {"match_type": "keyword", "match_value": "abgeschlossen", "score": 3},
            ],
        )
        db.add(cq)
        created += 1

    await db.flush()
    return created
