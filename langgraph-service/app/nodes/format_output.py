from __future__ import annotations
from app.schemas.evaluation import compute_ampel, Ampel

_CRITERION_WEIGHTS = {
    "completeness": 0.30,
    "clarity": 0.30,
    "testability": 0.20,
    "business_value": 0.10,
    "feasibility": 0.10,
}


def format_output(state: dict) -> dict:
    """
    Deterministic: assemble final score from intermediate node results.
    No LLM call.
    """
    criteria_completeness: float = state.get("criteria_completeness", 0.0)
    clarity_score: float = state.get("clarity_score", 5.0)
    findings: list[dict] = state.get("findings", [])

    testability_score = criteria_completeness * 10.0
    business_value_score = min(clarity_score + 0.5, 10.0)
    feasibility_score = 7.0

    criteria_scores = {
        "completeness": {
            "score": round(criteria_completeness * 10.0, 1),
            "weight": _CRITERION_WEIGHTS["completeness"],
            "explanation": f"AC-Vollständigkeit: {criteria_completeness*100:.0f}%",
        },
        "clarity": {
            "score": round(clarity_score, 1),
            "weight": _CRITERION_WEIGHTS["clarity"],
            "explanation": state.get("clarity_explanation", ""),
        },
        "testability": {
            "score": round(testability_score, 1),
            "weight": _CRITERION_WEIGHTS["testability"],
            "explanation": "Abgeleitet aus AC-Vollständigkeit und GWT-Format",
        },
        "business_value": {
            "score": round(business_value_score, 1),
            "weight": _CRITERION_WEIGHTS["business_value"],
            "explanation": "Approximiert aus Klarheitsbewertung",
        },
        "feasibility": {
            "score": feasibility_score,
            "weight": _CRITERION_WEIGHTS["feasibility"],
            "explanation": "Standard-Schätzung (keine technische Analyse in MVP)",
        },
    }

    final_score = round(
        sum(v["score"] * v["weight"] for v in criteria_scores.values()), 2
    )

    knockout = any(f.get("severity") == "CRITICAL" for f in findings)
    if state.get("knockout"):
        knockout = True

    ampel: Ampel = compute_ampel(score=final_score, knockout=knockout)

    confidence = round(
        0.5
        + (0.2 if criteria_completeness > 0 else 0)
        + (0.2 if clarity_score != 5.0 else 0)
        + (0.1 if findings else 0),
        2,
    )

    return {
        "final_score": final_score,
        "ampel": ampel.value,
        "knockout": knockout,
        "confidence": min(confidence, 1.0),
        "criteria_scores": criteria_scores,
    }
