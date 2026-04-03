"""
routing_matrix.py — Maps task category + complexity to a LiteLLM model alias.

Adding a provider = adding entries to _AUTO_MAP + LiteLLM config. No business-logic changes.
"""
from __future__ import annotations

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)

_TASK_TO_SETTING: dict[str, str] = {
    "suggest": "PROVIDER_ROUTING_SUGGEST",
    "docs":    "PROVIDER_ROUTING_DOCS",
}

_AUTO_MAP: dict[tuple[bool, str], str] = {
    (True,  "low"):    "ionos-fast",
    (True,  "medium"): "ionos-quality",
    (True,  "high"):   "ionos-quality",
    (False, "low"):    "claude-haiku-4-5",
    (False, "medium"): "claude-sonnet-4-6",
    (False, "high"):   "claude-sonnet-4-6",
}


def _has_key(settings, model_alias: str) -> bool:
    if model_alias.startswith("ionos"):
        return bool(settings.IONOS_API_KEY)
    if model_alias.startswith("claude"):
        return bool(settings.ANTHROPIC_API_KEY)
    if model_alias.startswith("gpt"):
        return bool(settings.OPENAI_API_KEY)
    return True


def resolve_model(task: str, complexity: str = "medium") -> str:
    """Return the LiteLLM model alias for this task + complexity."""
    settings = get_settings()
    field = _TASK_TO_SETTING.get(task, "PROVIDER_ROUTING_SUGGEST")
    configured = getattr(settings, field, "auto")

    if configured == "auto":
        has_ionos = bool(settings.IONOS_API_KEY)
        model = _AUTO_MAP.get((has_ionos, complexity), "claude-sonnet-4-6")
    else:
        model = configured

    if not _has_key(settings, model):
        fallback = settings.PROVIDER_ROUTING_FALLBACK
        logger.warning("routing: model=%s has no API key — using fallback=%s", model, fallback)
        return fallback

    return model
