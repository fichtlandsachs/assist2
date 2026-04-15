"""Grounded Generation — builds evidence-grounded prompts and parses structured output.

Only called when PolicyEngine.evaluate() returns allowed=True.
All LLM calls go through LiteLLM (via AsyncOpenAI client pointing at LiteLLM gateway).
"""
from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.ai.evidence import EvidenceItem, EvidenceSet
from app.config import get_settings

logger = logging.getLogger(__name__)

_GROUNDED_SYSTEM = """Du bist ein faktenbasierter KI-Assistent mit Quellenpflicht.

REGELN (nicht verhandelbar):
1. Antworte ausschließlich auf Basis der bereitgestellten Evidenz.
2. Erfinde keine Fakten, APIs, Felder, Prozesse oder Quellenangaben.
3. Trenne klar: Fakten (aus Evidenz belegt), Annahmen (plausibel aber unbelegt), Unsicherheiten.
4. Wenn Evidenz fehlt oder unzureichend ist, sage es explizit.
5. Empfehlungen nur aus belegten Fakten ableiten.
6. Antworte immer als strukturiertes JSON gemäß dem vorgegebenen Schema.

AUSGABEFORMAT (strikt einhalten):
{
  "summary": "Kurzzusammenfassung in 1-2 Sätzen",
  "facts": ["Belegte Aussage 1", "Belegte Aussage 2"],
  "assumptions": ["Annahme 1 (nicht aus Quellen belegt)"],
  "uncertainties": ["Unklar: ..."],
  "open_questions": ["Offene Frage 1"],
  "recommendations": ["Empfehlung nur aus Fakten abgeleitet"],
  "warnings": ["Warnung falls Evidenz schwach oder widersprüchlich"]
}
"""


def _build_evidence_block(evidence: EvidenceSet) -> str:
    lines = ["=== VERFÜGBARE EVIDENZ ==="]
    for i, e in enumerate(evidence.usable, 1):
        lines.append(
            f"\n[{i}] {e.source_type.upper()} | {e.source_name}"
            f"\n    URL: {e.excerpt_location or 'keine'}"
            f"\n    Relevanz: {e.relevance_score:.2f} | Aktualität: {e.freshness_score:.2f}"
            f"\n    Inhalt: {e.excerpt}"
        )
    if evidence.has_contradiction:
        lines.append("\n⚠️ HINWEIS: Die Evidenzquellen enthalten möglicherweise widersprüchliche Informationen.")
    lines.append("\n=== ENDE EVIDENZ ===")
    return "\n".join(lines)


async def generate_grounded(
    user_query: str,
    evidence: EvidenceSet,
    models: tuple[str, ...] = ("ionos-reasoning", "ionos-quality", "ionos-fast"),
) -> dict:
    """Call LiteLLM with evidence-grounded prompt, return parsed JSON dict."""
    settings = get_settings()
    oai = AsyncOpenAI(
        api_key=settings.LITELLM_API_KEY or "sk-heykarl",
        base_url=f"{settings.LITELLM_URL}/v1",
    )

    evidence_block = _build_evidence_block(evidence)
    messages = [
        {"role": "system", "content": _GROUNDED_SYSTEM},
        {"role": "user", "content": f"{evidence_block}\n\nFRAGE: {user_query}"},
    ]

    for model in models:
        try:
            resp = await oai.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.1,    # low temperature for factual grounding
                stream=False,
            )
            raw = resp.choices[0].message.content or ""
            return _parse_structured(raw)
        except Exception as exc:
            logger.warning("Grounded gen model %s failed: %s", model, exc)

    return {"summary": "", "facts": [], "assumptions": [], "uncertainties": [],
            "open_questions": [], "recommendations": [], "warnings": ["LLM unavailable"]}


def _parse_structured(raw: str) -> dict:
    """Extract JSON from model output, with fallback."""
    raw = raw.strip()
    # Try to extract JSON block
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
    # Fallback: wrap raw text as summary
    return {
        "summary": raw[:300],
        "facts": [],
        "assumptions": [],
        "uncertainties": ["Strukturierte Ausgabe konnte nicht geparst werden."],
        "open_questions": [],
        "recommendations": [],
        "warnings": ["Antwort ist nicht strukturiert validiert."],
    }
