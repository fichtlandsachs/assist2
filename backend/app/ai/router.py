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
from app.config import get_settings

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


def route_request(
    complexity: ComplexityScore,
    task_type: TaskType,
    provider: str = "anthropic",
    model_override: str = "",
) -> RouteDecision:
    """
    Produce a RouteDecision from complexity classification and task type.
    Falls back to medium if an unknown combination is passed.

    model_override: org-level override takes priority over env override.
    provider: "anthropic" (default) or "openai".
    """
    settings = get_settings()
    level = complexity.level
    entry = _TABLE.get((task_type, level), _TABLE[("suggest", "medium")])

    # Priority: org-level override → env-level override → default for provider
    model_map = _MODEL_MAP_OPENAI if provider == "openai" else _MODEL_MAP
    env_override = getattr(settings, "AI_MODEL_OVERRIDE", "")
    effective_override = model_override or env_override
    model = effective_override if effective_override else model_map[level]

    return RouteDecision(
        model=model,
        max_tokens=entry["max_tokens"],
        temperature=entry["temperature"],
        pipeline=entry["pipeline"],
        complexity_level=level,
        task_type=task_type,
    )
