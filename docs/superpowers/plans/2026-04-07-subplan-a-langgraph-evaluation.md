# Sub-Plan A: LangGraph-Service + Backend Evaluation API

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy a working `langgraph-service` container and Backend endpoints that evaluate a User Story and return a structured score with findings and rewrite suggestion.

**Architecture:** New `langgraph-service` (FastAPI + LangGraph, port 8100, internal-only) called synchronously by the Backend. Backend persists all results. LiteLLM (`http://litellm:4000`) is the only LLM gateway. Frontend polls `/api/v1/evaluations/stories/{id}/latest` after triggering evaluation.

**Tech Stack:** LangGraph 0.2.x, LangChain-Core, FastAPI, httpx, SQLAlchemy async, pgvector (already enabled), Alembic, pytest + pytest-asyncio

---

## Files Created / Modified

### New: `langgraph-service/`
```
langgraph-service/
  app/
    main.py                         # FastAPI app, health endpoint
    config.py                       # Settings (LiteLLM URL, API key, callback URL)
    schemas/
      evaluation.py                 # All Pydantic I/O types (shared contract)
    llm/
      client.py                     # LiteLLM wrapper (all LLM calls go here)
    nodes/
      story_parser.py               # Deterministic: parse + clean story fields
      criteria_validator.py         # Deterministic: AC completeness check
      clarity_scorer.py             # LLM: score clarity 0-10 + explanation
      generate_findings.py          # LLM: produce structured Finding list
      rewrite_generator.py          # LLM: produce rewrite suggestion
      format_output.py              # Deterministic: assemble final EvaluationResult
    workflows/
      evaluate.py                   # StateGraph assembly
    routers/
      workflows.py                  # POST /workflows/evaluate
  tests/
    conftest.py
    test_health.py
    test_nodes.py
    test_evaluate_workflow.py
  Dockerfile
  requirements.txt
```

### Modified: `backend/`
```
backend/app/
  config.py                         # +LANGGRAPH_BASE_URL, LANGGRAPH_API_KEY
  models/
    evaluation_run.py               # New: EvaluationRun, EvaluationFinding SQLAlchemy models
    approval_request.py             # New: ApprovalRequest model
    story_embedding.py              # New: StoryEmbedding model (pgvector)
    integration_event.py            # New: IntegrationEvent model
  schemas/
    evaluation.py                   # New: Pydantic schemas (mirrors langgraph-service schemas)
  services/
    evaluation_service.py           # New: orchestrates LangGraph call + DB persistence
  routers/
    evaluations.py                  # New: /evaluations/* endpoints
  main.py                           # +import + include_router evaluations
migrations/versions/
  0029_add_evaluation_tables.py     # evaluation_runs, evaluation_findings, approval_requests
  0030_add_story_embeddings.py      # story_embeddings with pgvector HNSW
  0031_add_integration_events.py    # integration_events
infra/
  docker-compose.yml                # +langgraph-service service block
litellm/
  config.yaml                       # +eval-fast, eval-quality aliases
```

---

## Task 1: LiteLLM eval aliases

**Files:**
- Modify: `litellm/config.yaml`

- [ ] **Step 1: Add evaluation model aliases to LiteLLM config**

```yaml
# Add after the existing claude-haiku-4-5 entry in litellm/config.yaml:

  # ── Evaluation aliases (point to existing models) ────────────────
  # eval-fast: quick criteria checks, deterministic validation
  - model_name: eval-fast
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 30
      max_retries: 2

  # eval-quality: deep analysis, findings, rewrite generation
  - model_name: eval-quality
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY
      timeout: 90
      max_retries: 2
```

- [ ] **Step 2: Verify LiteLLM reloads config**

```bash
cd infra && docker compose -f docker-compose.yml restart litellm
docker logs assist2-litellm --tail 20
```
Expected: no error lines, `"model_list"` logged with new aliases visible.

- [ ] **Step 3: Smoke test new aliases**

```bash
curl -s -X POST http://localhost:4000/chat/completions \
  -H "Authorization: Bearer sk-assist2" \
  -H "Content-Type: application/json" \
  -d '{"model":"eval-fast","messages":[{"role":"user","content":"ping"}],"max_tokens":5}' \
  | jq '.choices[0].message.content'
```
Expected: short string response, no error.

- [ ] **Step 4: Commit**

```bash
git add litellm/config.yaml
git commit -m "feat(litellm): add eval-fast and eval-quality model aliases"
```

---

## Task 2: langgraph-service scaffold

**Files:**
- Create: `langgraph-service/requirements.txt`
- Create: `langgraph-service/Dockerfile`
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: Create requirements.txt**

```text
# langgraph-service/requirements.txt
fastapi==0.115.6
uvicorn[standard]==0.32.1
langgraph==0.2.73
langchain-core==0.3.28
httpx==0.27.2
pydantic==2.10.4
pydantic-settings==2.7.0
pytest==8.3.4
pytest-asyncio==0.24.0
httpx==0.27.2
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
# langgraph-service/Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
```

- [ ] **Step 3: Add service to docker-compose.yml**

In `infra/docker-compose.yml`, add after the `worker:` service block:

```yaml
  langgraph-service:
    image: assist2-langgraph
    build:
      context: ../langgraph-service
      dockerfile: Dockerfile
    container_name: assist2-langgraph
    restart: unless-stopped
    environment:
      LITELLM_BASE_URL: http://litellm:4000
      LITELLM_API_KEY: ${LITELLM_API_KEY:-sk-assist2}
      BACKEND_BASE_URL: http://backend:8000
      LANGGRAPH_API_KEY: ${LANGGRAPH_API_KEY:-dev-langgraph-secret}
      LOG_LEVEL: INFO
    networks:
      - internal
    depends_on:
      litellm:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

Note: **no `proxy` network** — this service must not be publicly reachable.

- [ ] **Step 4: Add LANGGRAPH_API_KEY to infra/.env if not present**

```bash
grep -q "LANGGRAPH_API_KEY" /opt/assist2/infra/.env || echo "LANGGRAPH_API_KEY=dev-langgraph-secret" >> /opt/assist2/infra/.env
```

- [ ] **Step 5: Commit scaffold**

```bash
git add langgraph-service/requirements.txt langgraph-service/Dockerfile infra/docker-compose.yml infra/.env
git commit -m "feat(langgraph): add service scaffold, Dockerfile, docker-compose entry"
```

---

## Task 3: langgraph-service config + health endpoint

**Files:**
- Create: `langgraph-service/app/config.py`
- Create: `langgraph-service/app/main.py`
- Create: `langgraph-service/tests/conftest.py`
- Create: `langgraph-service/tests/test_health.py`

- [ ] **Step 1: Write failing test**

```python
# langgraph-service/tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_health_returns_ok():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_unauthenticated_is_allowed():
    """Health check must not require API key."""
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
```

- [ ] **Step 2: Create conftest.py**

```python
# langgraph-service/tests/conftest.py
import os
os.environ.setdefault("LITELLM_BASE_URL", "http://localhost:4000")
os.environ.setdefault("LITELLM_API_KEY", "test-key")
os.environ.setdefault("BACKEND_BASE_URL", "http://localhost:8000")
os.environ.setdefault("LANGGRAPH_API_KEY", "test-secret")
```

- [ ] **Step 3: Run test — verify it fails**

```bash
cd langgraph-service && python -m pytest tests/test_health.py -v
```
Expected: `ImportError` or `ModuleNotFoundError` — `app.main` does not exist yet.

- [ ] **Step 4: Create config.py**

```python
# langgraph-service/app/config.py
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str = "sk-assist2"
    backend_base_url: str = "http://backend:8000"
    langgraph_api_key: str = "dev-langgraph-secret"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Create main.py**

```python
# langgraph-service/app/main.py
import logging
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="langgraph-service", version="1.0.0", docs_url=None, redoc_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Run test — verify it passes**

```bash
cd langgraph-service && python -m pytest tests/test_health.py -v
```
Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add langgraph-service/app/ langgraph-service/tests/
git commit -m "feat(langgraph): health endpoint + config"
```

---

## Task 4: Evaluation schemas (shared contract)

**Files:**
- Create: `langgraph-service/app/schemas/evaluation.py`
- Create: `langgraph-service/tests/test_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# langgraph-service/tests/test_schemas.py
from app.schemas.evaluation import (
    EvaluateRequest, EvaluationResult, EvalFinding, CriterionScore,
    FindingSeverity, Ampel,
)


def test_evaluate_request_requires_mandatory_fields():
    req = EvaluateRequest(
        run_id="550e8400-e29b-41d4-a716-446655440000",
        story_id="550e8400-e29b-41d4-a716-446655440001",
        org_id="550e8400-e29b-41d4-a716-446655440002",
        title="Als Nutzer möchte ich...",
        description="Ich möchte den Status sehen",
        acceptance_criteria="Gegeben ich bin eingeloggt, wenn..., dann...",
    )
    assert req.story_id == "550e8400-e29b-41d4-a716-446655440001"


def test_ampel_logic_green():
    from app.schemas.evaluation import compute_ampel
    assert compute_ampel(score=8.0, knockout=False) == Ampel.GREEN


def test_ampel_logic_yellow():
    from app.schemas.evaluation import compute_ampel
    assert compute_ampel(score=6.0, knockout=False) == Ampel.YELLOW


def test_ampel_logic_red_by_score():
    from app.schemas.evaluation import compute_ampel
    assert compute_ampel(score=3.0, knockout=False) == Ampel.RED


def test_ampel_logic_red_by_knockout():
    from app.schemas.evaluation import compute_ampel
    assert compute_ampel(score=9.0, knockout=True) == Ampel.RED
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd langgraph-service && python -m pytest tests/test_schemas.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create schemas/evaluation.py**

```python
# langgraph-service/app/schemas/evaluation.py
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class FindingCategory(str, Enum):
    CLARITY = "CLARITY"
    COMPLETENESS = "COMPLETENESS"
    TESTABILITY = "TESTABILITY"
    FEASIBILITY = "FEASIBILITY"
    BUSINESS_VALUE = "BUSINESS_VALUE"


class Ampel(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class EvalFinding(BaseModel):
    id: str
    severity: FindingSeverity
    category: FindingCategory
    title: str
    description: str
    suggestion: str


class CriterionScore(BaseModel):
    score: float = Field(ge=0, le=10)
    weight: float = Field(ge=0, le=1)
    explanation: str


class RewriteSuggestion(BaseModel):
    title: str
    story: str
    acceptance_criteria: list[str]


class EvaluateRequest(BaseModel):
    run_id: str
    story_id: str
    org_id: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    context_hints: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    run_id: str
    story_id: str
    org_id: str
    score: float = Field(ge=0, le=10)
    ampel: Ampel
    knockout: bool
    confidence: float = Field(ge=0, le=1)
    criteria_scores: dict[str, CriterionScore]
    findings: list[EvalFinding]
    open_questions: list[str]
    rewrite: RewriteSuggestion
    model_used: str
    input_tokens: int
    output_tokens: int


def compute_ampel(score: float, knockout: bool) -> Ampel:
    """Deterministic ampel — no LLM involved."""
    if knockout:
        return Ampel.RED
    if score >= 7.5:
        return Ampel.GREEN
    if score >= 5.0:
        return Ampel.YELLOW
    return Ampel.RED
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd langgraph-service && python -m pytest tests/test_schemas.py -v
```
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add langgraph-service/app/schemas/ langgraph-service/tests/test_schemas.py
git commit -m "feat(langgraph): evaluation Pydantic schemas + ampel logic"
```

---

## Task 5: LiteLLM client wrapper

**Files:**
- Create: `langgraph-service/app/llm/client.py`
- Create: `langgraph-service/tests/test_llm_client.py`

- [ ] **Step 1: Write failing test**

```python
# langgraph-service/tests/test_llm_client.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_chat_returns_text_and_usage():
    from app.llm.client import LiteLLMClient
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = '{"score": 7.5}'
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 50

    client = LiteLLMClient(base_url="http://fake:4000", api_key="test")
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": '{"score": 7.5}'}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
                "model": "eval-quality",
            },
            raise_for_status=lambda: None,
        )
        text, usage = await client.chat(
            model="eval-quality",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=100,
        )
    assert text == '{"score": 7.5}'
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50


@pytest.mark.asyncio
async def test_chat_raises_on_http_error():
    import httpx
    from app.llm.client import LiteLLMClient, LLMCallError
    client = LiteLLMClient(base_url="http://fake:4000", api_key="test")
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.TimeoutException("timeout")
        with pytest.raises(LLMCallError, match="timeout"):
            await client.chat(model="eval-fast", messages=[], max_tokens=10)
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd langgraph-service && python -m pytest tests/test_llm_client.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create llm/client.py**

```python
# langgraph-service/app/llm/__init__.py
# (empty)
```

```python
# langgraph-service/app/llm/client.py
from __future__ import annotations
import logging
import httpx
from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMCallError(Exception):
    pass


class LiteLLMClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        settings = get_settings()
        self._base_url = (base_url or settings.litellm_base_url).rstrip("/")
        self._api_key = api_key or settings.litellm_api_key
        self._http = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_format: dict | None = None,
    ) -> tuple[str, dict]:
        """
        Call LiteLLM /chat/completions.
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
            response = await self._http.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as e:
            raise LLMCallError(f"LiteLLM timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMCallError(f"LiteLLM HTTP error {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise LLMCallError(f"LiteLLM unexpected error: {e}") from e

        content = data["choices"][0]["message"]["content"] or ""
        usage = {
            "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
            "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
            "model": data.get("model", model),
        }
        logger.debug("LLM call model=%s in=%d out=%d", model, usage["input_tokens"], usage["output_tokens"])
        return content.strip(), usage

    async def aclose(self):
        await self._http.aclose()
```

- [ ] **Step 4: Run test — verify it passes**

```bash
cd langgraph-service && python -m pytest tests/test_llm_client.py -v
```
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add langgraph-service/app/llm/ langgraph-service/tests/test_llm_client.py
git commit -m "feat(langgraph): LiteLLM client wrapper"
```

---

## Task 6: LangGraph evaluation nodes

**Files:**
- Create: `langgraph-service/app/nodes/__init__.py`
- Create: `langgraph-service/app/nodes/story_parser.py`
- Create: `langgraph-service/app/nodes/criteria_validator.py`
- Create: `langgraph-service/app/nodes/clarity_scorer.py`
- Create: `langgraph-service/app/nodes/generate_findings.py`
- Create: `langgraph-service/app/nodes/rewrite_generator.py`
- Create: `langgraph-service/app/nodes/format_output.py`
- Create: `langgraph-service/tests/test_nodes.py`

- [ ] **Step 1: Write failing tests**

```python
# langgraph-service/tests/test_nodes.py
import pytest
from app.nodes.story_parser import parse_input
from app.nodes.criteria_validator import validate_criteria
from app.nodes.format_output import format_output


def _base_state():
    return {
        "run_id": "run-1",
        "story_id": "story-1",
        "org_id": "org-1",
        "title": "Als Nutzer möchte ich Login",
        "description": "Ich möchte mich einloggen",
        "acceptance_criteria": "Gegeben ich bin auf der Login-Seite\nWenn ich Daten eingebe\nDann werde ich eingeloggt",
        "context_hints": [],
        "parsed_criteria": [],
        "criteria_completeness": 0.0,
        "clarity_score": 0.0,
        "clarity_explanation": "",
        "findings": [],
        "rewrite_title": "",
        "rewrite_story": "",
        "rewrite_criteria": [],
        "open_questions": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "model_used": "",
    }


def test_parse_input_extracts_criteria():
    state = _base_state()
    result = parse_input(state)
    assert len(result["parsed_criteria"]) == 3
    assert "Gegeben ich bin auf der Login-Seite" in result["parsed_criteria"]


def test_parse_input_empty_criteria():
    state = _base_state()
    state["acceptance_criteria"] = ""
    result = parse_input(state)
    assert result["parsed_criteria"] == []


def test_validate_criteria_full_given_when_then():
    state = _base_state()
    state["parsed_criteria"] = [
        "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich Stats"
    ]
    result = validate_criteria(state)
    assert result["criteria_completeness"] > 0.5


def test_validate_criteria_no_criteria():
    state = _base_state()
    state["parsed_criteria"] = []
    result = validate_criteria(state)
    assert result["criteria_completeness"] == 0.0


def test_format_output_computes_score():
    state = _base_state()
    state.update({
        "criteria_completeness": 0.8,
        "clarity_score": 7.0,
        "clarity_explanation": "Klar formuliert",
        "findings": [],
        "rewrite_title": "Als Projektmanager...",
        "rewrite_story": "Als PM möchte ich...",
        "rewrite_criteria": ["Gegeben..., wenn..., dann..."],
        "open_questions": [],
        "total_input_tokens": 200,
        "total_output_tokens": 100,
        "model_used": "eval-quality",
    })
    result = format_output(state)
    assert 0 <= result["final_score"] <= 10
    assert result["ampel"] in ("GREEN", "YELLOW", "RED")
    assert result["knockout"] is False
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd langgraph-service && python -m pytest tests/test_nodes.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create nodes/__init__.py**

```python
# langgraph-service/app/nodes/__init__.py
```

- [ ] **Step 4: Create story_parser.py**

```python
# langgraph-service/app/nodes/story_parser.py
from __future__ import annotations


def parse_input(state: dict) -> dict:
    """
    Deterministic: split acceptance_criteria into list, clean whitespace.
    No LLM call.
    """
    raw = state.get("acceptance_criteria", "") or ""
    criteria = [line.strip() for line in raw.splitlines() if line.strip()]
    return {"parsed_criteria": criteria}
```

- [ ] **Step 5: Create criteria_validator.py**

```python
# langgraph-service/app/nodes/criteria_validator.py
from __future__ import annotations

_GWT_KEYWORDS = {"gegeben", "wenn", "dann", "given", "when", "then", "as", "i want", "so that"}


def validate_criteria(state: dict) -> dict:
    """
    Deterministic: score AC completeness 0.0–1.0.
    No LLM call.

    Formula:
      - count_score: min(count / 3, 1.0) weighted 0.5
        (3 or more ACs = full score)
      - gwt_score: fraction of ACs containing GWT keywords, weighted 0.5
    """
    criteria: list[str] = state.get("parsed_criteria", [])
    if not criteria:
        return {"criteria_completeness": 0.0}

    count_score = min(len(criteria) / 3.0, 1.0)

    def has_gwt(ac: str) -> bool:
        lower = ac.lower()
        return any(kw in lower for kw in _GWT_KEYWORDS)

    gwt_score = sum(1 for c in criteria if has_gwt(c)) / len(criteria)
    completeness = round(count_score * 0.5 + gwt_score * 0.5, 3)
    return {"criteria_completeness": completeness}
```

- [ ] **Step 6: Create clarity_scorer.py**

```python
# langgraph-service/app/nodes/clarity_scorer.py
from __future__ import annotations
import asyncio
import json
import logging

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für Anforderungsqualität. Bewerte die vorliegende User Story auf Klarheit.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt diesem Format (keine weiteren Zeichen außen herum):
{
  "score": <float 0-10>,
  "explanation": "<max 2 Sätze auf Deutsch>",
  "has_clear_persona": <true|false>,
  "has_clear_goal": <true|false>,
  "has_measurable_value": <true|false>,
  "knockout": <true — nur wenn Story fundamental unverständlich>
}

Bewertungsskala:
0-3: fundamental unklar, kein Verständnis möglich
4-5: grob verständlich, aber wesentliche Lücken
6-7: verständlich, kleinere Lücken
8-10: klar, vollständig, präzise
"""


def clarity_scorer(state: dict) -> dict:
    """LLM node — scores story clarity. Runs sync via asyncio.run() inside StateGraph."""
    return asyncio.get_event_loop().run_until_complete(_async_clarity_scorer(state))


async def _async_clarity_scorer(state: dict) -> dict:
    client = LiteLLMClient()
    user_msg = (
        f"Titel: {state.get('title', '')}\n"
        f"Beschreibung: {state.get('description', '')}\n"
        f"Akzeptanzkriterien:\n{state.get('acceptance_criteria', '')}"
    )
    try:
        text, usage = await client.chat(
            model="eval-fast",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        return {
            "clarity_score": float(data.get("score", 5.0)),
            "clarity_explanation": data.get("explanation", ""),
            "knockout": bool(data.get("knockout", False)),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-fast"),
        }
    except Exception as e:
        logger.error("clarity_scorer failed: %s", e)
        return {
            "clarity_score": 5.0,
            "clarity_explanation": f"Bewertung nicht verfügbar: {e}",
            "knockout": False,
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-fast",
        }
    finally:
        await client.aclose()
```

- [ ] **Step 7: Create generate_findings.py**

```python
# langgraph-service/app/nodes/generate_findings.py
from __future__ import annotations
import asyncio
import json
import logging
import uuid

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für Anforderungsqualität. Analysiere die User Story und erzeuge konkrete Verbesserungshinweise.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt in exakt diesem Format:
{
  "findings": [
    {
      "severity": "<CRITICAL|MAJOR|MINOR|INFO>",
      "category": "<CLARITY|COMPLETENESS|TESTABILITY|FEASIBILITY|BUSINESS_VALUE>",
      "title": "<max 60 Zeichen>",
      "description": "<Problembeschreibung, max 2 Sätze>",
      "suggestion": "<konkreter Verbesserungsvorschlag, max 2 Sätze>"
    }
  ],
  "open_questions": ["<Frage 1>", "<Frage 2>"]
}

Regeln:
- Maximal 5 Findings
- CRITICAL nur bei fundamentalen Mängeln (keine Persona, kein Ziel, kein Wert erkennbar)
- Keine redundanten Findings — lieber weniger, dafür präzise
- open_questions: maximal 3, nur wenn wirklich unklar
- Antworte auf Deutsch
"""


def generate_findings(state: dict) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_generate_findings(state))


async def _async_generate_findings(state: dict) -> dict:
    client = LiteLLMClient()
    user_msg = (
        f"Titel: {state.get('title', '')}\n"
        f"Beschreibung: {state.get('description', '')}\n"
        f"Akzeptanzkriterien:\n{state.get('acceptance_criteria', '')}\n"
        f"Klarheits-Score: {state.get('clarity_score', 0)}/10\n"
        f"AC-Vollständigkeit: {state.get('criteria_completeness', 0)*10:.1f}/10"
    )
    try:
        text, usage = await client.chat(
            model="eval-quality",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1200,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        findings = []
        for i, f in enumerate(data.get("findings", [])):
            findings.append({
                "id": f"f-{i+1:03d}",
                "severity": f.get("severity", "MINOR"),
                "category": f.get("category", "CLARITY"),
                "title": f.get("title", ""),
                "description": f.get("description", ""),
                "suggestion": f.get("suggestion", ""),
            })
        return {
            "findings": findings,
            "open_questions": data.get("open_questions", []),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-quality"),
        }
    except Exception as e:
        logger.error("generate_findings failed: %s", e)
        return {
            "findings": [],
            "open_questions": [],
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-quality",
        }
    finally:
        await client.aclose()
```

- [ ] **Step 8: Create rewrite_generator.py**

```python
# langgraph-service/app/nodes/rewrite_generator.py
from __future__ import annotations
import asyncio
import json
import logging

from app.llm.client import LiteLLMClient

logger = logging.getLogger(__name__)

_SYSTEM = """\
Du bist ein Experte für agile Anforderungen. Erstelle einen verbesserten Rewrite der User Story.

Antworte AUSSCHLIESSLICH mit einem JSON-Objekt:
{
  "title": "<verbesserter Titel, max 80 Zeichen>",
  "story": "<vollständige User Story: Als [Rolle] möchte ich [Ziel], damit [Nutzen]>",
  "acceptance_criteria": [
    "<AC 1: Gegeben..., wenn..., dann...>",
    "<AC 2>",
    "<AC 3>"
  ]
}

Regeln:
- Behalte den fachlichen Kern der Original-Story
- Verbessere Persona, Ziel und Nutzen wenn unklar
- ACs im Given-When-Then-Format
- Mindestens 2, maximal 5 ACs
- Antworte auf Deutsch
"""


def rewrite_generator(state: dict) -> dict:
    return asyncio.get_event_loop().run_until_complete(_async_rewrite_generator(state))


async def _async_rewrite_generator(state: dict) -> dict:
    client = LiteLLMClient()
    findings_text = "\n".join(
        f"- [{f['severity']}] {f['title']}: {f['suggestion']}"
        for f in state.get("findings", [])
    )
    user_msg = (
        f"Original-Story:\n"
        f"Titel: {state.get('title', '')}\n"
        f"Story: {state.get('description', '')}\n"
        f"ACs: {state.get('acceptance_criteria', '')}\n\n"
        f"Gefundene Mängel:\n{findings_text or 'Keine kritischen Mängel.'}"
    )
    try:
        text, usage = await client.chat(
            model="eval-quality",
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=1000,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        data = json.loads(text)
        return {
            "rewrite_title": data.get("title", state.get("title", "")),
            "rewrite_story": data.get("story", state.get("description", "")),
            "rewrite_criteria": data.get("acceptance_criteria", []),
            "total_input_tokens": state.get("total_input_tokens", 0) + usage["input_tokens"],
            "total_output_tokens": state.get("total_output_tokens", 0) + usage["output_tokens"],
            "model_used": usage.get("model", "eval-quality"),
        }
    except Exception as e:
        logger.error("rewrite_generator failed: %s", e)
        return {
            "rewrite_title": state.get("title", ""),
            "rewrite_story": state.get("description", ""),
            "rewrite_criteria": [],
            "total_input_tokens": state.get("total_input_tokens", 0),
            "total_output_tokens": state.get("total_output_tokens", 0),
            "model_used": "eval-quality",
        }
    finally:
        await client.aclose()
```

- [ ] **Step 9: Create format_output.py**

```python
# langgraph-service/app/nodes/format_output.py
from __future__ import annotations
from app.schemas.evaluation import compute_ampel, Ampel


_CRITERION_WEIGHTS = {
    "completeness": 0.30,
    "clarity": 0.30,
    "testability": 0.20,
    "business_value": 0.10,
    "feasibility": 0.10,
}


def format_output(state: dict) -> dict:
    """
    Deterministic: assemble final score from intermediate node results.
    No LLM call.
    """
    criteria_completeness: float = state.get("criteria_completeness", 0.0)
    clarity_score: float = state.get("clarity_score", 5.0)
    findings: list[dict] = state.get("findings", [])

    # Testability: derived from AC count + GWT presence (criteria_completeness proxy)
    testability_score = criteria_completeness * 10.0

    # Business value: approximate from clarity (no dedicated LLM call in MVP)
    business_value_score = min(clarity_score + 0.5, 10.0)

    # Feasibility: default 7.0 (no technical analysis in MVP)
    feasibility_score = 7.0

    criteria_scores = {
        "completeness": {
            "score": round(criteria_completeness * 10.0, 1),
            "weight": _CRITERION_WEIGHTS["completeness"],
            "explanation": f"AC-Vollständigkeit: {criteria_completeness*100:.0f}%",
        },
        "clarity": {
            "score": round(clarity_score, 1),
            "weight": _CRITERION_WEIGHTS["clarity"],
            "explanation": state.get("clarity_explanation", ""),
        },
        "testability": {
            "score": round(testability_score, 1),
            "weight": _CRITERION_WEIGHTS["testability"],
            "explanation": "Abgeleitet aus AC-Vollständigkeit und GWT-Format",
        },
        "business_value": {
            "score": round(business_value_score, 1),
            "weight": _CRITERION_WEIGHTS["business_value"],
            "explanation": "Approximiert aus Klarheitsbewertung",
        },
        "feasibility": {
            "score": feasibility_score,
            "weight": _CRITERION_WEIGHTS["feasibility"],
            "explanation": "Standard-Schätzung (keine technische Analyse in MVP)",
        },
    }

    # Weighted total score
    final_score = round(
        sum(v["score"] * v["weight"] for v in criteria_scores.values()), 2
    )

    # Knockout: any CRITICAL finding
    knockout = any(f.get("severity") == "CRITICAL" for f in findings)
    if state.get("knockout"):
        knockout = True

    ampel: Ampel = compute_ampel(score=final_score, knockout=knockout)

    # Confidence: simple proxy — higher if no fallback values used
    confidence = round(
        0.5
        + (0.2 if criteria_completeness > 0 else 0)
        + (0.2 if clarity_score != 5.0 else 0)
        + (0.1 if findings else 0),
        2,
    )

    return {
        "final_score": final_score,
        "ampel": ampel.value,
        "knockout": knockout,
        "confidence": min(confidence, 1.0),
        "criteria_scores": criteria_scores,
    }
```

- [ ] **Step 10: Run node tests — verify they pass**

```bash
cd langgraph-service && python -m pytest tests/test_nodes.py -v
```
Expected: `9 passed`.

- [ ] **Step 11: Commit nodes**

```bash
git add langgraph-service/app/nodes/ langgraph-service/tests/test_nodes.py
git commit -m "feat(langgraph): evaluation graph nodes (parser, validator, scorer, findings, rewrite, format)"
```

---

## Task 7: LangGraph StateGraph assembly

**Files:**
- Create: `langgraph-service/app/workflows/__init__.py`
- Create: `langgraph-service/app/workflows/evaluate.py`
- Create: `langgraph-service/tests/test_evaluate_workflow.py`

- [ ] **Step 1: Write failing integration test**

```python
# langgraph-service/tests/test_evaluate_workflow.py
import pytest
from unittest.mock import patch, AsyncMock


def _mock_chat_clarity(model, messages, **kwargs):
    import json
    return json.dumps({
        "score": 7.0,
        "explanation": "Klar formuliert, Persona vorhanden",
        "has_clear_persona": True,
        "has_clear_goal": True,
        "has_measurable_value": True,
        "knockout": False,
    }), {"input_tokens": 100, "output_tokens": 50, "model": model}


def _mock_chat_findings(model, messages, **kwargs):
    import json
    return json.dumps({
        "findings": [
            {
                "severity": "MINOR",
                "category": "TESTABILITY",
                "title": "AC könnte messbarer sein",
                "description": "AC3 enthält keinen konkreten Schwellenwert.",
                "suggestion": "Ergänze einen messbaren Wert.",
            }
        ],
        "open_questions": ["Welche Rollen haben Zugriff?"],
    }), {"input_tokens": 200, "output_tokens": 100, "model": model}


def _mock_chat_rewrite(model, messages, **kwargs):
    import json
    return json.dumps({
        "title": "Als Projektmanager möchte ich Sprint-Übersicht sehen",
        "story": "Als Projektmanager möchte ich alle Sprints sehen, damit ich den Status kenne.",
        "acceptance_criteria": [
            "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich alle Sprints.",
        ],
    }), {"input_tokens": 150, "output_tokens": 80, "model": model}


def test_evaluate_workflow_returns_valid_result():
    from app.workflows.evaluate import run_evaluation
    from app.schemas.evaluation import EvaluateRequest

    request = EvaluateRequest(
        run_id="run-001",
        story_id="story-001",
        org_id="org-001",
        title="Als Nutzer möchte ich den Sprint-Status sehen",
        description="Ich möchte alle aktiven Sprints auf einem Dashboard sehen",
        acceptance_criteria=(
            "Gegeben ich bin eingeloggt, wenn ich Dashboard öffne, dann sehe ich Sprints.\n"
            "Gegeben ein Sprint ist überfällig, dann ist er rot markiert.\n"
            "Die Seite lädt in unter 2 Sekunden."
        ),
    )

    call_count = [0]

    async def mock_chat(model, messages, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return _mock_chat_clarity(model, messages, **kwargs)
        elif call_count[0] == 2:
            return _mock_chat_findings(model, messages, **kwargs)
        else:
            return _mock_chat_rewrite(model, messages, **kwargs)

    with patch("app.llm.client.LiteLLMClient.chat", new=AsyncMock(side_effect=mock_chat)):
        result = run_evaluation(request)

    assert result.story_id == "story-001"
    assert result.run_id == "run-001"
    assert 0 <= result.score <= 10
    assert result.ampel in ("GREEN", "YELLOW", "RED")
    assert isinstance(result.findings, list)
    assert result.rewrite.title != ""
    assert result.input_tokens > 0


def test_evaluate_workflow_handles_llm_failure_gracefully():
    """If LLM calls fail, workflow should still return a result with fallback values."""
    from app.workflows.evaluate import run_evaluation
    from app.schemas.evaluation import EvaluateRequest
    from app.llm.client import LLMCallError

    request = EvaluateRequest(
        run_id="run-002",
        story_id="story-002",
        org_id="org-001",
        title="Test",
        description="",
        acceptance_criteria="",
    )

    with patch("app.llm.client.LiteLLMClient.chat", new=AsyncMock(side_effect=LLMCallError("timeout"))):
        result = run_evaluation(request)

    assert result.run_id == "run-002"
    assert result.score >= 0
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd langgraph-service && python -m pytest tests/test_evaluate_workflow.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create workflows/evaluate.py**

```python
# langgraph-service/app/workflows/__init__.py
```

```python
# langgraph-service/app/workflows/evaluate.py
from __future__ import annotations
import logging
from typing import TypedDict

from langgraph.graph import StateGraph, END

from app.nodes.story_parser import parse_input
from app.nodes.criteria_validator import validate_criteria
from app.nodes.clarity_scorer import clarity_scorer
from app.nodes.generate_findings import generate_findings
from app.nodes.rewrite_generator import rewrite_generator
from app.nodes.format_output import format_output
from app.schemas.evaluation import EvaluateRequest, EvaluationResult, EvalFinding, CriterionScore, RewriteSuggestion, Ampel

logger = logging.getLogger(__name__)


class EvalState(TypedDict):
    # Input
    run_id: str
    story_id: str
    org_id: str
    title: str
    description: str
    acceptance_criteria: str
    context_hints: list
    # Intermediate
    parsed_criteria: list
    criteria_completeness: float
    clarity_score: float
    clarity_explanation: str
    knockout: bool
    findings: list
    open_questions: list
    rewrite_title: str
    rewrite_story: str
    rewrite_criteria: list
    # Accumulate token usage across nodes
    total_input_tokens: int
    total_output_tokens: int
    model_used: str
    # Output
    final_score: float
    ampel: str
    confidence: float
    criteria_scores: dict


def _build_graph() -> StateGraph:
    g = StateGraph(EvalState)
    g.add_node("parse_input", parse_input)
    g.add_node("validate_criteria", validate_criteria)
    g.add_node("clarity_scorer", clarity_scorer)
    g.add_node("generate_findings", generate_findings)
    g.add_node("rewrite_generator", rewrite_generator)
    g.add_node("format_output", format_output)

    g.set_entry_point("parse_input")
    g.add_edge("parse_input", "validate_criteria")
    g.add_edge("validate_criteria", "clarity_scorer")
    g.add_edge("clarity_scorer", "generate_findings")
    g.add_edge("generate_findings", "rewrite_generator")
    g.add_edge("rewrite_generator", "format_output")
    g.add_edge("format_output", END)
    return g


_compiled_graph = _build_graph().compile()


def run_evaluation(request: EvaluateRequest) -> EvaluationResult:
    """
    Execute the evaluation StateGraph synchronously.
    All LLM calls happen inside nodes; this function blocks until complete.
    """
    initial_state: EvalState = {
        "run_id": request.run_id,
        "story_id": request.story_id,
        "org_id": request.org_id,
        "title": request.title,
        "description": request.description,
        "acceptance_criteria": request.acceptance_criteria,
        "context_hints": request.context_hints,
        "parsed_criteria": [],
        "criteria_completeness": 0.0,
        "clarity_score": 5.0,
        "clarity_explanation": "",
        "knockout": False,
        "findings": [],
        "open_questions": [],
        "rewrite_title": "",
        "rewrite_story": "",
        "rewrite_criteria": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "model_used": "",
        "final_score": 0.0,
        "ampel": "YELLOW",
        "confidence": 0.5,
        "criteria_scores": {},
    }

    logger.info("Starting evaluation workflow run_id=%s story_id=%s", request.run_id, request.story_id)
    final_state = _compiled_graph.invoke(initial_state)
    logger.info(
        "Completed evaluation run_id=%s score=%.2f ampel=%s",
        request.run_id, final_state["final_score"], final_state["ampel"],
    )

    findings = [EvalFinding(**f) for f in final_state.get("findings", [])]
    criteria_scores = {
        k: CriterionScore(**v)
        for k, v in final_state.get("criteria_scores", {}).items()
    }

    return EvaluationResult(
        run_id=final_state["run_id"],
        story_id=final_state["story_id"],
        org_id=final_state["org_id"],
        score=final_state["final_score"],
        ampel=Ampel(final_state["ampel"]),
        knockout=final_state["knockout"],
        confidence=final_state["confidence"],
        criteria_scores=criteria_scores,
        findings=findings,
        open_questions=final_state.get("open_questions", []),
        rewrite=RewriteSuggestion(
            title=final_state.get("rewrite_title", request.title),
            story=final_state.get("rewrite_story", request.description),
            acceptance_criteria=final_state.get("rewrite_criteria", []),
        ),
        model_used=final_state.get("model_used", "eval-quality"),
        input_tokens=final_state["total_input_tokens"],
        output_tokens=final_state["total_output_tokens"],
    )
```

- [ ] **Step 4: Run workflow tests — verify they pass**

```bash
cd langgraph-service && python -m pytest tests/test_evaluate_workflow.py -v
```
Expected: `2 passed`.

- [ ] **Step 5: Run full test suite**

```bash
cd langgraph-service && python -m pytest tests/ -v
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add langgraph-service/app/workflows/ langgraph-service/tests/test_evaluate_workflow.py
git commit -m "feat(langgraph): evaluation StateGraph with 6 nodes"
```

---

## Task 8: langgraph-service HTTP endpoint

**Files:**
- Create: `langgraph-service/app/routers/__init__.py`
- Create: `langgraph-service/app/routers/workflows.py`
- Modify: `langgraph-service/app/main.py`
- Create: `langgraph-service/tests/test_workflow_endpoint.py`

- [ ] **Step 1: Write failing test**

```python
# langgraph-service/tests/test_workflow_endpoint.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock


def _mock_evaluation_result():
    from app.schemas.evaluation import (
        EvaluationResult, Ampel, EvalFinding, CriterionScore, RewriteSuggestion,
        FindingSeverity, FindingCategory,
    )
    return EvaluationResult(
        run_id="run-test",
        story_id="story-test",
        org_id="org-test",
        score=7.2,
        ampel=Ampel.GREEN,
        knockout=False,
        confidence=0.85,
        criteria_scores={
            "clarity": CriterionScore(score=7.0, weight=0.3, explanation="Klar"),
        },
        findings=[],
        open_questions=[],
        rewrite=RewriteSuggestion(title="T", story="S", acceptance_criteria=[]),
        model_used="eval-quality",
        input_tokens=300,
        output_tokens=150,
    )


@pytest.mark.asyncio
async def test_evaluate_endpoint_returns_result():
    from app.main import app
    with patch("app.routers.workflows.run_evaluation", return_value=_mock_evaluation_result()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/workflows/evaluate",
                json={
                    "run_id": "run-test",
                    "story_id": "story-test",
                    "org_id": "org-test",
                    "title": "Als Nutzer...",
                    "description": "...",
                    "acceptance_criteria": "Gegeben...",
                },
                headers={"X-API-Key": "test-secret"},
            )
    assert response.status_code == 200
    data = response.json()
    assert data["run_id"] == "run-test"
    assert data["score"] == 7.2
    assert data["ampel"] == "GREEN"


@pytest.mark.asyncio
async def test_evaluate_endpoint_rejects_missing_api_key():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/workflows/evaluate",
            json={"run_id": "x", "story_id": "x", "org_id": "x", "title": "x"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_endpoint_rejects_wrong_api_key():
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/workflows/evaluate",
            json={"run_id": "x", "story_id": "x", "org_id": "x", "title": "x"},
            headers={"X-API-Key": "wrong-key"},
        )
    assert response.status_code == 401
```

- [ ] **Step 2: Run — verify it fails**

```bash
cd langgraph-service && python -m pytest tests/test_workflow_endpoint.py -v
```
Expected: `ImportError`.

- [ ] **Step 3: Create routers/workflows.py**

```python
# langgraph-service/app/routers/__init__.py
```

```python
# langgraph-service/app/routers/workflows.py
from __future__ import annotations
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.schemas.evaluation import EvaluateRequest, EvaluationResult
from app.workflows.evaluate import run_evaluation

logger = logging.getLogger(__name__)
router = APIRouter()
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    settings = get_settings()
    if x_api_key != settings.langgraph_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@router.post(
    "/workflows/evaluate",
    response_model=EvaluationResult,
    dependencies=[Depends(_verify_api_key)],
)
def evaluate_story(request: EvaluateRequest) -> EvaluationResult:
    """
    Execute story evaluation workflow synchronously.
    Blocks until all LangGraph nodes complete (up to ~60s).
    Called by Backend only — not publicly exposed.
    """
    logger.info("evaluate_story run_id=%s story_id=%s", request.run_id, request.story_id)
    return run_evaluation(request)
```

- [ ] **Step 4: Update main.py to include router**

```python
# langgraph-service/app/main.py
import logging
from fastapi import FastAPI

from app.config import get_settings
from app.routers.workflows import router as workflows_router

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="langgraph-service", version="1.0.0", docs_url=None, redoc_url=None)
app.include_router(workflows_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Run all tests**

```bash
cd langgraph-service && python -m pytest tests/ -v
```
Expected: all pass.

- [ ] **Step 6: Build Docker image**

```bash
cd infra && docker compose -f docker-compose.yml build langgraph-service
```
Expected: build succeeds, no errors.

- [ ] **Step 7: Start service and check health**

```bash
cd infra && docker compose -f docker-compose.yml up -d langgraph-service
docker logs assist2-langgraph --tail 20
curl -s http://localhost:8100/health
```
Expected: `{"status":"ok"}` (only accessible from internal network or forwarded port).

- [ ] **Step 8: Commit**

```bash
git add langgraph-service/app/routers/ langgraph-service/app/main.py langgraph-service/tests/test_workflow_endpoint.py
git commit -m "feat(langgraph): POST /workflows/evaluate endpoint with API-key auth"
```

---

## Task 9: Backend — Alembic migrations

**Files:**
- Create: `backend/migrations/versions/0029_add_evaluation_tables.py`
- Create: `backend/migrations/versions/0030_add_story_embeddings.py`
- Create: `backend/migrations/versions/0031_add_integration_events.py`

- [ ] **Step 1: Create migration 0029 — evaluation_runs + evaluation_findings + approval_requests**

```python
# backend/migrations/versions/0029_add_evaluation_tables.py
"""Add evaluation_runs, evaluation_findings, approval_requests

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-07
"""
from alembic import op

revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE evaluation_status AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED');
        CREATE TYPE ampel_status AS ENUM ('GREEN', 'YELLOW', 'RED');
        CREATE TYPE finding_severity AS ENUM ('CRITICAL', 'MAJOR', 'MINOR', 'INFO');
        CREATE TYPE approval_status AS ENUM ('PENDING', 'APPROVED', 'REJECTED');
    """)

    op.execute("""
        CREATE TABLE evaluation_runs (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id        UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            triggered_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
            status          evaluation_status NOT NULL DEFAULT 'PENDING',
            score           NUMERIC(4,2),
            ampel           ampel_status,
            knockout        BOOLEAN DEFAULT FALSE,
            confidence      NUMERIC(4,3),
            result_json     JSONB,
            model_used      VARCHAR(100),
            input_tokens    INTEGER DEFAULT 0,
            output_tokens   INTEGER DEFAULT 0,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            completed_at    TIMESTAMPTZ,
            deleted_at      TIMESTAMPTZ
        );

        CREATE INDEX ix_evaluation_runs_org_id     ON evaluation_runs(organization_id);
        CREATE INDEX ix_evaluation_runs_story_id   ON evaluation_runs(story_id);
        CREATE INDEX ix_evaluation_runs_status     ON evaluation_runs(status);
        CREATE INDEX ix_evaluation_runs_created_at ON evaluation_runs(created_at DESC);
    """)

    op.execute("""
        CREATE TABLE evaluation_findings (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            evaluation_run_id UUID NOT NULL REFERENCES evaluation_runs(id) ON DELETE CASCADE,
            finding_key     VARCHAR(20) NOT NULL,
            severity        finding_severity NOT NULL,
            category        VARCHAR(50) NOT NULL,
            title           VARCHAR(200) NOT NULL,
            description     TEXT NOT NULL,
            suggestion      TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_eval_findings_run_id ON evaluation_findings(evaluation_run_id);
    """)

    op.execute("""
        CREATE TABLE approval_requests (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id        UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            evaluation_run_id UUID REFERENCES evaluation_runs(id) ON DELETE SET NULL,
            status          approval_status NOT NULL DEFAULT 'PENDING',
            reviewer_id     UUID REFERENCES users(id) ON DELETE SET NULL,
            decided_by_id   UUID REFERENCES users(id) ON DELETE SET NULL,
            decided_at      TIMESTAMPTZ,
            comment         TEXT,
            slack_message_ts VARCHAR(50),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE INDEX ix_approval_requests_org_id   ON approval_requests(organization_id);
        CREATE INDEX ix_approval_requests_story_id ON approval_requests(story_id);
        CREATE INDEX ix_approval_requests_status   ON approval_requests(status);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approval_requests")
    op.execute("DROP TABLE IF EXISTS evaluation_findings")
    op.execute("DROP TABLE IF EXISTS evaluation_runs")
    op.execute("DROP TYPE IF EXISTS approval_status")
    op.execute("DROP TYPE IF EXISTS finding_severity")
    op.execute("DROP TYPE IF EXISTS ampel_status")
    op.execute("DROP TYPE IF EXISTS evaluation_status")
```

- [ ] **Step 2: Create migration 0030 — story_embeddings**

```python
# backend/migrations/versions/0030_add_story_embeddings.py
"""Add story_embeddings table with pgvector HNSW index

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-07
"""
from alembic import op

revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE story_embeddings (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            story_id        UUID NOT NULL REFERENCES user_stories(id) ON DELETE CASCADE,
            embedding       vector(1024),
            content_hash    VARCHAR(64) NOT NULL,
            model_used      VARCHAR(100) NOT NULL DEFAULT 'ionos-embed',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (story_id)
        );

        CREATE INDEX ix_story_embeddings_org_id ON story_embeddings(organization_id);
    """)

    # HNSW index — supports cosine distance queries
    op.execute("""
        CREATE INDEX ix_story_embeddings_hnsw
        ON story_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_story_embeddings_hnsw")
    op.execute("DROP TABLE IF EXISTS story_embeddings")
```

- [ ] **Step 3: Create migration 0031 — integration_events**

```python
# backend/migrations/versions/0031_add_integration_events.py
"""Add integration_events table for Jira/ServiceNow webhook audit

Revision ID: 0031
Revises: 0030
Create Date: 2026-04-07
"""
from alembic import op

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE integration_events (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
            source          VARCHAR(50) NOT NULL,
            event_type      VARCHAR(100) NOT NULL,
            external_id     VARCHAR(200),
            payload_json    JSONB NOT NULL,
            processed       BOOLEAN NOT NULL DEFAULT FALSE,
            error_message   TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (source, external_id, organization_id)
        );

        CREATE INDEX ix_integration_events_org_id     ON integration_events(organization_id);
        CREATE INDEX ix_integration_events_source     ON integration_events(source);
        CREATE INDEX ix_integration_events_created_at ON integration_events(created_at DESC);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS integration_events")
```

- [ ] **Step 4: Run migrations**

```bash
cd infra && docker compose -f docker-compose.yml exec backend alembic upgrade head
```
Expected: `Running upgrade 0028 -> 0029`, `0029 -> 0030`, `0030 -> 0031` — no errors.

- [ ] **Step 5: Verify tables exist**

```bash
cd infra && docker compose -f docker-compose.yml exec postgres psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\dt evaluation*" -c "\dt approval*" -c "\dt story_emb*" -c "\dt integration_events"
```
Expected: 5 tables listed.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0029_add_evaluation_tables.py \
        backend/migrations/versions/0030_add_story_embeddings.py \
        backend/migrations/versions/0031_add_integration_events.py
git commit -m "feat(backend): add evaluation_runs, findings, approvals, story_embeddings, integration_events migrations"
```

---

## Task 10: Backend — SQLAlchemy models

**Files:**
- Create: `backend/app/models/evaluation_run.py`
- Create: `backend/app/models/approval_request.py`

- [ ] **Step 1: Create evaluation_run.py**

```python
# backend/app/models/evaluation_run.py
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user_story import UserStory
    from app.models.user import User


class EvaluationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AmpelStatus(str, enum.Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    story_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_stories.id"), nullable=False, index=True)
    triggered_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[EvaluationStatus] = mapped_column(
        Enum(EvaluationStatus, name="evaluation_status"), default=EvaluationStatus.PENDING, nullable=False
    )
    score: Mapped[Optional[float]] = mapped_column(Numeric(4, 2), nullable=True)
    ampel: Mapped[Optional[AmpelStatus]] = mapped_column(
        Enum(AmpelStatus, name="ampel_status"), nullable=True
    )
    knockout: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    result_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

```python
# backend/app/models/approval_request.py
from __future__ import annotations
import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApprovalStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    story_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_stories.id"), nullable=False, index=True)
    evaluation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=True)
    status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"), default=ApprovalStatus.PENDING, nullable=False
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slack_message_ts: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Commit models**

```bash
git add backend/app/models/evaluation_run.py backend/app/models/approval_request.py
git commit -m "feat(backend): SQLAlchemy models for EvaluationRun and ApprovalRequest"
```

---

## Task 11: Backend — config additions

**Files:**
- Modify: `backend/app/config.py`
- Modify: `infra/.env` (add LANGGRAPH_BASE_URL)

- [ ] **Step 1: Add LangGraph settings to config.py**

In `backend/app/config.py`, add to the `Settings` class after the `N8N_API_KEY` line:

```python
    # LangGraph Service
    LANGGRAPH_BASE_URL: str = "http://langgraph-service:8100"
    LANGGRAPH_API_KEY: str = "dev-langgraph-secret"
    LANGGRAPH_TIMEOUT: int = 90  # seconds
```

- [ ] **Step 2: Ensure .env has the variable**

```bash
grep -q "LANGGRAPH_BASE_URL" /opt/assist2/infra/.env || echo "LANGGRAPH_BASE_URL=http://langgraph-service:8100" >> /opt/assist2/infra/.env
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py infra/.env
git commit -m "feat(backend): add LangGraph service config settings"
```

---

## Task 12: Backend — evaluation_service + schemas

**Files:**
- Create: `backend/app/schemas/evaluation.py`
- Create: `backend/app/services/evaluation_service.py`
- Create: `backend/tests/test_evaluation_service.py`

- [ ] **Step 1: Create backend/app/schemas/evaluation.py**

```python
# backend/app/schemas/evaluation.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class EvaluationStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AmpelEnum(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


class CriterionScoreRead(BaseModel):
    score: float
    weight: float
    explanation: str


class FindingRead(BaseModel):
    id: str
    severity: str
    category: str
    title: str
    description: str
    suggestion: str


class RewriteRead(BaseModel):
    title: str
    story: str
    acceptance_criteria: list[str]


class EvaluationResultRead(BaseModel):
    score: float
    ampel: AmpelEnum
    knockout: bool
    confidence: float
    criteria_scores: dict[str, CriterionScoreRead]
    findings: list[FindingRead]
    open_questions: list[str]
    rewrite: RewriteRead
    model_used: str
    input_tokens: int
    output_tokens: int


class EvaluationRunRead(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    org_id: uuid.UUID
    status: EvaluationStatusEnum
    score: Optional[float]
    ampel: Optional[AmpelEnum]
    knockout: bool
    confidence: Optional[float]
    result: Optional[EvaluationResultRead]
    error_message: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class StartEvaluationResponse(BaseModel):
    run_id: uuid.UUID
    status: EvaluationStatusEnum
    result: Optional[EvaluationResultRead] = None
```

- [ ] **Step 2: Write failing service test**

```python
# backend/tests/test_evaluation_service.py
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_start_evaluation_creates_run_and_calls_langgraph():
    from app.services.evaluation_service import start_evaluation
    from app.models.evaluation_run import EvaluationStatus

    story_id = uuid.uuid4()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_story = MagicMock()
    mock_story.id = story_id
    mock_story.organization_id = org_id
    mock_story.title = "Test Story"
    mock_story.description = "Beschreibung"
    mock_story.acceptance_criteria = "Gegeben..., wenn..., dann..."

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_story)

    mock_lg_result = {
        "run_id": str(uuid.uuid4()),
        "story_id": str(story_id),
        "org_id": str(org_id),
        "score": 7.5,
        "ampel": "GREEN",
        "knockout": False,
        "confidence": 0.85,
        "criteria_scores": {"clarity": {"score": 7.5, "weight": 0.3, "explanation": "Klar"}},
        "findings": [],
        "open_questions": [],
        "rewrite": {"title": "T", "story": "S", "acceptance_criteria": []},
        "model_used": "eval-quality",
        "input_tokens": 200,
        "output_tokens": 100,
    }

    with patch("app.services.evaluation_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lg_result
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        result = await start_evaluation(
            story_id=story_id,
            org_id=org_id,
            triggered_by_id=user_id,
            db=mock_db,
        )

    assert result.status == EvaluationStatus.COMPLETED
    assert result.score == 7.5
    assert mock_db.add.called
    assert mock_db.commit.called
```

- [ ] **Step 3: Run test — verify it fails**

```bash
cd infra && docker compose -f docker-compose.yml exec backend python -m pytest tests/test_evaluation_service.py -v 2>&1 | tail -20
```
Expected: `ImportError` or module not found.

- [ ] **Step 4: Create evaluation_service.py**

```python
# backend/app/services/evaluation_service.py
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.evaluation_run import EvaluationRun, EvaluationStatus, AmpelStatus
from app.models.evaluation_finding import EvaluationFinding  # see note below
from app.models.user_story import UserStory
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)


async def start_evaluation(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    triggered_by_id: uuid.UUID,
    db: AsyncSession,
) -> EvaluationRun:
    """
    1. Load story from DB (verify org_id matches)
    2. Create evaluation_run (PENDING)
    3. Call LangGraph service synchronously
    4. Update run with result (COMPLETED or FAILED)
    5. Return run
    """
    settings = get_settings()

    story = await db.get(UserStory, story_id)
    if story is None or story.organization_id != org_id:
        raise NotFoundException("Story not found")

    run_id = uuid.uuid4()
    run = EvaluationRun(
        id=run_id,
        organization_id=org_id,
        story_id=story_id,
        triggered_by_id=triggered_by_id,
        status=EvaluationStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Call LangGraph service
    payload = {
        "run_id": str(run_id),
        "story_id": str(story_id),
        "org_id": str(org_id),
        "title": story.title,
        "description": story.description or "",
        "acceptance_criteria": story.acceptance_criteria or "",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.LANGGRAPH_TIMEOUT) as client:
            response = await client.post(
                f"{settings.LANGGRAPH_BASE_URL}/workflows/evaluate",
                json=payload,
                headers={"X-API-Key": settings.LANGGRAPH_API_KEY},
            )
            response.raise_for_status()
            data = response.json()

        run.status = EvaluationStatus.COMPLETED
        run.score = data.get("score")
        run.ampel = AmpelStatus(data["ampel"]) if data.get("ampel") else None
        run.knockout = data.get("knockout", False)
        run.confidence = data.get("confidence")
        run.result_json = data
        run.model_used = data.get("model_used")
        run.input_tokens = data.get("input_tokens", 0)
        run.output_tokens = data.get("output_tokens", 0)
        run.completed_at = datetime.now(timezone.utc)

    except httpx.TimeoutException as e:
        logger.error("LangGraph timeout for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = f"Timeout nach {settings.LANGGRAPH_TIMEOUT}s"
        run.completed_at = datetime.now(timezone.utc)

    except httpx.HTTPStatusError as e:
        logger.error("LangGraph HTTP error for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = f"LangGraph HTTP {e.response.status_code}"
        run.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        logger.error("Unexpected error for run %s: %s", run_id, e)
        run.status = EvaluationStatus.FAILED
        run.error_message = str(e)[:500]
        run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(run)
    return run


async def get_latest_evaluation(
    story_id: uuid.UUID,
    org_id: uuid.UUID,
    db: AsyncSession,
) -> EvaluationRun | None:
    from sqlalchemy import select
    stmt = (
        select(EvaluationRun)
        .where(
            EvaluationRun.story_id == story_id,
            EvaluationRun.organization_id == org_id,
            EvaluationRun.deleted_at.is_(None),
            EvaluationRun.status == EvaluationStatus.COMPLETED,
        )
        .order_by(EvaluationRun.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
```

Note: `EvaluationFinding` model is a simple child of `EvaluationRun`. Create `backend/app/models/evaluation_finding.py`:

```python
# backend/app/models/evaluation_finding.py
from __future__ import annotations
import uuid
from sqlalchemy import ForeignKey, String, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
from app.models.base import Base
from app.models.evaluation_run import AmpelStatus
import enum


class FindingSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class EvaluationFinding(Base):
    __tablename__ = "evaluation_findings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False, index=True)
    finding_key: Mapped[str] = mapped_column(String(20), nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(Enum(FindingSeverity, name="finding_severity"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
```

- [ ] **Step 5: Run test — verify it passes**

```bash
cd infra && docker compose -f docker-compose.yml exec backend python -m pytest tests/test_evaluation_service.py -v 2>&1 | tail -20
```
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/evaluation.py \
        backend/app/services/evaluation_service.py \
        backend/app/models/evaluation_run.py \
        backend/app/models/evaluation_finding.py \
        backend/app/models/approval_request.py \
        backend/tests/test_evaluation_service.py
git commit -m "feat(backend): evaluation_service, schemas, models"
```

---

## Task 13: Backend — evaluations router

**Files:**
- Create: `backend/app/routers/evaluations.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_evaluations_router.py`

- [ ] **Step 1: Write failing endpoint test**

```python
# backend/tests/test_evaluations_router.py
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from app.main import app


def _make_run(story_id, org_id, score=7.5):
    from app.models.evaluation_run import EvaluationRun, EvaluationStatus, AmpelStatus
    run = MagicMock(spec=EvaluationRun)
    run.id = uuid.uuid4()
    run.story_id = story_id
    run.organization_id = org_id
    run.status = EvaluationStatus.COMPLETED
    run.score = score
    run.ampel = AmpelStatus.GREEN
    run.knockout = False
    run.confidence = 0.85
    run.result_json = {
        "score": score, "ampel": "GREEN", "knockout": False, "confidence": 0.85,
        "criteria_scores": {"clarity": {"score": 7.5, "weight": 0.3, "explanation": "Klar"}},
        "findings": [], "open_questions": [],
        "rewrite": {"title": "T", "story": "S", "acceptance_criteria": []},
        "model_used": "eval-quality", "input_tokens": 200, "output_tokens": 100,
    }
    run.model_used = "eval-quality"
    run.input_tokens = 200
    run.output_tokens = 100
    run.error_message = None
    run.created_at = datetime.now(timezone.utc)
    run.completed_at = datetime.now(timezone.utc)
    return run


@pytest.mark.asyncio
async def test_start_evaluation_returns_result(auth_headers, sample_story):
    """Authenticated user can trigger evaluation for their org's story."""
    story_id = sample_story.id
    org_id = sample_story.organization_id
    mock_run = _make_run(story_id, org_id)

    with patch("app.routers.evaluations.start_evaluation", new_callable=AsyncMock, return_value=mock_run):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/evaluations/stories/{story_id}/evaluate",
                headers=auth_headers,
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["result"]["score"] == 7.5
    assert data["result"]["ampel"] == "GREEN"


@pytest.mark.asyncio
async def test_start_evaluation_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/evaluations/stories/{uuid.uuid4()}/evaluate")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_latest_evaluation_returns_none_when_no_runs(auth_headers, sample_story):
    story_id = sample_story.id
    with patch("app.routers.evaluations.get_latest_evaluation", new_callable=AsyncMock, return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/evaluations/stories/{story_id}/latest",
                headers=auth_headers,
            )
    assert response.status_code == 200
    assert response.json() == {"result": None}
```

- [ ] **Step 2: Run test — verify it fails**

```bash
cd infra && docker compose -f docker-compose.yml exec backend python -m pytest tests/test_evaluations_router.py -v 2>&1 | tail -20
```
Expected: `ImportError` (router not registered yet).

- [ ] **Step 3: Create evaluations router**

```python
# backend/app/routers/evaluations.py
from __future__ import annotations
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.evaluation import StartEvaluationResponse, EvaluationRunRead, EvaluationResultRead
from app.services.evaluation_service import start_evaluation, get_latest_evaluation
from app.core.exceptions import NotFoundException

logger = logging.getLogger(__name__)
router = APIRouter()


def _run_to_read(run) -> EvaluationRunRead:
    result = None
    if run.result_json:
        result = EvaluationResultRead.model_validate(run.result_json)
    return EvaluationRunRead(
        id=run.id,
        story_id=run.story_id,
        org_id=run.organization_id,
        status=run.status,
        score=run.score,
        ampel=run.ampel,
        knockout=run.knockout,
        confidence=run.confidence,
        result=result,
        error_message=run.error_message,
        created_at=run.created_at,
        completed_at=run.completed_at,
    )


@router.post("/evaluations/stories/{story_id}/evaluate", response_model=StartEvaluationResponse)
async def trigger_evaluation(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StartEvaluationResponse:
    """Start story evaluation. Blocks until LangGraph workflow completes (≤90s)."""
    # org_id extracted from story in service — cross-org access blocked there
    # We need current user's org context: derive from story ownership
    from sqlalchemy import select
    from app.models.user_story import UserStory
    from app.models.membership import Membership

    result = await db.execute(
        select(UserStory).where(UserStory.id == story_id)
    )
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("Story not found")

    # Verify user is member of story's org
    membership = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == story.organization_id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    run = await start_evaluation(
        story_id=story_id,
        org_id=story.organization_id,
        triggered_by_id=current_user.id,
        db=db,
    )

    run_read = _run_to_read(run)
    return StartEvaluationResponse(
        run_id=run.id,
        status=run.status,
        result=run_read.result,
    )


@router.get("/evaluations/stories/{story_id}/latest")
async def get_latest(
    story_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return most recent completed evaluation for a story."""
    from sqlalchemy import select
    from app.models.user_story import UserStory
    from app.models.membership import Membership

    result = await db.execute(select(UserStory).where(UserStory.id == story_id))
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("Story not found")

    membership = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == story.organization_id,
        )
    )
    if membership.scalar_one_or_none() is None:
        raise HTTPException(status_code=403, detail="Not a member of this organization")

    run = await get_latest_evaluation(story_id=story_id, org_id=story.organization_id, db=db)
    if run is None:
        return {"result": None}

    return _run_to_read(run)


@router.get("/evaluations/{run_id}/status")
async def get_run_status(
    run_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll evaluation run status by run_id."""
    from sqlalchemy import select
    from app.models.evaluation_run import EvaluationRun
    from app.models.membership import Membership

    result = await db.execute(
        select(EvaluationRun).where(
            EvaluationRun.id == run_id,
            EvaluationRun.organization_id.in_(
                select(Membership.organization_id).where(Membership.user_id == current_user.id)
            ),
        )
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise NotFoundException("Evaluation run not found")

    return _run_to_read(run)
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add after the existing imports:

```python
from app.routers.evaluations import router as evaluations_router
```

And after the last `app.include_router(...)` call:

```python
app.include_router(evaluations_router, prefix="/api/v1", tags=["Evaluations"])
```

- [ ] **Step 5: Restart backend and run tests**

```bash
cd infra && docker compose -f docker-compose.yml restart backend
docker logs assist2-backend --tail 20
```
Expected: no startup errors.

```bash
cd infra && docker compose -f docker-compose.yml exec backend python -m pytest tests/test_evaluations_router.py -v 2>&1 | tail -20
```
Expected: tests pass (mock-based, no real LangGraph needed).

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/evaluations.py backend/app/main.py backend/tests/test_evaluations_router.py
git commit -m "feat(backend): POST /evaluations/stories/{id}/evaluate and GET /latest endpoints"
```

---

## Task 14: End-to-end smoke test

- [ ] **Step 1: Verify all services are healthy**

```bash
cd infra && docker compose -f docker-compose.yml ps
```
Expected: `backend`, `langgraph-service`, `litellm` all `healthy`.

- [ ] **Step 2: Get a JWT token**

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"yourpassword"}' \
  | jq -r '.access_token')
echo "Token: ${TOKEN:0:30}..."
```

- [ ] **Step 3: Find a story ID from your org**

```bash
curl -s http://localhost:8000/api/v1/user-stories \
  -H "Authorization: Bearer $TOKEN" | jq '.[0].id'
```

- [ ] **Step 4: Trigger evaluation**

```bash
STORY_ID="<id from step 3>"
curl -s -X POST http://localhost:8000/api/v1/evaluations/stories/$STORY_ID/evaluate \
  -H "Authorization: Bearer $TOKEN" \
  | jq '{status, score: .result.score, ampel: .result.ampel}'
```
Expected:
```json
{
  "status": "COMPLETED",
  "score": <float>,
  "ampel": "GREEN" | "YELLOW" | "RED"
}
```

- [ ] **Step 5: Verify result is in DB**

```bash
cd infra && docker compose -f docker-compose.yml exec postgres \
  psql -U ${POSTGRES_USER} -d ${POSTGRES_DB} \
  -c "SELECT id, story_id, status, score, ampel, model_used FROM evaluation_runs ORDER BY created_at DESC LIMIT 3;"
```
Expected: row with status=COMPLETED.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: Sub-Plan A complete — LangGraph evaluation service + Backend API"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] `langgraph-service` container deployable: Tasks 2, 3, 8
- [x] All LLM calls via LiteLLM only: Task 5 (llm/client.py)
- [x] Backend is system of record: Task 9 (migrations), Task 12 (service persists)
- [x] API-Key auth on LangGraph service: Task 8 (`_verify_api_key`)
- [x] org_id in all DB queries: Tasks 9, 12, 13
- [x] No cross-org access: Task 13 (membership check)
- [x] LiteLLM eval aliases: Task 1
- [x] LangGraph service not publicly exposed: Task 2 (no proxy network)
- [x] Evaluation result structured with score/ampel/findings/rewrite: Tasks 4, 6, 7

**Not in Sub-Plan A (intentionally deferred):**
- pgvector duplicate check (Sub-Plan B)
- Slack notifications (Sub-Plan D)
- Jira/ServiceNow triggers (Sub-Plan C)
- UI components (Sub-Plan E)
- Async/Celery evaluation (Phase 2 of Sub-Plan A)

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-07-subplan-a-langgraph-evaluation.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks

**2. Inline Execution** — Execute tasks in this session using executing-plans

Which approach?
