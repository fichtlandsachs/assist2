"""Unit tests for story_refinement_service helpers."""
import pytest
from app.services.story_refinement_service import (
    build_system_prompt,
    extract_proposal,
    extract_score,
)


def test_build_system_prompt_contains_story_fields():
    prompt = build_system_prompt(
        title="Als Nutzer möchte ich einloggen",
        description="Einfaches Login",
        acceptance_criteria="Gegeben ich bin auf /login, wenn ich mich anmelde, dann bin ich eingeloggt",
        priority="high",
        status="draft",
        epic_title="Auth Epic",
        project_name="Haupt-Projekt",
    )
    assert "Als Nutzer möchte ich einloggen" in prompt
    assert "Auth Epic" in prompt
    assert "high" in prompt


def test_build_system_prompt_handles_none_fields():
    prompt = build_system_prompt(
        title="Story ohne Epic",
        description=None,
        acceptance_criteria=None,
        priority="medium",
        status="draft",
        epic_title=None,
        project_name=None,
    )
    assert "Story ohne Epic" in prompt
    assert "medium" in prompt


def test_extract_proposal_returns_dict():
    text = 'Hier ist mein Vorschlag.\n<!--proposal\n{"title": "Neuer Titel", "description": "Neue Beschreibung"}\n-->'
    proposal = extract_proposal(text)
    assert proposal is not None
    assert proposal["title"] == "Neuer Titel"
    assert proposal["description"] == "Neue Beschreibung"


def test_extract_proposal_returns_none_when_absent():
    text = "Keine Vorschläge hier."
    assert extract_proposal(text) is None


def test_extract_proposal_handles_malformed_json():
    text = "<!--proposal\nnot-valid-json\n-->"
    assert extract_proposal(text) is None


def test_extract_score_returns_int():
    text = "Tolle Story. <!--score:78-->"
    assert extract_score(text) == 78


def test_extract_score_returns_none_when_absent():
    assert extract_score("Kein Score hier.") is None


def test_extract_score_clamps_to_valid_range():
    assert extract_score("<!--score:150-->") == 100
    assert extract_score("<!--score:-5-->") == 0
