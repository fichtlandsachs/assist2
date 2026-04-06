"""
ionos_adapter.py — IONOS AI provider adapter.

Uses OpenAI-compatible API at https://openai.ionos.com/openai.
Native IONOS endpoints (/predictions, /collections) are NOT used here.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import openai

from app.services.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)

# In-process model list cache keyed by api_base
_MODEL_CACHE: dict = {}

# Map LiteLLM aliases → real IONOS model IDs
_IONOS_ALIAS_MAP: dict[str, str] = {
    "ionos-fast":      "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "ionos-quality":   "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "ionos-reasoning": "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "ionos-embed":     "BAAI/bge-m3",
}


class IONOSAdapter(ProviderAdapter):

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model_cache_ttl: int = 300,
        timeout: int = 60,
    ) -> None:
        if not api_key:
            logger.warning("IONOSAdapter: IONOS_API_KEY is not set — calls will fail")

        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._cache_ttl = model_cache_ttl
        self._timeout = timeout

        self._openai = openai.OpenAI(
            api_key=api_key or "placeholder",
            base_url=f"{self._api_base}/v1",
            timeout=timeout,
            max_retries=0,
        )

    @property
    def provider_name(self) -> str:
        return "ionos"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        resolved = _IONOS_ALIAS_MAP.get(model, model)
        resp = self._openai.chat.completions.create(
            model=resolved,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        content = resp.choices[0].message.content
        text = (content or "").strip()
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
        return text, usage

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        resolved = _IONOS_ALIAS_MAP.get(model, model)
        resp = self._openai.embeddings.create(model=resolved, input=texts)
        return [item.embedding for item in resp.data]

    async def list_models(self) -> list[str]:
        import asyncio
        now = time.monotonic()
        cached = _MODEL_CACHE.get(self._api_base)
        if cached and self._cache_ttl > 0:
            if now - cached["fetched_at"] < self._cache_ttl:
                return cached["models"]

        loop = asyncio.get_event_loop()
        page = await loop.run_in_executor(None, self._openai.models.list)
        model_ids = [m.id for m in page.data]
        _MODEL_CACHE[self._api_base] = {"models": model_ids, "fetched_at": now}
        return model_ids

    def close(self) -> None:
        self._openai.close()
