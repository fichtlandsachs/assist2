from __future__ import annotations
import json
import logging

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für agile Anforderungen. Erstelle einen verbesserten Rewrite der User Story.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{
  "title": "<verbesserter Titel, max 80 Zeichen>",
  "story": "<vollständige User Story: Als [Rolle] möchte ich [Ziel], damit [Nutzen]>",
  "acceptance_criteria": [
    "<AC 1: Gegeben..., wenn..., dann...>",
    "<AC 2>",
    "<AC 3>"
  ]
}

Regeln:
- Behalte den fachlichen Kern der Original-Story
- Verbessere Persona, Ziel und Nutzen wenn unklar
- ACs im Given-When-Then-Format
- Mindestens 2, maximal 5 ACs
- Antworte auf Deutsch
"""


def rewrite_generator(state: dict) -> dict:
    """LLM node — generates improved rewrite of the story."""
    client = LiteLLMClient()
    findings_text = "\n".join(
        f"- [{f['severity']}] {f['title']}: {f['suggestion']}"
        for f in state.get("findings", [])
    )
    user_msg = (
        f"Original-Story:\n"
        f"Titel: {state.get('title', '')}\n"
        f"Story: {state.get('description', '')}\n"
        f"ACs: {state.get('acceptance_criteria', '')}\n\n"
        f"Gefundene Mängel:\n{findings_text or 'Keine kritischen Mängel.'}"
    )
    try:
        text, usage = client.chat(
            model="eval-quality",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        return {
            "rewrite_title": data.get("title", state.get("title", "")),
            "rewrite_story": data.get("story", state.get("description", "")),
            "rewrite_criteria": data.get("acceptance_criteria", []),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-quality"),
        }
    except Exception as e:
        logger.error("rewrite_generator failed: %s", e)
        return {
            "rewrite_title": state.get("title", ""),
            "rewrite_story": state.get("description", ""),
            "rewrite_criteria": [],
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-quality",
        }
