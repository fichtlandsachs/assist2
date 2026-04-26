"""Seed service for Conversation Engine configuration data."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import (
    AnswerSignal,
    ConversationProtocolArea,
    DialogProfile,
    PromptTemplate,
    QuestionBlock,
    ReadinessRule,
    StorySizingRule,
    ConversationRule,
)


# ── Dialog Profiles ─────────────────────────────────────────────────────────

DIALOG_PROFILES: list[dict[str, Any]] = [
    {
        "key": "exploration_default",
        "name": "Explorativ durchdenken",
        "description": "Freier Dialog zur Ideenklärung",
        "mode": "exploration",
        "tone": "friendly",
        "is_default": True,
        "is_active": True,
        "config_json": {
            "max_questions_per_round": 2,
            "use_protocol": True,
            "enable_fact_reuse": True,
            "enable_story_sizing": False,
            "enable_readiness_check": False,
        },
    },
    {
        "key": "story_builder",
        "name": "Story gemeinsam schärfen",
        "description": "Geführter Dialog zur User-Story-Erstellung",
        "mode": "story",
        "tone": "friendly",
        "is_default": False,
        "is_active": True,
        "config_json": {
            "max_questions_per_round": 3,
            "use_protocol": True,
            "enable_fact_reuse": True,
            "enable_story_sizing": True,
            "enable_readiness_check": True,
        },
    },
    {
        "key": "story_review",
        "name": "Story prüfen",
        "description": "Review und Bewertung bestehender Stories",
        "mode": "review",
        "tone": "analytical",
        "is_default": False,
        "is_active": True,
        "config_json": {
            "max_questions_per_round": 2,
            "use_protocol": True,
            "enable_fact_reuse": True,
            "enable_story_sizing": True,
            "enable_readiness_check": True,
        },
    },
]


# ── Protocol Areas ────────────────────────────────────────────────────────────

PROTOCOL_AREAS: list[dict[str, Any]] = [
    {"key": "context", "display_name": "Kontext", "description": "Projekt, Epic, Prozess oder Capability", "help_text": "Ordnet die Story fachlich ein.", "sort_order": 10, "is_required": True},
    {"key": "target_user", "display_name": "Nutzergruppe", "description": "Betroffene Rolle oder Nutzergruppe", "help_text": "Beschreibt, für wen die Story gedacht ist.", "sort_order": 20, "is_required": True},
    {"key": "problem", "display_name": "Problem", "description": "Aktueller Schmerzpunkt", "help_text": "Beschreibt, welches Problem gelöst werden soll.", "sort_order": 30, "is_required": True},
    {"key": "desired_outcome", "display_name": "Zielbild", "description": "Gewünschter Zielzustand", "help_text": "Beschreibt, wie es nach der Umsetzung funktionieren soll.", "sort_order": 40, "is_required": True},
    {"key": "business_value", "display_name": "Nutzen", "description": "Fachlicher Mehrwert", "help_text": "Warum lohnt sich die Umsetzung?", "sort_order": 50, "is_required": True},
    {"key": "scope", "display_name": "Scope", "description": "Enthaltene Anforderungen", "help_text": "Was gehört zur Story?", "sort_order": 60, "is_required": True},
    {"key": "out_of_scope", "display_name": "Out of Scope", "description": "Bewusst ausgeschlossene Inhalte", "help_text": "Was gehört ausdrücklich nicht dazu?", "sort_order": 70, "is_required": False},
    {"key": "acceptance_criteria", "display_name": "Akzeptanzkriterien", "description": "Prüfbare Kriterien", "help_text": "Woran erkennt man, dass die Story fertig ist?", "sort_order": 80, "is_required": True},
    {"key": "risks", "display_name": "Risiken", "description": "Fachliche oder technische Risiken", "help_text": "Welche Risiken müssen berücksichtigt werden?", "sort_order": 90, "is_required": False},
    {"key": "compliance", "display_name": "Compliance-Hinweise", "description": "Regulatorische oder interne Anforderungen", "help_text": "Welche Vorgaben, Nachweise oder Kontrollen sind relevant?", "sort_order": 100, "is_required": False},
    {"key": "dependencies", "display_name": "Abhängigkeiten", "description": "Systeme, Teams, Daten oder Entscheidungen", "help_text": "Was muss vorhanden sein, damit die Story umgesetzt werden kann?", "sort_order": 110, "is_required": False},
    {"key": "evidence", "display_name": "Nachweise", "description": "Dokumente, Links oder Entscheidungen", "help_text": "Welche Nachweise stützen diese Story?", "sort_order": 120, "is_required": False},
    {"key": "open_points", "display_name": "Offene Punkte", "description": "Noch ungeklärte Fragen", "help_text": "Welche Informationen fehlen noch?", "sort_order": 130, "is_required": False},
]


# ── Question Blocks ──────────────────────────────────────────────────────────

QUESTION_BLOCKS: list[dict[str, Any]] = [
    {
        "key": "ask_target_user",
        "category": "target_user",
        "label": "Für welche Nutzergruppe ist das gedacht?",
        "question_text": "Für welche Nutzergruppe oder Rolle ist diese Funktionalität gedacht?",
        "follow_up_text": "Welche spezifischen Berechtigungen oder Eigenschaften hat diese Nutzergruppe?",
        "priority": 1,
        "is_required": True,
        "is_active": True,
    },
    {
        "key": "ask_problem",
        "category": "problem",
        "label": "Welches Problem soll gelöst werden?",
        "question_text": "Welches konkrete Problem oder welchen Schmerzpunkt soll diese Story lösen?",
        "follow_up_text": "Wie wird das Problem aktuell gelöst? Was ist daran aufwendig oder fehleranfällig?",
        "priority": 1,
        "is_required": True,
        "is_active": True,
    },
    {
        "key": "ask_business_value",
        "category": "business_value",
        "label": "Welchen fachlichen Nutzen soll das bringen?",
        "question_text": "Welchen fachlichen Nutzen oder Mehrwert soll die Umsetzung bringen?",
        "follow_up_text": "Wird Zeit gespart, Qualität verbessert oder ein Risiko reduziert?",
        "priority": 2,
        "is_required": True,
        "is_active": True,
    },
    {
        "key": "ask_acceptance",
        "category": "acceptance_criteria",
        "label": "Woran erkennst du, dass es funktioniert?",
        "question_text": "Woran erkennst du, dass die Story erfolgreich umgesetzt ist?",
        "follow_up_text": "Welche konkreten Ergebnisse müssen sichtbar sein? Welche Fälle müssen geprüft werden?",
        "priority": 2,
        "is_required": True,
        "is_active": True,
    },
    {
        "key": "ask_scope",
        "category": "scope",
        "label": "Was soll in dieser Story enthalten sein?",
        "question_text": "Was soll konkret in dieser Story umgesetzt werden?",
        "follow_up_text": "Was gehört ausdrücklich nicht dazu (Out of Scope)?",
        "priority": 3,
        "is_required": True,
        "is_active": True,
    },
]


# ── Answer Signals ───────────────────────────────────────────────────────────

ANSWER_SIGNALS: list[dict[str, Any]] = [
    {
        "key": "signal_target_user",
        "fact_category": "target_user",
        "pattern_type": "keyword",
        "pattern": "Admin|OrgAdmin|Sachbearbeiter|Mitarbeiter|Reviewer|Nutzer|Benutzer|Rolle|Anwender",
        "confidence_boost": 0.75,
        "is_active": True,
    },
    {
        "key": "signal_problem",
        "fact_category": "problem",
        "pattern_type": "keyword",
        "pattern": "Problem|aktuell|heute|manuell|aufwendig|fehleranfällig|Schmerzpunkt|Herausforderung|Ist-Zustand",
        "confidence_boost": 0.70,
        "is_active": True,
    },
    {
        "key": "signal_desired_outcome",
        "fact_category": "desired_outcome",
        "pattern_type": "keyword",
        "pattern": "soll|Ziel|möchte|künftig|automatisch|Zielbild|Soll-Zustand|Ergebnis",
        "confidence_boost": 0.70,
        "is_active": True,
    },
    {
        "key": "signal_acceptance",
        "fact_category": "acceptance_criteria",
        "pattern_type": "keyword",
        "pattern": "wenn|dann|gegeben|sollte|muss anzeigen|muss speichern|Akzeptanz|Kriterium|Prüfung",
        "confidence_boost": 0.80,
        "is_active": True,
    },
    {
        "key": "signal_dependency",
        "fact_category": "dependencies",
        "pattern_type": "keyword",
        "pattern": "abhängig|braucht|vorausgesetzt|Schnittstelle|System|Abhängigkeit|Vorbedingung|Integration",
        "confidence_boost": 0.75,
        "is_active": True,
    },
]


# ── Conversation Rules ─────────────────────────────────────────────────────────

CONVERSATION_RULES: list[dict[str, Any]] = [
    {
        "key": "no_duplicate_questions",
        "rule_type": "dialog",
        "label": "Keine doppelten Fragen",
        "value_json": {"enabled": True, "description": "Bereits beantwortete Fragen dürfen nicht erneut gestellt werden."},
        "is_active": True,
    },
    {
        "key": "max_questions_per_turn",
        "rule_type": "dialog",
        "label": "Maximale Fragen pro Runde",
        "value_json": {"maxQuestions": 3, "description": "Pro Antwort sollen maximal drei Fragen gestellt werden."},
        "is_active": True,
    },
    {
        "key": "fact_reuse_required",
        "rule_type": "dialog",
        "label": "Fact-Reuse verpflichtend",
        "value_json": {"enabled": True, "description": "Bekannte Fakten müssen aktiv verwendet werden."},
        "is_active": True,
    },
    {
        "key": "no_hallucination_without_context",
        "rule_type": "safety",
        "label": "Keine Halluzination ohne Kontext",
        "value_json": {"enabled": True, "description": "Wenn kein Kontext vorhanden ist, muss dies transparent gesagt werden."},
        "is_active": True,
    },
    {
        "key": "ask_context_on_high_complexity",
        "rule_type": "context",
        "label": "Kontextfrage bei hoher Komplexität",
        "value_json": {"enabled": True, "description": "Bei umfangreichen Eingaben ohne Kontext wird nach Projekt, Epic oder Prozess gefragt."},
        "is_active": True,
    },
]


# ── Sizing Rules ──────────────────────────────────────────────────────────────

SIZING_RULES: list[dict[str, Any]] = [
    {
        "key": "multiple_user_groups",
        "label": "Mehrere Nutzergruppen",
        "dimension": "user_groups",
        "weight": 15.0,
        "thresholds_json": {"type": "count", "field": "target_user", "min": 2, "user_hint": "Ich erkenne mehrere Nutzergruppen. Das kann auf mehrere Stories hindeuten."},
        "is_active": True,
    },
    {
        "key": "multiple_functions",
        "label": "Mehrere Funktionen",
        "dimension": "functions",
        "weight": 25.0,
        "thresholds_json": {"type": "count", "field": "functions", "min": 2, "user_hint": "Ich erkenne mehrere Funktionen. Eine Aufteilung könnte sinnvoll sein."},
        "is_active": True,
    },
    {
        "key": "multiple_systems",
        "label": "Mehrere Systeme",
        "dimension": "systems",
        "weight": 15.0,
        "thresholds_json": {"type": "count", "field": "systems", "min": 2, "user_hint": "Mehrere Systeme sind beteiligt. Das erhöht die Umsetzungskomplexität."},
        "is_active": True,
    },
    {
        "key": "multiple_processes",
        "label": "Mehrere Prozesse",
        "dimension": "processes",
        "weight": 20.0,
        "thresholds_json": {"type": "count", "field": "processes", "min": 2, "user_hint": "Mehrere Prozesse sind betroffen. Ich prüfe eine sinnvolle Struktur."},
        "is_active": True,
    },
    {
        "key": "many_acceptance_criteria",
        "label": "Viele Akzeptanzkriterien",
        "dimension": "acceptance_criteria",
        "weight": 10.0,
        "thresholds_json": {"type": "count", "field": "acceptance_criteria", "min": 7, "user_hint": "Es entstehen viele Akzeptanzkriterien. Die Story könnte zu groß werden."},
        "is_active": True,
    },
]


# ── Readiness Rules ───────────────────────────────────────────────────────────

READINESS_RULES: list[dict[str, Any]] = [
    {
        "key": "has_target_user",
        "label": "Nutzergruppe vorhanden",
        "required_category": "target_user",
        "min_confidence": 0.6,
        "is_blocking": True,
        "weight": 15.0,
        "is_active": True,
    },
    {
        "key": "has_problem",
        "label": "Problem vorhanden",
        "required_category": "problem",
        "min_confidence": 0.6,
        "is_blocking": True,
        "weight": 15.0,
        "is_active": True,
    },
    {
        "key": "has_business_value",
        "label": "Nutzen vorhanden",
        "required_category": "business_value",
        "min_confidence": 0.6,
        "is_blocking": True,
        "weight": 15.0,
        "is_active": True,
    },
    {
        "key": "has_acceptance_criteria",
        "label": "Akzeptanzkriterien vorhanden",
        "required_category": "acceptance_criteria",
        "min_confidence": 0.6,
        "is_blocking": True,
        "weight": 20.0,
        "is_active": True,
    },
]


# ── Prompt Templates ───────────────────────────────────────────────────────────

PROMPT_TEMPLATES: list[dict[str, Any]] = [
    {
        "key": "fact_extraction_system",
        "mode": "story",
        "phase": "fact_extract",
        "prompt_text": """Du bist ein strukturierter Fact-Extractor für User Stories.

Aufgabe: Analysiere die Konversation und extrahiere strukturierte Fakten.

Kategorien:
- target_user: Wer nutzt die Funktion?
- problem: Welches Problem besteht aktuell?
- desired_outcome: Was soll erreicht werden?
- business_value: Welcher Nutzen entsteht?
- scope: Was gehört dazu?
- out_of_scope: Was gehört nicht dazu?
- acceptance_criteria: Testbare Kriterien?
- risks: Risiken?
- compliance: Regulatorisches?
- dependencies: Abhängigkeiten?

Antworte im JSON-Format:
{
  "facts": [
    {"category": "...", "value": "...", "confidence": 0.9}
  ]
}""",
        "is_active": True,
    },
    {
        "key": "question_planning_system",
        "mode": "story",
        "phase": "question_plan",
        "prompt_text": """Du bist ein Question Planner für User Stories.

Aufgabe: Plane die nächsten Fragen basierend auf:
1. Bekannte Fakten (nicht wiederholen)
2. Fehlende kritische Informationen
3. Maximale 2-3 Fragen pro Runde

Regeln:
- Frage nur, was wirklich fehlt
- Vermeide Duplikate
- Priorisiere: Nutzergruppe > Problem > Nutzen > Scope > ACs
- Formuliere freundlich und motivierend

Antworte im JSON-Format:
{
  "questions": [
    {"category": "...", "question": "...", "priority": 1, "reason": "..."}
  ]
}""",
        "is_active": True,
    },
]


async def seed_conversation_engine(db: AsyncSession) -> dict[str, int]:
    """Seed all conversation engine configuration data.
    
    Returns counts of created/updated items per category.
    """
    counts = {
        "dialog_profiles": 0,
        "protocol_areas": 0,
        "question_blocks": 0,
        "answer_signals": 0,
        "conversation_rules": 0,
        "sizing_rules": 0,
        "readiness_rules": 0,
        "prompt_templates": 0,
    }

    # ── Dialog Profiles ─────────────────────────────────────────────────────
    for data in DIALOG_PROFILES:
        stmt = select(DialogProfile).where(DialogProfile.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            profile = DialogProfile(**data)
            db.add(profile)
            counts["dialog_profiles"] += 1

    # ── Protocol Areas ────────────────────────────────────────────────────────
    for data in PROTOCOL_AREAS:
        stmt = select(ConversationProtocolArea).where(
            ConversationProtocolArea.key == data["key"],
            ConversationProtocolArea.org_id.is_(None)
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            area = ConversationProtocolArea(org_id=None, **data)
            db.add(area)
            counts["protocol_areas"] += 1

    # ── Question Blocks ───────────────────────────────────────────────────────
    for data in QUESTION_BLOCKS:
        stmt = select(QuestionBlock).where(QuestionBlock.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            block = QuestionBlock(**data)
            db.add(block)
            counts["question_blocks"] += 1

    # ── Answer Signals ────────────────────────────────────────────────────────
    for data in ANSWER_SIGNALS:
        stmt = select(AnswerSignal).where(AnswerSignal.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            signal = AnswerSignal(**data)
            db.add(signal)
            counts["answer_signals"] += 1

    # ── Conversation Rules ────────────────────────────────────────────────────
    for data in CONVERSATION_RULES:
        stmt = select(ConversationRule).where(ConversationRule.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            rule = ConversationRule(**data)
            db.add(rule)
            counts["conversation_rules"] += 1

    # ── Sizing Rules ─────────────────────────────────────────────────────────
    for data in SIZING_RULES:
        stmt = select(StorySizingRule).where(StorySizingRule.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            rule = StorySizingRule(**data)
            db.add(rule)
            counts["sizing_rules"] += 1

    # ── Readiness Rules ───────────────────────────────────────────────────────
    for data in READINESS_RULES:
        stmt = select(ReadinessRule).where(ReadinessRule.key == data["key"])
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            rule = ReadinessRule(**data)
            db.add(rule)
            counts["readiness_rules"] += 1

    # ── Prompt Templates ──────────────────────────────────────────────────────
    for data in PROMPT_TEMPLATES:
        stmt = select(PromptTemplate).where(
            PromptTemplate.key == data["key"],
            PromptTemplate.mode == data["mode"]
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing:
            template = PromptTemplate(**data)
            db.add(template)
            counts["prompt_templates"] += 1

    await db.commit()
    return counts
