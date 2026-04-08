"""LangGraph workflow: semantic duplicate detection."""
from __future__ import annotations

import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.semantic_comparator import semantic_comparator
from app.schemas.evaluation import (
    DuplicateCandidate,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)

logger = logging.getLogger(__name__)


class DuplicateCheckState(TypedDict):
    # Input
    story_id: str
    org_id: str
    title: str
    description: str
    acceptance_criteria: str
    candidates: list[dict]
    # Intermediate: candidate lookup by story_id for enrichment
    candidate_map: dict  # story_id -> DuplicateCandidate dict
    # Output
    comparison_results: list[dict]
    duplicates: list[dict]
    similar: list[dict]


def format_results(state: DuplicateCheckState) -> dict:
    """
    Pure formatting node.
    Splits comparison_results into duplicates and similar lists,
    enriching each entry with the original similarity_score from candidate_map.
    """
    candidate_map: dict = state.get("candidate_map", {})
    comparison_results: list[dict] = state.get("comparison_results", [])

    duplicates: list[dict] = []
    similar: list[dict] = []

    for result in comparison_results:
        sid = result["story_id"]
        original = candidate_map.get(sid, {})
        enriched = {
            "story_id": sid,
            "title": original.get("title", ""),
            "similarity_score": original.get("similarity_score", 0.0),
            "explanation": result.get("explanation", ""),
        }
        if result.get("classification") == "duplicate":
            duplicates.append(enriched)
        else:
            similar.append(enriched)

    return {"duplicates": duplicates, "similar": similar}


def _build_graph() -> StateGraph:
    g = StateGraph(DuplicateCheckState)
    g.add_node("semantic_comparator", semantic_comparator)
    g.add_node("format_results", format_results)
    g.set_entry_point("semantic_comparator")
    g.add_edge("semantic_comparator", "format_results")
    g.add_edge("format_results", END)
    return g


_compiled_graph = _build_graph().compile()


def run_duplicate_check(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    """
    Execute the duplicate check StateGraph synchronously.
    Accepts a DuplicateCheckRequest with pre-fetched candidates (from pgvector search).
    Returns a DuplicateCheckResponse with classified duplicates and similar stories.
    """
    candidates_as_dicts = [c.model_dump() for c in request.candidates]
    candidate_map = {c["story_id"]: c for c in candidates_as_dicts}

    initial_state: DuplicateCheckState = {
        "story_id": request.story_id,
        "org_id": request.org_id,
        "title": request.title,
        "description": request.description,
        "acceptance_criteria": request.acceptance_criteria,
        "candidates": candidates_as_dicts,
        "candidate_map": candidate_map,
        "comparison_results": [],
        "duplicates": [],
        "similar": [],
    }

    logger.info(
        "Starting duplicate check workflow story_id=%s org_id=%s candidates=%d",
        request.story_id,
        request.org_id,
        len(request.candidates),
    )
    final_state = _compiled_graph.invoke(initial_state)
    logger.info(
        "Completed duplicate check story_id=%s duplicates=%d similar=%d",
        request.story_id,
        len(final_state["duplicates"]),
        len(final_state["similar"]),
    )

    duplicates = [DuplicateCandidate(**d) for d in final_state["duplicates"]]
    similar = [DuplicateCandidate(**s) for s in final_state["similar"]]

    return DuplicateCheckResponse(duplicates=duplicates, similar=similar)
