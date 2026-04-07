from __future__ import annotations
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.story_parser import parse_input
from app.nodes.criteria_validator import validate_criteria
from app.nodes.clarity_scorer import clarity_scorer
from app.nodes.generate_findings import generate_findings
from app.nodes.rewrite_generator import rewrite_generator
from app.nodes.format_output import format_output
from app.schemas.evaluation import (
    EvaluateRequest, EvaluationResult, EvalFinding,
    CriterionScore, RewriteSuggestion, Ampel,
)

logger = logging.getLogger(__name__)


class EvalState(TypedDict):
    # Input
    run_id: str
    story_id: str
    org_id: str
    title: str
    description: str
    acceptance_criteria: str
    context_hints: list
    # Intermediate
    parsed_criteria: list
    criteria_completeness: float
    clarity_score: float
    clarity_explanation: str
    knockout: bool
    findings: list
    open_questions: list
    rewrite_title: str
    rewrite_story: str
    rewrite_criteria: list
    total_input_tokens: int
    total_output_tokens: int
    model_used: str
    # Output
    final_score: float
    ampel: str
    confidence: float
    criteria_scores: dict


def _build_graph() -> StateGraph:
    g = StateGraph(EvalState)
    g.add_node("parse_input", parse_input)
    g.add_node("validate_criteria", validate_criteria)
    g.add_node("clarity_scorer", clarity_scorer)
    g.add_node("generate_findings", generate_findings)
    g.add_node("rewrite_generator", rewrite_generator)
    g.add_node("format_output", format_output)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "validate_criteria")
    g.add_edge("validate_criteria", "clarity_scorer")
    g.add_edge("clarity_scorer", "generate_findings")
    g.add_edge("generate_findings", "rewrite_generator")
    g.add_edge("rewrite_generator", "format_output")
    g.add_edge("format_output", END)
    return g


_compiled_graph = _build_graph().compile()


def run_evaluation(request: EvaluateRequest) -> EvaluationResult:
    """
    Execute the evaluation StateGraph synchronously.
    All LLM calls happen inside nodes via the sync LiteLLMClient.
    Blocks until complete (up to LANGGRAPH_TIMEOUT seconds).
    """
    initial_state: EvalState = {
        "run_id": request.run_id,
        "story_id": request.story_id,
        "org_id": request.org_id,
        "title": request.title,
        "description": request.description,
        "acceptance_criteria": request.acceptance_criteria,
        "context_hints": request.context_hints,
        "parsed_criteria": [],
        "criteria_completeness": 0.0,
        "clarity_score": 5.0,
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

    logger.info(
        "Starting evaluation workflow run_id=%s story_id=%s",
        request.run_id, request.story_id,
    )
    final_state = _compiled_graph.invoke(initial_state)
    logger.info(
        "Completed evaluation run_id=%s score=%.2f ampel=%s",
        request.run_id, final_state["final_score"], final_state["ampel"],
    )

    findings = [EvalFinding(**f) for f in final_state.get("findings", [])]
    criteria_scores = {
        k: CriterionScore(**v)
        for k, v in final_state.get("criteria_scores", {}).items()
    }

    return EvaluationResult(
        run_id=final_state["run_id"],
        story_id=final_state["story_id"],
        org_id=final_state["org_id"],
        score=final_state["final_score"],
        ampel=Ampel(final_state["ampel"]),
        knockout=final_state["knockout"],
        confidence=final_state["confidence"],
        criteria_scores=criteria_scores,
        findings=findings,
        open_questions=final_state.get("open_questions", []),
        rewrite=RewriteSuggestion(
            title=final_state.get("rewrite_title", request.title),
            story=final_state.get("rewrite_story", request.description),
            acceptance_criteria=final_state.get("rewrite_criteria", []),
        ),
        model_used=final_state.get("model_used", "eval-quality"),
        input_tokens=final_state["total_input_tokens"],
        output_tokens=final_state["total_output_tokens"],
    )
