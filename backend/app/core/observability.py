"""
observability.py — Structured logging helpers for AI provider calls.

Emits structured log lines for:
  - Every provider call (model, provider, task, latency, tokens)
  - Rate-limit events (provider, attempt, delay — no key material)
  - Fallback activations
  - Request-ID correlation (injected from HTTP header or generated)

Never log prompt text, API keys, or response bodies.
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Generator

logger = logging.getLogger(__name__)

# Context variable — holds the current request ID for the duration of a request.
_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    rid = _request_id_var.get()
    if not rid:
        rid = str(uuid.uuid4())[:8]
        _request_id_var.set(rid)
    return rid


def set_request_id(rid: str) -> None:
    _request_id_var.set(rid)


@dataclass
class ProviderCallMetrics:
    provider: str
    model: str
    task_type: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    request_id: str
    pipeline_stage: str = "single"
    fallback: bool = False
    error: str = ""


def log_provider_call(m: ProviderCallMetrics) -> None:
    """Emit a single structured log line for one provider call."""
    status = "error" if m.error else "ok"
    logger.info(
        "provider_call "
        "request_id=%s provider=%s model=%s task=%s pipeline=%s "
        "latency_ms=%d in_tokens=%d out_tokens=%d fallback=%s status=%s%s",
        m.request_id,
        m.provider,
        m.model,
        m.task_type,
        m.pipeline_stage,
        m.latency_ms,
        m.input_tokens,
        m.output_tokens,
        m.fallback,
        status,
        f" error={m.error}" if m.error else "",
    )


def log_rate_limit(provider: str, attempt: int, delay_s: float, source: str) -> None:
    """Log a rate-limit event. Never includes key material."""
    logger.warning(
        "rate_limit provider=%s attempt=%d delay_s=%.1f source=%s request_id=%s",
        provider,
        attempt,
        delay_s,
        source,
        get_request_id(),
    )


def log_fallback(from_provider: str, to_provider: str, reason: str) -> None:
    logger.warning(
        "provider_fallback from=%s to=%s reason=%s request_id=%s",
        from_provider,
        to_provider,
        reason,
        get_request_id(),
    )


@contextmanager
def timed_call(
    provider: str,
    model: str,
    task_type: str,
    pipeline_stage: str = "single",
) -> Generator[dict, None, None]:
    """
    Context manager that measures wall-clock latency and emits a metrics log line.

    Usage:
        with timed_call("ionos", "ionos-fast", "suggest") as meta:
            result = do_call()
            meta["input_tokens"] = ...
            meta["output_tokens"] = ...
    """
    meta: dict = {
        "input_tokens": 0,
        "output_tokens": 0,
        "error": "",
        "fallback": False,
    }
    t0 = time.monotonic()
    try:
        yield meta
    except Exception as exc:
        meta["error"] = type(exc).__name__
        raise
    finally:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        log_provider_call(
            ProviderCallMetrics(
                provider=provider,
                model=model,
                task_type=task_type,
                latency_ms=elapsed_ms,
                input_tokens=meta.get("input_tokens", 0),
                output_tokens=meta.get("output_tokens", 0),
                request_id=get_request_id(),
                pipeline_stage=pipeline_stage,
                fallback=meta.get("fallback", False),
                error=meta.get("error", ""),
            )
        )
