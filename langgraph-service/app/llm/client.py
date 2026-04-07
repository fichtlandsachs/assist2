from __future__ import annotations
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    pass


class LiteLLMClient:
    """
    Synchronous LiteLLM client.
    All LangGraph nodes are called by StateGraph.invoke() (sync),
    so we use httpx.Client (sync) here — no asyncio complexity needed.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self._base_url = (base_url or settings.litellm_base_url).rstrip("/")
        self._api_key = api_key or settings.litellm_api_key

    def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> tuple[str, dict]:
        """
        Call LiteLLM /chat/completions synchronously.
        Returns (content_text, usage_dict).
        Raises LLMCallError on any failure.
        """
        payload: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            with httpx.Client(timeout=120.0) as http:
                response = http.post(
                    f"{self._base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as e:
            raise LLMCallError(f"LiteLLM timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMCallError(
                f"LiteLLM HTTP error {e.response.status_code}: {e.response.text}"
            ) from e
        except Exception as e:
            raise LLMCallError(f"LiteLLM unexpected error: {e}") from e

        content = data["choices"][0]["message"]["content"] or ""
        usage = {
            "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
            "model": data.get("model", model),
        }
        logger.debug(
            "LLM call model=%s in=%d out=%d",
            model, usage["input_tokens"], usage["output_tokens"],
        )
        return content.strip(), usage
