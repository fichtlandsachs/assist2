from __future__ import annotations
import json
import logging

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für Anforderungsqualität. Analysiere die User Story und erzeuge konkrete Verbesserungshinweise.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt diesem Format:
{
  "findings": [
    {
      "severity": "<CRITICAL|MAJOR|MINOR|INFO>",
      "category": "<CLARITY|COMPLETENESS|TESTABILITY|FEASIBILITY|BUSINESS_VALUE>",
      "title": "<max 60 Zeichen>",
      "description": "<Problembeschreibung, max 2 Sätze>",
      "suggestion": "<konkreter Verbesserungsvorschlag, max 2 Sätze>"
    }
  ],
  "open_questions": ["<Frage 1>", "<Frage 2>"]
}

Regeln:
- Maximal 5 Findings
- CRITICAL nur bei fundamentalen Mängeln (keine Persona, kein Ziel, kein Wert erkennbar)
- Keine redundanten Findings — lieber weniger, dafür präzise
- open_questions: maximal 3, nur wenn wirklich unklar
- Antworte auf Deutsch
"""


def generate_findings(state: dict) -> dict:
    """LLM node — generates structured findings list."""
    client = LiteLLMClient()
    user_msg = (
        f"Titel: {state.get('title', '')}\n"
        f"Beschreibung: {state.get('description', '')}\n"
        f"Akzeptanzkriterien:\n{state.get('acceptance_criteria', '')}\n"
        f"Klarheits-Score: {state.get('clarity_score', 0)}/10\n"
        f"AC-Vollständigkeit: {state.get('criteria_completeness', 0)*10:.1f}/10"
    )
    try:
        text, usage = client.chat(
            model="eval-quality",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1200,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        findings = []
        for i, f in enumerate(data.get("findings", [])):
            findings.append({
                "id": f"f-{i+1:03d}",
                "severity": f.get("severity", "MINOR"),
                "category": f.get("category", "CLARITY"),
                "title": f.get("title", ""),
                "description": f.get("description", ""),
                "suggestion": f.get("suggestion", ""),
            })
        return {
            "findings": findings,
            "open_questions": data.get("open_questions", []),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-quality"),
        }
    except Exception as e:
        logger.error("generate_findings failed: %s", e)
        return {
            "findings": [],
            "open_questions": [],
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-quality",
        }
