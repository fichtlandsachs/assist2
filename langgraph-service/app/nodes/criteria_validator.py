from __future__ import annotations

_GWT_KEYWORDS = {"gegeben", "wenn", "dann", "given", "when", "then", "as", "i want", "so that"}


def validate_criteria(state: dict) -> dict:
    """
    Deterministic: score AC completeness 0.0–1.0.
    No LLM call.

    Formula:
      - count_score: min(count / 3, 1.0) weighted 0.5
        (3 or more ACs = full score)
      - gwt_score: fraction of ACs containing GWT keywords, weighted 0.5
    """
    criteria: list[str] = state.get("parsed_criteria", [])
    if not criteria:
        return {"criteria_completeness": 0.0}

    count_score = min(len(criteria) / 3.0, 1.0)

    def has_gwt(ac: str) -> bool:
        lower = ac.lower()
        return any(kw in lower for kw in _GWT_KEYWORDS)

    gwt_score = sum(1 for c in criteria if has_gwt(c)) / len(criteria)
    completeness = round(count_score * 0.5 + gwt_score * 0.5, 3)
    return {"criteria_completeness": completeness}
