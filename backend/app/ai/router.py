"""
AI Request Router — maps a ComplexityScore + task type to a RouteDecision.

RouteDecision carries:
  - model          which Claude model to use
  - max_tokens     upper token budget
  - temperature    sampling temperature
  - pipeline       "single" | "multi"  — drives pipeline.py selection

Routing table:

  task=suggest, low     → haiku,   512 tok,  0.3 temp,  single
  task=suggest, medium  → sonnet,  1024 tok, 0.4 temp,  single
  task=suggest, high    → sonnet,  2048 tok, 0.2 temp,  multi

  task=docs,    low     → haiku,   768 tok,  0.3 temp,  single
  task=docs,    medium  → sonnet,  1536 tok, 0.4 temp,  single
  task=docs,    high    → sonnet,  2048 tok, 0.3 temp,  multi
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.ai.complexity_scorer import ComplexityScore

TaskType = Literal["suggest", "docs"]
PipelineMode = Literal["single", "multi"]


@dataclass(frozen=True)
class RouteDecision:
    model: str
    max_tokens: int
    temperature: float
    pipeline: PipelineMode
    complexity_level: str       # kept for logging / AIStep
    task_type: TaskType


# ---------------------------------------------------------------------------
# Routing table (data-driven, easy to extend)
# ---------------------------------------------------------------------------

_TABLE: dict[tuple[TaskType, str], dict] = {
    ("suggest", "low"):    {"max_tokens": 1024, "temperature": 0.30, "pipeline": "single"},
    ("suggest", "medium"): {"max_tokens": 2048, "temperature": 0.40, "pipeline": "single"},
    ("suggest", "high"):   {"max_tokens": 4096, "temperature": 0.20, "pipeline": "multi"},
    ("docs",    "low"):    {"max_tokens": 1536, "temperature": 0.30, "pipeline": "single"},
    ("docs",    "medium"): {"max_tokens": 3072, "temperature": 0.40, "pipeline": "single"},
    ("docs",    "high"):   {"max_tokens": 4096, "temperature": 0.30, "pipeline": "multi"},
}

_MODEL_MAP: dict[str, str] = {
    "low":    "claude-haiku-4-5-20251001",   # fast, cheap, sufficient for simple inputs
    "medium": "claude-sonnet-4-6",            # current default — balanced
    "high":   "claude-sonnet-4-6",            # most capable for complex / risky
}

_MODEL_MAP_OPENAI: dict[str, str] = {
    "low":    "gpt-4o-mini",   # fast, cheap
    "medium": "gpt-4o-mini",   # broadly accessible
    "high":   "gpt-4o-mini",   # broadly accessible
}

_MODEL_MAP_IONOS: dict[str, str] = {
    "low":    "ionos-fast",      # Llama 3.1 8B — fast, cheap
    "medium": "ionos-quality",   # Llama 3.1 70B — balanced
    "high":   "ionos-reasoning", # Mixtral 8x7B — complex reasoning
}


def route_request(
    complexity: ComplexityScore,
    task_type: TaskType,
    provider: str = "ionos",
) -> RouteDecision:
    """
    Produce a RouteDecision from complexity classification and task type.
    Falls back to medium if an unknown combination is passed.

    All calls go through LiteLLM; provider selects the model map.
    """
    level = complexity.level
    entry = _TABLE.get((task_type, level), _TABLE[("suggest", "medium")])

    if provider == "openai":
        model_map = _MODEL_MAP_OPENAI
    elif provider == "ionos":
        model_map = _MODEL_MAP_IONOS
    else:
        model_map = _MODEL_MAP
    model = model_map[level]

    return RouteDecision(
        model=model,
        max_tokens=entry["max_tokens"],
        temperature=entry["temperature"],
        pipeline=entry["pipeline"],
        complexity_level=level,
        task_type=task_type,
    )
