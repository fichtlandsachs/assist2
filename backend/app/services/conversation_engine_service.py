# app/services/conversation_engine_service.py
"""Conversation Engine core logic: Fact extraction, Question Planner, Story Sizing, Readiness."""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.conversation_engine import (
    AnswerSignal,
    ConversationFact,
    ConversationSession,
    QuestionBlock,
    ReadinessRule,
    StorySizingRule,
    PromptTemplate,
    ConversationRule,
)

logger = logging.getLogger(__name__)

# ── Fact categories ───────────────────────────────────────────────────────────
FACT_CATEGORIES = [
    "context",        # project, epic, capability, process
    "user_group",     # who uses it
    "problem",        # what problem is solved
    "benefit",        # what value it creates
    "scope",          # what is IN scope
    "out_of_scope",   # what is NOT in scope
    "acceptance_criterion",  # testable condition
    "risk",           # known risk
    "compliance",     # regulatory / compliance note
    "dependency",     # system or team dependency
    "evidence",       # proof / artefact reference
    "open_question",  # unresolved point
]

# ── Built-in seed data ────────────────────────────────────────────────────────

SEED_DIALOG_PROFILES = [
    {
        "key": "default_story",
        "name": "Story-Erstellung (Standard)",
        "description": "Freundlicher, strukturierter Dialog zur User Story Erstellung.",
        "mode": "story_mode",
        "tone": "friendly",
        "is_default": True,
        "config_json": {"max_questions_per_turn": 2, "fact_reuse": True, "sizing_active": True},
    },
    {
        "key": "exploration",
        "name": "Explorativer Dialog",
        "description": "Freie Ideenfindung ohne Zwang zur sofortigen Story.",
        "mode": "exploration_mode",
        "tone": "open",
        "is_default": False,
        "config_json": {"max_questions_per_turn": 3, "fact_reuse": True, "sizing_active": False},
    },
    {
        "key": "review",
        "name": "Review & Bewertung",
        "description": "Bewertung bestehender Artefakte.",
        "mode": "review_mode",
        "tone": "analytical",
        "is_default": False,
        "config_json": {"max_questions_per_turn": 1, "fact_reuse": True, "sizing_active": True},
    },
]

SEED_QUESTION_BLOCKS = [
    # context
    {"key": "q_project", "category": "context", "label": "Projektbezug", "priority": 1, "is_required": True,
     "question_text": "Arbeitest du in einem bestehenden Projekt oder soll ich eines anlegen?"},
    {"key": "q_epic", "category": "context", "label": "Epic-Bezug", "priority": 2, "is_required": False,
     "question_text": "Gibt es bereits ein Epic, zu dem diese Story geh\u00f6rt?"},
    {"key": "q_process", "category": "context", "label": "Prozessbezug", "priority": 3, "is_required": False,
     "question_text": "Welchem Gesch\u00e4ftsprozess ordnest du diese \u00c4nderung zu?"},
    # user_group
    {"key": "q_user_group", "category": "user_group", "label": "Nutzergruppe", "priority": 1, "is_required": True,
     "question_text": "F\u00fcr wen soll das funktionieren? Welche Nutzergruppe oder Rolle ist gemeint?"},
    {"key": "q_user_count", "category": "user_group", "label": "Nutzeranzahl", "priority": 4, "is_required": False,
     "question_text": "Wie viele Nutzer sind betroffen? Das hilft mir die Gr\u00f6\u00dfe besser einzusch\u00e4tzen."},
    # problem
    {"key": "q_problem", "category": "problem", "label": "Problem", "priority": 1, "is_required": True,
     "question_text": "Was ist das konkrete Problem oder der Bedarf? Was funktioniert heute nicht so wie es sollte?"},
    {"key": "q_current_workaround", "category": "problem", "label": "Aktueller Workaround", "priority": 5,
     "question_text": "Wie l\u00f6sen Nutzer das Problem heute? Gibt es Workarounds?"},
    # benefit
    {"key": "q_benefit", "category": "benefit", "label": "Nutzen", "priority": 1, "is_required": True,
     "question_text": "Welchen Nutzen bringt die L\u00f6sung? Was verbessert sich konkret?"},
    {"key": "q_measurable", "category": "benefit", "label": "Messbarkeit", "priority": 4,
     "question_text": "Kannst du den Nutzen messen? Gibt es eine Kennzahl oder ein Ziel?"},
    # scope
    {"key": "q_scope", "category": "scope", "label": "Scope", "priority": 2, "is_required": True,
     "question_text": "Was soll genau abgedeckt werden? Gibt es Grenzen die du jetzt schon kennst?"},
    {"key": "q_out_of_scope", "category": "out_of_scope", "label": "Out of Scope", "priority": 3,
     "question_text": "Was geh\u00f6rt ausdr\u00fccklich NICHT dazu?"},
    # acceptance_criterion
    {"key": "q_ac", "category": "acceptance_criterion", "label": "Akzeptanzkriterien", "priority": 2, "is_required": True,
     "question_text": "Woran erkennst du, dass die Story fertig und korrekt umgesetzt ist? Was muss testbar sein?"},
    # risk
    {"key": "q_risk", "category": "risk", "label": "Risiken", "priority": 3,
     "question_text": "Gibt es Risiken oder Abh\u00e4ngigkeiten zu anderen Systemen, Teams oder Prozessen?"},
    # compliance
    {"key": "q_compliance", "category": "compliance", "label": "Compliance", "priority": 4,
     "question_text": "Gibt es regulatorische Anforderungen oder Datenschutzaspekte die ber\u00fccksichtigt werden m\u00fcssen?"},
]

SEED_ANSWER_SIGNALS = [
    {"key": "sig_als_nutzer", "fact_category": "user_group", "pattern_type": "keyword",
     "pattern": "als (nutzer|anwender|admin|manager|mitarbeiter|kunde)", "confidence_boost": 0.3},
    {"key": "sig_ich_moechte", "fact_category": "benefit", "pattern_type": "keyword",
     "pattern": "ich m\u00f6chte|ich will|wir brauchen|damit ich|sodass", "confidence_boost": 0.2},
    {"key": "sig_problem", "fact_category": "problem", "pattern_type": "keyword",
     "pattern": "problem|fehler|funktioniert nicht|schwierig|umst\u00e4ndlich|issue|bug", "confidence_boost": 0.25},
    {"key": "sig_scope", "fact_category": "scope", "pattern_type": "keyword",
     "pattern": "soll enthalten|m\u00fcssen|folgendes|umfasst|beinhaltet", "confidence_boost": 0.2},
    {"key": "sig_oos", "fact_category": "out_of_scope", "pattern_type": "keyword",
     "pattern": "nicht enthalten|out of scope|geh\u00f6rt nicht|ausgenommen|kein teil von", "confidence_boost": 0.25},
    {"key": "sig_ac", "fact_category": "acceptance_criterion", "pattern_type": "keyword",
     "pattern": "akzeptiert wenn|done wenn|fertig wenn|muss funktionieren|testbar", "confidence_boost": 0.3},
    {"key": "sig_risk", "fact_category": "risk", "pattern_type": "keyword",
     "pattern": "risiko|abh\u00e4ngigkeit|blockiert|unklar|kann nicht|vielleicht", "confidence_boost": 0.2},
    {"key": "sig_compliance", "fact_category": "compliance", "pattern_type": "keyword",
     "pattern": "dsgvo|datenschutz|gdpr|iso|compliance|regulierung|gesetzlich", "confidence_boost": 0.3},
]

SEED_CONVERSATION_RULES = [
    {"key": "rule_max_questions", "rule_type": "question_limit", "label": "Max. Fragen pro Antwort",
     "value_json": {"max": 2}},
    {"key": "rule_fact_reuse", "rule_type": "fact_reuse", "label": "Facts wiederverwenden",
     "value_json": {"enabled": True, "min_confidence": 0.5}},
    {"key": "rule_mode_switch_threshold", "rule_type": "mode_switch", "label": "Moduswechsel-Schwelle",
     "value_json": {"complexity_score_for_guided": 3}},
    {"key": "rule_no_double_question", "rule_type": "no_duplicate_question", "label": "Keine doppelten Fragen",
     "value_json": {"enabled": True}},
    {"key": "rule_structure_proposal_threshold", "rule_type": "structure_proposal", "label": "Strukturvorschlag-Schwelle",
     "value_json": {"size_score_threshold": 6, "min_stories": 2}},
]

SEED_SIZING_RULES = [
    {"key": "size_user_groups", "dimension": "user_group", "label": "Nutzergruppen", "weight": 1.5,
     "thresholds_json": {"1": 1, "2": 2, "3+": 3}},
    {"key": "size_functions", "dimension": "scope", "label": "Funktionen / Scope-Elemente", "weight": 1.2,
     "thresholds_json": {"1-2": 1, "3-4": 2, "5+": 3}},
    {"key": "size_systems", "dimension": "dependency", "label": "Systeme / Abh\u00e4ngigkeiten", "weight": 1.0,
     "thresholds_json": {"0": 0, "1": 1, "2+": 2}},
    {"key": "size_acs", "dimension": "acceptance_criterion", "label": "Akzeptanzkriterien", "weight": 1.3,
     "thresholds_json": {"1-2": 1, "3-4": 2, "5+": 3}},
    {"key": "size_risks", "dimension": "risk", "label": "Risiken", "weight": 1.0,
     "thresholds_json": {"0": 0, "1": 1, "2+": 2}},
    {"key": "size_compliance", "dimension": "compliance", "label": "Compliance-Aspekte", "weight": 1.5,
     "thresholds_json": {"0": 0, "1": 2, "2+": 3}},
]

SEED_READINESS_RULES = [
    {"key": "ready_user_group", "required_category": "user_group", "label": "Nutzergruppe vorhanden",
     "min_confidence": 0.5, "is_blocking": True, "weight": 2.0},
    {"key": "ready_problem", "required_category": "problem", "label": "Problem beschrieben",
     "min_confidence": 0.5, "is_blocking": True, "weight": 2.0},
    {"key": "ready_benefit", "required_category": "benefit", "label": "Nutzen klar",
     "min_confidence": 0.5, "is_blocking": True, "weight": 1.5},
    {"key": "ready_scope", "required_category": "scope", "label": "Scope definiert",
     "min_confidence": 0.4, "is_blocking": False, "weight": 1.0},
    {"key": "ready_ac", "required_category": "acceptance_criterion", "label": "Akzeptanzkriterien testbar",
     "min_confidence": 0.5, "is_blocking": True, "weight": 2.0},
    {"key": "ready_risk", "required_category": "risk", "label": "Risiken ber\u00fccksichtigt",
     "min_confidence": 0.3, "is_blocking": False, "weight": 0.5},
]

SEED_PROMPT_TEMPLATES = [
    {
        "key": "ce_system_story_mode",
        "mode": "story_mode",
        "phase": "system",
        "prompt_text": (
            "Du bist Karl, ein erfahrener Agile Coach und Product Owner im HeyKarl Workspace.\n"
            "Deine Aufgabe ist es, durch einen freundlichen, zielorientierten Dialog eine vollst\u00e4ndige User Story zu erarbeiten.\n\n"
            "VERHALTEN:\n"
            "- Stelle maximal 2 Fragen pro Antwort\n"
            "- Wiederhole keine Fragen zu bereits bekannten Informationen\n"
            "- Merke dir alle Aussagen als Facts\n"
            "- Sei motivierend und konstruktiv\n"
            "- Erkenne wenn ein Thema zu gro\u00df f\u00fcr eine Story ist und schlage eine Strukturierung vor\n\n"
            "KONTEXT:\n{context}"
        ),
    },
    {
        "key": "ce_system_exploration_mode",
        "mode": "exploration_mode",
        "phase": "system",
        "prompt_text": (
            "Du bist Karl, ein Sparringspartner f\u00fcr Ideen und Arbeitsanforderungen.\n"
            "In diesem Modus darfst du frei explorieren ohne sofort eine fertige Story zu verlangen.\n\n"
            "VERHALTEN:\n"
            "- Stelle offene Fragen\n"
            "- Hilf bei der Strukturierung von Ideen\n"
            "- Weise auf m\u00f6gliche Implikationen hin\n"
            "- Sammle implizit Facts ohne den Nutzer zu \u00fcberfordern\n\n"
            "KONTEXT:\n{context}"
        ),
    },
    {
        "key": "ce_fact_extract",
        "mode": "any",
        "phase": "fact_extract",
        "prompt_text": (
            "Extrahiere strukturierte Facts aus folgender Nutzeraussage.\n\n"
            "Nutzeraussage: {user_text}\n\n"
            "Bekannte Facts:\n{known_facts}\n\n"
            "Gib JSON zur\u00fcck mit diesem Schema:\n"
            "{{\"facts\": [{{\n"
            "  \"category\": \"user_group|problem|benefit|scope|out_of_scope|acceptance_criterion|risk|compliance|dependency|context\",\n"
            "  \"value\": \"...\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"source_quote\": \"...\"\n"
            "}}]}}\n\n"
            "Regeln:\n"
            "- Nur aus dem gelieferten Text ableiten\n"
            "- Keine Halluzination\n"
            "- Bereits bekannte Facts nicht doppelt extrahieren\n"
            "- Confidence: 0.9 bei expliziter Aussage, 0.6 bei impliziter, 0.3 bei Vermutung"
        ),
    },
    {
        "key": "ce_question_plan",
        "mode": "story_mode",
        "phase": "question_plan",
        "prompt_text": (
            "Bestimme welche Fragen als n\u00e4chstes gestellt werden sollen.\n\n"
            "Bekannte Facts (nicht nochmal fragen):\n{known_facts}\n\n"
            "Offene Pflichtfelder: {missing_required}\n\n"
            "Bereits gestellte Fragen: {asked_keys}\n\n"
            "Verf\u00fcgbare Fragebl\u00f6cke: {available_blocks}\n\n"
            "W\u00e4hle maximal {max_questions} Fragen, priorisiere Pflichtfelder.\n"
            "Gib JSON zur\u00fcck: {{\"selected_keys\": [\"...\", \"...\"]}}"
        ),
    },
    {
        "key": "ce_sizing",
        "mode": "story_mode",
        "phase": "sizing",
        "prompt_text": (
            "Berechne die Story-Gr\u00f6\u00dfe basierend auf den Facts.\n\n"
            "Facts: {facts_summary}\n\n"
            "Dimensionen: Nutzergruppen, Funktionen/Scope, Systeme/Abh\u00e4ngigkeiten, Akzeptanzkriterien, Risiken, Compliance\n\n"
            "Gib JSON zur\u00fcck:\n"
            "{{\"score\": 0-10, \"size_label\": \"XS|S|M|L|XL\", \"stories_suggested\": 1-5,\n"
            "  \"recommendation\": \"single_story|epic_candidate|too_large\",\n"
            "  \"breakdown\": {{\"user_groups\": 0, \"functions\": 0, \"systems\": 0, \"acs\": 0, \"risks\": 0, \"compliance\": 0}}}}"
        ),
    },
    {
        "key": "ce_readiness",
        "mode": "story_mode",
        "phase": "readiness",
        "prompt_text": (
            "Bewerte die Story-Readiness.\n\n"
            "Facts: {facts_summary}\n\n"
            "Bewertungskriterien: Nutzergruppe, Problem, Nutzen, testbare Kriterien, Scope, Risiken\n\n"
            "Gib JSON zur\u00fcck:\n"
            "{{\"status\": \"ready|incomplete|too_large|epic_candidate\",\n"
            "  \"score\": 0-100,\n"
            "  \"missing\": [\"...\"],\n"
            "  \"blockers\": [\"...\"]}}"
        ),
    },
    {
        "key": "ce_structure_proposal",
        "mode": "story_mode",
        "phase": "structure_proposal",
        "prompt_text": (
            "Das Thema ist zu gro\u00df f\u00fcr eine einzelne User Story.\n"
            "Erstelle einen Strukturvorschlag.\n\n"
            "Facts: {facts_summary}\n\n"
            "Gib JSON zur\u00fcck:\n"
            "{{\"epic\": {{\"title\": \"...\", \"description\": \"...\"}},\n"
            "  \"stories\": [\n"
            "    {{\"title\": \"...\", \"user_group\": \"...\", \"benefit\": \"...\", \"scope_hint\": \"...\"}}\n"
            "  ]}}"
        ),
    },
]


# ── LLM call helper ───────────────────────────────────────────────────────────

async def _llm_json(system: str, user: str, temperature: float = 0.1) -> dict | list | None:
    """Call LiteLLM and parse the JSON response. Returns None on any error."""
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.LITELLM_URL}/v1/chat/completions",
                headers=headers,
                json={
                    "model": "ionos-quality",
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"]
            return json.loads(raw)
    except Exception as exc:
        logger.warning("CE LLM call failed: %s", exc)
        return None


# ── Fact extraction ───────────────────────────────────────────────────────────

@dataclass
class ExtractedFact:
    category: str
    value: str
    confidence: float
    source_quote: str = ""


async def extract_facts(
    user_text: str,
    known_facts: list[ConversationFact],
    db: AsyncSession,
) -> list[ExtractedFact]:
    """Extract facts from user text using signals + LLM, skip already-known facts."""
    # 1. Signal-based pre-extraction (fast, no LLM cost)
    signals_result = await db.execute(
        select(AnswerSignal).where(AnswerSignal.is_active == True)
    )
    signals = signals_result.scalars().all()

    signal_hits: list[ExtractedFact] = []
    for sig in signals:
        if sig.pattern_type in ("keyword", "regex"):
            pattern = sig.pattern if sig.pattern_type == "regex" else "|".join(
                re.escape(p.strip()) for p in sig.pattern.split("|")
            )
            if re.search(pattern, user_text, re.IGNORECASE):
                signal_hits.append(ExtractedFact(
                    category=sig.fact_category,
                    value=user_text[:200],
                    confidence=min(0.5 + sig.confidence_boost, 0.85),
                    source_quote=user_text[:100],
                ))

    # 2. LLM-based extraction
    known_summary = "\n".join(
        f"[{f.category}] {f.value[:80]} (confidence={f.confidence:.1f})"
        for f in known_facts if f.status != "rejected"
    ) or "Noch keine bekannten Facts."

    tpl_result = await db.execute(
        select(PromptTemplate).where(
            PromptTemplate.key == "ce_fact_extract",
            PromptTemplate.is_active == True,
        ).order_by(PromptTemplate.version.desc())
    )
    tpl = tpl_result.scalars().first()
    prompt = (tpl.prompt_text if tpl else SEED_PROMPT_TEMPLATES[2]["prompt_text"]).replace(
        "{user_text}", user_text
    ).replace("{known_facts}", known_summary)

    result = await _llm_json("Du bist ein strukturierter Fact-Extraktor.", prompt)

    llm_facts: list[ExtractedFact] = []
    if result and isinstance(result.get("facts"), list):
        for item in result["facts"]:
            cat = item.get("category", "")
            val = item.get("value", "")
            conf = float(item.get("confidence", 0.6))
            quote = item.get("source_quote", "")
            if cat in FACT_CATEGORIES and val:
                # Deduplicate against known facts
                already_known = any(
                    f.category == cat and f.value[:50].lower() == val[:50].lower()
                    for f in known_facts
                )
                if not already_known:
                    llm_facts.append(ExtractedFact(cat, val, conf, quote))

    # Merge: LLM facts take precedence; signal hits fill gaps
    merged = {f.category: f for f in signal_hits}
    for f in llm_facts:
        merged[f"{f.category}_{f.value[:20]}"] = f

    return list(merged.values())


# ── Question Planner ──────────────────────────────────────────────────────────

async def plan_questions(
    session: ConversationSession,
    facts: list[ConversationFact],
    db: AsyncSession,
    max_questions: int = 2,
) -> list[QuestionBlock]:
    """Return the next N most important unanswered questions."""
    covered_categories = {f.category for f in facts if f.status != "rejected" and f.confidence >= 0.4}
    asked_keys = set(session.asked_question_keys or [])

    blocks_result = await db.execute(
        select(QuestionBlock).where(QuestionBlock.is_active == True).order_by(QuestionBlock.priority)
    )
    all_blocks = blocks_result.scalars().all()

    candidates = [
        b for b in all_blocks
        if b.key not in asked_keys
        and b.category not in covered_categories
    ]

    # Required first, then by priority
    required = [b for b in candidates if b.is_required]
    optional = [b for b in candidates if not b.is_required]

    selected = (required + optional)[:max_questions]
    return selected


# ── Story Sizing ──────────────────────────────────────────────────────────────

@dataclass
class SizingResult:
    score: float
    size_label: str
    stories_suggested: int
    recommendation: str  # single_story | epic_candidate | too_large
    breakdown: dict[str, int] = field(default_factory=dict)


def _count_facts_by_category(facts: list[ConversationFact], category: str) -> int:
    return len([f for f in facts if f.category == category and f.status != "rejected"])


async def compute_sizing(facts: list[ConversationFact], db: AsyncSession) -> SizingResult:
    """Compute story size based on active sizing rules."""
    rules_result = await db.execute(
        select(StorySizingRule).where(StorySizingRule.is_active == True)
    )
    rules = rules_result.scalars().all()

    score = 0.0
    breakdown: dict[str, int] = {}

    for rule in rules:
        count = _count_facts_by_category(facts, rule.dimension)
        thresholds = rule.thresholds_json
        # Find matching threshold bucket
        rule_score = 0
        for key, val in sorted(thresholds.items(), key=lambda x: -int(str(x[0]).split("+")[0].split("-")[0].replace(".", "0"))):
            key_str = str(key)
            if "+" in key_str:
                lower = int(key_str.replace("+", ""))
                if count >= lower:
                    rule_score = int(val)
                    break
            elif "-" in key_str:
                parts = key_str.split("-")
                if int(parts[0]) <= count <= int(parts[1]):
                    rule_score = int(val)
                    break
            else:
                if count == int(key_str):
                    rule_score = int(val)
                    break
        score += rule_score * rule.weight
        breakdown[rule.dimension] = count

    # Map score to labels
    if score <= 3:
        size_label, stories, recommendation = "XS", 1, "single_story"
    elif score <= 5:
        size_label, stories, recommendation = "S", 1, "single_story"
    elif score <= 8:
        size_label, stories, recommendation = "M", 2, "single_story"
    elif score <= 12:
        size_label, stories, recommendation = "L", 2, "epic_candidate"
    else:
        size_label, stories, recommendation = "XL", 3, "too_large"

    return SizingResult(
        score=round(score, 1),
        size_label=size_label,
        stories_suggested=stories,
        recommendation=recommendation,
        breakdown=breakdown,
    )


# ── Story Readiness ───────────────────────────────────────────────────────────

@dataclass
class ReadinessResult:
    status: str  # ready | incomplete | too_large | epic_candidate
    score: int   # 0-100
    missing: list[str]
    blockers: list[str]


async def evaluate_readiness(facts: list[ConversationFact], db: AsyncSession) -> ReadinessResult:
    """Evaluate if facts are sufficient to write a user story."""
    rules_result = await db.execute(
        select(ReadinessRule).where(ReadinessRule.is_active == True)
    )
    rules = rules_result.scalars().all()

    covered_categories = {
        f.category for f in facts
        if f.status != "rejected"
    }
    high_conf_categories = {
        f.category for f in facts
        if f.status != "rejected" and f.confidence >= 0.5
    }

    missing = []
    blockers = []
    total_weight = sum(r.weight for r in rules)
    achieved_weight = 0.0

    for rule in rules:
        has_fact = rule.required_category in high_conf_categories
        if has_fact:
            achieved_weight += rule.weight
        else:
            label = rule.label
            missing.append(label)
            if rule.is_blocking:
                blockers.append(label)

    score = int(achieved_weight / total_weight * 100) if total_weight > 0 else 0

    if blockers:
        status = "incomplete"
    elif score >= 80:
        status = "ready"
    else:
        status = "incomplete"

    return ReadinessResult(status=status, score=score, missing=missing, blockers=blockers)


# ── Seed ──────────────────────────────────────────────────────────────────────

async def seed_conversation_engine(db: AsyncSession) -> dict:
    """Insert built-in configuration if tables are empty."""
    from app.models.conversation_engine import (
        DialogProfile, QuestionBlock, AnswerSignal,
        PromptTemplate, ConversationRule, StorySizingRule, ReadinessRule,
    )
    counts: dict[str, int] = {}

    async def _seed(Model, data_list: list[dict], key_field: str = "key") -> int:
        inserted = 0
        for item in data_list:
            existing = await db.execute(
                select(Model).where(getattr(Model, key_field) == item[key_field])
            )
            if existing.scalar_one_or_none() is None:
                db.add(Model(**item))
                inserted += 1
        if inserted:
            await db.commit()
        return inserted

    counts["dialog_profiles"] = await _seed(DialogProfile, SEED_DIALOG_PROFILES)
    counts["question_blocks"] = await _seed(QuestionBlock, SEED_QUESTION_BLOCKS)
    counts["answer_signals"] = await _seed(AnswerSignal, SEED_ANSWER_SIGNALS)
    counts["conversation_rules"] = await _seed(ConversationRule, SEED_CONVERSATION_RULES)
    counts["sizing_rules"] = await _seed(StorySizingRule, SEED_SIZING_RULES)
    counts["readiness_rules"] = await _seed(ReadinessRule, SEED_READINESS_RULES)

    # Prompt templates need special handling (key+version unique)
    inserted = 0
    for item in SEED_PROMPT_TEMPLATES:
        existing = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.key == item["key"],
                PromptTemplate.version == item.get("version", 1),
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(PromptTemplate(**{**item, "version": item.get("version", 1)}))
            inserted += 1
    if inserted:
        await db.commit()
    counts["prompt_templates"] = inserted

    return counts
