from app.schemas.evaluation import (
    EvaluateRequest, EvaluationResult, EvalFinding, CriterionScore,
    FindingSeverity, FindingCategory, Ampel, compute_ampel,
)


def test_evaluate_request_requires_mandatory_fields():
    req = EvaluateRequest(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        story_id="550e8400-e29b-41d4-a716-446655440001",
        org_id="550e8400-e29b-41d4-a716-446655440002",
        title="Als Nutzer möchte ich...",
        description="Ich möchte den Status sehen",
        acceptance_criteria="Gegeben ich bin eingeloggt, wenn..., dann...",
    )
    assert req.story_id == "550e8400-e29b-41d4-a716-446655440001"


def test_ampel_logic_green():
    assert compute_ampel(score=8.0, knockout=False) == Ampel.GREEN


def test_ampel_logic_yellow():
    assert compute_ampel(score=6.0, knockout=False) == Ampel.YELLOW


def test_ampel_logic_red_by_score():
    assert compute_ampel(score=3.0, knockout=False) == Ampel.RED


def test_ampel_logic_red_by_knockout():
    assert compute_ampel(score=9.0, knockout=True) == Ampel.RED
