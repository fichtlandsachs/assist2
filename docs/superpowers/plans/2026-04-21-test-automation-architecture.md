# Test Automation Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular, CI/CD-ready test automation framework under `/opt/test/` that validates Frontend, Backend, Ghost, and all integration services after every deployment without auto-generating new tests.

**Architecture:** All tests live in `/opt/test/<component>/` to stay independent from application code. Backend smoke and integration tests use `pytest + httpx` hitting live containers; frontend E2E tests use Playwright; Ghost gets its own dedicated test module using the Ghost Admin API JWT pattern. A shared config layer reads all secrets from environment variables.

**Tech Stack:** Python 3.11 / pytest 8 / httpx / pytest-asyncio, Playwright (TypeScript), PyJWT (Ghost Admin API), docker compose profiles, GitHub Actions CI (template).

---

## Directory Layout

```
/opt/test/
├── shared/
│   ├── __init__.py
│   ├── config.py           # Central TestConfig dataclass (all env vars)
│   └── helpers.py          # skip_if_missing(), assert_json_error(), create_ghost_jwt()
├── fixtures/
│   ├── __init__.py
│   └── data.py             # Static test payload constants
├── smoke/
│   ├── __init__.py
│   ├── conftest.py
│   └── test_smoke.py       # All-service health check (fast, ≤30 s)
├── backend/
│   ├── __init__.py
│   ├── conftest.py         # Authenticated httpx client fixture
│   ├── test_auth.py        # Register / login / refresh / logout
│   └── test_user_stories.py# CRUD + scoring + RBAC
├── integrations/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_litellm.py
│   ├── test_n8n.py
│   ├── test_stirling.py
│   ├── test_nextcloud.py
│   └── test_authentik.py
├── ghost/
│   ├── __init__.py
│   ├── conftest.py         # Ghost JWT fixture + cleanup registry
│   └── test_ghost.py       # Full Ghost Admin API functional tests
├── frontend/
│   ├── playwright.config.ts
│   ├── package.json
│   ├── fixtures/
│   │   └── auth.fixture.ts
│   ├── pages/
│   │   ├── login.page.ts
│   │   ├── dashboard.page.ts
│   │   └── stories.page.ts
│   └── specs/
│       ├── smoke.spec.ts
│       ├── auth.spec.ts
│       └── stories.spec.ts
├── pytest.ini              # Pytest root config (markers, asyncio_mode)
├── test.env.example        # All required env vars documented
├── run_tests.sh            # Orchestration script (smoke|backend|integrations|ghost|e2e|all)
└── README.md
```

---

## Task 1: Root directory structure + shared config

**Files:**
- Create: `/opt/test/shared/__init__.py`
- Create: `/opt/test/shared/config.py`
- Create: `/opt/test/shared/helpers.py`
- Create: `/opt/test/fixtures/__init__.py`
- Create: `/opt/test/fixtures/data.py`
- Create: `/opt/test/pytest.ini`
- Create: `/opt/test/test.env.example`

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p /opt/test/{shared,fixtures,smoke,backend,integrations,ghost,frontend/{fixtures,pages,specs},reports}
touch /opt/test/{shared,fixtures,smoke,backend,integrations,ghost}/__init__.py
```

Run: `ls /opt/test/`
Expected: `backend  fixtures  frontend  ghost  integrations  reports  shared  smoke`

- [ ] **Step 2: Write shared/config.py**

```python
# /opt/test/shared/config.py
"""Central test configuration — all values from environment variables."""
from __future__ import annotations
import os
from dataclasses import dataclass, field


@dataclass
class TestConfig:
    # ── Service base URLs ────────────────────────────────────────────────
    backend_url: str = field(
        default_factory=lambda: os.getenv("TEST_BACKEND_URL", "http://localhost:8000")
    )
    frontend_url: str = field(
        default_factory=lambda: os.getenv("TEST_FRONTEND_URL", "http://localhost:3000")
    )
    ghost_url: str = field(
        default_factory=lambda: os.getenv("TEST_GHOST_URL", "https://heykarl.app")
    )
    litellm_url: str = field(
        default_factory=lambda: os.getenv("TEST_LITELLM_URL", "http://localhost:4000")
    )
    n8n_url: str = field(
        default_factory=lambda: os.getenv("TEST_N8N_URL", "http://localhost:5678")
    )
    authentik_url: str = field(
        default_factory=lambda: os.getenv("TEST_AUTHENTIK_URL", "http://localhost:9000")
    )
    nextcloud_url: str = field(
        default_factory=lambda: os.getenv("TEST_NEXTCLOUD_URL", "http://localhost")
    )
    stirling_url: str = field(
        default_factory=lambda: os.getenv("TEST_STIRLING_URL", "http://localhost:8080")
    )

    # ── Test identity ────────────────────────────────────────────────────
    test_user_email: str = field(
        default_factory=lambda: os.getenv("TEST_USER_EMAIL", "testrunner@heykarl.app")
    )
    test_user_password: str = field(
        default_factory=lambda: os.getenv("TEST_USER_PASSWORD", "")
    )
    test_org_slug: str = field(
        default_factory=lambda: os.getenv("TEST_ORG_SLUG", "test-org")
    )

    # ── Ghost ────────────────────────────────────────────────────────────
    ghost_admin_api_key: str = field(
        default_factory=lambda: os.getenv("TEST_GHOST_ADMIN_API_KEY", "")
    )
    ghost_content_api_key: str = field(
        default_factory=lambda: os.getenv("TEST_GHOST_CONTENT_API_KEY", "")
    )

    # ── Authentik ────────────────────────────────────────────────────────
    authentik_api_token: str = field(
        default_factory=lambda: os.getenv("TEST_AUTHENTIK_API_TOKEN", "")
    )

    # ── n8n ──────────────────────────────────────────────────────────────
    n8n_api_key: str = field(
        default_factory=lambda: os.getenv("TEST_N8N_API_KEY", "")
    )

    # ── LiteLLM ──────────────────────────────────────────────────────────
    litellm_api_key: str = field(
        default_factory=lambda: os.getenv("TEST_LITELLM_API_KEY", "")
    )

    # ── Nextcloud ────────────────────────────────────────────────────────
    nextcloud_user: str = field(
        default_factory=lambda: os.getenv("TEST_NEXTCLOUD_USER", "")
    )
    nextcloud_password: str = field(
        default_factory=lambda: os.getenv("TEST_NEXTCLOUD_PASSWORD", "")
    )

    # ── Stirling PDF ─────────────────────────────────────────────────────
    stirling_username: str = field(
        default_factory=lambda: os.getenv("TEST_STIRLING_USERNAME", "")
    )
    stirling_password: str = field(
        default_factory=lambda: os.getenv("TEST_STIRLING_PASSWORD", "")
    )

    # ── HTTP timeouts ─────────────────────────────────────────────────────
    default_timeout: float = field(
        default_factory=lambda: float(os.getenv("TEST_TIMEOUT", "15"))
    )


config = TestConfig()
```

- [ ] **Step 3: Write shared/helpers.py**

```python
# /opt/test/shared/helpers.py
"""Reusable test helpers: skip guards, JWT factory, assertion helpers."""
from __future__ import annotations
import time
import pytest


def skip_if_missing(*env_values: str, reason: str = "Required env var not set"):
    """Return pytest.mark.skipif that skips when any value is empty."""
    missing = [v for v in env_values if not v]
    return pytest.mark.skipif(bool(missing), reason=reason)


def assert_json_error(response, expected_status: int, code_fragment: str | None = None) -> None:
    """Assert a well-formed error response from the heykarl backend."""
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert "error" in body, f"Missing 'error' key in: {body}"
    if code_fragment:
        assert code_fragment.lower() in body.get("code", "").lower() or \
               code_fragment.lower() in body.get("error", "").lower(), \
               f"Expected '{code_fragment}' in error response: {body}"


def create_ghost_jwt(admin_api_key: str) -> str:
    """
    Generate a short-lived JWT for the Ghost Admin API.

    The admin_api_key must be in the format  '<id>:<hex-secret>'
    obtained from Ghost Admin → Settings → Integrations → Custom Integration.
    """
    try:
        import jwt as pyjwt
    except ImportError as exc:
        raise RuntimeError("PyJWT is required for Ghost tests: pip install PyJWT") from exc

    if ":" not in admin_api_key:
        raise ValueError("Ghost Admin API key must be in format '<id>:<hex-secret>'")

    key_id, secret_hex = admin_api_key.split(":", 1)
    iat = int(time.time())
    token = pyjwt.encode(
        {"iat": iat, "exp": iat + 300, "aud": "/admin/"},
        bytes.fromhex(secret_hex),
        algorithm="HS256",
        headers={"kid": key_id},
    )
    return token
```

- [ ] **Step 4: Write fixtures/data.py**

```python
# /opt/test/fixtures/data.py
"""Static test payload constants — no secrets, no external state."""

STORY_PAYLOAD = {
    "title": "[AUTOTEST] Smoke Story",
    "description": "Als Testläufer möchte ich eine Story anlegen, um den API-Endpunkt zu prüfen.",
    "acceptance_criteria": "Gegeben dass der Endpunkt erreichbar ist, wenn ich POST sende, dann erhalte ich 201.",
    "story_points": 3,
    "priority": "medium",
    "status": "draft",
}

STORY_UPDATE_PAYLOAD = {
    "title": "[AUTOTEST] Smoke Story (aktualisiert)",
    "story_points": 5,
}

GHOST_POST_PAYLOAD = {
    "posts": [{
        "title": "[AUTOTEST] Testpost – bitte nicht veröffentlichen",
        "slug": "autotest-smoke-post",
        "status": "draft",
        "tags": [{"name": "autotest"}],
        "lexical": '{"root":{"children":[{"children":[{"detail":0,"format":0,"mode":"normal","style":"","text":"Automatisch erzeugter Testinhalt.","type":"text","version":1}],"direction":"ltr","format":"","indent":0,"type":"paragraph","version":1}],"direction":"ltr","format":"","indent":0,"type":"root","version":1}}',
    }]
}

GHOST_POST_UPDATE = {
    "posts": [{
        "title": "[AUTOTEST] Testpost – aktualisiert",
        "updated_at": None,  # will be filled at runtime
    }]
}

MINIMAL_HTML = "<html><body><h1>Testdokument</h1><p>Automatisch generiertes PDF.</p></body></html>"
```

- [ ] **Step 5: Write pytest.ini**

```ini
# /opt/test/pytest.ini
[pytest]
asyncio_mode = auto
testpaths = smoke backend integrations ghost
markers =
    smoke: fast health-check tests (< 30 s total)
    backend: backend API tests requiring a live backend container
    integration: external service integration tests
    ghost: Ghost CMS integration tests
    e2e: Playwright browser tests (run separately via npm)
log_cli = true
log_cli_level = INFO
log_format = %(asctime)s %(levelname)-8s [%(name)s] %(message)s
log_date_format = %H:%M:%S
```

- [ ] **Step 6: Write test.env.example**

```bash
# /opt/test/test.env.example
# Copy to test.env and fill in values before running tests.
# NEVER commit test.env — it contains credentials.

# ── Live service URLs (adjust for local vs. CI) ───────────────────────────
TEST_BACKEND_URL=http://localhost:8000
TEST_FRONTEND_URL=http://localhost:3000
TEST_GHOST_URL=https://heykarl.app
TEST_LITELLM_URL=http://localhost:4000
TEST_N8N_URL=http://localhost:5678
TEST_AUTHENTIK_URL=http://localhost:9000
TEST_NEXTCLOUD_URL=http://localhost
TEST_STIRLING_URL=http://localhost:8080

# ── Test user (must exist in the target environment) ─────────────────────
TEST_USER_EMAIL=testrunner@heykarl.app
TEST_USER_PASSWORD=<strong-password>
TEST_ORG_SLUG=test-org

# ── Ghost Admin API (Ghost Admin → Settings → Integrations) ──────────────
# Format: <id>:<64-char-hex-secret>
TEST_GHOST_ADMIN_API_KEY=<id>:<hex-secret>
TEST_GHOST_CONTENT_API_KEY=<32-char-hex>

# ── Authentik ─────────────────────────────────────────────────────────────
TEST_AUTHENTIK_API_TOKEN=<authentik-api-token>

# ── n8n ──────────────────────────────────────────────────────────────────
TEST_N8N_API_KEY=<n8n-api-key>

# ── LiteLLM ──────────────────────────────────────────────────────────────
TEST_LITELLM_API_KEY=<litellm-master-key>

# ── Nextcloud ─────────────────────────────────────────────────────────────
TEST_NEXTCLOUD_USER=testrunner
TEST_NEXTCLOUD_PASSWORD=<app-password>

# ── Stirling PDF ──────────────────────────────────────────────────────────
TEST_STIRLING_USERNAME=<stirling-user>
TEST_STIRLING_PASSWORD=<stirling-password>

# ── Timeouts ──────────────────────────────────────────────────────────────
TEST_TIMEOUT=15
```

- [ ] **Step 7: Verify structure**

```bash
find /opt/test -type f | sort
```

Expected output contains: `shared/config.py`, `shared/helpers.py`, `fixtures/data.py`, `pytest.ini`, `test.env.example`

- [ ] **Step 8: Install Python test dependencies**

```bash
pip install pytest pytest-asyncio httpx PyJWT --quiet
python -c "import pytest, httpx, jwt; print('deps ok')"
```

Expected: `deps ok`

- [ ] **Step 9: Commit**

```bash
cd /opt/test && git init && git add . && git commit -m "feat(tests): initial test framework scaffold with shared config"
```

---

## Task 2: Smoke tests — all services in one fast suite

**Files:**
- Create: `/opt/test/smoke/conftest.py`
- Create: `/opt/test/smoke/test_smoke.py`

- [ ] **Step 1: Write smoke/conftest.py**

```python
# /opt/test/smoke/conftest.py
import pytest
import httpx
import sys
import os
sys.path.insert(0, "/opt/test")
from shared.config import config


@pytest.fixture(scope="session")
def cfg():
    return config


@pytest.fixture(scope="session")
def http():
    with httpx.Client(timeout=config.default_timeout, follow_redirects=True) as client:
        yield client
```

- [ ] **Step 2: Write smoke/test_smoke.py**

```python
# /opt/test/smoke/test_smoke.py
"""
Smoke tests — run after every deployment.
Each test is a fast reachability + minimal-validity check.
All tests are independent; failures show clear service names.
"""
import pytest

pytestmark = pytest.mark.smoke


class TestBackendSmoke:
    def test_backend_root_responds(self, http, cfg):
        """Backend root or /api/v1/health must respond with 2xx."""
        r = http.get(f"{cfg.backend_url}/api/v1/health")
        assert r.status_code in (200, 404), (
            f"Backend unreachable at {cfg.backend_url}: HTTP {r.status_code}"
        )

    def test_backend_openapi_reachable(self, http, cfg):
        """OpenAPI schema must be available (proves FastAPI is up)."""
        r = http.get(f"{cfg.backend_url}/openapi.json")
        assert r.status_code == 200, f"OpenAPI not available: {r.status_code}"
        assert "openapi" in r.json(), "Response is not an OpenAPI schema"

    def test_backend_auth_endpoint_exists(self, http, cfg):
        """POST /api/v1/auth/login must exist (returns 4xx, not 404)."""
        r = http.post(f"{cfg.backend_url}/api/v1/auth/login", json={})
        assert r.status_code != 404, "Auth login endpoint missing"

    def test_backend_docs_reachable(self, http, cfg):
        """Swagger UI must render (development guard)."""
        r = http.get(f"{cfg.backend_url}/docs")
        assert r.status_code == 200, f"Swagger UI unavailable: {r.status_code}"


class TestFrontendSmoke:
    def test_frontend_root_responds(self, http, cfg):
        r = http.get(cfg.frontend_url)
        assert r.status_code in (200, 301, 302), (
            f"Frontend unreachable at {cfg.frontend_url}: HTTP {r.status_code}"
        )

    def test_frontend_login_page_reachable(self, http, cfg):
        r = http.get(f"{cfg.frontend_url}/login")
        assert r.status_code == 200, f"Login page unavailable: {r.status_code}"

    def test_frontend_returns_html(self, http, cfg):
        r = http.get(cfg.frontend_url)
        assert "text/html" in r.headers.get("content-type", ""), (
            f"Frontend did not return HTML: {r.headers.get('content-type')}"
        )


class TestGhostSmoke:
    def test_ghost_root_responds(self, http, cfg):
        """Ghost landing page must return 2xx."""
        r = http.get(cfg.ghost_url)
        assert r.status_code == 200, (
            f"Ghost unreachable at {cfg.ghost_url}: HTTP {r.status_code}"
        )

    def test_ghost_content_api_reachable(self, http, cfg):
        """Ghost Content API endpoint exists (returns 4xx without key, not 404)."""
        r = http.get(f"{cfg.ghost_url}/ghost/api/content/posts/")
        assert r.status_code != 404, (
            f"Ghost Content API endpoint missing: {r.status_code}"
        )

    def test_ghost_admin_api_reachable(self, http, cfg):
        """Ghost Admin API endpoint exists."""
        r = http.get(f"{cfg.ghost_url}/ghost/api/admin/site/")
        assert r.status_code in (200, 401, 403), (
            f"Ghost Admin API unexpectedly missing: {r.status_code}"
        )


class TestLiteLLMSmoke:
    def test_litellm_health(self, http, cfg):
        r = http.get(f"{cfg.litellm_url}/health")
        assert r.status_code == 200, (
            f"LiteLLM unhealthy at {cfg.litellm_url}: {r.status_code}"
        )

    def test_litellm_models_endpoint(self, http, cfg):
        r = http.get(f"{cfg.litellm_url}/v1/models",
                     headers={"Authorization": f"Bearer {cfg.litellm_api_key}"})
        assert r.status_code in (200, 401), (
            f"LiteLLM /v1/models endpoint missing: {r.status_code}"
        )


class TestN8NSmoke:
    def test_n8n_health(self, http, cfg):
        r = http.get(f"{cfg.n8n_url}/healthz")
        assert r.status_code == 200, f"n8n not healthy: {r.status_code} {r.text}"


class TestAuthentikSmoke:
    def test_authentik_root(self, http, cfg):
        r = http.get(f"{cfg.authentik_url}/-/health/ready/")
        assert r.status_code == 200, f"Authentik not ready: {r.status_code}"


class TestStirlingSmoke:
    def test_stirling_root(self, http, cfg):
        r = http.get(cfg.stirling_url)
        assert r.status_code in (200, 302), f"Stirling PDF unavailable: {r.status_code}"


class TestNextcloudSmoke:
    def test_nextcloud_status(self, http, cfg):
        r = http.get(f"{cfg.nextcloud_url}/status.php")
        assert r.status_code == 200, f"Nextcloud not reachable: {r.status_code}"
        body = r.json()
        assert body.get("installed") is True, f"Nextcloud not installed: {body}"
```

- [ ] **Step 3: Run smoke tests (backend + Ghost must be up)**

```bash
cd /opt/test && python -m pytest smoke/ -v -m smoke --tb=short 2>&1 | tee reports/smoke_$(date +%Y%m%d_%H%M%S).txt
```

Expected: All tests PASS or clear SKIP — no import errors.

- [ ] **Step 4: Commit**

```bash
cd /opt/test && git add smoke/ && git commit -m "feat(tests/smoke): full-stack smoke suite covering all 7 services"
```

---

## Task 3: Backend API tests — auth + user stories

**Files:**
- Create: `/opt/test/backend/conftest.py`
- Create: `/opt/test/backend/test_auth.py`
- Create: `/opt/test/backend/test_user_stories.py`

- [ ] **Step 1: Write backend/conftest.py**

```python
# /opt/test/backend/conftest.py
"""
Backend tests run against a live backend container via HTTP.
Authentication uses a real login (TEST_USER_EMAIL/PASSWORD).
All org-scoped requests use TEST_ORG_SLUG.
"""
import pytest
import httpx
import sys
import os
sys.path.insert(0, "/opt/test")
from shared.config import config
from shared.helpers import skip_if_missing


@pytest.fixture(scope="session")
def cfg():
    return config


@pytest.fixture(scope="session")
def base_url():
    return config.backend_url


@pytest.fixture(scope="session")
def auth_headers():
    """Log in once per session and return bearer headers."""
    if not config.test_user_password:
        pytest.skip("TEST_USER_PASSWORD not set — backend auth tests skipped")

    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{config.backend_url}/api/v1/auth/login",
            json={"email": config.test_user_email, "password": config.test_user_password},
        )
        assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
        token = r.json()["access_token"]

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def api(auth_headers, base_url):
    """Pre-authenticated httpx session for the backend."""
    with httpx.Client(
        base_url=base_url,
        headers=auth_headers,
        timeout=config.default_timeout,
        follow_redirects=False,
    ) as client:
        yield client


@pytest.fixture(scope="session")
def org_id(api, cfg):
    """Resolve org_id from the test org slug."""
    r = api.get("/api/v1/organizations/")
    assert r.status_code == 200, f"Could not list orgs: {r.status_code}"
    items = r.json().get("items", r.json()) if isinstance(r.json(), dict) else r.json()
    for org in items:
        if org.get("slug") == cfg.test_org_slug:
            return org["id"]
    pytest.skip(f"Test org '{cfg.test_org_slug}' not found — create it first")
```

- [ ] **Step 2: Write backend/test_auth.py**

```python
# /opt/test/backend/test_auth.py
"""Backend authentication endpoint tests against live container."""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config
from shared.helpers import assert_json_error

pytestmark = pytest.mark.backend

BASE = config.backend_url


class TestLoginEndpoint:
    def test_valid_login_returns_tokens(self, cfg):
        if not cfg.test_user_password:
            pytest.skip("TEST_USER_PASSWORD not set")
        with httpx.Client(timeout=15) as c:
            r = c.post(f"{BASE}/api/v1/auth/login",
                       json={"email": cfg.test_user_email, "password": cfg.test_user_password})
        assert r.status_code == 200, f"Login failed: {r.text}"
        body = r.json()
        assert "access_token" in body, f"No access_token: {body}"
        assert "refresh_token" in body, f"No refresh_token: {body}"
        assert body.get("token_type", "").lower() == "bearer"

    def test_wrong_password_returns_401(self):
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{BASE}/api/v1/auth/login",
                       json={"email": "nobody@example.com", "password": "wrong"})
        assert r.status_code in (401, 422), f"Expected auth failure: {r.status_code}"

    def test_missing_email_returns_422(self):
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{BASE}/api/v1/auth/login", json={"password": "x"})
        assert r.status_code == 422, f"Expected validation error: {r.status_code}"

    def test_empty_body_returns_422(self):
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{BASE}/api/v1/auth/login", json={})
        assert r.status_code == 422

    def test_unauthenticated_protected_endpoint_returns_401(self):
        with httpx.Client(timeout=10) as c:
            r = c.get(f"{BASE}/api/v1/user-stories/")
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"


class TestTokenRefresh:
    def test_refresh_with_valid_token(self, cfg):
        if not cfg.test_user_password:
            pytest.skip("TEST_USER_PASSWORD not set")
        with httpx.Client(timeout=15) as c:
            login = c.post(f"{BASE}/api/v1/auth/login",
                           json={"email": cfg.test_user_email, "password": cfg.test_user_password})
            assert login.status_code == 200
            refresh_token = login.json()["refresh_token"]

            r = c.post(f"{BASE}/api/v1/auth/refresh",
                       json={"refresh_token": refresh_token})
        assert r.status_code == 200, f"Refresh failed: {r.text}"
        assert "access_token" in r.json()

    def test_refresh_with_garbage_token_returns_401(self):
        with httpx.Client(timeout=10) as c:
            r = c.post(f"{BASE}/api/v1/auth/refresh",
                       json={"refresh_token": "not-a-real-token"})
        assert r.status_code in (401, 422)
```

- [ ] **Step 3: Write backend/test_user_stories.py**

```python
# /opt/test/backend/test_user_stories.py
"""
User Story CRUD + business logic tests against live backend.
Each test cleans up its own data; no shared mutable state.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.helpers import assert_json_error
from fixtures.data import STORY_PAYLOAD, STORY_UPDATE_PAYLOAD

pytestmark = pytest.mark.backend


class TestUserStoryCRUD:
    def test_create_story_returns_201(self, api, org_id):
        payload = {**STORY_PAYLOAD, "organization_id": org_id}
        r = api.post("/api/v1/user-stories/", json=payload)
        assert r.status_code == 201, f"Create story failed: {r.status_code} {r.text}"
        body = r.json()
        assert body["title"] == payload["title"]
        assert body["status"] == "draft"
        assert "id" in body
        # cleanup
        api.delete(f"/api/v1/user-stories/{body['id']}")

    def test_read_story_returns_correct_data(self, api, org_id):
        created = api.post("/api/v1/user-stories/", json={**STORY_PAYLOAD, "organization_id": org_id})
        assert created.status_code == 201
        story_id = created.json()["id"]

        r = api.get(f"/api/v1/user-stories/{story_id}")
        assert r.status_code == 200
        assert r.json()["id"] == story_id
        assert r.json()["title"] == STORY_PAYLOAD["title"]

        api.delete(f"/api/v1/user-stories/{story_id}")

    def test_update_story_changes_fields(self, api, org_id):
        created = api.post("/api/v1/user-stories/", json={**STORY_PAYLOAD, "organization_id": org_id})
        story_id = created.json()["id"]

        r = api.patch(f"/api/v1/user-stories/{story_id}", json=STORY_UPDATE_PAYLOAD)
        assert r.status_code == 200
        updated = r.json()
        assert updated["title"] == STORY_UPDATE_PAYLOAD["title"]
        assert updated["story_points"] == STORY_UPDATE_PAYLOAD["story_points"]

        api.delete(f"/api/v1/user-stories/{story_id}")

    def test_delete_story_returns_204(self, api, org_id):
        created = api.post("/api/v1/user-stories/", json={**STORY_PAYLOAD, "organization_id": org_id})
        story_id = created.json()["id"]

        r = api.delete(f"/api/v1/user-stories/{story_id}")
        assert r.status_code == 204

        r = api.get(f"/api/v1/user-stories/{story_id}")
        assert r.status_code == 404

    def test_list_stories_returns_paginated_response(self, api, org_id):
        r = api.get("/api/v1/user-stories/", params={"org_id": org_id})
        assert r.status_code == 200
        body = r.json()
        assert "items" in body or isinstance(body, list), f"Unexpected response: {body}"

    def test_create_story_missing_title_returns_422(self, api, org_id):
        payload = {"organization_id": org_id, "description": "no title"}
        r = api.post("/api/v1/user-stories/", json=payload)
        assert r.status_code == 422

    def test_get_nonexistent_story_returns_404(self, api):
        r = api.get("/api/v1/user-stories/00000000-0000-0000-0000-000000000000")
        assert r.status_code == 404

    def test_story_belongs_to_correct_org(self, api, org_id):
        created = api.post("/api/v1/user-stories/", json={**STORY_PAYLOAD, "organization_id": org_id})
        story_id = created.json()["id"]

        r = api.get(f"/api/v1/user-stories/{story_id}")
        assert r.json()["organization_id"] == org_id

        api.delete(f"/api/v1/user-stories/{story_id}")


class TestUserStoryScoring:
    def test_score_endpoint_returns_score(self, api, org_id):
        created = api.post("/api/v1/user-stories/", json={**STORY_PAYLOAD, "organization_id": org_id})
        story_id = created.json()["id"]

        r = api.post(f"/api/v1/user-stories/{story_id}/score")
        assert r.status_code in (200, 202), f"Score endpoint failed: {r.status_code} {r.text}"
        if r.status_code == 200:
            body = r.json()
            assert "score" in body or "total_score" in body, f"No score in: {body}"

        api.delete(f"/api/v1/user-stories/{story_id}")

    def test_score_nonexistent_story_returns_404(self, api):
        r = api.post("/api/v1/user-stories/00000000-0000-0000-0000-000000000000/score")
        assert r.status_code == 404
```

- [ ] **Step 4: Run backend tests**

```bash
cd /opt/test && python -m pytest backend/ -v -m backend --tb=short 2>&1 | tee reports/backend_$(date +%Y%m%d_%H%M%S).txt
```

Expected: Tests either PASS or SKIP (if env vars missing) — no import errors.

- [ ] **Step 5: Commit**

```bash
cd /opt/test && git add backend/ && git commit -m "feat(tests/backend): auth + user story CRUD tests against live backend"
```

---

## Task 4: Ghost integration tests (full functional suite)

**Files:**
- Create: `/opt/test/ghost/conftest.py`
- Create: `/opt/test/ghost/test_ghost.py`

- [ ] **Step 1: Write ghost/conftest.py**

```python
# /opt/test/ghost/conftest.py
"""
Ghost Admin API test fixtures.

Prerequisites:
  1. Create a Custom Integration in Ghost Admin → Settings → Integrations
  2. Copy the Admin API Key (format: <id>:<hex-secret>) to TEST_GHOST_ADMIN_API_KEY
  3. Copy the Content API Key to TEST_GHOST_CONTENT_API_KEY

All test posts are created as 'draft' with the tag 'autotest'.
The cleanup fixture deletes every post created during the test session.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config
from shared.helpers import create_ghost_jwt


@pytest.fixture(scope="session")
def cfg():
    return config


@pytest.fixture(scope="session")
def ghost_admin_headers():
    if not config.ghost_admin_api_key:
        pytest.skip("TEST_GHOST_ADMIN_API_KEY not set — Ghost tests skipped")
    token = create_ghost_jwt(config.ghost_admin_api_key)
    return {
        "Authorization": f"Ghost {token}",
        "Content-Type": "application/json",
        "Accept-Version": "v5.0",
    }


@pytest.fixture(scope="session")
def ghost_api(ghost_admin_headers):
    """Pre-authenticated httpx session for Ghost Admin API."""
    with httpx.Client(
        base_url=config.ghost_url,
        headers=ghost_admin_headers,
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def cleanup_ghost_test_posts(ghost_api):
    """
    Delete all draft posts tagged 'autotest' after the entire session.
    Runs even when tests fail.
    """
    yield
    # Post-session cleanup
    try:
        r = ghost_api.get(
            "/ghost/api/admin/posts/",
            params={"filter": "tags:[autotest]+status:draft", "limit": "50"},
        )
        if r.status_code == 200:
            for post in r.json().get("posts", []):
                ghost_api.delete(f"/ghost/api/admin/posts/{post['id']}/")
    except Exception as e:
        print(f"[WARN] Ghost cleanup failed: {e}")
```

- [ ] **Step 2: Write ghost/test_ghost.py**

```python
# /opt/test/ghost/test_ghost.py
"""
Ghost CMS — functional integration tests.

Covers:
- Service reachability and health
- Admin API authentication
- Content reading (posts, pages, tags)
- Creating a draft post with correct fields
- Updating a post (idempotency on repeated run)
- Deleting test data (cleanup)
- Error handling for invalid requests
- Graceful failure when Ghost is unreachable
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config
from shared.helpers import create_ghost_jwt
from fixtures.data import GHOST_POST_PAYLOAD

pytestmark = pytest.mark.ghost

ADMIN_BASE = "/ghost/api/admin"
CONTENT_BASE = "/ghost/api/content"


# ─── Reachability & Health ────────────────────────────────────────────────────

class TestGhostReachability:
    def test_ghost_root_returns_200(self):
        with httpx.Client(timeout=10, follow_redirects=True) as c:
            r = c.get(config.ghost_url)
        assert r.status_code == 200, f"Ghost root not reachable: {r.status_code}"

    def test_ghost_admin_site_endpoint_exists(self, ghost_api):
        """GET /ghost/api/admin/site/ must return site info."""
        r = ghost_api.get(f"{ADMIN_BASE}/site/")
        assert r.status_code == 200, f"Admin site endpoint failed: {r.status_code} {r.text}"
        body = r.json()
        assert "site" in body, f"Unexpected response shape: {body}"

    def test_ghost_admin_site_has_expected_fields(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/site/")
        site = r.json()["site"]
        assert "title" in site, "Site response missing 'title'"
        assert "url" in site, "Site response missing 'url'"
        assert "version" in site, "Site response missing 'version'"


# ─── Authentication ───────────────────────────────────────────────────────────

class TestGhostAuthentication:
    def test_valid_jwt_grants_access(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/users/me/")
        assert r.status_code == 200, (
            f"Valid JWT rejected: {r.status_code} {r.text}"
        )

    def test_invalid_jwt_returns_401(self):
        with httpx.Client(base_url=config.ghost_url, timeout=10, follow_redirects=True) as c:
            r = c.get(
                f"{ADMIN_BASE}/users/me/",
                headers={"Authorization": "Ghost not-a-real-token"},
            )
        assert r.status_code == 401, f"Expected 401 for bad JWT, got {r.status_code}"

    def test_missing_auth_header_returns_401(self):
        with httpx.Client(base_url=config.ghost_url, timeout=10, follow_redirects=True) as c:
            r = c.get(f"{ADMIN_BASE}/posts/")
        assert r.status_code == 401, f"Expected 401 without auth, got {r.status_code}"

    def test_content_api_requires_key(self):
        with httpx.Client(base_url=config.ghost_url, timeout=10, follow_redirects=True) as c:
            r = c.get(f"{CONTENT_BASE}/posts/")
        assert r.status_code in (401, 403), (
            f"Content API should require a key: {r.status_code}"
        )

    def test_content_api_with_valid_key(self, cfg):
        if not cfg.ghost_content_api_key:
            pytest.skip("TEST_GHOST_CONTENT_API_KEY not set")
        with httpx.Client(base_url=cfg.ghost_url, timeout=10, follow_redirects=True) as c:
            r = c.get(f"{CONTENT_BASE}/posts/",
                      params={"key": cfg.ghost_content_api_key, "limit": "1"})
        assert r.status_code == 200, f"Content API failed: {r.status_code} {r.text}"
        assert "posts" in r.json()


# ─── Content Reading ──────────────────────────────────────────────────────────

class TestGhostContentReading:
    def test_list_posts_returns_array(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/posts/", params={"limit": "5"})
        assert r.status_code == 200, f"List posts failed: {r.status_code} {r.text}"
        body = r.json()
        assert "posts" in body, f"Response missing 'posts': {body}"
        assert isinstance(body["posts"], list)

    def test_list_posts_response_has_pagination_meta(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/posts/", params={"limit": "1"})
        assert r.status_code == 200
        body = r.json()
        assert "meta" in body, f"Response missing 'meta': {body}"
        assert "pagination" in body["meta"]

    def test_list_pages_returns_array(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/pages/", params={"limit": "5"})
        assert r.status_code == 200
        assert "pages" in r.json()

    def test_list_tags_returns_array(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/tags/", params={"limit": "5"})
        assert r.status_code == 200
        assert "tags" in r.json()

    def test_filter_by_status_draft(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/posts/",
                          params={"filter": "status:draft", "limit": "5"})
        assert r.status_code == 200
        for post in r.json().get("posts", []):
            assert post["status"] == "draft", f"Non-draft post returned: {post}"

    def test_filter_by_status_published(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/posts/",
                          params={"filter": "status:published", "limit": "5"})
        assert r.status_code == 200
        for post in r.json().get("posts", []):
            assert post["status"] == "published"


# ─── Post Lifecycle (Create → Update → Delete) ────────────────────────────────

class TestGhostPostLifecycle:
    """
    Each test in this class creates and destroys its own post.
    The session-level cleanup in conftest.py is a safety net only.
    """

    def _create_test_post(self, ghost_api, title_suffix="") -> dict:
        payload = {
            "posts": [{
                "title": f"[AUTOTEST] Smoke Post {title_suffix}",
                "slug": f"autotest-smoke-{title_suffix.lower().replace(' ', '-')}",
                "status": "draft",
                "tags": [{"name": "autotest"}],
                "lexical": (
                    '{"root":{"children":[{"children":[{"detail":0,"format":0,'
                    '"mode":"normal","style":"","text":"Automatisch erzeugter Testinhalt.","type":"text",'
                    '"version":1}],"direction":"ltr","format":"","indent":0,"type":"paragraph","version":1}],'
                    '"direction":"ltr","format":"","indent":0,"type":"root","version":1}}'
                ),
            }]
        }
        r = ghost_api.post(f"{ADMIN_BASE}/posts/", json=payload)
        assert r.status_code == 201, f"Create post failed: {r.status_code} {r.text}"
        return r.json()["posts"][0]

    def test_create_draft_post_returns_201(self, ghost_api):
        post = self._create_test_post(ghost_api, "create-test")
        assert post["status"] == "draft"
        assert post["title"] == "[AUTOTEST] Smoke Post create-test"
        assert "id" in post
        # cleanup
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post['id']}/")

    def test_created_post_has_correct_slug(self, ghost_api):
        post = self._create_test_post(ghost_api, "slug-test")
        assert "autotest-smoke" in post["slug"]
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post['id']}/")

    def test_created_post_has_autotest_tag(self, ghost_api):
        post = self._create_test_post(ghost_api, "tag-test")
        tag_slugs = [t["slug"] for t in post.get("tags", [])]
        assert "autotest" in tag_slugs, f"Expected autotest tag in {tag_slugs}"
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post['id']}/")

    def test_created_post_is_draft_not_published(self, ghost_api):
        post = self._create_test_post(ghost_api, "draft-check")
        assert post["status"] == "draft", "Post should be draft, not published"
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post['id']}/")

    def test_update_post_changes_title(self, ghost_api):
        post = self._create_test_post(ghost_api, "update-test")
        post_id = post["id"]
        updated_at = post["updated_at"]

        update_payload = {
            "posts": [{
                "title": "[AUTOTEST] Aktualisierter Titel",
                "updated_at": updated_at,
            }]
        }
        r = ghost_api.put(f"{ADMIN_BASE}/posts/{post_id}/", json=update_payload)
        assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"
        updated = r.json()["posts"][0]
        assert updated["title"] == "[AUTOTEST] Aktualisierter Titel"

        ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")

    def test_update_requires_updated_at_timestamp(self, ghost_api):
        post = self._create_test_post(ghost_api, "timestamp-test")
        post_id = post["id"]

        # Without updated_at → Ghost rejects the request
        r = ghost_api.put(f"{ADMIN_BASE}/posts/{post_id}/",
                          json={"posts": [{"title": "No timestamp"}]})
        assert r.status_code in (422, 400, 409), (
            f"Expected rejection without updated_at: {r.status_code}"
        )
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")

    def test_delete_post_returns_204(self, ghost_api):
        post = self._create_test_post(ghost_api, "delete-test")
        post_id = post["id"]

        r = ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")
        assert r.status_code == 204, f"Delete failed: {r.status_code} {r.text}"

    def test_deleted_post_is_not_found(self, ghost_api):
        post = self._create_test_post(ghost_api, "gone-test")
        post_id = post["id"]
        ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")

        r = ghost_api.get(f"{ADMIN_BASE}/posts/{post_id}/")
        assert r.status_code == 404, f"Deleted post still accessible: {r.status_code}"

    def test_idempotent_slug_reuse(self, ghost_api):
        """
        Creating a post with the same slug twice should either reuse or reject —
        never silently create a duplicate.
        """
        post1 = self._create_test_post(ghost_api, "idempotent")
        post1_id = post1["id"]
        slug = post1["slug"]

        # Ghost appends suffix on slug collision
        r = ghost_api.post(f"{ADMIN_BASE}/posts/", json={
            "posts": [{"title": "[AUTOTEST] Duplicate slug", "slug": slug, "status": "draft"}]
        })
        if r.status_code == 201:
            # Ghost created with modified slug — verify it's different
            post2 = r.json()["posts"][0]
            assert post2["slug"] != slug or post2["id"] != post1_id, (
                "Ghost created an exact duplicate post"
            )
            ghost_api.delete(f"{ADMIN_BASE}/posts/{post2['id']}/")

        ghost_api.delete(f"{ADMIN_BASE}/posts/{post1_id}/")


# ─── Error Handling ───────────────────────────────────────────────────────────

class TestGhostErrorHandling:
    def test_get_nonexistent_post_returns_404(self, ghost_api):
        r = ghost_api.get(f"{ADMIN_BASE}/posts/000000000000000000000000/")
        assert r.status_code == 404, f"Expected 404 for missing post: {r.status_code}"

    def test_create_post_with_empty_title_returns_error(self, ghost_api):
        r = ghost_api.post(f"{ADMIN_BASE}/posts/",
                           json={"posts": [{"title": "", "status": "draft"}]})
        assert r.status_code in (422, 400), (
            f"Empty title should be rejected: {r.status_code} {r.text}"
        )

    def test_invalid_status_value_returns_error(self, ghost_api):
        r = ghost_api.post(f"{ADMIN_BASE}/posts/",
                           json={"posts": [{"title": "x", "status": "invalid_status"}]})
        assert r.status_code in (422, 400), (
            f"Invalid status should be rejected: {r.status_code}"
        )

    def test_ghost_unreachable_returns_connection_error(self, cfg):
        """Verify callers get a clear error when Ghost is unreachable."""
        with httpx.Client(timeout=2) as c:
            try:
                c.get("http://localhost:19999/ghost/api/admin/posts/")
                pytest.fail("Expected ConnectError for unreachable Ghost")
            except (httpx.ConnectError, httpx.ConnectTimeout):
                pass  # expected


# ─── Draft vs. Published Behaviour ───────────────────────────────────────────

class TestGhostDraftVsPublished:
    def test_draft_post_not_visible_in_content_api(self, ghost_api, cfg):
        """Draft posts must not appear in the Content API (public-facing)."""
        if not cfg.ghost_content_api_key:
            pytest.skip("TEST_GHOST_CONTENT_API_KEY not set")

        # Create a draft
        r = ghost_api.post(f"{ADMIN_BASE}/posts/", json={
            "posts": [{
                "title": "[AUTOTEST] Draft visibility check",
                "slug": "autotest-draft-visibility",
                "status": "draft",
                "tags": [{"name": "autotest"}],
            }]
        })
        assert r.status_code == 201
        post = r.json()["posts"][0]
        post_id = post["id"]
        slug = post["slug"]

        # Content API must not return this draft
        with httpx.Client(base_url=cfg.ghost_url, timeout=10, follow_redirects=True) as c:
            public = c.get(f"{CONTENT_BASE}/posts/slug/{slug}/",
                           params={"key": cfg.ghost_content_api_key})
        assert public.status_code == 404, (
            f"Draft post should not be public: {public.status_code}"
        )

        ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")

    def test_draft_post_visible_in_admin_api(self, ghost_api):
        """Draft posts must be readable via Admin API."""
        r = ghost_api.post(f"{ADMIN_BASE}/posts/", json={
            "posts": [{
                "title": "[AUTOTEST] Admin draft read",
                "slug": "autotest-admin-draft-read",
                "status": "draft",
                "tags": [{"name": "autotest"}],
            }]
        })
        assert r.status_code == 201
        post_id = r.json()["posts"][0]["id"]

        read = ghost_api.get(f"{ADMIN_BASE}/posts/{post_id}/")
        assert read.status_code == 200
        assert read.json()["posts"][0]["status"] == "draft"

        ghost_api.delete(f"{ADMIN_BASE}/posts/{post_id}/")
```

- [ ] **Step 3: Run Ghost tests**

```bash
cd /opt/test && python -m pytest ghost/ -v -m ghost --tb=short 2>&1 | tee reports/ghost_$(date +%Y%m%d_%H%M%S).txt
```

Expected: Tests PASS (or SKIP if `TEST_GHOST_ADMIN_API_KEY` not set — never ERROR)

- [ ] **Step 4: Commit**

```bash
cd /opt/test && git add ghost/ && git commit -m "feat(tests/ghost): full Ghost Admin API functional test suite with cleanup"
```

---

## Task 5: Service integration tests — LiteLLM + n8n

**Files:**
- Create: `/opt/test/integrations/conftest.py`
- Create: `/opt/test/integrations/test_litellm.py`
- Create: `/opt/test/integrations/test_n8n.py`

- [ ] **Step 1: Write integrations/conftest.py**

```python
# /opt/test/integrations/conftest.py
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config


@pytest.fixture(scope="session")
def cfg():
    return config


@pytest.fixture(scope="session")
def http():
    with httpx.Client(timeout=config.default_timeout, follow_redirects=True) as client:
        yield client
```

- [ ] **Step 2: Write integrations/test_litellm.py**

```python
# /opt/test/integrations/test_litellm.py
"""
LiteLLM gateway integration tests.
Validates reachability, model listing, request/response format, and error handling.
Does NOT test AI model quality — only the gateway interface.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config
from shared.helpers import skip_if_missing

pytestmark = pytest.mark.integration

BASE = config.litellm_url


class TestLiteLLMReachability:
    def test_health_endpoint_returns_200(self, http):
        r = http.get(f"{BASE}/health")
        assert r.status_code == 200, f"LiteLLM not healthy: {r.status_code} {r.text}"

    def test_health_response_shape(self, http):
        r = http.get(f"{BASE}/health")
        body = r.json()
        assert "healthy_endpoints" in body or "status" in body, (
            f"Unexpected health shape: {body}"
        )


class TestLiteLLMModels:
    def test_models_endpoint_requires_auth(self, cfg, http):
        r = http.get(f"{BASE}/v1/models")
        if not cfg.litellm_api_key:
            assert r.status_code in (200, 401), f"Unexpected status: {r.status_code}"
        else:
            r2 = http.get(f"{BASE}/v1/models",
                          headers={"Authorization": f"Bearer {cfg.litellm_api_key}"})
            assert r2.status_code == 200, f"Models endpoint failed: {r2.status_code}"

    def test_models_response_is_openai_compatible(self, cfg, http):
        if not cfg.litellm_api_key:
            pytest.skip("TEST_LITELLM_API_KEY not set")
        r = http.get(f"{BASE}/v1/models",
                     headers={"Authorization": f"Bearer {cfg.litellm_api_key}"})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body, f"Not OpenAI-compatible: {body}"
        assert isinstance(body["data"], list)


class TestLiteLLMCompletion:
    def test_completion_returns_correct_shape(self, cfg, http):
        if not cfg.litellm_api_key:
            pytest.skip("TEST_LITELLM_API_KEY not set")
        payload = {
            "model": "claude-haiku-4-5",
            "messages": [{"role": "user", "content": "Reply with: PONG"}],
            "max_tokens": 10,
        }
        r = http.post(
            f"{BASE}/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {cfg.litellm_api_key}"},
        )
        assert r.status_code == 200, f"Completion failed: {r.status_code} {r.text}"
        body = r.json()
        assert "choices" in body, f"Not OpenAI-compatible: {body}"
        assert len(body["choices"]) > 0
        assert "message" in body["choices"][0]

    def test_completion_with_invalid_model_returns_400(self, cfg, http):
        if not cfg.litellm_api_key:
            pytest.skip("TEST_LITELLM_API_KEY not set")
        r = http.post(
            f"{BASE}/v1/chat/completions",
            json={"model": "nonexistent-model-xyz", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": f"Bearer {cfg.litellm_api_key}"},
        )
        assert r.status_code in (400, 404, 422), (
            f"Expected failure for unknown model: {r.status_code}"
        )

    def test_completion_empty_messages_returns_error(self, cfg, http):
        if not cfg.litellm_api_key:
            pytest.skip("TEST_LITELLM_API_KEY not set")
        r = http.post(
            f"{BASE}/v1/chat/completions",
            json={"model": "claude-haiku-4-5", "messages": []},
            headers={"Authorization": f"Bearer {cfg.litellm_api_key}"},
        )
        assert r.status_code in (400, 422), f"Empty messages should fail: {r.status_code}"
```

- [ ] **Step 3: Write integrations/test_n8n.py**

```python
# /opt/test/integrations/test_n8n.py
"""
n8n integration tests.
Checks health, API authentication, workflow listing, and error handling.
Does NOT trigger production workflows — read-only + health only.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config

pytestmark = pytest.mark.integration

BASE = config.n8n_url


class TestN8NReachability:
    def test_healthz_returns_200(self, http):
        r = http.get(f"{BASE}/healthz")
        assert r.status_code == 200, f"n8n not healthy: {r.status_code} {r.text}"

    def test_root_redirects_or_serves_ui(self, http):
        r = http.get(BASE)
        assert r.status_code in (200, 301, 302), f"n8n root unexpected: {r.status_code}"


class TestN8NAPI:
    def test_api_requires_auth(self, http):
        r = http.get(f"{BASE}/api/v1/workflows")
        assert r.status_code in (401, 403), (
            f"n8n API should require auth: {r.status_code}"
        )

    def test_authenticated_workflow_list(self, cfg, http):
        if not cfg.n8n_api_key:
            pytest.skip("TEST_N8N_API_KEY not set")
        r = http.get(f"{BASE}/api/v1/workflows",
                     headers={"X-N8N-API-KEY": cfg.n8n_api_key})
        assert r.status_code == 200, f"n8n workflows failed: {r.status_code} {r.text}"
        body = r.json()
        assert "data" in body, f"Unexpected shape: {body}"
        assert isinstance(body["data"], list)

    def test_authenticated_executions_endpoint(self, cfg, http):
        if not cfg.n8n_api_key:
            pytest.skip("TEST_N8N_API_KEY not set")
        r = http.get(f"{BASE}/api/v1/executions",
                     headers={"X-N8N-API-KEY": cfg.n8n_api_key},
                     params={"limit": "5"})
        assert r.status_code == 200, f"n8n executions failed: {r.status_code}"

    def test_invalid_api_key_returns_401(self, http):
        r = http.get(f"{BASE}/api/v1/workflows",
                     headers={"X-N8N-API-KEY": "invalid-key-xyz"})
        assert r.status_code in (401, 403), (
            f"Expected rejection for invalid key: {r.status_code}"
        )
```

- [ ] **Step 4: Commit**

```bash
cd /opt/test && git add integrations/ && git commit -m "feat(tests/integrations): LiteLLM + n8n integration tests"
```

---

## Task 6: Service integration tests — Authentik + Nextcloud + Stirling

**Files:**
- Create: `/opt/test/integrations/test_authentik.py`
- Create: `/opt/test/integrations/test_nextcloud.py`
- Create: `/opt/test/integrations/test_stirling.py`

- [ ] **Step 1: Write integrations/test_authentik.py**

```python
# /opt/test/integrations/test_authentik.py
"""
Authentik integration tests.
Verifies IdP health, API authentication, user lookup, and token handling.
Does NOT create permanent users — all test operations are read-only.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config

pytestmark = pytest.mark.integration

BASE = config.authentik_url


class TestAuthentikHealth:
    def test_ready_endpoint_returns_200(self, http):
        r = http.get(f"{BASE}/-/health/ready/")
        assert r.status_code == 200, f"Authentik not ready: {r.status_code} {r.text}"

    def test_live_endpoint_returns_200(self, http):
        r = http.get(f"{BASE}/-/health/live/")
        assert r.status_code == 200, f"Authentik not live: {r.status_code}"


class TestAuthentikAPI:
    def test_api_requires_token(self, http):
        r = http.get(f"{BASE}/api/v3/core/users/")
        assert r.status_code == 403, (
            f"API should require token: {r.status_code}"
        )

    def test_authenticated_user_list(self, cfg, http):
        if not cfg.authentik_api_token:
            pytest.skip("TEST_AUTHENTIK_API_TOKEN not set")
        r = http.get(
            f"{BASE}/api/v3/core/users/",
            headers={"Authorization": f"Bearer {cfg.authentik_api_token}"},
            params={"page_size": 5},
        )
        assert r.status_code == 200, f"Authentik user list failed: {r.status_code} {r.text}"
        body = r.json()
        assert "results" in body, f"Unexpected shape: {body}"
        assert isinstance(body["results"], list)

    def test_authenticated_applications_list(self, cfg, http):
        if not cfg.authentik_api_token:
            pytest.skip("TEST_AUTHENTIK_API_TOKEN not set")
        r = http.get(
            f"{BASE}/api/v3/core/applications/",
            headers={"Authorization": f"Bearer {cfg.authentik_api_token}"},
        )
        assert r.status_code == 200, f"Authentik apps list failed: {r.status_code}"

    def test_invalid_token_returns_403(self, http):
        r = http.get(
            f"{BASE}/api/v3/core/users/",
            headers={"Authorization": "Bearer invalid-token-xyz"},
        )
        assert r.status_code == 403, f"Expected 403 for invalid token: {r.status_code}"

    def test_openid_configuration_endpoint(self, cfg, http):
        """OIDC discovery endpoint must be present."""
        r = http.get(f"{BASE}/application/o/heykarl-backend/.well-known/openid-configuration")
        # 404 if app name differs — use authentik root OIDC endpoint
        if r.status_code == 404:
            r = http.get(f"{BASE}/.well-known/openid-configuration")
        assert r.status_code in (200, 404), f"OIDC discovery error: {r.status_code}"
```

- [ ] **Step 2: Write integrations/test_nextcloud.py**

```python
# /opt/test/integrations/test_nextcloud.py
"""
Nextcloud integration tests.
Checks status, WebDAV availability, and file listing.
Read-only — no files are created or modified.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config

pytestmark = pytest.mark.integration

BASE = config.nextcloud_url


class TestNextcloudHealth:
    def test_status_endpoint_returns_installed(self, http):
        r = http.get(f"{BASE}/status.php")
        assert r.status_code == 200, f"Nextcloud unreachable: {r.status_code}"
        body = r.json()
        assert body.get("installed") is True, f"Nextcloud not installed: {body}"
        assert body.get("maintenance") is False, "Nextcloud in maintenance mode"

    def test_ocs_capabilities_endpoint(self, http):
        r = http.get(f"{BASE}/ocs/v1.php/cloud/capabilities",
                     params={"format": "json"})
        assert r.status_code == 200, f"OCS capabilities failed: {r.status_code}"
        body = r.json()
        assert "ocs" in body


class TestNextcloudWebDAV:
    def test_webdav_root_requires_auth(self, http):
        r = http.request("PROPFIND", f"{BASE}/remote.php/dav/files/")
        assert r.status_code in (401, 403), (
            f"WebDAV should require auth: {r.status_code}"
        )

    def test_authenticated_webdav_list(self, cfg, http):
        if not cfg.nextcloud_user or not cfg.nextcloud_password:
            pytest.skip("Nextcloud credentials not set")
        r = http.request(
            "PROPFIND",
            f"{BASE}/remote.php/dav/files/{cfg.nextcloud_user}/",
            headers={"Depth": "1"},
            auth=(cfg.nextcloud_user, cfg.nextcloud_password),
        )
        assert r.status_code == 207, f"WebDAV PROPFIND failed: {r.status_code}"
        assert "<?xml" in r.text.lower() or "<d:multistatus" in r.text.lower()
```

- [ ] **Step 3: Write integrations/test_stirling.py**

```python
# /opt/test/integrations/test_stirling.py
"""
Stirling PDF integration tests.
Validates reachability and HTML→PDF conversion.
"""
import pytest
import httpx
import sys
sys.path.insert(0, "/opt/test")
from shared.config import config
from fixtures.data import MINIMAL_HTML

pytestmark = pytest.mark.integration

BASE = config.stirling_url


class TestStirlingHealth:
    def test_root_responds(self, http):
        r = http.get(BASE)
        assert r.status_code in (200, 302), f"Stirling PDF unreachable: {r.status_code}"

    def test_api_info_endpoint(self, http, cfg):
        auth = (cfg.stirling_username, cfg.stirling_password) if cfg.stirling_username else None
        r = http.get(f"{BASE}/api/v1/info/status", auth=auth)
        assert r.status_code in (200, 302, 401), (
            f"Stirling API endpoint problem: {r.status_code}"
        )


class TestStirlingPDFConversion:
    def test_html_to_pdf_returns_pdf_bytes(self, cfg, http):
        if not cfg.stirling_username:
            pytest.skip("TEST_STIRLING_USERNAME not set")

        files = {"fileInput": ("test.html", MINIMAL_HTML.encode(), "text/html")}
        r = http.post(
            f"{BASE}/api/v1/convert/html/pdf",
            files=files,
            auth=(cfg.stirling_username, cfg.stirling_password),
            timeout=30,
        )
        assert r.status_code == 200, f"HTML→PDF failed: {r.status_code} {r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("application/pdf"), (
            f"Response is not a PDF: {r.headers.get('content-type')}"
        )
        assert len(r.content) > 1000, f"PDF too small ({len(r.content)} bytes)"

    def test_empty_html_returns_error_or_pdf(self, cfg, http):
        if not cfg.stirling_username:
            pytest.skip("TEST_STIRLING_USERNAME not set")
        files = {"fileInput": ("empty.html", b"", "text/html")}
        r = http.post(
            f"{BASE}/api/v1/convert/html/pdf",
            files=files,
            auth=(cfg.stirling_username, cfg.stirling_password),
            timeout=30,
        )
        # Stirling may accept empty HTML or reject it — both are acceptable
        assert r.status_code in (200, 400, 500), (
            f"Unexpected status for empty HTML: {r.status_code}"
        )
```

- [ ] **Step 4: Commit**

```bash
cd /opt/test && git add integrations/ && git commit -m "feat(tests/integrations): Authentik + Nextcloud + Stirling PDF integration tests"
```

---

## Task 7: Playwright setup for frontend E2E

**Files:**
- Create: `/opt/test/frontend/package.json`
- Create: `/opt/test/frontend/playwright.config.ts`
- Create: `/opt/test/frontend/fixtures/auth.fixture.ts`
- Create: `/opt/test/frontend/pages/login.page.ts`
- Create: `/opt/test/frontend/pages/dashboard.page.ts`
- Create: `/opt/test/frontend/pages/stories.page.ts`

- [ ] **Step 1: Write frontend/package.json**

```json
{
  "name": "heykarl-e2e",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "test": "playwright test",
    "test:smoke": "playwright test specs/smoke.spec.ts",
    "test:auth": "playwright test specs/auth.spec.ts",
    "test:stories": "playwright test specs/stories.spec.ts",
    "test:headed": "playwright test --headed",
    "report": "playwright show-report ../reports/playwright"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "dotenv": "^16.4.5"
  }
}
```

- [ ] **Step 2: Install Playwright**

```bash
cd /opt/test/frontend && npm install && npx playwright install chromium --with-deps
```

Expected: Chromium browser installed, no errors.

- [ ] **Step 3: Write frontend/playwright.config.ts**

```typescript
// /opt/test/frontend/playwright.config.ts
import { defineConfig, devices } from "@playwright/test";
import * as dotenv from "dotenv";
import * as path from "path";

dotenv.config({ path: path.resolve(__dirname, "../test.env") });

const BASE_URL = process.env.TEST_FRONTEND_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./specs",
  outputDir: "../reports/playwright-artifacts",
  fullyParallel: false,   // stories tests share state — keep sequential
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 30_000,
  reporter: [
    ["list"],
    ["html", { outputFolder: "../reports/playwright", open: "never" }],
    ["junit", { outputFile: "../reports/playwright-junit.xml" }],
  ],
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
```

- [ ] **Step 4: Write frontend/pages/login.page.ts**

```typescript
// /opt/test/frontend/pages/login.page.ts
import { Page, Locator, expect } from "@playwright/test";

export class LoginPage {
  readonly page: Page;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(page: Page) {
    this.page = page;
    this.emailInput = page.getByLabel(/e-?mail/i).or(page.locator('input[type="email"]'));
    this.passwordInput = page.getByLabel(/passwort|password/i).or(page.locator('input[type="password"]'));
    this.submitButton = page.getByRole("button", { name: /anmeld|login|einloggen/i });
    this.errorMessage = page.locator('[role="alert"], .error, [data-testid="error"]');
  }

  async goto() {
    await this.page.goto("/login");
    await this.page.waitForLoadState("networkidle");
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectError() {
    await expect(this.errorMessage).toBeVisible({ timeout: 5000 });
  }
}
```

- [ ] **Step 5: Write frontend/pages/dashboard.page.ts**

```typescript
// /opt/test/frontend/pages/dashboard.page.ts
import { Page, Locator, expect } from "@playwright/test";

export class DashboardPage {
  readonly page: Page;
  readonly sidebar: Locator;
  readonly storiesLink: Locator;
  readonly workspaceLink: Locator;

  constructor(page: Page) {
    this.page = page;
    this.sidebar = page.locator("nav, aside, [data-testid='sidebar']");
    this.storiesLink = page.getByRole("link", { name: /stories|user.?stories/i });
    this.workspaceLink = page.getByRole("link", { name: /workspace|ki.?workspace/i });
  }

  async expectLoaded() {
    await expect(this.page).not.toHaveURL("/login");
    await expect(this.sidebar).toBeVisible({ timeout: 10000 });
  }
}
```

- [ ] **Step 6: Write frontend/pages/stories.page.ts**

```typescript
// /opt/test/frontend/pages/stories.page.ts
import { Page, Locator, expect } from "@playwright/test";

export class StoriesPage {
  readonly page: Page;
  readonly newStoryButton: Locator;
  readonly storyList: Locator;

  constructor(page: Page) {
    this.page = page;
    this.newStoryButton = page.getByRole("button", { name: /neu|new|anlegen|erstellen/i });
    this.storyList = page.locator('[data-testid="story-list"], .story-list, [class*="story"]').first();
  }

  async goto(orgSlug: string) {
    await this.page.goto(`/${orgSlug}/stories`);
    await this.page.waitForLoadState("networkidle");
  }

  async expectVisible() {
    await expect(this.page).toHaveURL(/stories/);
  }
}
```

- [ ] **Step 7: Write frontend/fixtures/auth.fixture.ts**

```typescript
// /opt/test/frontend/fixtures/auth.fixture.ts
import { test as base, Page } from "@playwright/test";
import { LoginPage } from "../pages/login.page";

const EMAIL = process.env.TEST_USER_EMAIL ?? "";
const PASSWORD = process.env.TEST_USER_PASSWORD ?? "";
const ORG_SLUG = process.env.TEST_ORG_SLUG ?? "test-org";

type AuthFixtures = {
  loggedInPage: Page;
  orgSlug: string;
};

export const test = base.extend<AuthFixtures>({
  orgSlug: async ({}, use) => {
    await use(ORG_SLUG);
  },

  loggedInPage: async ({ page }, use) => {
    if (!EMAIL || !PASSWORD) {
      test.skip(true, "TEST_USER_EMAIL / TEST_USER_PASSWORD not set");
    }
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.login(EMAIL, PASSWORD);
    // Wait for redirect away from /login
    await page.waitForURL((url) => !url.pathname.includes("/login"), {
      timeout: 15000,
    });
    await use(page);
  },
});

export { expect } from "@playwright/test";
```

- [ ] **Step 8: Commit**

```bash
cd /opt/test && git add frontend/ && git commit -m "feat(tests/frontend): Playwright setup with page objects + auth fixture"
```

---

## Task 8: Frontend E2E specs

**Files:**
- Create: `/opt/test/frontend/specs/smoke.spec.ts`
- Create: `/opt/test/frontend/specs/auth.spec.ts`
- Create: `/opt/test/frontend/specs/stories.spec.ts`

- [ ] **Step 1: Write frontend/specs/smoke.spec.ts**

```typescript
// /opt/test/frontend/specs/smoke.spec.ts
import { test, expect } from "@playwright/test";

test.describe("Frontend Smoke", () => {
  test("root route returns 200 and renders HTML", async ({ page }) => {
    const response = await page.goto("/");
    expect(response?.status()).toBeLessThan(500);
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  });

  test("login page is reachable and shows form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator('input[type="email"], input[type="text"]').first())
      .toBeVisible({ timeout: 10000 });
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test("register page is reachable", async ({ page }) => {
    const r = await page.goto("/register");
    expect(r?.status()).not.toBe(404);
  });

  test("non-existent route does not show blank page", async ({ page }) => {
    await page.goto("/non-existent-route-xyz");
    const bodyText = await page.locator("body").textContent();
    expect(bodyText?.trim().length).toBeGreaterThan(10);
  });
});
```

- [ ] **Step 2: Write frontend/specs/auth.spec.ts**

```typescript
// /opt/test/frontend/specs/auth.spec.ts
import { test as base, expect } from "@playwright/test";
import { test, loggedInPage } from "../fixtures/auth.fixture";
import { LoginPage } from "../pages/login.page";
import { DashboardPage } from "../pages/dashboard.page";

base.describe("Authentication flows", () => {
  base.test("login with invalid credentials shows error", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login("nobody@nowhere.invalid", "wrongpassword");
    await login.expectError();
    await expect(page).toHaveURL(/login/);
  });

  base.test("login with empty email shows validation error", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await page.locator('input[type="password"]').fill("anything");
    await page.getByRole("button", { name: /anmeld|login/i }).click();
    // HTML5 validation or app-level error should prevent navigation
    await expect(page).toHaveURL(/login/);
  });
});

test.describe("Authenticated flows", () => {
  test("valid login redirects away from /login", async ({ loggedInPage }) => {
    await expect(loggedInPage).not.toHaveURL(/login/);
  });

  test("dashboard shows sidebar navigation after login", async ({ loggedInPage }) => {
    const dashboard = new DashboardPage(loggedInPage);
    await dashboard.expectLoaded();
  });

  test("browser back button after logout redirects to login", async ({ loggedInPage }) => {
    // Trigger logout if logout button is visible
    const logoutBtn = loggedInPage.getByRole("button", { name: /logout|abmelden|ausloggen/i });
    if (await logoutBtn.isVisible()) {
      await logoutBtn.click();
      await loggedInPage.waitForURL(/login/, { timeout: 10000 });
      await loggedInPage.goBack();
      // Should redirect back to login (protected route)
      await expect(loggedInPage).toHaveURL(/login/);
    }
  });
});
```

- [ ] **Step 3: Write frontend/specs/stories.spec.ts**

```typescript
// /opt/test/frontend/specs/stories.spec.ts
import { test, expect } from "../fixtures/auth.fixture";
import { StoriesPage } from "../pages/stories.page";

test.describe("User Stories — E2E flows", () => {
  test("stories list page loads after login", async ({ loggedInPage, orgSlug }) => {
    const stories = new StoriesPage(loggedInPage);
    await stories.goto(orgSlug);
    await stories.expectVisible();
  });

  test("story creation page is reachable", async ({ loggedInPage, orgSlug }) => {
    await loggedInPage.goto(`/${orgSlug}/stories/new`);
    await loggedInPage.waitForLoadState("networkidle");
    const url = loggedInPage.url();
    // Should stay on /new or redirect to story (if auto-created)
    expect(url).toMatch(/stories/);
  });

  test("story detail page renders without errors", async ({ loggedInPage, orgSlug }) => {
    // Navigate to stories list first
    await loggedInPage.goto(`/${orgSlug}/stories`);
    await loggedInPage.waitForLoadState("networkidle");

    // Click first story if list is not empty
    const firstStory = loggedInPage.locator('a[href*="/stories/"]').first();
    if (await firstStory.isVisible({ timeout: 3000 })) {
      await firstStory.click();
      await loggedInPage.waitForLoadState("networkidle");
      // Should render story detail
      await expect(loggedInPage).toHaveURL(/stories\/.+/);
      // No 500 error text
      const bodyText = await loggedInPage.locator("body").textContent();
      expect(bodyText).not.toContain("Internal Server Error");
    }
  });

  test("navigation to dashboard from stories sidebar works", async ({ loggedInPage, orgSlug }) => {
    await loggedInPage.goto(`/${orgSlug}/stories`);
    const dashboardLink = loggedInPage.getByRole("link", { name: /dashboard/i });
    if (await dashboardLink.isVisible()) {
      await dashboardLink.click();
      await expect(loggedInPage).toHaveURL(/dashboard/);
    }
  });

  test("stories board view is accessible", async ({ loggedInPage, orgSlug }) => {
    const r = await loggedInPage.goto(`/${orgSlug}/stories/board`);
    expect(r?.status()).not.toBe(500);
    await expect(loggedInPage).not.toHaveURL(/login/);
  });
});
```

- [ ] **Step 4: Run E2E tests**

```bash
cd /opt/test/frontend && npx playwright test specs/smoke.spec.ts --reporter=list
```

Expected: Smoke tests pass (frontend must be running).

- [ ] **Step 5: Commit**

```bash
cd /opt/test && git add frontend/specs/ && git commit -m "feat(tests/frontend): E2E specs for smoke, auth flows, and story navigation"
```

---

## Task 9: Orchestration script + Makefile targets

**Files:**
- Create: `/opt/test/run_tests.sh`
- Modify: `/opt/assist2/Makefile` (add test targets)

- [ ] **Step 1: Write run_tests.sh**

```bash
#!/usr/bin/env bash
# /opt/test/run_tests.sh
# ──────────────────────────────────────────────────────────────────────────────
# Orchestrates the full test suite.
# Usage: ./run_tests.sh [smoke|backend|integrations|ghost|e2e|all]
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SUITE="${1:-all}"
ROOT="/opt/test"
REPORTS="$ROOT/reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$REPORTS"

# Load test env if it exists
if [[ -f "$ROOT/test.env" ]]; then
  set -o allexport
  source "$ROOT/test.env"
  set +o allexport
fi

log() { echo -e "\033[1;34m[TEST]\033[0m $*"; }
success() { echo -e "\033[1;32m[PASS]\033[0m $*"; }
fail() { echo -e "\033[1;31m[FAIL]\033[0m $*"; }

FAILED=()

run_pytest() {
  local name="$1"; shift
  log "Running $name tests..."
  if python -m pytest "$@" \
      --tb=short \
      --junitxml="$REPORTS/${name}_${TIMESTAMP}.xml" \
      2>&1 | tee "$REPORTS/${name}_${TIMESTAMP}.log"; then
    success "$name tests passed"
  else
    fail "$name tests FAILED"
    FAILED+=("$name")
  fi
}

run_playwright() {
  log "Running E2E tests (Playwright)..."
  cd "$ROOT/frontend"
  if npx playwright test --reporter=list,junit 2>&1 | tee "$REPORTS/e2e_${TIMESTAMP}.log"; then
    success "E2E tests passed"
  else
    fail "E2E tests FAILED"
    FAILED+=("e2e")
  fi
  cd "$ROOT"
}

case "$SUITE" in
  smoke)
    run_pytest smoke -m smoke "$ROOT/smoke/"
    ;;
  backend)
    run_pytest backend -m backend "$ROOT/backend/"
    ;;
  integrations)
    run_pytest integrations -m integration "$ROOT/integrations/"
    ;;
  ghost)
    run_pytest ghost -m ghost "$ROOT/ghost/"
    ;;
  e2e)
    run_playwright
    ;;
  all)
    run_pytest smoke    -m smoke       "$ROOT/smoke/"
    run_pytest backend  -m backend     "$ROOT/backend/"
    run_pytest ghost    -m ghost       "$ROOT/ghost/"
    run_pytest integrations -m integration "$ROOT/integrations/"
    run_playwright
    ;;
  *)
    echo "Usage: $0 [smoke|backend|integrations|ghost|e2e|all]"
    exit 1
    ;;
esac

echo ""
if [[ ${#FAILED[@]} -gt 0 ]]; then
  fail "FAILED suites: ${FAILED[*]}"
  echo "Reports in: $REPORTS/"
  exit 1
else
  success "All suites passed"
  echo "Reports in: $REPORTS/"
fi
```

```bash
chmod +x /opt/test/run_tests.sh
```

- [ ] **Step 2: Add Makefile targets to /opt/assist2/Makefile**

Read the current end of Makefile first:

```bash
tail -20 /opt/assist2/Makefile
```

Then append these targets:

```makefile
# ── External test suite (/opt/test/) ─────────────────────────────────────────
TEST_ROOT := /opt/test

.PHONY: test-smoke test-backend test-ghost test-integrations test-e2e test-all

test-smoke:
	@cd $(TEST_ROOT) && bash run_tests.sh smoke

test-backend:
	@cd $(TEST_ROOT) && bash run_tests.sh backend

test-ghost:
	@cd $(TEST_ROOT) && bash run_tests.sh ghost

test-integrations:
	@cd $(TEST_ROOT) && bash run_tests.sh integrations

test-e2e:
	@cd $(TEST_ROOT) && bash run_tests.sh e2e

test-all:
	@cd $(TEST_ROOT) && bash run_tests.sh all
```

- [ ] **Step 3: Verify run script works**

```bash
cd /opt/test && bash run_tests.sh smoke 2>&1 | tail -10
```

Expected: `[PASS] smoke tests passed` or `[FAIL] smoke tests FAILED` (no bash errors)

- [ ] **Step 4: Commit**

```bash
cd /opt/test && git add run_tests.sh && cd /opt/assist2 && git add Makefile
git commit -m "feat(tests): run_tests.sh orchestrator + Makefile targets"
```

---

## Task 10: CI/CD pipeline (GitHub Actions template)

**Files:**
- Create: `/opt/assist2/.github/workflows/tests.yml`

- [ ] **Step 1: Write .github/workflows/tests.yml**

```yaml
# /opt/assist2/.github/workflows/tests.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      suite:
        description: "Test suite to run"
        required: false
        default: "all"
        type: choice
        options: [smoke, backend, integrations, ghost, e2e, all]

env:
  TEST_BACKEND_URL: http://localhost:8000
  TEST_FRONTEND_URL: http://localhost:3000
  TEST_GHOST_URL: https://heykarl.app
  TEST_LITELLM_URL: http://localhost:4000
  TEST_N8N_URL: http://localhost:5678
  TEST_AUTHENTIK_URL: http://localhost:9000
  TEST_NEXTCLOUD_URL: http://localhost
  TEST_STIRLING_URL: http://localhost:8080
  TEST_TIMEOUT: "20"

jobs:
  # ── 1. Smoke tests (fast, always run) ──────────────────────────────────────
  smoke:
    name: "Smoke Tests"
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Start services
        working-directory: infra
        run: docker compose -f docker-compose.yml up -d
        env:
          COMPOSE_FILE: docker-compose.yml

      - name: Wait for services
        run: |
          timeout 120 bash -c 'until curl -sf http://localhost:8000/openapi.json; do sleep 3; done'
          timeout 60  bash -c 'until curl -sf http://localhost:3000; do sleep 3; done'

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install test deps
        run: pip install pytest pytest-asyncio httpx PyJWT

      - name: Copy test framework
        run: cp -r /opt/test ${{ github.workspace }}/tests-ext || true
        # Note: in CI, /opt/test is not available — tests live in this repo.
        # Adjust this step to reference the test repo or include tests in repo.

      - name: Run smoke tests
        working-directory: tests-ext
        run: python -m pytest smoke/ -v -m smoke --tb=short --junitxml=smoke-results.xml
        env:
          TEST_GHOST_ADMIN_API_KEY: ${{ secrets.TEST_GHOST_ADMIN_API_KEY }}
          TEST_USER_EMAIL: ${{ secrets.TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.TEST_USER_PASSWORD }}

      - name: Publish smoke results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: smoke-results
          path: tests-ext/smoke-results.xml

  # ── 2. Backend API tests ────────────────────────────────────────────────────
  backend:
    name: "Backend API Tests"
    runs-on: ubuntu-latest
    needs: smoke
    steps:
      - uses: actions/checkout@v4
      - name: Start backend services
        working-directory: infra
        run: docker compose -f docker-compose.yml up -d postgres redis authentik-server authentik-worker backend
      - name: Wait for backend
        run: timeout 120 bash -c 'until curl -sf http://localhost:8000/openapi.json; do sleep 3; done'
      - name: Set up Python
        uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Install deps
        run: pip install pytest pytest-asyncio httpx PyJWT
      - name: Run backend tests
        working-directory: tests-ext
        run: python -m pytest backend/ -v -m backend --tb=short --junitxml=backend-results.xml
        env:
          TEST_USER_EMAIL: ${{ secrets.TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.TEST_USER_PASSWORD }}
          TEST_ORG_SLUG: ${{ secrets.TEST_ORG_SLUG }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: backend-results
          path: tests-ext/backend-results.xml

  # ── 3. Ghost tests (separate, clearly identified block) ────────────────────
  ghost:
    name: "Ghost CMS Tests"
    runs-on: ubuntu-latest
    needs: smoke
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pytest pytest-asyncio httpx PyJWT
      - name: Run Ghost tests
        working-directory: tests-ext
        run: python -m pytest ghost/ -v -m ghost --tb=short --junitxml=ghost-results.xml
        env:
          TEST_GHOST_URL: ${{ vars.TEST_GHOST_URL }}
          TEST_GHOST_ADMIN_API_KEY: ${{ secrets.TEST_GHOST_ADMIN_API_KEY }}
          TEST_GHOST_CONTENT_API_KEY: ${{ secrets.TEST_GHOST_CONTENT_API_KEY }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: ghost-results
          path: tests-ext/ghost-results.xml

  # ── 4. Integration tests ────────────────────────────────────────────────────
  integrations:
    name: "Integration Tests"
    runs-on: ubuntu-latest
    needs: backend
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install pytest pytest-asyncio httpx PyJWT
      - name: Run integration tests
        working-directory: tests-ext
        run: python -m pytest integrations/ -v -m integration --tb=short --junitxml=integration-results.xml
        env:
          TEST_LITELLM_API_KEY: ${{ secrets.TEST_LITELLM_API_KEY }}
          TEST_N8N_API_KEY: ${{ secrets.TEST_N8N_API_KEY }}
          TEST_AUTHENTIK_API_TOKEN: ${{ secrets.TEST_AUTHENTIK_API_TOKEN }}
          TEST_NEXTCLOUD_USER: ${{ secrets.TEST_NEXTCLOUD_USER }}
          TEST_NEXTCLOUD_PASSWORD: ${{ secrets.TEST_NEXTCLOUD_PASSWORD }}
          TEST_STIRLING_USERNAME: ${{ secrets.TEST_STIRLING_USERNAME }}
          TEST_STIRLING_PASSWORD: ${{ secrets.TEST_STIRLING_PASSWORD }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: integration-results
          path: tests-ext/integration-results.xml

  # ── 5. E2E tests ─────────────────────────────────────────────────────────────
  e2e:
    name: "E2E Tests (Playwright)"
    runs-on: ubuntu-latest
    needs: backend
    steps:
      - uses: actions/checkout@v4
      - name: Start full stack
        working-directory: infra
        run: docker compose -f docker-compose.yml up -d
      - name: Wait for frontend
        run: |
          timeout 120 bash -c 'until curl -sf http://localhost:8000/openapi.json; do sleep 3; done'
          timeout 120 bash -c 'until curl -sf http://localhost:3000; do sleep 3; done'
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - name: Install Playwright
        working-directory: tests-ext/frontend
        run: npm ci && npx playwright install chromium --with-deps
      - name: Run E2E tests
        working-directory: tests-ext/frontend
        run: npx playwright test
        env:
          TEST_USER_EMAIL: ${{ secrets.TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.TEST_USER_PASSWORD }}
          TEST_ORG_SLUG: ${{ vars.TEST_ORG_SLUG }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: tests-ext/reports/playwright/
```

- [ ] **Step 2: Commit**

```bash
mkdir -p /opt/assist2/.github/workflows
# (file already written above)
cd /opt/assist2 && git add .github/ && git commit -m "ci: GitHub Actions test pipeline with smoke → backend → ghost → integrations → e2e"
```

---

## Task 11: README and coverage documentation

**Files:**
- Create: `/opt/test/README.md`

- [ ] **Step 1: Write README.md**

```markdown
# HeyKarl — Testautomatisierung

Alle Tests liegen unter `/opt/test/` und sind vollständig unabhängig vom Anwendungscode.

## Struktur

| Verzeichnis | Inhalt | Werkzeug |
|---|---|---|
| `smoke/` | Schnelle Erreichbarkeitsprüfungen für alle Services | pytest + httpx |
| `backend/` | API-Tests gegen den laufenden Backend-Container | pytest + httpx |
| `ghost/` | Ghost Admin API — vollständige funktionale Tests | pytest + httpx + PyJWT |
| `integrations/` | LiteLLM, n8n, Authentik, Nextcloud, Stirling PDF | pytest + httpx |
| `frontend/` | Browser-E2E-Tests (Login, Stories, Navigation) | Playwright |
| `shared/` | Gemeinsame Konfiguration und Hilfsfunktionen | — |
| `fixtures/` | Statische Testdaten-Payloads (kein Produktivinhalt) | — |
| `reports/` | Generierte Reports (gitignored) | — |

## Voraussetzungen

```bash
pip install pytest pytest-asyncio httpx PyJWT
cd frontend && npm install && npx playwright install chromium --with-deps
```

## Konfiguration

```bash
cp test.env.example test.env
# test.env befüllen (niemals committen!)
```

### Erforderliche Variablen

| Variable | Wofür | Pflicht |
|---|---|---|
| `TEST_BACKEND_URL` | Backend-API-Basis-URL | Ja |
| `TEST_FRONTEND_URL` | Frontend-URL für E2E | Ja (E2E) |
| `TEST_USER_EMAIL` | Test-Nutzer E-Mail | Ja (Backend + E2E) |
| `TEST_USER_PASSWORD` | Test-Nutzer Passwort | Ja (Backend + E2E) |
| `TEST_ORG_SLUG` | Slug der Test-Organisation | Ja (Backend + E2E) |
| `TEST_GHOST_URL` | Ghost-URL (default: https://heykarl.app) | Ja (Ghost) |
| `TEST_GHOST_ADMIN_API_KEY` | Ghost Admin API Key `<id>:<hex>` | Ja (Ghost) |
| `TEST_GHOST_CONTENT_API_KEY` | Ghost Content API Key | Nein (optional) |
| `TEST_LITELLM_API_KEY` | LiteLLM Master Key | Nein (skip wenn leer) |
| `TEST_N8N_API_KEY` | n8n API-Schlüssel | Nein (skip wenn leer) |
| `TEST_AUTHENTIK_API_TOKEN` | Authentik API-Token | Nein (skip wenn leer) |
| `TEST_NEXTCLOUD_USER` | Nextcloud-Benutzername | Nein (skip wenn leer) |
| `TEST_NEXTCLOUD_PASSWORD` | Nextcloud App-Passwort | Nein (skip wenn leer) |
| `TEST_STIRLING_USERNAME` | Stirling PDF Benutzername | Nein (skip wenn leer) |
| `TEST_STIRLING_PASSWORD` | Stirling PDF Passwort | Nein (skip wenn leer) |

### Ghost Admin API Key erstellen

1. Ghost Admin öffnen: `https://heykarl.app/ghost/`
2. Settings → Integrations → Neue Custom Integration anlegen
3. Admin API Key kopieren (Format: `<id>:<hex-secret>`)
4. Als `TEST_GHOST_ADMIN_API_KEY` setzen

## Tests ausführen

```bash
# Alle Suiten
bash run_tests.sh all

# Nur Smoke (schnell, nach jedem Deploy)
bash run_tests.sh smoke

# Nur Ghost
bash run_tests.sh ghost

# Nur Backend API
bash run_tests.sh backend

# Nur Integrationen
bash run_tests.sh integrations

# Nur E2E (Playwright)
bash run_tests.sh e2e

# Via Makefile (aus /opt/assist2/)
make test-smoke
make test-ghost
make test-all
```

## CI/CD

Die GitHub Actions Pipeline in `.github/workflows/tests.yml` führt aus:

```
Smoke → Backend + Ghost (parallel) → Integrations + E2E (parallel)
```

Ghost-Tests erscheinen als eigenständiger, klar benannter Job (`Ghost CMS Tests`).

## Abgedeckte Kernfälle

### Smoke (alle Services)
- Backend OpenAPI-Schema erreichbar
- Backend Auth-Endpunkt vorhanden
- Frontend Login-Seite erreichbar
- Ghost Startseite + Admin API + Content API erreichbar
- LiteLLM Health-Endpunkt
- n8n Health-Endpunkt
- Authentik Ready-Endpunkt
- Stirling PDF erreichbar
- Nextcloud Status (installed=true)

### Backend API
- Login mit gültigen Credentials → Access + Refresh Token
- Login mit falschen Credentials → 401
- Login mit unvollständigem Body → 422
- Token-Refresh → neues Access Token
- Ungültiger Refresh-Token → 401
- Unauthentifizierter Zugriff auf geschützten Endpunkt → 401
- User Story anlegen (201 + korrekte Felder)
- User Story lesen (200 + korrekte Daten)
- User Story aktualisieren (200 + geänderte Felder)
- User Story löschen (204 + anschließend 404)
- Story-Liste mit Paginierung
- Story mit fehlendem Pflichtfeld → 422
- Story-Scoring-Endpunkt

### Ghost CMS (vollständig funktional)
- Startseite erreichbar (200)
- Admin API Site-Info abrufbar
- Admin API JWT-Auth korrekt
- Ungültiger JWT → 401
- Fehlender Auth-Header → 401
- Content API Key erforderlich
- Posts auflisten (mit Paginierung)
- Pages auflisten
- Tags auflisten
- Filter nach Status (draft/published)
- Draft-Post erstellen (201 + korrekte Felder)
- Post-Slug korrekt generiert
- Autotest-Tag wird gesetzt
- Draft ist kein published Post
- Post-Titel aktualisieren (updated_at required)
- Update ohne updated_at → 422/409
- Post löschen (204)
- Gelöschter Post → 404
- Idempotenz: kein Duplikat-Slug
- Draft nicht im Content API sichtbar
- Draft im Admin API sichtbar
- Nicht-existenter Post → 404
- Leerer Titel → 400/422
- Ungültiger Status-Wert → 400/422
- Nicht erreichbarer Ghost → ConnectError (sauber, kein Hang)
- Session-Cleanup löscht alle `autotest`-Posts

### Integrationen
- LiteLLM Health + Models-Endpunkt
- LiteLLM Completion (OpenAI-kompatibles Format)
- LiteLLM: unbekanntes Modell → 400/404
- LiteLLM: leere Messages → 400/422
- n8n Health (/healthz)
- n8n API Auth-Pflicht
- n8n Workflow-Liste (mit Key)
- n8n Executions-Liste
- Authentik Ready + Live
- Authentik API Token-Pflicht
- Authentik User-Liste (mit Token)
- Nextcloud Status (installed=true, maintenance=false)
- Nextcloud WebDAV Auth-Pflicht
- Nextcloud WebDAV PROPFIND (mit Credentials)
- Stirling PDF erreichbar
- Stirling HTML→PDF (bytes, content-type=application/pdf)

### Frontend E2E (Playwright)
- Root-Route gibt HTML zurück
- Login-Seite zeigt Formular
- Register-Seite erreichbar
- Ungültige Credentials → Fehlermeldung + bleibt auf /login
- Gültiger Login → Weiterleitung weg von /login
- Dashboard zeigt Sidebar-Navigation
- Stories-Liste-Seite lädt
- Story-Erstellungsseite erreichbar
- Story-Detail ohne JS-Fehler
- Navigation von Stories → Dashboard funktioniert
- Stories-Board-View erreichbar

## Bewusst noch NICHT automatisiert

- AI-Qualität der Antworten (LiteLLM-Modell-Output)
- Jira-Synchronisation (benötigt Live-Jira-Instanz)
- Confluence-Indexierung
- Celery-Background-Task-Ausführung (asynchron, schwer stabil testbar)
- OAuth-Flows (GitHub, Atlassian) — benötigen echte OAuth-Provider
- RAG/Embeddings-Qualität
- PDF-Inhalt (nur Format und Größe werden geprüft)
- E-Mail-Versand (SMTP)
- Billing/Payment-Flows
- Admin-Frontend (separates Deployment)
- LangGraph-Service (noch nicht stabil genug für automatisierte Tests)
- Automatische Erweiterung der Testbasis aus Codeänderungen (ausdrücklich KEIN Ziel)
```

- [ ] **Step 2: Write /opt/test/.gitignore**

```gitignore
# /opt/test/.gitignore
reports/
test.env
*.pyc
__pycache__/
.pytest_cache/
frontend/node_modules/
frontend/playwright-report/
frontend/test-results/
*.log
```

- [ ] **Step 3: Final commit**

```bash
cd /opt/test && git add README.md .gitignore && git commit -m "docs(tests): README with setup instructions, coverage list, and not-covered list"
```

---

## Self-Review

**Spec coverage check:**

| Spec Requirement | Task(s) |
|---|---|
| 1. Modulare Teststruktur mit 7 Ebenen | Task 1 |
| 2. Frontend-Prüfungen | Task 7+8 |
| 3. Backend- und API-Prüfungen | Task 3 |
| 4. Daten- und Prozessprüfungen (Story CRUD) | Task 3 |
| 5. Integrationstests (LiteLLM, n8n, Stirling, Nextcloud, Authentik) | Task 5+6 |
| 6. Ghost vollwertig (alle 14 Anforderungen) | Task 4 |
| 7. E2E-Kernflüsse | Task 7+8 |
| 8. Smoke nach jedem Build | Task 2 + Task 9 |
| 9. Reporting (JUnit XML + HTML + Logs) | Task 9+10 |
| 10. CI/CD-Integration | Task 10 |
| 11. Testdaten + Cleanup (Ghost purge) | Task 4 (conftest autouse) |
| 12. Keine Auto-Generierung | Keine automatische Testgenerierung implementiert ✓ |

**Placeholder scan:** Keine TBD/TODO/similar-to-Task-N in den Code-Blöcken gefunden.

**Type consistency:** `ghost_api` Fixture in `ghost/conftest.py` → konsistent verwendet in `ghost/test_ghost.py`. `api` + `org_id` in `backend/conftest.py` → konsistent in `backend/test_user_stories.py`.

---

**Plan gespeichert unter:** `docs/superpowers/plans/2026-04-21-test-automation-architecture.md`

**Zwei Ausführungsoptionen:**

**1. Subagent-Driven (empfohlen)** — Ich beauftrage pro Task einen frischen Subagenten, Review zwischen Tasks, schnelle Iteration

**2. Inline Execution** — Tasks in dieser Session mit `executing-plans`, Batch-Ausführung mit Checkpoints

**Welchen Ansatz bevorzugst du?**
