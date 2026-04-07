from __future__ import annotations
import json
import logging

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für Anforderungsqualität. Bewerte die vorliegende User Story auf Klarheit.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt diesem Format (keine weiteren Zeichen außen herum):
{
  "score": <float 0-10>,
  "explanation": "<max 2 Sätze auf Deutsch>",
  "knockout": <true nur wenn Story fundamental unverständlich, sonst false>
}

Bewertungsskala:
0-3: fundamental unklar, kein Verständnis möglich
4-5: grob verständlich, aber wesentliche Lücken
6-7: verständlich, kleinere Lücken
8-10: klar, vollständig, präzise
"""


def clarity_scorer(state: dict) -> dict:
    """LLM node — scores story clarity synchronously."""
    client = LiteLLMClient()
    user_msg = (
        f"Titel: {state.get('title', '')}\n"
        f"Beschreibung: {state.get('description', '')}\n"
        f"Akzeptanzkriterien:\n{state.get('acceptance_criteria', '')}"
    )
    try:
        text, usage = client.chat(
            model="eval-fast",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        return {
            "clarity_score": float(data.get("score", 5.0)),
            "clarity_explanation": data.get("explanation", ""),
            "knockout": bool(data.get("knockout", False)),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-fast"),
        }
    except Exception as e:
        logger.error("clarity_scorer failed: %s", e)
        return {
            "clarity_score": 5.0,
            "clarity_explanation": f"Bewertung nicht verfügbar: {e}",
            "knockout": False,
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-fast",
        }
