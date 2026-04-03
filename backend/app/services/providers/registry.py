"""
registry.py — Provider factory: model alias → adapter instance.
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _get_ionos_adapter():
    from app.services.providers.ionos_adapter import IONOSAdapter
    from app.config import get_settings
    s = get_settings()
    return IONOSAdapter(
        api_base=s.IONOS_API_BASE,
        api_key=s.IONOS_API_KEY,
        model_cache_ttl=s.IONOS_MODEL_CACHE_TTL,
    )


def get_adapter_for_model(model_alias: str):
    """Return the ProviderAdapter for the given LiteLLM model alias."""
    if model_alias.startswith("ionos"):
        return _get_ionos_adapter()
    if model_alias.startswith("claude") or model_alias.startswith("gpt"):
        return _get_legacy_adapter(model_alias)
    raise ValueError(f"No adapter registered for model alias: {model_alias!r}")


@lru_cache(maxsize=None)
def _get_legacy_adapter(model_alias: str):
    from app.services.providers.base import ProviderAdapter
    from app.ai.pipeline import ProviderClient
    import anthropic
    import openai as _openai
    from app.config import get_settings

    s = get_settings()

    class _LegacyAdapter(ProviderAdapter):
        @property
        def provider_name(self) -> str:
            return "anthropic" if model_alias.startswith("claude") else "openai"

        def chat(self, model, messages, max_tokens, temperature):
            if model_alias.startswith("claude"):
                raw = anthropic.Anthropic(api_key=s.ANTHROPIC_API_KEY)
                client = ProviderClient("anthropic", raw)
            else:
                raw = _openai.OpenAI(api_key=s.OPENAI_API_KEY)
                client = ProviderClient("openai", raw)
            return client.call(model, max_tokens, temperature, messages)

        def embed(self, model: str, texts: list[str]) -> list[list[float]]:
            raise NotImplementedError(f"{self.provider_name} embed not supported via legacy adapter")

        def is_available(self) -> bool:
            if model_alias.startswith("claude"):
                return bool(s.ANTHROPIC_API_KEY)
            if model_alias.startswith("gpt"):
                return bool(s.OPENAI_API_KEY)
            return False

    return _LegacyAdapter()
