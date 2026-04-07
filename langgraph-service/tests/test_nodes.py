from app.nodes.story_parser import parse_input
from app.nodes.criteria_validator import validate_criteria
from app.nodes.format_output import format_output


def _base_state():
    return {
        "run_id": "run-1",
        "story_id": "story-1",
        "org_id": "org-1",
        "title": "Als Nutzer möchte ich Login",
        "description": "Ich möchte mich einloggen",
        "acceptance_criteria": (
            "Gegeben ich bin auf der Login-Seite\n"
            "Wenn ich Daten eingebe\n"
            "Dann werde ich eingeloggt"
        ),
        "context_hints": [],
        "parsed_criteria": [],
        "criteria_completeness": 0.0,
        "clarity_score": 0.0,
        "clarity_explanation": "",
        "knockout": False,
        "findings": [],
        "open_questions": [],
        "rewrite_title": "",
        "rewrite_story": "",
        "rewrite_criteria": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "model_used": "",
        "final_score": 0.0,
        "ampel": "YELLOW",
        "confidence": 0.5,
        "criteria_scores": {},
    }


def test_parse_input_extracts_criteria():
    state = _base_state()
    result = parse_input(state)
    assert len(result["parsed_criteria"]) == 3
    assert "Gegeben ich bin auf der Login-Seite" in result["parsed_criteria"]


def test_parse_input_empty_criteria():
    state = _base_state()
    state["acceptance_criteria"] = ""
    result = parse_input(state)
    assert result["parsed_criteria"] == []


def test_validate_criteria_full_given_when_then():
    state = _base_state()
    state["parsed_criteria"] = [
        "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich Stats"
    ]
    result = validate_criteria(state)
    assert result["criteria_completeness"] > 0.5


def test_validate_criteria_no_criteria():
    state = _base_state()
    state["parsed_criteria"] = []
    result = validate_criteria(state)
    assert result["criteria_completeness"] == 0.0


def test_validate_criteria_three_acs_full_gwt():
    state = _base_state()
    state["parsed_criteria"] = [
        "Gegeben A, wenn B, dann C",
        "Gegeben D, wenn E, dann F",
        "Gegeben G, wenn H, dann I",
    ]
    result = validate_criteria(state)
    assert result["criteria_completeness"] == 1.0


def test_format_output_computes_score():
    state = _base_state()
    state.update({
        "criteria_completeness": 0.8,
        "clarity_score": 7.0,
        "clarity_explanation": "Klar formuliert",
        "findings": [],
        "rewrite_title": "Als Projektmanager...",
        "rewrite_story": "Als PM möchte ich...",
        "rewrite_criteria": ["Gegeben..., wenn..., dann..."],
        "open_questions": [],
        "total_input_tokens": 200,
        "total_output_tokens": 100,
        "model_used": "eval-quality",
    })
    result = format_output(state)
    assert 0 <= result["final_score"] <= 10
    assert result["ampel"] in ("GREEN", "YELLOW", "RED")
    assert result["knockout"] is False


def test_format_output_knockout_from_finding():
    state = _base_state()
    state.update({
        "criteria_completeness": 0.0,
        "clarity_score": 2.0,
        "clarity_explanation": "Unverständlich",
        "findings": [{"severity": "CRITICAL", "category": "CLARITY", "title": "T", "description": "D", "suggestion": "S", "id": "f-001"}],
        "rewrite_title": "", "rewrite_story": "", "rewrite_criteria": [],
        "open_questions": [],
        "total_input_tokens": 0, "total_output_tokens": 0, "model_used": "",
    })
    result = format_output(state)
    assert result["knockout"] is True
    assert result["ampel"] == "RED"


def test_format_output_knockout_from_clarity_scorer():
    state = _base_state()
    state.update({
        "knockout": True,
        "criteria_completeness": 0.9,
        "clarity_score": 9.0,
        "clarity_explanation": "Klar",
        "findings": [],
        "rewrite_title": "", "rewrite_story": "", "rewrite_criteria": [],
        "open_questions": [],
        "total_input_tokens": 0, "total_output_tokens": 0, "model_used": "",
    })
    result = format_output(state)
    assert result["knockout"] is True
    assert result["ampel"] == "RED"
