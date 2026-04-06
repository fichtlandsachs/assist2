"""
Pipeline executor — single-stage or multi-stage LLM processing.

single:  one call, return result directly
multi:   stage-1 decompose/analyse → stage-2 improve using stage-1 output
         used only for high-complexity inputs to produce better results

Both modes return (raw_text: str, total_usage: dict).
Usage dict: {"input_tokens": int, "output_tokens": int}
"""
from __future__ import annotations

import logging

from app.ai.router import RouteDecision

logger = logging.getLogger(__name__)

_ANALYSIS_PREAMBLE = """Du bist ein kritischer Analyst. Deine Aufgabe in diesem Schritt:
Analysiere den folgenden Input strukturiert und identifiziere:
1. Fehlende Informationen
2. Unklarheiten oder Widersprüche
3. Risiken und kritische Punkte
4. Was für eine vollständige Verarbeitung benötigt wird

Antworte strukturiert aber NICHT als JSON — Prosa-Text ist hier korrekt.
"""


class ProviderClient:
    """Unified wrapper for Anthropic and OpenAI clients."""

    def __init__(self, provider: str, raw_client):
        self.provider = provider
        self._client = raw_client

    def call(
        self, model: str, max_tokens: int, temperature: float, messages: list
    ) -> tuple[str, dict]:
        if self.provider == "ionos":
            from app.core.observability import timed_call
            from app.services.providers.ionos_adapter import _IONOS_ALIAS_MAP
            resolved_model = _IONOS_ALIAS_MAP.get(model, model)
            with timed_call("ionos", resolved_model, "pipeline") as meta:
                resp = self._client.chat.completions.create(
                    model=resolved_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                )
                content = resp.choices[0].message.content
                text = (content or "").strip()
                usage = {
                    "input_tokens": resp.usage.prompt_tokens,
                    "output_tokens": resp.usage.completion_tokens,
                }
                meta["input_tokens"] = usage["input_tokens"]
                meta["output_tokens"] = usage["output_tokens"]
            return text, usage

        if self.provider == "openai":
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                )
                text = resp.choices[0].message.content.strip()
                usage = {
                    "input_tokens": resp.usage.prompt_tokens,
                    "output_tokens": resp.usage.completion_tokens,
                }
                return text, usage
            except Exception as exc:
                # Fallback to Anthropic on quota/permission errors
                _exc_type = type(exc).__name__
                if any(k in _exc_type for k in ("RateLimit", "PermissionDenied", "QuotaExceeded", "AuthenticationError", "APIConnection", "ConnectError", "Connection")):
                    logger.warning("OpenAI call failed (%s: %s) — falling back to Anthropic", _exc_type, exc)
                    return self._call_anthropic_fallback(max_tokens, temperature, messages)
                raise

        # anthropic
        msg = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        text = msg.content[0].text.strip()
        usage = {
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
        }
        return text, usage

    def _call_anthropic_fallback(
        self, max_tokens: int, temperature: float, messages: list
    ) -> tuple[str, dict]:
        """Fallback: use Anthropic Claude when OpenAI is unavailable."""
        import anthropic as _anthropic
        from app.config import get_settings
        settings = get_settings()
        fallback_client = _anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = fallback_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        text = msg.content[0].text.strip()
        usage = {
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
        }
        return text, usage


def run_single_stage(
    client: ProviderClient,
    prompt: str,
    decision: RouteDecision,
) -> tuple[str, dict]:
    """Execute a single LLM call. Returns (text, usage)."""
    return client.call(
        model=decision.model,
        max_tokens=decision.max_tokens,
        temperature=decision.temperature,
        messages=[{"role": "user", "content": prompt}],
    )


def run_multi_stage(
    client: ProviderClient,
    prompt: str,
    decision: RouteDecision,
) -> tuple[str, dict]:
    """
    Two-stage pipeline for high-complexity inputs.

    Stage 1: Analysis pass — understand what's incomplete or risky.
             Uses half the token budget, slightly higher temperature for breadth.
    Stage 2: Improvement pass — uses Stage 1 analysis to produce a better output.
             Uses the full token budget, lower temperature for precision.

    Returns combined (final_text, total_usage).
    """
    stage1_budget = max(decision.max_tokens // 2, 512)

    # ── Stage 1: Analytical decomposition ──────────────────────────────────
    stage1_prompt = f"{_ANALYSIS_PREAMBLE}\n\nInput:\n{prompt}"
    analysis, usage1 = client.call(
        model=decision.model,
        max_tokens=stage1_budget,
        temperature=min(decision.temperature + 0.15, 0.70),  # slightly broader
        messages=[{"role": "user", "content": stage1_prompt}],
    )

    # ── Stage 2: Targeted improvement using Stage 1 findings ───────────────
    stage2_prompt = (
        f"Voranalyse (Schritt 1):\n{analysis}\n\n"
        f"Aufgabe (Schritt 2 — nutze die Voranalyse):\n{prompt}"
    )
    result, usage2 = client.call(
        model=decision.model,
        max_tokens=decision.max_tokens,
        temperature=decision.temperature,  # precise for final output
        messages=[{"role": "user", "content": stage2_prompt}],
    )

    total_usage = {
        "input_tokens": usage1["input_tokens"] + usage2["input_tokens"],
        "output_tokens": usage1["output_tokens"] + usage2["output_tokens"],
    }
    return result, total_usage


def execute_pipeline(
    client: ProviderClient,
    prompt: str,
    decision: RouteDecision,
) -> tuple[str, dict]:
    """Entry point — dispatches to single or multi based on RouteDecision."""
    if decision.pipeline == "multi":
        return run_multi_stage(client, prompt, decision)
    return run_single_stage(client, prompt, decision)
