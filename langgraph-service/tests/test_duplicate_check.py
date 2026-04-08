"""Tests for duplicate detection workflow and node."""
import json
import pytest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# Task 7: semantic_comparator node
# ---------------------------------------------------------------------------

def _make_comparator_response(results: list[dict]) -> tuple[str, dict]:
    return json.dumps({"comparisons": results}), {
        "input_tokens": 150,
        "output_tokens": 80,
        "model": "claude-sonnet-4-6",
    }


def test_semantic_comparator_classifies_candidates():
    from app.nodes.semantic_comparator import semantic_comparator

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Als Nutzer möchte ich mein Passwort zurücksetzen",
        "description": "Über einen E-Mail-Link kann ich ein neues Passwort setzen",
        "acceptance_criteria": "Gegeben ich bin ausgeloggt, wenn ich 'Passwort vergessen' klicke, dann erhalte ich eine E-Mail",
        "candidates": [
            {
                "story_id": "story-002",
                "title": "Passwort-Reset per E-Mail",
                "description": "User kann Passwort über E-Mail zurücksetzen",
                "acceptance_criteria": "Reset-Link per E-Mail",
                "similarity_score": 0.91,
            },
            {
                "story_id": "story-003",
                "title": "Passwort ändern im Profil",
                "description": "User kann Passwort im Profil ändern",
                "acceptance_criteria": "Formular mit altem und neuem Passwort",
                "similarity_score": 0.74,
            },
        ],
        "comparison_results": [],
    }

    llm_response = _make_comparator_response([
        {
            "story_id": "story-002",
            "classification": "duplicate",
            "explanation": "Beide Stories beschreiben denselben Passwort-Reset via E-Mail.",
        },
        {
            "story_id": "story-003",
            "classification": "similar",
            "explanation": "Ähnliches Thema, aber anderer Kontext (Profil vs. vergessenes Passwort).",
        },
    ])

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        result = semantic_comparator(state)

    assert "comparison_results" in result
    assert len(result["comparison_results"]) == 2
    classifications = {r["story_id"]: r["classification"] for r in result["comparison_results"]}
    assert classifications["story-002"] == "duplicate"
    assert classifications["story-003"] == "similar"
    for r in result["comparison_results"]:
        assert r["explanation"] != ""


def test_semantic_comparator_handles_empty_candidates():
    from app.nodes.semantic_comparator import semantic_comparator

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Neues Feature",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [],
        "comparison_results": [],
    }

    result = semantic_comparator(state)
    assert result["comparison_results"] == []


def test_semantic_comparator_handles_llm_failure():
    from app.nodes.semantic_comparator import semantic_comparator
    from app.llm.client import LLMCallError

    state = {
        "story_id": "story-001",
        "org_id": "org-001",
        "title": "Test",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [
            {
                "story_id": "story-002",
                "title": "Test 2",
                "description": "",
                "acceptance_criteria": "",
                "similarity_score": 0.88,
            }
        ],
        "comparison_results": [],
    }

    with patch("app.llm.client.LiteLLMClient.chat", side_effect=LLMCallError("timeout")):
        result = semantic_comparator(state)

    # On LLM failure: each candidate is kept with classification="similar" and a fallback explanation
    assert len(result["comparison_results"]) == 1
    assert result["comparison_results"][0]["story_id"] == "story-002"
    assert result["comparison_results"][0]["classification"] in ("duplicate", "similar")


# ---------------------------------------------------------------------------
# Task 8: duplicate_check workflow
# ---------------------------------------------------------------------------

def test_run_duplicate_check_returns_structured_response():
    from app.workflows.duplicate_check import run_duplicate_check
    from app.schemas.evaluation import DuplicateCheckRequest, DuplicateCandidate

    request = DuplicateCheckRequest(
        story_id="story-001",
        org_id="org-001",
        title="Passwort zurücksetzen",
        description="User kann Passwort via E-Mail zurücksetzen",
        acceptance_criteria="Reset-Link wird per E-Mail gesendet",
        candidates=[
            DuplicateCandidate(
                story_id="story-002",
                title="Passwort-Reset",
                description="Reset via E-Mail",
                acceptance_criteria="E-Mail mit Link",
                similarity_score=0.92,
            ),
            DuplicateCandidate(
                story_id="story-003",
                title="Passwort ändern",
                description="Passwort im Profil ändern",
                acceptance_criteria="Formular mit altem Passwort",
                similarity_score=0.75,
            ),
        ],
    )

    llm_response = _make_comparator_response([
        {
            "story_id": "story-002",
            "classification": "duplicate",
            "explanation": "Selber Anwendungsfall.",
        },
        {
            "story_id": "story-003",
            "classification": "similar",
            "explanation": "Anderer Kontext.",
        },
    ])

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        response = run_duplicate_check(request)

    assert len(response.duplicates) == 1
    assert response.duplicates[0].story_id == "story-002"
    assert response.duplicates[0].similarity_score == 0.92
    assert "Selber Anwendungsfall" in response.duplicates[0].explanation

    assert len(response.similar) == 1
    assert response.similar[0].story_id == "story-003"


def test_run_duplicate_check_empty_candidates():
    from app.workflows.duplicate_check import run_duplicate_check
    from app.schemas.evaluation import DuplicateCheckRequest

    request = DuplicateCheckRequest(
        story_id="story-001",
        org_id="org-001",
        title="Ganz neue Story",
        description="Kein Treffer erwartet",
        acceptance_criteria="",
        candidates=[],
    )

    response = run_duplicate_check(request)
    assert response.duplicates == []
    assert response.similar == []


# ---------------------------------------------------------------------------
# Task 9: /workflows/check-duplicates endpoint
# ---------------------------------------------------------------------------

def test_check_duplicates_endpoint_returns_200():
    import os
    os.environ["LANGGRAPH_API_KEY"] = "test-secret"

    from fastapi.testclient import TestClient
    from app.main import app

    llm_response = _make_comparator_response([
        {
            "story_id": "story-abc",
            "classification": "duplicate",
            "explanation": "Selber Anwendungsfall.",
        },
    ])

    payload = {
        "story_id": "story-999",
        "org_id": "org-001",
        "title": "Passwort zurücksetzen",
        "description": "via E-Mail",
        "acceptance_criteria": "E-Mail wird gesendet",
        "candidates": [
            {
                "story_id": "story-abc",
                "title": "Passwort Reset",
                "description": "via E-Mail",
                "acceptance_criteria": "",
                "similarity_score": 0.91,
            }
        ],
    }

    with patch("app.llm.client.LiteLLMClient.chat", return_value=llm_response):
        client = TestClient(app)
        response = client.post(
            "/workflows/check-duplicates",
            json=payload,
            headers={"X-API-Key": "test-secret"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "duplicates" in data
    assert "similar" in data
    assert data["duplicates"][0]["story_id"] == "story-abc"


def test_check_duplicates_endpoint_rejects_missing_api_key():
    from fastapi.testclient import TestClient
    from app.main import app

    payload = {
        "story_id": "story-999",
        "org_id": "org-001",
        "title": "Test",
        "description": "",
        "acceptance_criteria": "",
        "candidates": [],
    }

    client = TestClient(app)
    response = client.post("/workflows/check-duplicates", json=payload)
    assert response.status_code == 401
