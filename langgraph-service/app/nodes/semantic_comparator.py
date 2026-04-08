"""LangGraph node: LLM-based semantic comparison of pgvector candidates."""
from __future__ import annotations

import json
import logging

from app.llm.client import LiteLLMClient, LLMCallError

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are an expert in requirements engineering. Your task is to compare a query user story
against a list of candidate stories to detect duplicates.

For each candidate, classify it as:
- "duplicate": The candidate covers the same user need and would be redundant with the query story
- "similar": The candidate is related or overlapping but covers a meaningfully different scope

Respond ONLY with a JSON object in exactly this format (no extra characters):
{
  "comparisons": [
    {
      "story_id": "<story_id from input>",
      "classification": "duplicate" | "similar",
      "explanation": "<1-2 sentences explaining the classification>"
    }
  ]
}
"""


def semantic_comparator(state: dict) -> dict:
    """
    LangGraph node — LLM pairwise comparison of story candidates.
    Input state keys: story_id, org_id, title, description, acceptance_criteria, candidates
    Output state keys: comparison_results
    """
    candidates: list[dict] = state.get("candidates", [])

    if not candidates:
        return {"comparison_results": []}

    query_text = (
        f"Query Story:\n"
        f"Title: {state.get('title', '')}\n"
        f"Description: {state.get('description', '')}\n"
        f"Acceptance Criteria: {state.get('acceptance_criteria', '')}\n\n"
        f"Candidates:\n"
    )
    for c in candidates:
        query_text += (
            f"- story_id: {c['story_id']}\n"
            f"  Title: {c['title']}\n"
            f"  Description: {c.get('description', '')}\n"
            f"  Acceptance Criteria: {c.get('acceptance_criteria', '')}\n"
            f"  Vector similarity: {c['similarity_score']:.3f}\n\n"
        )

    client = LiteLLMClient()
    try:
        text, _usage = client.chat(
            model="claude-sonnet-4-6",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": query_text},
            ],
            max_tokens=1024,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        comparisons: list[dict] = data.get("comparisons", [])
        # Ensure all candidates are present even if LLM omitted some
        returned_ids = {c["story_id"] for c in comparisons}
        for candidate in candidates:
            if candidate["story_id"] not in returned_ids:
                comparisons.append({
                    "story_id": candidate["story_id"],
                    "classification": "similar",
                    "explanation": "Classification unavailable — defaulting to similar.",
                })
        return {"comparison_results": comparisons}

    except LLMCallError as e:
        logger.error("semantic_comparator: LLM call failed: %s", e)
        fallback = [
            {
                "story_id": c["story_id"],
                "classification": "similar",
                "explanation": f"LLM comparison unavailable: {e}",
            }
            for c in candidates
        ]
        return {"comparison_results": fallback}

    except Exception as e:
        logger.error("semantic_comparator: unexpected error: %s", e)
        fallback = [
            {
                "story_id": c["story_id"],
                "classification": "similar",
                "explanation": f"Comparison failed: {e}",
            }
            for c in candidates
        ]
        return {"comparison_results": fallback}
