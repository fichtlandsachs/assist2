from __future__ import annotations


def parse_input(state: dict) -> dict:
    """
    Deterministic: split acceptance_criteria into list, clean whitespace.
    No LLM call.
    """
    raw = state.get("acceptance_criteria", "") or ""
    criteria = [line.strip() for line in raw.splitlines() if line.strip()]
    return {"parsed_criteria": criteria}
