"""
retry.py — Exponential backoff with Retry-After support.

Design rules:
- Async-first (all retry loops use asyncio.sleep)
- No dependencies outside stdlib + asyncio
- Caller supplies is_rate_limit predicate — works with any HTTP client
- Caps delay at max_delay even when Retry-After is huge
- Logs each retry at WARNING level (no secrets in log messages)
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class RateLimitExhausted(Exception):
    """Raised when all retry attempts are consumed on rate-limit responses."""


@dataclass
class RetryConfig:
    """Configures backoff behaviour for a single call site."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True


def parse_retry_after(headers: dict) -> Optional[float]:
    """
    Parse the Retry-After header value into seconds (float).
    Returns None if absent or HTTP-date format (unsupported).
    """
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(raw)
        logger.debug("Retry-After header: %.1fs", value)
        return value
    except ValueError:
        return None


def _compute_delay(attempt: int, config: RetryConfig, retry_after: Optional[float]) -> float:
    if retry_after is not None:
        # Honour the server's explicit Retry-After value; no jitter applied.
        delay = retry_after
    else:
        delay = config.base_delay * (config.backoff_factor ** (attempt - 1))
        if config.jitter:
            delay *= 1.0 + random.uniform(-0.1, 0.1)
    return min(delay, config.max_delay)


async def retry_on_rate_limit(
    fn: Callable[[], Awaitable[Any]],
    config: RetryConfig = RetryConfig(),
    *,
    is_rate_limit: Callable[[Exception], bool] = lambda e: getattr(e, "status_code", None) == 429,
    get_headers: Callable[[Exception], dict] = lambda e: getattr(e, "response_headers", {}),
) -> Any:
    """
    Execute async fn(), retrying on rate-limit errors with exponential backoff.

    Raises RateLimitExhausted when all attempts consumed.
    Non-rate-limit exceptions propagate immediately.
    """
    for attempt in range(1, config.max_attempts + 1):
        try:
            return await fn()
        except Exception as exc:
            if not is_rate_limit(exc):
                raise

            if attempt == config.max_attempts:
                logger.error(
                    "Rate limit exhausted after %d attempts: %s",
                    config.max_attempts,
                    type(exc).__name__,
                )
                raise RateLimitExhausted(
                    f"Rate limit not resolved after {config.max_attempts} attempts"
                ) from exc

            headers = get_headers(exc)
            retry_after = parse_retry_after(headers)
            delay = _compute_delay(attempt, config, retry_after)

            logger.warning(
                "Rate limited (attempt %d/%d) — waiting %.1fs [%s]",
                attempt,
                config.max_attempts,
                delay,
                "Retry-After header" if retry_after else "backoff",
            )
            await asyncio.sleep(delay)
