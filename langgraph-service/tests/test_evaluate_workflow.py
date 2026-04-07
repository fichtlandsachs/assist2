import pytest
from unittest.mock import patch, MagicMock
import json


def _clarity_response():
    return json.dumps({
        "score": 7.0,
        "explanation": "Klar formuliert, Persona vorhanden",
        "knockout": False,
    }), {"input_tokens": 100, "output_tokens": 50, "model": "eval-fast"}


def _findings_response():
    return json.dumps({
        "findings": [
            {
                "severity": "MINOR",
                "category": "TESTABILITY",
                "title": "AC könnte messbarer sein",
                "description": "AC3 enthält keinen konkreten Schwellenwert.",
                "suggestion": "Ergänze einen messbaren Wert.",
            }
        ],
        "open_questions": ["Welche Rollen haben Zugriff?"],
    }), {"input_tokens": 200, "output_tokens": 100, "model": "eval-quality"}


def _rewrite_response():
    return json.dumps({
        "title": "Als Projektmanager möchte ich Sprint-Übersicht sehen",
        "story": "Als Projektmanager möchte ich alle Sprints sehen, damit ich den Status kenne.",
        "acceptance_criteria": [
            "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich alle Sprints.",
        ],
    }), {"input_tokens": 150, "output_tokens": 80, "model": "eval-quality"}


def test_evaluate_workflow_returns_valid_result():
    from app.workflows.evaluate import run_evaluation
    from app.schemas.evaluation import EvaluateRequest

    request = EvaluateRequest(
        run_id="run-001",
        story_id="story-001",
        org_id="org-001",
        title="Als Nutzer möchte ich den Sprint-Status sehen",
        description="Ich möchte alle aktiven Sprints auf einem Dashboard sehen",
        acceptance_criteria=(
            "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich Sprints.\n"
            "Gegeben ein Sprint ist überfällig, dann ist er rot markiert.\n"
            "Die Seite lädt in unter 2 Sekunden."
        ),
    )

    call_count = [0]

    def mock_chat(self, model, messages, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _clarity_response()
        elif call_count[0] == 2:
            return _findings_response()
        else:
            return _rewrite_response()

    with patch("app.llm.client.LiteLLMClient.chat", mock_chat):
        result = run_evaluation(request)

    assert result.story_id == "story-001"
    assert result.run_id == "run-001"
    assert 0 <= result.score <= 10
    assert result.ampel.value in ("GREEN", "YELLOW", "RED")
    assert isinstance(result.findings, list)
    assert result.rewrite.title != ""
    assert result.input_tokens > 0


def test_evaluate_workflow_handles_llm_failure_gracefully():
    """If LLM calls fail, workflow returns result with fallback values."""
    from app.workflows.evaluate import run_evaluation
    from app.schemas.evaluation import EvaluateRequest
    from app.llm.client import LLMCallError

    request = EvaluateRequest(
        run_id="run-002",
        story_id="story-002",
        org_id="org-001",
        title="Test",
        description="",
        acceptance_criteria="",
    )

    with patch("app.llm.client.LiteLLMClient.chat", side_effect=LLMCallError("timeout")):
        result = run_evaluation(request)

    assert result.run_id == "run-002"
    assert result.score >= 0
    assert result.ampel is not None
