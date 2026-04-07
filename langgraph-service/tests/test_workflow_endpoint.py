import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch


def _mock_result():
    from app.schemas.evaluation import (
        EvaluationResult, Ampel, EvalFinding, CriterionScore, RewriteSuggestion,
    )
    return EvaluationResult(
        run_id="run-test",
        story_id="story-test",
        org_id="org-test",
        score=7.2,
        ampel=Ampel.GREEN,
        knockout=False,
        confidence=0.85,
        criteria_scores={
            "clarity": CriterionScore(score=7.0, weight=0.3, explanation="Klar"),
        },
        findings=[],
        open_questions=[],
        rewrite=RewriteSuggestion(title="T", story="S", acceptance_criteria=[]),
        model_used="eval-quality",
        input_tokens=300,
        output_tokens=150,
    )


@pytest.mark.asyncio
async def test_evaluate_endpoint_returns_result():
    from app.main import app
    with patch("app.routers.workflows.run_evaluation", return_value=_mock_result()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/workflows/evaluate",
                json={
                    "run_id": "run-test",
                    "story_id": "story-test",
                    "org_id": "org-test",
                    "title": "Als Nutzer...",
                    "description": "...",
                    "acceptance_criteria": "Gegeben...",
                },
                headers={"X-API-Key": "test-secret"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run-test"
    assert data["score"] == 7.2
    assert data["ampel"] == "GREEN"


@pytest.mark.asyncio
async def test_evaluate_endpoint_rejects_missing_api_key():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/workflows/evaluate",
            json={"run_id": "x", "story_id": "x", "org_id": "x", "title": "x"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_endpoint_rejects_wrong_api_key():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/workflows/evaluate",
            json={"run_id": "x", "story_id": "x", "org_id": "x", "title": "x"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
