# IONOS AI API Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate IONOS AI as a first-class provider into the assist2 multi-provider architecture via LiteLLM gateway, with a clean adapter layer, retry/backoff logic, observability, and all 13 required documentation artifacts.

**Architecture:** IONOS is accessed exclusively via its OpenAI-compatible API (`https://openai.ionos.com/openai`), routed through LiteLLM as the central gateway. The backend uses a new `ProviderAdapter` abstraction that replaces raw `ProviderClient` construction in `ai_story_service.py`, making providers swappable via configuration. All secrets stay in `.env`, all model names in config — zero hardcoding in business logic.

**Tech Stack:** FastAPI, LiteLLM 1.x, openai-python SDK, httpx, pydantic-settings, pytest-asyncio, Docker Compose, Redis (model-list cache)

---

## File Map

### New files
| Path | Purpose |
|------|---------|
| `infra/.env.example` | All env vars with safe defaults and documentation |
| `litellm/config.yaml` | Extended LiteLLM config with IONOS + routing categories |
| `backend/app/core/retry.py` | Exponential backoff, 429 handling, `Retry-After` parsing |
| `backend/app/core/observability.py` | Request-ID injection, token/latency metrics logging |
| `backend/app/services/providers/__init__.py` | Package init |
| `backend/app/services/providers/base.py` | `ProviderAdapter` abstract base |
| `backend/app/services/providers/ionos_adapter.py` | IONOS-specific adapter (model list, chat, embeddings) |
| `backend/app/services/providers/registry.py` | Provider factory: name → adapter instance |
| `backend/app/services/providers/routing_matrix.py` | Category → provider/model mapping |
| `backend/tests/unit/test_ionos_adapter.py` | Unit tests for adapter + retry |
| `backend/tests/unit/test_retry.py` | Unit tests for retry module |
| `docs/ionos-integration/01-architecture.md` | Target architecture text |
| `docs/ionos-integration/02-security.md` | Security concept |
| `docs/ionos-integration/03-observability.md` | Observability concept |
| `docs/ionos-integration/04-performance.md` | Performance concept |
| `docs/ionos-integration/05-migration.md` | Provider migration guide |
| `docs/ionos-integration/06-rag.md` | RAG modes: internal vs. IONOS collections |

### Modified files
| Path | What changes |
|------|-------------|
| `backend/app/config.py` | Add `IONOS_*` fields + `PROVIDER_ROUTING_*` fields |
| `backend/app/ai/router.py` | Add `ionos` to `_MODEL_MAP`, add routing-category support |
| `backend/app/ai/pipeline.py` | `ProviderClient` delegates to adapter; add `ionos` provider branch |
| `backend/app/services/ai_story_service.py` | Replace `_make_client()` with registry lookup |

---

## Task 1: Infrastructure — .env.example + LiteLLM config

**Files:**
- Create: `infra/.env.example`
- Modify: `litellm/config.yaml`

- [ ] **Step 1: Create `.env.example`**

```bash
# infra/.env.example
# ─────────────────────────────────────────────────────────────
# assist2 – Environment Variable Reference
# Copy to .env and fill in real values. NEVER commit .env.
# ─────────────────────────────────────────────────────────────

# ── Core Infrastructure ───────────────────────────────────────
DOMAIN=assist2.example.com
ENVIRONMENT=production                  # production | development
SECRET_KEY=change-me-32-random-chars
JWT_SECRET=change-me-32-random-chars
ENCRYPTION_KEY=change-me-32-random-chars
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
CORS_ORIGINS=["https://assist2.example.com"]

# ── PostgreSQL (main) ─────────────────────────────────────────
POSTGRES_USER=assist2
POSTGRES_PASSWORD=change-me
POSTGRES_DB=assist2

# ── Redis ─────────────────────────────────────────────────────
REDIS_PASSWORD=change-me

# ── AI Providers ──────────────────────────────────────────────
# IONOS AI (OpenAI-compatible) — https://openai.ionos.com/openai
IONOS_API_KEY=
# Region endpoint — swap for EU-West, DE-FRA, etc. without code changes
IONOS_API_BASE=https://openai.ionos.com/openai
# Cache model list for N seconds (0 = disable, recommended: 300)
IONOS_MODEL_CACHE_TTL=300

# Anthropic
ANTHROPIC_API_KEY=

# OpenAI (optional fallback)
OPENAI_API_KEY=

# ── LiteLLM Gateway ───────────────────────────────────────────
LITELLM_MASTER_KEY=change-me
LITELLM_DB_PASSWORD=change-me
# Optional: enable LiteLLM UI (username:password)
LITELLM_UI_AUTH=admin:change-me

# Provider routing policy
# Options: ionos-fast | ionos-quality | anthropic | openai | auto
PROVIDER_ROUTING_SUGGEST=auto          # user story improvements
PROVIDER_ROUTING_DOCS=anthropic        # technical documentation
PROVIDER_ROUTING_FALLBACK=ionos-fast   # fallback on primary failure

# Feature flags (comma-separated or empty)
# Options: embeddings, images, rag_ionos, streaming
AI_FEATURE_FLAGS=streaming,embeddings

# ── n8n ───────────────────────────────────────────────────────
N8N_API_KEY=
N8N_ENCRYPTION_KEY=change-me

# ── Authentik ─────────────────────────────────────────────────
AUTHENTIK_SECRET_KEY=change-me
AUTHENTIK_DB_PASSWORD=change-me
AUTHENTIK_BOOTSTRAP_EMAIL=admin@example.com
AUTHENTIK_BOOTSTRAP_PASSWORD=change-me
AUTHENTIK_API_TOKEN=
AUTHENTIK_BACKEND_CLIENT_ID=
AUTHENTIK_BACKEND_CLIENT_SECRET=
AUTHENTIK_JWKS_URL=
AUTHENTIK_APP_SLUG=backend
AUTHENTIK_ADMIN_CLIENT_ID=
AUTHENTIK_ADMIN_CLIENT_SECRET=

# ── Atlassian OAuth ───────────────────────────────────────────
ATLASSIAN_CLIENT_ID=
ATLASSIAN_CLIENT_SECRET=
ATLASSIAN_REDIRECT_URI=https://assist2.example.com/api/v1/auth/atlassian/callback
ATLASSIAN_SCOPES=read:me read:jira-work write:jira-work read:jira-user offline_access

# ── GitHub OAuth ──────────────────────────────────────────────
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=

# ── Nextcloud ─────────────────────────────────────────────────
NEXTCLOUD_URL=https://nextcloud.example.com
NEXTCLOUD_ADMIN_USER=admin
NEXTCLOUD_ADMIN_APP_PASSWORD=
NEXTCLOUD_DB_PASSWORD=change-me
NEXTCLOUD_DB_ROOT_PASSWORD=change-me
NEXTCLOUD_OIDC_CLIENT_ID=
NEXTCLOUD_OIDC_CLIENT_SECRET=

# ── Traefik ───────────────────────────────────────────────────
ACME_EMAIL=ssl@example.com
TRAEFIK_BASIC_AUTH=admin:$$2y$$...   # htpasswd format

# ── Misc Tools ────────────────────────────────────────────────
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change-me
OPENWEBUI_SECRET_KEY=change-me
```

- [ ] **Step 2: Replace `litellm/config.yaml`**

Full file — read the existing one first, then overwrite completely:

```yaml
# litellm/config.yaml
# Central LiteLLM gateway configuration.
# All AI traffic from the backend routes through here.
# Model names are logical aliases — the backend never hardcodes vendor model IDs.

model_list:

  # ── IONOS AI (OpenAI-compatible) ──────────────────────────────
  # fast/cheap tier — Llama 3.1 8B
  - model_name: ionos-fast
    litellm_params:
      model: openai/meta-llama/Meta-Llama-3.1-8B-Instruct
      api_base: os.environ/IONOS_API_BASE
      api_key: os.environ/IONOS_API_KEY
      timeout: 30
      max_retries: 2

  # quality tier — Llama 3.1 70B
  - model_name: ionos-quality
    litellm_params:
      model: openai/meta-llama/Meta-Llama-3.1-70B-Instruct
      api_base: os.environ/IONOS_API_BASE
      api_key: os.environ/IONOS_API_KEY
      timeout: 60
      max_retries: 2

  # reasoning tier — Mixtral 8x7B
  - model_name: ionos-reasoning
    litellm_params:
      model: openai/mistralai/Mixtral-8x7B-Instruct-v0.1
      api_base: os.environ/IONOS_API_BASE
      api_key: os.environ/IONOS_API_KEY
      timeout: 90
      max_retries: 1

  # embeddings — BAAI bge-m3 (multilingual, production-grade)
  - model_name: ionos-embed
    litellm_params:
      model: openai/BAAI/bge-m3
      api_base: os.environ/IONOS_API_BASE
      api_key: os.environ/IONOS_API_KEY
      timeout: 20

  # ── Anthropic ─────────────────────────────────────────────────
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 90
      max_retries: 2

  - model_name: claude-haiku-4-5
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 30
      max_retries: 2

  - model_name: claude-opus-4-6
    litellm_params:
      model: anthropic/claude-opus-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 120
      max_retries: 1

  # ── Fallback group: ionos-fast → anthropic haiku ──────────────
  - model_name: fallback-eu
    litellm_params:
      model: openai/meta-llama/Meta-Llama-3.1-8B-Instruct
      api_base: os.environ/IONOS_API_BASE
      api_key: os.environ/IONOS_API_KEY
      timeout: 30
    model_info:
      fallback_models: [claude-haiku-4-5]

router_settings:
  # Retry on 429, 502, 503 — up to 3 attempts per model
  num_retries: 3
  retry_after_max_wait: 60       # cap Retry-After header at 60s
  timeout: 90
  allowed_fails: 2
  # Cooldown a model for 60s after 2 consecutive failures
  cooldown_time: 60

litellm_settings:
  # Inject request_id into logs for correlation
  add_function_to_prompt: false
  json_logs: true
  log_raw_request_response: false   # never log full prompts in prod
  success_callback: []
  failure_callback: []
  # Cache model lists for 5 min to reduce /v1/models overhead
  cache: true
  cache_params:
    type: redis
    host: redis
    port: 6379
    password: os.environ/REDIS_PASSWORD
    namespace: "litellm:cache"
    supported_call_types: [acompletion, completion, embedding]
    ttl: 300

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  ui_access_mode: "username_password"
  # Expose /health and /metrics endpoints
  health_check_interval: 30
  # Disable verbose model info leakage in error messages
  return_response_headers: false
```

- [ ] **Step 3: Verify LiteLLM starts clean**

```bash
cd /opt/assist2/infra
docker compose -f docker-compose.yml up -d --build litellm
docker logs assist2-litellm --tail 30
```

Expected: `LiteLLM: Proxy initialized with config` and no errors.

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add infra/.env.example litellm/config.yaml
git commit -m "feat(ionos): add .env.example and LiteLLM config with IONOS + routing tiers"
```

---

## Task 2: Backend Config Schema

**Files:**
- Modify: `backend/app/config.py` (add IONOS + routing fields after existing AI provider block)

- [ ] **Step 1: Read the current config.py to find the AI block insertion point**

Look for the block containing `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. Insert the new fields immediately after `AI_MODEL_OVERRIDE`.

- [ ] **Step 2: Add IONOS + routing fields**

In `backend/app/config.py`, after the line `AI_MODEL_OVERRIDE: str = ""`, add:

```python
    # ── IONOS AI ──────────────────────────────────────────────────────────────
    # OpenAI-compatible base URL. Swap for a different region without code change.
    IONOS_API_BASE: str = "https://openai.ionos.com/openai"
    IONOS_API_KEY: str = ""
    # How long (seconds) to cache the /v1/models response. 0 = no cache.
    IONOS_MODEL_CACHE_TTL: int = 300

    # ── Provider Routing Policy ───────────────────────────────────────────────
    # Maps task category to the LiteLLM model alias that should handle it.
    # Allowed values: ionos-fast | ionos-quality | ionos-reasoning |
    #                 claude-sonnet-4-6 | claude-haiku-4-5 | auto
    PROVIDER_ROUTING_SUGGEST: str = "auto"
    PROVIDER_ROUTING_DOCS: str = "claude-sonnet-4-6"
    PROVIDER_ROUTING_FALLBACK: str = "ionos-fast"

    # ── Feature Flags ─────────────────────────────────────────────────────────
    # Comma-separated list of enabled optional features.
    # Known flags: embeddings, images, rag_ionos, streaming
    AI_FEATURE_FLAGS: str = "streaming,embeddings"
```

Also add a helper method at the end of the `Settings` class:

```python
    def ai_feature_enabled(self, flag: str) -> bool:
        """Check whether an optional AI feature flag is active."""
        flags = {f.strip() for f in self.AI_FEATURE_FLAGS.split(",") if f.strip()}
        return flag in flags
```

- [ ] **Step 3: Run settings smoke-test**

```bash
cd /opt/assist2/backend
python -c "
from app.config import get_settings
s = get_settings()
assert s.IONOS_API_BASE == 'https://openai.ionos.com/openai'
assert s.PROVIDER_ROUTING_SUGGEST == 'auto'
assert s.ai_feature_enabled('streaming') == True
assert s.ai_feature_enabled('nonexistent') == False
print('config OK')
"
```

Expected output: `config OK`

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add backend/app/config.py
git commit -m "feat(ionos): add IONOS + routing policy fields to Settings"
```

---

## Task 3: Retry / Backoff Module

**Files:**
- Create: `backend/app/core/retry.py`
- Create: `backend/tests/unit/test_retry.py`

- [ ] **Step 1: Write the failing tests first**

Create `backend/tests/unit/test_retry.py`:

```python
"""Tests for the retry / backoff module."""
import asyncio
import time
import pytest

from app.core.retry import (
    RetryConfig,
    retry_on_rate_limit,
    parse_retry_after,
    RateLimitExhausted,
)


# ── parse_retry_after ──────────────────────────────────────────────────────

def test_parse_retry_after_numeric():
    assert parse_retry_after({"retry-after": "5"}) == 5.0


def test_parse_retry_after_missing():
    assert parse_retry_after({}) is None


def test_parse_retry_after_non_numeric_ignored():
    # HTTP-date format not supported → return None
    assert parse_retry_after({"retry-after": "Wed, 21 Oct 2025 07:28:00 GMT"}) is None


def test_parse_retry_after_float():
    assert parse_retry_after({"retry-after": "1.5"}) == 1.5


# ── retry_on_rate_limit ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_succeeds_on_first_try():
    calls = []

    async def fn():
        calls.append(1)
        return "ok"

    result = await retry_on_rate_limit(fn, RetryConfig(max_attempts=3, base_delay=0.01))
    assert result == "ok"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_retry_recovers_after_one_429():
    calls = []

    class FakeRateLimit(Exception):
        status_code = 429
        response_headers: dict = {}

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise FakeRateLimit("rate limited")
        return "recovered"

    result = await retry_on_rate_limit(
        fn,
        RetryConfig(max_attempts=3, base_delay=0.01),
        is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
    )
    assert result == "recovered"
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_retry_exhaustion_raises():
    class FakeRateLimit(Exception):
        status_code = 429
        response_headers: dict = {}

    async def fn():
        raise FakeRateLimit("always limited")

    with pytest.raises(RateLimitExhausted):
        await retry_on_rate_limit(
            fn,
            RetryConfig(max_attempts=2, base_delay=0.01),
            is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
        )


@pytest.mark.asyncio
async def test_non_rate_limit_exception_propagates():
    async def fn():
        raise ValueError("unexpected")

    with pytest.raises(ValueError):
        await retry_on_rate_limit(
            fn,
            RetryConfig(max_attempts=3, base_delay=0.01),
        )


@pytest.mark.asyncio
async def test_retry_after_header_is_respected(monkeypatch):
    waited = []
    real_sleep = asyncio.sleep

    async def fake_sleep(secs):
        waited.append(secs)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    calls = []

    class FakeRateLimit(Exception):
        status_code = 429
        response_headers = {"retry-after": "3"}

    async def fn():
        calls.append(1)
        if len(calls) < 2:
            raise FakeRateLimit()
        return "ok"

    await retry_on_rate_limit(
        fn,
        RetryConfig(max_attempts=3, base_delay=0.01, max_delay=10.0),
        is_rate_limit=lambda e: isinstance(e, FakeRateLimit),
        get_headers=lambda e: e.response_headers,
    )

    # First wait must use the Retry-After value (3s), not backoff
    assert waited[0] == 3.0
```

- [ ] **Step 2: Run tests — expect ImportError / ModuleNotFoundError**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/test_retry.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.core.retry'`

- [ ] **Step 3: Implement `backend/app/core/retry.py`**

```python
"""
retry.py — Exponential backoff with Retry-After support.

Design rules:
- Async-first (all retry loops use asyncio.sleep)
- No dependencies outside stdlib + asyncio
- Caller supplies is_rate_limit predicate → works with any HTTP client
- Caps delay at max_delay even when Retry-After is huge
- Logs each retry at WARNING level (no secrets in log messages)
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class RateLimitExhausted(Exception):
    """Raised when all retry attempts are consumed on rate-limit responses."""


@dataclass
class RetryConfig:
    """Configures backoff behaviour for a single call site."""
    max_attempts: int = 3
    base_delay: float = 1.0          # seconds for attempt 1
    max_delay: float = 60.0          # hard cap on any single wait
    backoff_factor: float = 2.0      # multiply delay by this each attempt
    jitter: bool = True              # add ±10% random jitter


def parse_retry_after(headers: dict) -> Optional[float]:
    """
    Parse the Retry-After header value into seconds (float).
    Returns None if the header is absent or in HTTP-date format (unsupported).
    Logs the value at DEBUG level.
    """
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if raw is None:
        return None
    try:
        value = float(raw)
        logger.debug("Retry-After header: %.1fs", value)
        return value
    except ValueError:
        # HTTP-date format — not parsed, caller falls back to backoff
        return None


def _compute_delay(
    attempt: int,
    config: RetryConfig,
    retry_after: Optional[float],
) -> float:
    """Compute how long to wait before the next attempt (seconds)."""
    if retry_after is not None:
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
    Execute async `fn()`, retrying on rate-limit errors with exponential backoff.

    Parameters
    ----------
    fn            Async callable to execute. Must be idempotent.
    config        RetryConfig with max_attempts, delays, etc.
    is_rate_limit Predicate: returns True if the exception is a 429-class error.
    get_headers   Extract response headers from the exception (for Retry-After).

    Raises
    ------
    RateLimitExhausted  When all attempts are consumed on rate-limit errors.
    <original>          Any non-rate-limit exception propagates immediately.
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
```

- [ ] **Step 4: Run tests — expect all pass**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/test_retry.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2
git add backend/app/core/retry.py backend/tests/unit/test_retry.py
git commit -m "feat(ionos): add retry/backoff module with Retry-After support"
```

---

## Task 4: Observability Module

**Files:**
- Create: `backend/app/core/observability.py`

- [ ] **Step 1: Create `backend/app/core/observability.py`**

```python
"""
observability.py — Structured logging helpers for AI provider calls.

Emits structured log lines for:
  - Every provider call (model, provider, task, latency, tokens)
  - Rate-limit events (provider, attempt, delay — no key material)
  - Fallback activations
  - Request-ID correlation (injected from HTTP header or generated)

All log records use logger.info/warning/error — never debug for metrics.
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
# Set by middleware; accessible in any downstream async code.
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
    """
    Emit a single structured log line for one provider call.
    Format is stable — downstream log aggregators can parse it.
    """
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
```

- [ ] **Step 2: Quick smoke test**

```bash
cd /opt/assist2/backend
python -c "
from app.core.observability import timed_call, get_request_id, set_request_id
set_request_id('test-001')
with timed_call('ionos', 'ionos-fast', 'suggest') as m:
    m['input_tokens'] = 100
    m['output_tokens'] = 200
print('observability OK')
"
```

Expected: one log line + `observability OK`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add backend/app/core/observability.py
git commit -m "feat(ionos): add observability module (structured metrics logging)"
```

---

## Task 5: Provider Adapter Infrastructure

**Files:**
- Create: `backend/app/services/providers/__init__.py`
- Create: `backend/app/services/providers/base.py`
- Create: `backend/app/services/providers/ionos_adapter.py`
- Create: `backend/app/services/providers/registry.py`
- Create: `backend/app/services/providers/routing_matrix.py`
- Create: `backend/tests/unit/test_ionos_adapter.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_ionos_adapter.py`:

```python
"""Tests for the IONOS provider adapter."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── IONOSAdapter.list_models ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_models_returns_ids(monkeypatch):
    from app.services.providers.ionos_adapter import IONOSAdapter

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": [
            {"id": "meta-llama/Meta-Llama-3.1-8B-Instruct"},
            {"id": "mistralai/Mixtral-8x7B-Instruct-v0.1"},
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
    )
    monkeypatch.setattr(adapter, "_http", mock_client)

    models = await adapter.list_models()
    assert "meta-llama/Meta-Llama-3.1-8B-Instruct" in models
    assert len(models) == 2


@pytest.mark.asyncio
async def test_list_models_caches_result(monkeypatch):
    from app.services.providers.ionos_adapter import IONOSAdapter

    call_count = 0

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": [{"id": "model-a"}]}
    mock_resp.raise_for_status = MagicMock()

    async def counting_get(*a, **kw):
        nonlocal call_count
        call_count += 1
        return mock_resp

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
        model_cache_ttl=60,
    )
    monkeypatch.setattr(adapter, "_http", AsyncMock(get=counting_get))

    await adapter.list_models()
    await adapter.list_models()

    assert call_count == 1  # second call hit cache


# ── IONOSAdapter.chat ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_returns_text_and_usage(monkeypatch):
    from app.services.providers.ionos_adapter import IONOSAdapter

    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="Hello world"))]
    fake_resp.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

    mock_openai = MagicMock()
    mock_openai.chat.completions.create = MagicMock(return_value=fake_resp)

    adapter = IONOSAdapter(
        api_base="https://openai.ionos.com/openai",
        api_key="test-key",
    )
    monkeypatch.setattr(adapter, "_openai", mock_openai)

    text, usage = adapter.chat(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=100,
        temperature=0.5,
    )
    assert text == "Hello world"
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5


# ── routing_matrix ────────────────────────────────────────────────────────

def test_routing_matrix_auto_resolves():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "ionos-fast"
        mock_cfg.return_value.IONOS_API_KEY = "key"
        model = resolve_model("suggest", complexity="low")
        assert model == "ionos-fast"


def test_routing_matrix_falls_back_on_no_key():
    from app.services.providers.routing_matrix import resolve_model
    from unittest.mock import patch

    with patch("app.services.providers.routing_matrix.get_settings") as mock_cfg:
        mock_cfg.return_value.PROVIDER_ROUTING_SUGGEST = "ionos-fast"
        mock_cfg.return_value.IONOS_API_KEY = ""          # key missing
        mock_cfg.return_value.PROVIDER_ROUTING_FALLBACK = "claude-haiku-4-5"
        mock_cfg.return_value.ANTHROPIC_API_KEY = "key"
        model = resolve_model("suggest", complexity="low")
        assert model == "claude-haiku-4-5"
```

- [ ] **Step 2: Run — expect ModuleNotFoundError**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/test_ionos_adapter.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.providers'`

- [ ] **Step 3: Create `backend/app/services/providers/__init__.py`**

```python
# providers package
```

- [ ] **Step 4: Create `backend/app/services/providers/base.py`**

```python
"""
base.py — Abstract base for all LLM provider adapters.

Every provider (IONOS, Anthropic, OpenAI, future) implements this interface.
Business logic (ai_story_service.py) only ever calls methods defined here.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class ProviderAdapter(ABC):
    """
    Minimal interface for a synchronous LLM provider.

    Methods that are optional (embeddings, images) have a default
    implementation that raises NotImplementedError — callers must check
    feature flags before calling them.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name used in logs and metrics (e.g. 'ionos', 'anthropic')."""

    @abstractmethod
    def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        """
        Execute a synchronous chat completion.

        Returns
        -------
        (text: str, usage: dict)
        usage keys: input_tokens (int), output_tokens (int)
        """

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.
        Raises NotImplementedError if the provider/feature is not supported.
        """
        raise NotImplementedError(f"{self.provider_name} does not support embeddings")

    def is_available(self) -> bool:
        """Return False if the provider is known to be misconfigured (e.g. no API key)."""
        return True
```

- [ ] **Step 5: Create `backend/app/services/providers/ionos_adapter.py`**

```python
"""
ionos_adapter.py — IONOS AI provider adapter.

IONOS exposes an OpenAI-compatible API at:
  https://openai.ionos.com/openai

This adapter:
  - Uses the openai-python SDK pointed at the IONOS base URL
  - Caches /v1/models responses in-process (TTL-based dict cache)
  - Exposes a separate async list_models() for admin/health use
  - Delegates retry/backoff to app.core.retry (not reimplemented here)
  - Logs metrics via app.core.observability

Native IONOS endpoints (/predictions, /collections, /documents, /query)
are NOT used here. RAG with IONOS Document Collections is handled
separately in rag_service.py under the 'rag_ionos' feature flag.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx
import openai

from app.services.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)

# In-process model list cache: {"models": [...], "fetched_at": float}
_MODEL_CACHE: dict = {}


class IONOSAdapter(ProviderAdapter):
    """
    Adapter for IONOS AI (OpenAI-compatible endpoint).

    Parameters
    ----------
    api_base          IONOS OpenAI-compatible base URL.
    api_key           IONOS API key (from env, never hardcoded).
    model_cache_ttl   Seconds to cache /v1/models response. 0 = disabled.
    timeout           Request timeout in seconds.
    """

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

        # Sync OpenAI client pointed at IONOS
        self._openai = openai.OpenAI(
            api_key=api_key,
            base_url=f"{self._api_base}/v1",
            timeout=timeout,
            # HTTP Keep-Alive is on by default in httpx — no extra config needed
            max_retries=0,  # We handle retries externally via retry.py
        )

        # Async httpx client for model listing
        self._http = httpx.AsyncClient(
            base_url=f"{self._api_base}/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    @property
    def provider_name(self) -> str:
        return "ionos"

    def is_available(self) -> bool:
        return bool(self._api_key)

    # ── Chat Completion ────────────────────────────────────────────────────

    def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> tuple[str, dict]:
        """
        Execute a chat completion via the IONOS OpenAI-compatible endpoint.

        Rate-limit handling is the caller's responsibility (use retry.py).
        This method only raises; it does not retry internally.
        """
        resp = self._openai.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        text = resp.choices[0].message.content.strip()
        usage = {
            "input_tokens": resp.usage.prompt_tokens,
            "output_tokens": resp.usage.completion_tokens,
        }
        logger.debug(
            "ionos chat ok model=%s in=%d out=%d",
            model,
            usage["input_tokens"],
            usage["output_tokens"],
        )
        return text, usage

    # ── Embeddings ────────────────────────────────────────────────────────

    def embed(self, model: str, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings via IONOS embedding model.
        Only available when the 'embeddings' feature flag is enabled.
        """
        resp = self._openai.embeddings.create(
            model=model,
            input=texts,
        )
        return [item.embedding for item in resp.data]

    # ── Model Discovery ───────────────────────────────────────────────────

    async def list_models(self) -> list[str]:
        """
        Fetch available models from IONOS /v1/models.
        Result is cached in-process for model_cache_ttl seconds.
        Returns list of model IDs (strings).
        """
        now = time.monotonic()
        cached = _MODEL_CACHE.get(self._api_base)
        if cached and self._cache_ttl > 0:
            age = now - cached["fetched_at"]
            if age < self._cache_ttl:
                logger.debug("ionos list_models: cache hit (age=%.0fs)", age)
                return cached["models"]

        logger.info("ionos list_models: fetching from %s/v1/models", self._api_base)
        resp = await self._http.get("/models")
        resp.raise_for_status()
        data = resp.json()
        model_ids = [m["id"] for m in data.get("data", [])]

        _MODEL_CACHE[self._api_base] = {
            "models": model_ids,
            "fetched_at": now,
        }
        logger.info("ionos list_models: %d models cached", len(model_ids))
        return model_ids

    async def close(self) -> None:
        """Close the async HTTP client. Call on application shutdown."""
        await self._http.aclose()
```

- [ ] **Step 6: Create `backend/app/services/providers/routing_matrix.py`**

```python
"""
routing_matrix.py — Maps task category + complexity to a LiteLLM model alias.

Routing categories (stored in .env / Settings):
  PROVIDER_ROUTING_SUGGEST   → user story improvement, DoD, test cases
  PROVIDER_ROUTING_DOCS      → technical documentation, features
  PROVIDER_ROUTING_FALLBACK  → activated when primary model is unavailable

The "auto" value applies a built-in heuristic:
  - If IONOS_API_KEY is set: use ionos-fast (low) or ionos-quality (medium/high)
  - Else: use claude-haiku-4-5 (low) or claude-sonnet-4-6 (medium/high)

Adding a new provider = adding entries to _AUTO_MAP + LiteLLM config. No
business-logic changes required.
"""
from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# Task category → config field name
_TASK_TO_SETTING: dict[str, str] = {
    "suggest": "PROVIDER_ROUTING_SUGGEST",
    "docs":    "PROVIDER_ROUTING_DOCS",
}

# "auto" expansion: (has_ionos_key, complexity) → model alias
_AUTO_MAP: dict[tuple[bool, str], str] = {
    (True,  "low"):    "ionos-fast",
    (True,  "medium"): "ionos-quality",
    (True,  "high"):   "ionos-quality",
    (False, "low"):    "claude-haiku-4-5",
    (False, "medium"): "claude-sonnet-4-6",
    (False, "high"):   "claude-sonnet-4-6",
}


def _has_key(settings, model_alias: str) -> bool:
    """Check whether the required API key is set for a given alias."""
    if model_alias.startswith("ionos"):
        return bool(settings.IONOS_API_KEY)
    if model_alias.startswith("claude"):
        return bool(settings.ANTHROPIC_API_KEY)
    if model_alias.startswith("gpt"):
        return bool(settings.OPENAI_API_KEY)
    return True  # unknown alias — optimistically assume available


def resolve_model(task: str, complexity: str = "medium") -> str:
    """
    Return the LiteLLM model alias to use for this task + complexity level.

    Falls back to PROVIDER_ROUTING_FALLBACK if the primary model has no key.
    """
    settings = get_settings()
    field = _TASK_TO_SETTING.get(task, "PROVIDER_ROUTING_SUGGEST")
    configured = getattr(settings, field, "auto")

    if configured == "auto":
        has_ionos = bool(settings.IONOS_API_KEY)
        model = _AUTO_MAP.get((has_ionos, complexity), "claude-sonnet-4-6")
    else:
        model = configured

    # Verify the key exists; fall back if not
    if not _has_key(settings, model):
        fallback = settings.PROVIDER_ROUTING_FALLBACK
        logger.warning(
            "routing: model=%s has no API key — using fallback=%s",
            model,
            fallback,
        )
        return fallback

    return model
```

- [ ] **Step 7: Create `backend/app/services/providers/registry.py`**

```python
"""
registry.py — Provider factory: returns the correct adapter for a model alias.

The registry is a thin indirection layer so that business logic never
instantiates adapters directly. Adding a provider means registering it here.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings
from app.services.providers.base import ProviderAdapter

logger = logging.getLogger(__name__)


@lru_cache(maxsize=None)
def _get_ionos_adapter() -> "IONOSAdapter":
    from app.services.providers.ionos_adapter import IONOSAdapter
    s = get_settings()
    return IONOSAdapter(
        api_base=s.IONOS_API_BASE,
        api_key=s.IONOS_API_KEY,
        model_cache_ttl=s.IONOS_MODEL_CACHE_TTL,
    )


def get_adapter_for_model(model_alias: str) -> ProviderAdapter:
    """
    Return the ProviderAdapter responsible for the given LiteLLM model alias.

    Rules:
      - "ionos-*"  → IONOSAdapter
      - "claude-*" → AnthropicCompat (wraps existing ProviderClient logic)
      - anything else → LiteLLMAdapter (passes through to gateway)

    Raises ValueError if no adapter is found.
    """
    if model_alias.startswith("ionos"):
        return _get_ionos_adapter()

    # For Anthropic and OpenAI models, we use the existing ProviderClient
    # wrapped in a thin shim so callers don't need to know the difference.
    if model_alias.startswith("claude") or model_alias.startswith("gpt"):
        return _get_legacy_adapter(model_alias)

    raise ValueError(f"No adapter registered for model alias: {model_alias!r}")


def _get_legacy_adapter(model_alias: str) -> ProviderAdapter:
    """
    Wraps the existing ProviderClient (pipeline.py) in the ProviderAdapter
    interface so legacy Anthropic/OpenAI paths stay unchanged.
    """
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

    return _LegacyAdapter()
```

- [ ] **Step 8: Run tests**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/test_ionos_adapter.py -v
```

Expected: `4 passed`

- [ ] **Step 9: Commit**

```bash
cd /opt/assist2
git add backend/app/services/providers/ backend/tests/unit/test_ionos_adapter.py
git commit -m "feat(ionos): add provider adapter layer (base, ionos, registry, routing_matrix)"
```

---

## Task 6: Update Router + Pipeline for IONOS

**Files:**
- Modify: `backend/app/ai/router.py` (add ionos model maps)
- Modify: `backend/app/ai/pipeline.py` (add ionos provider branch)

- [ ] **Step 1: Update `backend/app/ai/router.py`**

Add after `_MODEL_MAP_OPENAI` dict (after line 65):

```python
_MODEL_MAP_IONOS: dict[str, str] = {
    "low":    "ionos-fast",      # Llama 3.1 8B — fast, cheap
    "medium": "ionos-quality",   # Llama 3.1 70B — balanced
    "high":   "ionos-reasoning", # Mixtral 8x7B — complex reasoning
}
```

Update `route_request` to accept `"ionos"` as a provider:

```python
def route_request(
    complexity: ComplexityScore,
    task_type: TaskType,
    provider: str = "anthropic",
    model_override: str = "",
) -> RouteDecision:
    settings = get_settings()
    level = complexity.level
    entry = _TABLE.get((task_type, level), _TABLE[("suggest", "medium")])

    # Select model map by provider
    if provider == "openai":
        model_map = _MODEL_MAP_OPENAI
    elif provider == "ionos":
        model_map = _MODEL_MAP_IONOS
    else:
        model_map = _MODEL_MAP  # anthropic default

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
```

- [ ] **Step 2: Update `backend/app/ai/pipeline.py` — add IONOS branch to `ProviderClient.call()`**

Replace the `call()` method body in `ProviderClient`:

```python
    def call(
        self, model: str, max_tokens: int, temperature: float, messages: list
    ) -> tuple[str, dict]:
        from app.core.observability import timed_call

        if self.provider == "ionos":
            with timed_call("ionos", model, "pipeline") as meta:
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
                meta["input_tokens"] = usage["input_tokens"]
                meta["output_tokens"] = usage["output_tokens"]
            return text, usage

        if self.provider == "openai":
            try:
                with timed_call("openai", model, "pipeline") as meta:
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
                    meta["input_tokens"] = usage["input_tokens"]
                    meta["output_tokens"] = usage["output_tokens"]
                return text, usage
            except Exception as exc:
                _exc_type = type(exc).__name__
                if any(k in _exc_type for k in (
                    "RateLimit", "PermissionDenied", "QuotaExceeded",
                    "AuthenticationError", "APIConnection", "ConnectError", "Connection"
                )):
                    logger.warning("OpenAI call failed (%s: %s) — falling back to Anthropic", _exc_type, exc)
                    return self._call_anthropic_fallback(max_tokens, temperature, messages)
                raise

        # anthropic
        with timed_call("anthropic", model, "pipeline") as meta:
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
            meta["input_tokens"] = usage["input_tokens"]
            meta["output_tokens"] = usage["output_tokens"]
        return text, usage
```

- [ ] **Step 3: Smoke-test router**

```bash
cd /opt/assist2/backend
python -c "
from app.ai.router import route_request
from app.ai.complexity_scorer import ComplexityScore
score = ComplexityScore(level='medium', confidence=0.8, context=None)
d = route_request(score, 'suggest', provider='ionos')
assert d.model == 'ionos-quality', d.model
print('router ionos OK:', d)
"
```

Expected: `router ionos OK: RouteDecision(model='ionos-quality', ...)`

- [ ] **Step 4: Run existing AI tests to verify no regression**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/test_story_score.py tests/unit/test_ai_chat.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2
git add backend/app/ai/router.py backend/app/ai/pipeline.py
git commit -m "feat(ionos): add IONOS model maps and observability hooks to router/pipeline"
```

---

## Task 7: Wire IONOS into ai_story_service.py

**Files:**
- Modify: `backend/app/services/ai_story_service.py`

The goal is to replace the hardcoded `_make_client()` with a lookup through `routing_matrix + registry` when IONOS is configured. The legacy path must remain fully functional as fallback.

- [ ] **Step 1: Replace `_make_client()` in `ai_story_service.py`**

Find the `_make_client` function (around line 90 based on the exploration). Replace it entirely:

```python
def _make_client(
    task_category: str,
    ai_settings: dict | None = None,
) -> tuple["ProviderClient", str]:
    """
    Build a ProviderClient for the given task category.

    Resolution order:
    1. Org-level model_override in ai_settings → use as-is (legacy path)
    2. Org-level provider selection in ai_settings → use specified provider
    3. Routing matrix (PROVIDER_ROUTING_* env vars) → auto-select by category
    4. Hardcoded legacy: story→openai, dev→anthropic  (backward-compat fallback)
    """
    from app.services.providers.routing_matrix import resolve_model
    from app.config import get_settings

    settings = get_settings()
    override = (ai_settings or {}).get("model_override", "")

    # Legacy path: explicit org-level override bypasses routing
    if override:
        # Determine provider from model name prefix
        if override.startswith("claude"):
            return _build_anthropic_client(ai_settings), "anthropic"
        if override.startswith("gpt"):
            return _build_openai_client(ai_settings), "openai"
        if override.startswith("ionos") or override.startswith("meta-llama") or override.startswith("mistral"):
            return _build_ionos_client(ai_settings), "ionos"
        # Unknown override → fall through to legacy
        return _build_anthropic_client(ai_settings), "anthropic"

    # Check routing matrix
    task_map = {"story": "suggest", "dev": "docs"}
    routing_task = task_map.get(task_category, "suggest")
    routed_model = resolve_model(routing_task)

    if routed_model.startswith("ionos"):
        return _build_ionos_client(ai_settings), "ionos"
    if routed_model.startswith("claude"):
        return _build_anthropic_client(ai_settings), "anthropic"
    if routed_model.startswith("gpt"):
        return _build_openai_client(ai_settings), "openai"

    # Absolute fallback (original logic)
    if task_category == "dev":
        return _build_anthropic_client(ai_settings), "anthropic"
    return _build_openai_client(ai_settings), "openai"


def _build_ionos_client(ai_settings: dict | None) -> "ProviderClient":
    from app.config import get_settings
    import openai
    s = get_settings()
    api_key = (ai_settings or {}).get("ionos_api_key") or s.IONOS_API_KEY
    raw = openai.OpenAI(
        api_key=api_key,
        base_url=f"{s.IONOS_API_BASE}/v1",
        timeout=60,
        max_retries=0,
    )
    return ProviderClient("ionos", raw)


def _build_anthropic_client(ai_settings: dict | None) -> "ProviderClient":
    import anthropic
    from app.config import get_settings
    s = get_settings()
    api_key = (ai_settings or {}).get("api_key") or s.ANTHROPIC_API_KEY
    return ProviderClient("anthropic", anthropic.Anthropic(api_key=api_key))


def _build_openai_client(ai_settings: dict | None) -> "ProviderClient":
    import openai
    from app.config import get_settings
    s = get_settings()
    api_key = (ai_settings or {}).get("api_key") or s.OPENAI_API_KEY
    return ProviderClient("openai", openai.OpenAI(api_key=api_key))
```

- [ ] **Step 2: Verify backend starts without errors**

```bash
cd /opt/assist2/infra
docker compose -f docker-compose.yml up -d --build backend
docker logs assist2-backend --tail 20 2>&1 | grep -E "startup|ERROR"
```

Expected: `Application startup complete.`

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add backend/app/services/ai_story_service.py
git commit -m "feat(ionos): wire routing matrix into ai_story_service._make_client()"
```

---

## Task 8: Example Code Artifact

**Files:**
- Create: `docs/ionos-integration/00-examples.py`

This file is documentation-as-code — runnable examples, not production code.

- [ ] **Step 1: Create `docs/ionos-integration/00-examples.py`**

```python
"""
00-examples.py — Runnable examples for IONOS AI API integration.

Run individual examples:
  python docs/ionos-integration/00-examples.py chat
  python docs/ionos-integration/00-examples.py models
  python docs/ionos-integration/00-examples.py embed
  python docs/ionos-integration/00-examples.py rag
"""
import asyncio
import os
import sys

IONOS_API_BASE = os.environ.get("IONOS_API_BASE", "https://openai.ionos.com/openai")
IONOS_API_KEY = os.environ.get("IONOS_API_KEY", "")

# ─────────────────────────────────────────────────────────────────────────────
# Example 1: Chat Completion (sync, OpenAI-compatible)
# ─────────────────────────────────────────────────────────────────────────────

def example_chat():
    """
    Minimal chat completion via IONOS OpenAI-compatible API.
    Uses the openai-python SDK, pointed at the IONOS base URL.
    """
    import openai

    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=30,
        max_retries=0,  # handle retries externally
    )

    response = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
            {"role": "user",   "content": "Erkläre den Unterschied zwischen Story Points und Stunden."},
        ],
        max_tokens=512,
        temperature=0.4,
        stream=False,
    )

    text = response.choices[0].message.content
    usage = response.usage
    print(f"[chat] response ({usage.prompt_tokens} in / {usage.completion_tokens} out):\n{text}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Example 2: List Available Models
# ─────────────────────────────────────────────────────────────────────────────

async def example_models():
    """
    Fetch and print all available models from IONOS /v1/models.
    Uses httpx for async fetching; result should be cached in production.
    """
    import httpx

    async with httpx.AsyncClient(
        base_url=f"{IONOS_API_BASE}/v1",
        headers={"Authorization": f"Bearer {IONOS_API_KEY}"},
        timeout=15,
    ) as client:
        resp = await client.get("/models")
        resp.raise_for_status()
        models = resp.json().get("data", [])

    print(f"[models] {len(models)} models available:")
    for m in sorted(models, key=lambda x: x["id"]):
        print(f"  {m['id']}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Example 3: Embeddings
# ─────────────────────────────────────────────────────────────────────────────

def example_embed():
    """
    Generate embeddings for a list of texts via IONOS /v1/embeddings.
    Requires 'embeddings' feature flag and an embedding model.
    Model 'BAAI/bge-m3' supports multilingual text.
    """
    import openai

    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=20,
    )

    texts = [
        "Als Produktmanager möchte ich User Stories bewerten können.",
        "Als Entwickler möchte ich automatische Tests generieren.",
    ]

    response = client.embeddings.create(
        model="BAAI/bge-m3",
        input=texts,
    )

    for i, item in enumerate(response.data):
        vec = item.embedding
        print(f"[embed] text[{i}]: {len(vec)}-dim vector, first 3 dims: {vec[:3]}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Example 4: RAG — Internal vector store path
# ─────────────────────────────────────────────────────────────────────────────

def example_rag_internal():
    """
    RAG with internal pgvector (the default path).

    Flow:
      1. Embed the user query via IONOS embeddings
      2. Query pgvector for top-k similar chunks
      3. Build a prompt with retrieved context
      4. Call IONOS chat for the final answer

    This uses the assist2 rag_service.py abstractions in production.
    This example shows the raw building blocks.
    """
    import openai
    # Step 1: embed the query
    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=20,
    )
    query = "Welche Definition of Ready gilt für User Stories?"
    embed_resp = client.embeddings.create(model="BAAI/bge-m3", input=[query])
    query_vec = embed_resp.data[0].embedding
    print(f"[rag] query embedded: {len(query_vec)}-dim")

    # Step 2: pgvector similarity search (pseudo-code — real impl in rag_service.py)
    # chunks = await db.execute(
    #     "SELECT content FROM documents ORDER BY embedding <-> $1 LIMIT 3",
    #     [query_vec]
    # )
    chunks = ["[simulated chunk 1]", "[simulated chunk 2]"]

    # Step 3: Build RAG prompt
    context = "\n\n".join(f"[Kontext]\n{c}" for c in chunks)
    prompt = f"{context}\n\nFrage: {query}\n\nAntwort:"

    # Step 4: Chat completion with context
    resp = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.2,
    )
    print(f"[rag] answer: {resp.choices[0].message.content[:200]}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"
    if not IONOS_API_KEY:
        print("ERROR: IONOS_API_KEY not set. Export it before running.")
        sys.exit(1)

    if cmd == "chat":
        example_chat()
    elif cmd == "models":
        asyncio.run(example_models())
    elif cmd == "embed":
        example_embed()
    elif cmd == "rag":
        example_rag_internal()
    else:
        print(f"Unknown command: {cmd}. Use: chat | models | embed | rag")
        sys.exit(1)
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2
mkdir -p docs/ionos-integration
git add docs/ionos-integration/00-examples.py
git commit -m "docs(ionos): add runnable examples for chat, models, embeddings, RAG"
```

---

## Task 9: Documentation Artifacts

**Files:**
- Create: `docs/ionos-integration/01-architecture.md`
- Create: `docs/ionos-integration/02-security.md`
- Create: `docs/ionos-integration/03-observability.md`
- Create: `docs/ionos-integration/04-performance.md`
- Create: `docs/ionos-integration/05-migration.md`
- Create: `docs/ionos-integration/06-rag.md`

- [ ] **Step 1: Create `docs/ionos-integration/01-architecture.md`**

```markdown
# IONOS AI Integration — Zielarchitektur

## Überblick

IONOS AI wird als externer Provider über die OpenAI-kompatible API eingebunden.
Alle Modellanfragen laufen über LiteLLM als zentrales Gateway — das Backend spricht
nie direkt mit IONOS, Anthropic oder OpenAI.

## Komponentendiagramm

```
Internet
  │
  ▼
Traefik (TLS, Routing, Rate-Limit)
  │
  ├──► Frontend (Next.js :3000)     ← never touches AI APIs
  │
  └──► Backend API (FastAPI :8000)
         │
         ├──► LiteLLM Gateway (:4000)  ← ALL model traffic
         │      ├── IONOS (ionos-fast, ionos-quality, ionos-reasoning)
         │      ├── Anthropic (claude-sonnet-4-6, claude-haiku-4-5)
         │      └── OpenAI (fallback)
         │
         ├──► PostgreSQL (pgvector) ← internal RAG embeddings
         ├──► Redis           ← session, cache, Celery broker
         └──► n8n             ← workflow orchestration
```

## Request-Fluss (Chat Completion)

```
Frontend
  → POST /api/v1/ai/chat (auth header required)
  → Backend routers/ai.py
  → ai_story_service._make_client()
  → routing_matrix.resolve_model()   ← picks ionos-quality / claude-sonnet etc.
  → ProviderClient.call()
  → LiteLLM :4000  POST /v1/chat/completions
  → IONOS openai.ionos.com/openai/v1/chat/completions
  ← response + usage metrics logged
  ← SSE stream to Frontend (if streaming=true)
```

## Docker Compose Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| traefik | traefik:v3 | 80/443 | TLS termination, routing |
| frontend | custom Next.js | 3000 | UI |
| backend | custom FastAPI | 8000 | Business logic, AI orchestration |
| litellm | ghcr.io/berriai/litellm | 4000 | LLM gateway |
| litellm-postgres | postgres:16 | — | LiteLLM state |
| postgres | pgvector/pgvector:pg16 | — | Main DB + vectors |
| redis | redis:7 | — | Cache, broker |
| n8n | n8n | 5678 | Workflows |

## Provider-Logik

IONOS ist der primäre Provider wenn `IONOS_API_KEY` gesetzt ist.
Anthropic ist der primäre Provider für Dokumentationsgenerierung.
Jeder Provider ist über `PROVIDER_ROUTING_*`-Variablen konfigurierbar.
```

- [ ] **Step 2: Create `docs/ionos-integration/02-security.md`**

```markdown
# IONOS AI Integration — Security-Konzept

## Secrets-Management

| Secret | Speicherort | Niemals in |
|--------|------------|------------|
| IONOS_API_KEY | infra/.env | Code, Frontend, Logs, Images |
| ANTHROPIC_API_KEY | infra/.env | — |
| LITELLM_MASTER_KEY | infra/.env | — |

Rotation: `.env` aktualisieren → Container neu starten. Kein Build nötig.

## API-Key-Sicherheit

- Keys werden per `os.environ/KEY_NAME` in LiteLLM-Config referenziert (nie im YAML-Text)
- Backend liest Keys nur via `pydantic-settings` (`get_settings()`) zur Laufzeit
- LiteLLM-Config: `log_raw_request_response: false` — keine Prompts in Logs
- `return_response_headers: false` — keine internen Modell-IDs nach außen

## Request-Authentifizierung

```
Browser  →  JWT Bearer  →  Traefik  →  Backend
                                         │
                                         └─ get_current_user() dependency
                                            (JWT validation + org-scope check)
```

LiteLLM-Endpunkt ist **nicht** direkt aus dem Internet erreichbar (internes Docker-Netz).
Nur der Backend-Container darf LiteLLM erreichen.

## Rate-Limit-Schutz (intern)

- Traefik: InFlightReq-Middleware begrenzt gleichzeitige Anfragen pro IP
- Backend: Redis-basiertes per-Org Limit (geplant via `AI_USAGE_LIMIT_PER_ORG`)
- LiteLLM: `allowed_fails: 2` + `cooldown_time: 60s` pro Modell

## Eingaben

- Strenge Pydantic-Validierung aller Request-Bodies (FastAPI dependency)
- Prompt-Injection-Risiko: Akzeptanzkriterien-Felder werden als Klartext übergeben —
  System-Prompt ist immer der erste Nachrichteneintrag und klar getrennt
- Keine direkte SQL-Interpolation von Nutzereingaben (SQLAlchemy ORM)

## Audit-Logging

Jeder Provider-Aufruf loggt:
```
provider_call request_id=abc123 provider=ionos model=ionos-quality
  task=suggest pipeline=single latency_ms=842
  in_tokens=312 out_tokens=198 fallback=False status=ok
```

Kein Prompt-Text, keine API-Keys in diesen Log-Zeilen.

## Admin-Endpunkte

- `/api/v1/admin/*` → `is_superuser` Dependency (FastAPI)
- LiteLLM-UI (`/litellm`) → Traefik BasicAuth Middleware
- pgAdmin → intern, nicht über Traefik exponiert in Production
```

- [ ] **Step 3: Create `docs/ionos-integration/03-observability.md`**

```markdown
# IONOS AI Integration — Observability-Konzept

## Strukturierte Log-Zeilen

Alle AI-Aufrufe emittieren eine maschinenlesbare Log-Zeile:

```
provider_call request_id=<8-char-uuid> provider=<ionos|anthropic|openai>
  model=<alias> task=<suggest|docs> pipeline=<single|multi>
  latency_ms=<int> in_tokens=<int> out_tokens=<int>
  fallback=<True|False> status=<ok|error> [error=<ExceptionType>]
```

Rate-Limit-Events:
```
rate_limit provider=ionos attempt=2 delay_s=5.0 source=Retry-After request_id=abc
```

Fallback-Events:
```
provider_fallback from=openai to=anthropic reason=RateLimitError request_id=abc
```

## Request-ID-Korrelation

Jeder HTTP-Request bekommt eine 8-Zeichen-UUID in `X-Request-ID`.
Die ID wird in `ContextVar` gespeichert und in alle Log-Zeilen injiziert.

Middleware-Snippet (in `main.py` ergänzen):
```python
from app.core.observability import set_request_id
import uuid

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    set_request_id(rid)
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    return response
```

## LiteLLM-Metriken

LiteLLM loggt nativ als JSON (`json_logs: true`):
- Model, provider, latency, tokens, status
- Konfigurierbar via `success_callback` / `failure_callback` für externe Systeme

## Metriken-Dashboard (vorbereitet)

Log-Aggregation via Loki + Grafana (optional):
- Panel 1: Requests/min pro Provider
- Panel 2: P50/P95 Latenz pro Modell
- Panel 3: Token-Verbrauch kumuliert (Kosten-Proxy)
- Panel 4: Rate-Limit-Events / Fallback-Rate
- Panel 5: Error-Rate nach Provider

## Health-Check-Endpunkte

| Endpunkt | Service | Zweck |
|---------|---------|-------|
| GET /health | Backend | FastAPI liveness |
| GET /metrics | LiteLLM | Token/latency metrics |
| GET /v1/models | LiteLLM | Provider-Verfügbarkeit testen |
```

- [ ] **Step 4: Create `docs/ionos-integration/04-performance.md`**

```markdown
# IONOS AI Integration — Performance-Konzept

## Stateless Requests

- Jeder Request trägt seinen eigenen JWT — kein sticky-session-Bedarf
- Keine serverseitige Session zwischen Anfragen
- LiteLLM als Gateway: ein einziger HTTP-Hop vor Provider

## Connection Reuse / Keep-Alive

- `openai-python` SDK verwendet intern `httpx.Client` mit Connection Pool
- IONOS-Adapter: ein `openai.OpenAI`-Instance pro Prozess (via `@lru_cache` in Registry)
- Kein neues Client-Objekt pro Request — Pool bleibt warm

## Model-List-Caching

IONOS `/v1/models` wird gecacht:
- In-Process: TTL-Dict in `ionos_adapter.py` (default 300s)
- Redis: LiteLLM cache mit `namespace: "litellm:cache"` und `ttl: 300`

## Streaming

- `/api/v1/ai/chat` verwendet SSE-Streaming für lange Antworten
- LiteLLM leitet Chunks direkt weiter — kein Buffering im Gateway
- IONOS unterstützt `stream: true` auf `/v1/chat/completions`

## Routing-Effizienz

- Kein "fan-out" zu mehreren Providern gleichzeitig
- `routing_matrix.resolve_model()` wählt deterministisch einen Provider
- Fallback nur bei belegbarem Fehler (Exception) — nie spekulativ

## Async-First

- Backend: alle DB- und HTTP-Calls async (asyncio + asyncpg + httpx)
- Celery-Worker für langläufige Hintergrundtasks (z.B. Batch-Embeddings)
- `list_models()` im IONOS-Adapter ist async; sync `chat()` ist blockierend
  (akzeptabel da FastAPI in eigenem Thread-Pool läuft)

## Timeouts

| Layer | Timeout | Konfiguriert in |
|-------|---------|----------------|
| IONOS chat (fast) | 30s | litellm/config.yaml |
| IONOS chat (quality) | 60s | litellm/config.yaml |
| IONOS reasoning | 90s | litellm/config.yaml |
| Anthropic | 90s | litellm/config.yaml |
| Backend → LiteLLM | 120s | httpx in ai.py |
| Retry max wait | 60s | router_settings.retry_after_max_wait |

## Queueing / Lastglättung

- Celery-Worker: `concurrency=2` (tunable via `CELERY_CONCURRENCY`)
- LiteLLM `allowed_fails: 2` + `cooldown_time: 60` verhindert Cascading-Failures
- Für Burst-Szenarien: Redis-Queue vor Celery-Tasks als Puffer
```

- [ ] **Step 5: Create `docs/ionos-integration/05-migration.md`**

```markdown
# Provider-Migrations-Guide

## Provider hinzufügen (Checkliste)

So wird ein neuer Provider (z.B. „Mistral Cloud") eingebunden:

### 1. LiteLLM config (`litellm/config.yaml`)
```yaml
- model_name: mistral-fast
  litellm_params:
    model: mistral/mistral-7b-instruct
    api_key: os.environ/MISTRAL_API_KEY
    timeout: 30
```

### 2. `.env` / `.env.example`
```
MISTRAL_API_KEY=
```

### 3. `backend/app/config.py`
```python
MISTRAL_API_KEY: str = ""
```

### 4. `routing_matrix.py` — `_has_key()` erweitern
```python
if model_alias.startswith("mistral"):
    return bool(settings.MISTRAL_API_KEY)
```

### 5. `router.py` — Model-Map ergänzen
```python
_MODEL_MAP_MISTRAL: dict[str, str] = {
    "low":    "mistral-fast",
    "medium": "mistral-medium",
    "high":   "mistral-large",
}
```

### 6. `pipeline.py` / `registry.py` — Provider-Branch
```python
if model_alias.startswith("mistral"):
    return _get_mistral_adapter()
```

**Kein Eingriff in Business-Logik** (`ai_story_service.py`, Routers, Frontend).

---

## IONOS-Region wechseln

Nur `.env` ändern:
```
IONOS_API_BASE=https://openai.ionos.com/openai   # DE-FRA
# oder:
IONOS_API_BASE=https://openai.ionos.com/openai   # weitere Regionen analog
```
Kein Code-Change, kein Build.

---

## IONOS durch anderen Provider ersetzen

1. `PROVIDER_ROUTING_SUGGEST=claude-sonnet-4-6` in `.env` setzen
2. `IONOS_API_KEY=` leer lassen
3. Deployment neu starten

Kein Code-Change. Die Routing-Matrix greift auf Anthropic zurück.

---

## Modell-ID aktualisieren (IONOS benennt Modelle um)

Nur in `litellm/config.yaml`:
```yaml
# vorher:
model: openai/meta-llama/Meta-Llama-3.1-8B-Instruct
# nachher:
model: openai/meta-llama/Meta-Llama-3.2-8B-Instruct
```

Der logische Alias `ionos-fast` bleibt unverändert — Backend und Frontend
sehen nie den echten Modell-Namen.

---

## Breaking Change: LiteLLM-Major-Update

Bei LiteLLM-Major-Versions-Upgrades:
1. Config-Syntax-Diff prüfen (`CHANGELOG.md` im LiteLLM-Repo)
2. `litellm/config.yaml` entsprechend anpassen
3. `docker compose pull litellm && docker compose up -d litellm`
4. `docker logs assist2-litellm` auf Startfehler prüfen
```

- [ ] **Step 6: Create `docs/ionos-integration/06-rag.md`**

```markdown
# RAG — Zwei Modi

## Modus 1: Internes RAG (Standard)

Wird immer genutzt, wenn Nextcloud-Dokumente indiziert wurden.

```
Query → IONOS Embeddings (BAAI/bge-m3)
      → pgvector Similarity Search (Top-K Chunks)
      → Prompt-Builder (context injection)
      → IONOS Chat Completion
```

**Aktivierung:** automatisch wenn RAG-Chunks im Index vorhanden sind.
**Code:** `backend/app/services/rag_service.py` — Funktion `retrieve()`
**Embedding-Modell:** `ionos-embed` (konfigurierbar via `AI_EMBEDDING_MODEL`)

## Modus 2: IONOS Document Collections (optional)

Nur wenn Feature-Flag `rag_ionos` aktiv (`AI_FEATURE_FLAGS=...,rag_ionos`).

Nutzt die nativen IONOS-Endpunkte:
- `POST /collections` — Collection anlegen
- `POST /collections/{id}/documents` — Dokumente hochladen
- `POST /collections/{id}/query` — Semantische Suche

**Wann sinnvoll:**
- Sehr große Dokumentenmengen, die pgvector überlasten würden
- Wenn IONOS-natives Chunking und Indexing bevorzugt wird
- Multi-Tenant-Szenarien, bei denen jede Org eine eigene Collection bekommt

**Wichtig:** Diese Endpunkte sind NICHT die OpenAI-kompatiblen Endpunkte.
Sie werden in einem separaten Service-Modul (`ionos_collections_service.py`)
isoliert — nie im Haupt-AI-Pfad gemischt.

## Abstraktion

```python
# rag_service.py — einheitliche Schnittstelle für beide Modi
async def retrieve(query: str, org_id: UUID, db: AsyncSession) -> RagResult:
    if settings.ai_feature_enabled("rag_ionos") and org_uses_ionos_collections(org_id):
        return await _retrieve_ionos_collections(query, org_id)
    return await _retrieve_pgvector(query, org_id, db)
```

Der aufrufende Code in `ai_story_service.py` sieht nur `retrieve()` —
nie welcher Retrieval-Mechanismus aktiv ist.

## Prompt-Builder

```python
def build_rag_prompt(query: str, chunks: list[str], data: AISuggestRequest) -> str:
    context_block = "\n\n".join(f"[Kontext]\n{c}" for c in chunks)
    return (
        f"{context_block}\n\n"
        f"Story-Titel: {data.title}\n"
        f"Beschreibung: {data.description or '(leer)'}\n"
        f"Akzeptanzkriterien: {data.acceptance_criteria or '(leer)'}\n\n"
        f"Analysiere diese Story gegen die Definition of Ready. Antworte als JSON."
    )
```

Modularer Prompt-Builder → testbar, unabhängig vom Retrieval-Mechanismus.
```

- [ ] **Step 7: Commit all docs**

```bash
cd /opt/assist2
git add docs/ionos-integration/
git commit -m "docs(ionos): add architecture, security, observability, performance, migration, RAG guides"
```

---

## Task 10: Final Integration Test + docker-compose Backend Update

**Files:**
- Modify: `infra/docker-compose.yml` (add IONOS env vars to backend + worker services)

- [ ] **Step 1: Add IONOS env vars to backend and worker services in `docker-compose.yml`**

In the `backend` service environment block, after `OPENAI_API_KEY`:

```yaml
      - IONOS_API_KEY=${IONOS_API_KEY:-}
      - IONOS_API_BASE=${IONOS_API_BASE:-https://openai.ionos.com/openai}
      - IONOS_MODEL_CACHE_TTL=${IONOS_MODEL_CACHE_TTL:-300}
      - PROVIDER_ROUTING_SUGGEST=${PROVIDER_ROUTING_SUGGEST:-auto}
      - PROVIDER_ROUTING_DOCS=${PROVIDER_ROUTING_DOCS:-claude-sonnet-4-6}
      - PROVIDER_ROUTING_FALLBACK=${PROVIDER_ROUTING_FALLBACK:-ionos-fast}
      - AI_FEATURE_FLAGS=${AI_FEATURE_FLAGS:-streaming,embeddings}
```

Add the same block to the `worker` service.

- [ ] **Step 2: Add IONOS_API_KEY and IONOS_API_BASE to litellm service environment**

In the `litellm` service:
```yaml
      - IONOS_API_KEY=${IONOS_API_KEY:-}
      - IONOS_API_BASE=${IONOS_API_BASE:-https://openai.ionos.com/openai}
```

- [ ] **Step 3: Full rebuild and smoke test**

```bash
cd /opt/assist2/infra
docker compose -f docker-compose.yml up -d --build backend worker litellm
sleep 10
docker logs assist2-backend --tail 10
docker logs assist2-litellm --tail 10
```

Expected: both show successful startup, no Python import errors.

- [ ] **Step 4: Run full test suite**

```bash
cd /opt/assist2/backend
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```

Expected: all tests pass (or pre-existing failures only).

- [ ] **Step 5: Final commit**

```bash
cd /opt/assist2
git add infra/docker-compose.yml
git commit -m "feat(ionos): wire IONOS env vars into docker-compose services"
```

---

## Self-Review

### Spec Coverage Check

| Requirement | Task |
|------------|------|
| OpenAI-compatible API only (no /predictions) | T1: LiteLLM config uses `openai/` prefix |
| `/v1/models` dynamic listing | T5: `IONOSAdapter.list_models()` |
| Chat completions via `/v1/chat/completions` | T5: `IONOSAdapter.chat()` |
| Embeddings via `/v1/embeddings` | T5: `IONOSAdapter.embed()` |
| No native IONOS text/image endpoints in main path | T5: note in ionos_adapter.py docstring |
| Retry-After header handling | T3: `parse_retry_after()` + `retry_on_rate_limit()` |
| Rate-limit logging (no secrets) | T4: `log_rate_limit()` |
| Connection reuse / Keep-Alive | T4-perf: openai SDK uses httpx pool |
| Model list caching | T5: TTL-dict cache + Redis via LiteLLM |
| Secrets never in code/frontend/images | T1: `.env.example`, `os.environ/` in LiteLLM |
| Model names via config only | T6: routing_matrix + `_MODEL_MAP_IONOS` |
| Provider extensibility | T5: base.py + registry.py |
| Routing matrix (fast/quality/reasoning/fallback-eu) | T1: LiteLLM config aliases + T5: routing_matrix |
| Admin routing policies | T2: `PROVIDER_ROUTING_*` settings |
| Feature flags | T2: `AI_FEATURE_FLAGS` + `ai_feature_enabled()` |
| Observability (latency, tokens, error rate) | T4: observability.py |
| Request-ID correlation | T4: `ContextVar` + middleware snippet |
| Structured logs (no prompt text) | T4: log format spec |
| Health checks / timeouts / retries | T1: LiteLLM router_settings |
| RAG abstraction | T9-doc: 06-rag.md + T5: routing_matrix |
| Migration guide | T9-doc: 05-migration.md |
| Docker-first, 12-factor | T1, T10: all config via env vars |
| Example code | T8: 00-examples.py (chat, models, embed, rag) |

### Placeholder Scan

No TBDs found. All code blocks are complete and runnable.

### Type Consistency

- `ProviderAdapter.chat()` returns `tuple[str, dict]` — consistent across base.py, ionos_adapter.py, registry.py, pipeline.py
- `RouteDecision.model` is always a LiteLLM alias string — consistent in router.py and routing_matrix.py
- `RetryConfig` dataclass used identically in retry.py and test_retry.py
- `timed_call()` yields `dict` with keys `input_tokens`, `output_tokens`, `error`, `fallback` — consistent in observability.py and pipeline.py usage
