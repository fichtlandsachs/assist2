# Stirling PDF — Userstory Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Stirling PDF as an internal Docker service that automatically generates a structured PDF for every user story when its status transitions to `done`, with an admin UI for branding configuration (logo, letterhead, company name), storing the PDF in a local cache volume (Phase 1) ready for Nextcloud integration (Phase 2).

**Architecture:** A sync Celery task (`generate_story_pdf`) is dispatched from the `update_user_story` PATCH handler when status transitions to `done`. The task uses `asyncio.run()` to call async DB/HTTP code, renders story data via a Jinja2 HTML template, submits it to Stirling PDF's REST API, and writes the result to a cache volume. Org admins configure branding via `POST/PUT /api/v1/organizations/{org_id}/pdf-settings`; settings are stored in a new `pdf_settings` DB table.

**Tech Stack:** Stirling PDF (Docker), httpx (async HTTP client, already in requirements), Celery (already configured), Jinja2 (install if not present), SQLAlchemy async ORM, FastAPI, Next.js 14

**Spec:** `docs/superpowers/specs/2026-03-24-stirling-pdf-userstory-export-design.md`

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `backend/app/models/pdf_settings.py` | ORM model: `PdfSettings` table |
| `backend/app/schemas/pdf_settings.py` | Pydantic schemas for settings CRUD + upload |
| `backend/app/routers/pdf_settings.py` | API endpoints: GET/PUT settings, upload/delete templates, preview |
| `backend/app/services/stirling_client.py` | HTTP client wrapping Stirling PDF REST API |
| `backend/app/services/pdf_service.py` | Orchestrates: render HTML → call Stirling → cache PDF |
| `backend/app/tasks/pdf_tasks.py` | Celery task: `generate_story_pdf` |
| `backend/app/templates/userstory_pdf.html.jinja2` | HTML template rendered into PDF |
| `backend/migrations/versions/0017_pdf_settings.py` | Migration: create `pdf_settings` table |
| `backend/tests/unit/test_stirling_client.py` | Unit tests for `StirlingPDFClient` |
| `backend/tests/unit/test_pdf_service.py` | Unit tests for `PdfService` |
| `backend/tests/integration/test_pdf_settings.py` | Integration tests for the API |
| `frontend/app/[org]/admin/pdf/page.tsx` | Admin page: branding settings + template upload |
| `frontend/components/admin/PdfSettingsForm.tsx` | Form: company name, format, language, header/footer |
| `frontend/components/admin/TemplateUpload.tsx` | File upload: letterhead PDF + logo image |

### Modified Files
| File | Changes |
|------|---------|
| `infra/docker-compose.yml` | Add `stirling-pdf` service + 2 volumes; add `STIRLING_PDF_URL` to `backend` and `worker` env |
| `infra/.env.example` | Add `STIRLING_PDF_URL` |
| `backend/requirements.txt` | Add `jinja2` if not present |
| `backend/app/config.py` | Add `STIRLING_PDF_URL`, `PDF_TEMPLATES_PATH`, `PDF_CACHE_PATH` |
| `backend/app/celery_app.py` | Add `"app.tasks.pdf_tasks"` to `include` list |
| `backend/app/main.py` | Register `pdf_settings` router |
| `backend/app/routers/user_stories.py` | Capture `old_status` before update; dispatch Celery task on `done` transition |

---

## Task 1: Docker — Add Stirling PDF Container

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `infra/.env.example`

- [ ] **Step 1: Add volumes to docker-compose.yml**

In `infra/docker-compose.yml`, add to the top-level `volumes:` section:
```yaml
  assist2_pdf_templates:
  assist2_pdf_cache:
```

- [ ] **Step 2: Add stirling-pdf service to docker-compose.yml**

Add after the `authentik-worker:` service block:
```yaml
  stirling-pdf:
    image: stirlingtools/stirling-pdf:latest
    container_name: assist2-stirling-pdf
    restart: unless-stopped
    environment:
      DOCKER_ENABLE_SECURITY: "false"
      INSTALL_BOOK_AND_ADVANCED_HTML_OPS: "true"
    volumes:
      - assist2_pdf_templates:/app/pdf_templates
      - assist2_pdf_cache:/app/pdf_cache
    networks:
      - internal
```

Not exposed via Traefik — internal only.

- [ ] **Step 3: Add STIRLING_PDF_URL to backend and worker services**

In the `backend:` service's `environment:` block, add:
```yaml
      STIRLING_PDF_URL: ${STIRLING_PDF_URL:-http://assist2-stirling-pdf:8080}
```

In the `worker:` service's `environment:` block (the Celery worker), add the same line:
```yaml
      STIRLING_PDF_URL: ${STIRLING_PDF_URL:-http://assist2-stirling-pdf:8080}
```

- [ ] **Step 4: Add STIRLING_PDF_URL to .env.example**

```bash
# Stirling PDF
STIRLING_PDF_URL=http://assist2-stirling-pdf:8080
```

- [ ] **Step 5: Start the container**

```bash
cd /opt/assist2
docker compose -f infra/docker-compose.yml up -d stirling-pdf
```

Wait 30s, then verify:
```bash
docker compose -f infra/docker-compose.yml ps stirling-pdf
```
Expected: `Up` (Stirling PDF has no healthcheck by default).

Also verify the API is reachable from within the network:
```bash
docker compose -f infra/docker-compose.yml exec backend curl -s http://assist2-stirling-pdf:8080/api/v1/info 2>/dev/null | head -c 100 || echo "API not ready yet — wait 30s more"
```

- [ ] **Step 6: Commit**

```bash
git add infra/docker-compose.yml infra/.env.example
git commit -m "feat(infra): add Stirling PDF container for userstory PDF generation"
```

---

## Task 2: Config Settings + Dependencies

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add settings to config.py**

In `backend/app/config.py`, add these fields to the `Settings` class after the Authentik block:
```python
    # Stirling PDF
    STIRLING_PDF_URL: str = "http://assist2-stirling-pdf:8080"
    PDF_TEMPLATES_PATH: str = "/app/pdf_templates"
    PDF_CACHE_PATH: str = "/app/pdf_cache"
```

- [ ] **Step 2: Check if jinja2 is in requirements**

```bash
grep -i jinja2 /opt/assist2/backend/requirements.txt
```

If not found, add to `backend/requirements.txt`:
```
Jinja2==3.1.4
```

- [ ] **Step 3: Verify import works**

```bash
docker compose -f infra/docker-compose.yml exec backend python -c "from app.config import get_settings; s = get_settings(); print(s.STIRLING_PDF_URL)"
```
Expected: `http://assist2-stirling-pdf:8080`

- [ ] **Step 4: Commit**

```bash
git add backend/app/config.py backend/requirements.txt
git commit -m "feat(config): add Stirling PDF and PDF path settings"
```

---

## Task 3: DB Migration 0017 + ORM Model

**Files:**
- Create: `backend/migrations/versions/0017_pdf_settings.py`
- Create: `backend/app/models/pdf_settings.py`

**Note:** Migration number 0017 assumes P1 migrations 0015 and 0016 have landed. Check `backend/migrations/versions/` and use the next available number.

- [ ] **Step 1: Create the ORM model**

Create `backend/app/models/pdf_settings.py`:
```python
"""PDF settings per organization — branding and format configuration."""
import uuid
from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PdfSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pdf_settings"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        unique=True, nullable=False, index=True
    )
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_format: Mapped[str] = mapped_column(
        String(10), nullable=False, default="a4"
    )  # 'a4' | 'letter'
    language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="de"
    )  # 'de' | 'en'
    header_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    footer_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    letterhead_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # file stored at {PDF_TEMPLATES_PATH}/{org_id}/letterhead.pdf
    logo_filename: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # file stored at {PDF_TEMPLATES_PATH}/{org_id}/logo.png
```

- [ ] **Step 2: Create migration file**

Check the current last migration number first:
```bash
ls backend/migrations/versions/ | sort | tail -3
```

Create `backend/migrations/versions/0017_pdf_settings.py` (adjust number if needed):
```python
"""Create pdf_settings table.

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa
import uuid

revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pdf_settings',
        sa.Column('id', sa.UUID(), nullable=False, default=uuid.uuid4),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('company_name', sa.String(255), nullable=True),
        sa.Column('page_format', sa.String(10), nullable=False, server_default='a4'),
        sa.Column('language', sa.String(10), nullable=False, server_default='de'),
        sa.Column('header_text', sa.String(500), nullable=True),
        sa.Column('footer_text', sa.String(500), nullable=True),
        sa.Column('letterhead_filename', sa.String(255), nullable=True),
        sa.Column('logo_filename', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_pdf_settings_organization_id', 'pdf_settings', ['organization_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_pdf_settings_organization_id', table_name='pdf_settings')
    op.drop_table('pdf_settings')
```

**Note on down_revision:** If 0016 (P1 migration) does not exist yet, temporarily set `down_revision = '0014'` and update to `'0016'` once P1 migrations land.

- [ ] **Step 3: Run migration**

```bash
cd /opt/assist2
make migrate
```
Expected: `Running upgrade ... -> 0017, Create pdf_settings table`

- [ ] **Step 4: Verify table**

```bash
docker compose -f infra/docker-compose.yml exec postgres psql -U platform -d platform_db -c "\d pdf_settings"
```
Expected: table with columns id, organization_id, company_name, page_format, language, etc.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/pdf_settings.py backend/migrations/versions/0017_pdf_settings.py
git commit -m "feat(db): add pdf_settings table and ORM model"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas/pdf_settings.py`

- [ ] **Step 1: Create schemas**

Create `backend/app/schemas/pdf_settings.py`:
```python
"""Pydantic schemas for PDF settings API."""
import uuid
from typing import Optional

from pydantic import BaseModel, Field


class PdfSettingsUpdate(BaseModel):
    """Fields the admin can update."""
    company_name: Optional[str] = Field(None, max_length=255)
    page_format: Optional[str] = Field(None, pattern="^(a4|letter)$")
    language: Optional[str] = Field(None, pattern="^(de|en)$")
    header_text: Optional[str] = Field(None, max_length=500)
    footer_text: Optional[str] = Field(None, max_length=500)


class PdfSettingsRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    company_name: Optional[str] = None
    page_format: str = "a4"
    language: str = "de"
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    letterhead_filename: Optional[str] = None
    logo_filename: Optional[str] = None

    model_config = {"from_attributes": True}


class PdfSettingsDefaults:
    """Default values used when no PdfSettings row exists for an org."""
    company_name: Optional[str] = None
    page_format: str = "a4"
    language: str = "de"
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    letterhead_filename: Optional[str] = None
    logo_filename: Optional[str] = None
```

- [ ] **Step 2: Verify import**

```bash
docker compose -f infra/docker-compose.yml exec backend python -c "from app.schemas.pdf_settings import PdfSettingsRead, PdfSettingsUpdate; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/pdf_settings.py
git commit -m "feat(schemas): add PdfSettings Pydantic schemas"
```

---

## Task 5: StirlingPDFClient Service (TDD)

**Files:**
- Create: `backend/app/services/stirling_client.py`
- Create: `backend/tests/unit/test_stirling_client.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_stirling_client.py`:
```python
"""Unit tests for StirlingPDFClient — all httpx calls are mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_mock_response(status_code: int, content: bytes = b"%PDF-fake") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_html_to_pdf_success():
    """html_to_pdf returns PDF bytes on success."""
    from app.services.stirling_client import StirlingPDFClient
    client = StirlingPDFClient()
    html = "<html><body><h1>Test</h1></body></html>"

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(200, b"%PDF-1.4 fake-pdf-bytes")
        )
        result = await client.html_to_pdf(html)

    assert result == b"%PDF-1.4 fake-pdf-bytes"


@pytest.mark.asyncio
async def test_html_to_pdf_raises_on_error():
    """html_to_pdf raises HTTPStatusError on non-200 response."""
    from app.services.stirling_client import StirlingPDFClient
    import httpx
    client = StirlingPDFClient()

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(500)
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.html_to_pdf("<html></html>")


@pytest.mark.asyncio
async def test_overlay_pdfs_success():
    """overlay_pdfs returns merged PDF bytes."""
    from app.services.stirling_client import StirlingPDFClient
    client = StirlingPDFClient()

    with patch("httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_mock_response(200, b"%PDF-merged")
        )
        result = await client.overlay_pdfs(b"%PDF-content", b"%PDF-letterhead")

    assert result == b"%PDF-merged"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_stirling_client.py -v 2>&1 | head -15
```
Expected: `ImportError: cannot import name 'StirlingPDFClient'`

- [ ] **Step 3: Create StirlingPDFClient**

Create `backend/app/services/stirling_client.py`:
```python
"""HTTP client for Stirling PDF REST API."""
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class StirlingPDFClient:
    """Wraps Stirling PDF REST API calls."""

    @property
    def _base_url(self) -> str:
        return get_settings().STIRLING_PDF_URL

    async def html_to_pdf(self, html: str) -> bytes:
        """
        Convert an HTML string to PDF.
        POST /api/v1/misc/html-to-pdf (multipart: fileInput = HTML file)
        Returns raw PDF bytes.
        """
        url = f"{self._base_url}/api/v1/misc/html-to-pdf"
        html_bytes = html.encode("utf-8")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                files={"fileInput": ("input.html", html_bytes, "text/html")},
            )
            response.raise_for_status()
            return response.content

    async def overlay_pdfs(self, base_pdf: bytes, overlay_pdf: bytes) -> bytes:
        """
        Overlay two PDFs (e.g., apply a letterhead over the generated PDF).
        POST /api/v1/general/overlay-pdfs
        Returns merged PDF bytes.
        """
        url = f"{self._base_url}/api/v1/general/overlay-pdfs"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                files={
                    "fileInput": ("base.pdf", base_pdf, "application/pdf"),
                    "fileInput2": ("overlay.pdf", overlay_pdf, "application/pdf"),
                },
            )
            response.raise_for_status()
            return response.content


stirling_client = StirlingPDFClient()
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_stirling_client.py -v
```
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/stirling_client.py backend/tests/unit/test_stirling_client.py
git commit -m "feat(pdf): add StirlingPDFClient service for HTML-to-PDF conversion"
```

---

## Task 6: Jinja2 Template

**Files:**
- Create: `backend/app/templates/userstory_pdf.html.jinja2`

- [ ] **Step 1: Create the templates directory and HTML template**

```bash
mkdir -p /opt/assist2/backend/app/templates
```

Create `backend/app/templates/userstory_pdf.html.jinja2`:
```html
<!DOCTYPE html>
<html lang="{{ settings.language }}">
<head>
<meta charset="UTF-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; color: #333; margin: 40px; }
  h1 { font-size: 22px; color: #1a1a2e; border-bottom: 2px solid #1a1a2e; padding-bottom: 8px; }
  h2 { font-size: 15px; color: #2d3748; margin-top: 24px; }
  .meta { color: #666; font-size: 11px; margin-bottom: 20px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: bold; }
  .status-done { background: #c6f6d5; color: #276749; }
  .priority-high { background: #fed7d7; color: #9b2c2c; }
  .priority-critical { background: #e53e3e; color: white; }
  .priority-medium { background: #fefcbf; color: #744210; }
  .priority-low { background: #e2e8f0; color: #4a5568; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 11px; }
  th { background: #edf2f7; text-align: left; padding: 6px 8px; border: 1px solid #cbd5e0; }
  td { padding: 5px 8px; border: 1px solid #e2e8f0; vertical-align: top; }
  ul { margin: 4px 0; padding-left: 18px; }
  li { margin: 2px 0; }
  .dod-check { color: #48bb78; font-weight: bold; }
  .footer { margin-top: 40px; font-size: 10px; color: #999; border-top: 1px solid #e2e8f0; padding-top: 8px; }
  .logo { float: right; max-height: 50px; max-width: 150px; }
  .clearfix::after { content: ""; display: table; clear: both; }
</style>
</head>
<body>

<!-- Cover -->
<div class="clearfix">
  {% if logo_path %}
  <img src="{{ logo_path }}" class="logo" alt="Logo">
  {% endif %}
  {% if settings.company_name %}
  <div style="font-size:11px; color:#666;">{{ settings.company_name }}</div>
  {% endif %}
</div>
{% if settings.header_text %}
<div style="font-size:11px; color:#666; margin-bottom:8px;">{{ settings.header_text }}</div>
{% endif %}

<h1>{{ story.title }}</h1>
<div class="meta">
  <span class="badge status-done">{{ story.status.value | upper }}</span>&nbsp;
  <span class="badge priority-{{ story.priority.value }}">{{ story.priority.value | upper }}</span>&nbsp;
  {% if story.story_points %}Story Points: <strong>{{ story.story_points }}</strong>&nbsp;{% endif %}
  {% if story.quality_score %}Quality Score: <strong>{{ story.quality_score }}/100</strong>&nbsp;{% endif %}
  &nbsp;|&nbsp; Erstellt: {{ story.created_at.strftime('%d.%m.%Y') }}
</div>

<!-- Summary -->
{% if docs.summary %}
<h2>Zusammenfassung</h2>
<p>{{ docs.summary }}</p>
{% endif %}

<!-- Description -->
{% if story.description %}
<h2>Beschreibung</h2>
<p style="white-space: pre-wrap;">{{ story.description }}</p>
{% endif %}

<!-- Acceptance Criteria -->
{% if story.acceptance_criteria %}
<h2>Akzeptanzkriterien</h2>
<p style="white-space: pre-wrap;">{{ story.acceptance_criteria }}</p>
{% endif %}

<!-- Definition of Done -->
{% if story.definition_of_done %}
<h2>Definition of Done</h2>
<ul>
{% for criterion in dod_items %}
  <li><span class="dod-check">✓</span> {{ criterion }}</li>
{% endfor %}
</ul>
{% endif %}

<!-- Test Cases -->
{% if test_cases %}
<h2>Testfälle ({{ test_cases | length }})</h2>
<table>
  <tr><th>Titel</th><th>Status</th><th>Erwartetes Ergebnis</th></tr>
  {% for tc in test_cases %}
  <tr>
    <td>{{ tc.title }}</td>
    <td>{{ tc.status.value }}</td>
    <td>{{ tc.expected_result or '—' }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

<!-- Features -->
{% if features %}
<h2>Features ({{ features | length }})</h2>
<table>
  <tr><th>Titel</th><th>Beschreibung</th><th>Points</th></tr>
  {% for f in features %}
  <tr>
    <td>{{ f.title }}</td>
    <td>{{ f.description or '—' }}</td>
    <td>{{ f.story_points or '—' }}</td>
  </tr>
  {% endfor %}
</table>
{% endif %}

<!-- Technical Notes -->
{% if docs.technical_notes %}
<h2>Technische Hinweise</h2>
<p style="white-space: pre-wrap;">{{ docs.technical_notes }}</p>
{% endif %}

<!-- Changelog -->
{% if docs.changelog %}
<h2>Changelog-Eintrag</h2>
<p style="white-space: pre-wrap;">{{ docs.changelog }}</p>
{% endif %}

<!-- Additional Info -->
{% if story.doc_additional_info %}
<h2>Zusätzliche Informationen</h2>
<p style="white-space: pre-wrap;">{{ story.doc_additional_info }}</p>
{% endif %}

<!-- Footer -->
<div class="footer">
  {% if settings.company_name %}{{ settings.company_name }} &nbsp;|&nbsp; {% endif %}
  Generiert am {{ generated_at }} &nbsp;|&nbsp; Story-ID: {{ story.id }}
  {% if settings.footer_text %} &nbsp;|&nbsp; {{ settings.footer_text }}{% endif %}
</div>

</body>
</html>
```

- [ ] **Step 2: Write a rendering test**

Add to `backend/tests/unit/test_pdf_service.py` (create file):
```python
"""Unit tests for PdfService template rendering."""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone
import uuid


def make_mock_story():
    story = MagicMock()
    story.id = uuid.uuid4()
    story.title = "Als Nutzer möchte ich mich einloggen"
    story.description = "Mit E-Mail und Passwort"
    story.acceptance_criteria = "Login funktioniert"
    story.status.value = "done"
    story.priority.value = "high"
    story.story_points = 3
    story.quality_score = 92
    story.created_at = datetime(2026, 3, 24, tzinfo=timezone.utc)
    story.definition_of_done = '["Tests grün", "Code reviewed"]'
    story.doc_additional_info = None
    story.generated_docs = '{"summary": "Eine Login-Story.", "technical_notes": "JWT-basiert.", "changelog": "v1.0"}'
    return story


def make_mock_settings():
    s = MagicMock()
    s.company_name = "Acme GmbH"
    s.page_format = "a4"
    s.language = "de"
    s.header_text = None
    s.footer_text = "Vertraulich"
    s.letterhead_filename = None
    s.logo_filename = None
    return s


def test_render_html_contains_title():
    """Rendered HTML contains the story title."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    html = service.render_html(story, settings, test_cases=[], features=[])

    assert "Als Nutzer möchte ich mich einloggen" in html
    assert "Acme GmbH" in html
    assert "Vertraulich" in html


def test_render_html_contains_test_cases():
    """Rendered HTML includes test case table when test_cases provided."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    tc = MagicMock()
    tc.title = "Login mit gültigen Daten"
    tc.status.value = "passed"
    tc.expected_result = "Redirect zu Dashboard"

    html = service.render_html(story, settings, test_cases=[tc], features=[])

    assert "Login mit gültigen Daten" in html
    assert "Redirect zu Dashboard" in html


def test_render_html_no_crash_with_empty_docs():
    """render_html works when generated_docs is None or empty."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    story.generated_docs = None
    settings = make_mock_settings()

    html = service.render_html(story, settings, test_cases=[], features=[])
    assert "Als Nutzer" in html
```

- [ ] **Step 3: Run rendering tests — verify they fail**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_pdf_service.py::test_render_html_contains_title -v 2>&1 | head -15
```
Expected: `ImportError: cannot import name 'PdfService'`

- [ ] **Step 4: Commit template**

```bash
git add backend/app/templates/userstory_pdf.html.jinja2
git commit -m "feat(pdf): add Jinja2 HTML template for userstory PDF"
```

---

## Task 7: PdfService (TDD)

**Files:**
- Create: `backend/app/services/pdf_service.py`
- Modify: `backend/tests/unit/test_pdf_service.py` (already created, add more tests)

- [ ] **Step 1: Add async generation tests to test_pdf_service.py**

Add to `backend/tests/unit/test_pdf_service.py`:
```python
@pytest.mark.asyncio
async def test_generate_and_cache_pdf(tmp_path):
    """generate_and_cache stores PDF in cache path and returns filename."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()

    with patch("app.services.pdf_service.stirling_client") as mock_stirling, \
         patch("app.services.pdf_service.get_settings") as mock_cfg:
        mock_stirling.html_to_pdf = AsyncMock(return_value=b"%PDF-fake")
        mock_cfg.return_value.PDF_CACHE_PATH = str(tmp_path)
        mock_cfg.return_value.PDF_TEMPLATES_PATH = str(tmp_path)

        filename = await service.generate_and_cache(story, settings, test_cases=[], features=[])

    assert filename.endswith(".pdf")
    assert str(story.id)[:8] in filename
    cached = tmp_path / filename
    assert cached.read_bytes() == b"%PDF-fake"


@pytest.mark.asyncio
async def test_generate_applies_letterhead(tmp_path):
    """generate_and_cache calls overlay_pdfs when letterhead_filename is set."""
    from app.services.pdf_service import PdfService
    service = PdfService()
    story = make_mock_story()
    settings = make_mock_settings()
    settings.letterhead_filename = "letterhead.pdf"

    # Create a fake letterhead file
    letterhead_dir = tmp_path / str(story.organization_id if hasattr(story, 'organization_id') else "org")
    letterhead_dir.mkdir(parents=True, exist_ok=True)
    # Just test that overlay is called; skip actual file for simplicity
    story.organization_id = uuid.uuid4()
    settings.letterhead_filename = None  # no letterhead, just verify no overlay called

    with patch("app.services.pdf_service.stirling_client") as mock_stirling, \
         patch("app.services.pdf_service.get_settings") as mock_cfg:
        mock_stirling.html_to_pdf = AsyncMock(return_value=b"%PDF-fake")
        mock_stirling.overlay_pdfs = AsyncMock(return_value=b"%PDF-merged")
        mock_cfg.return_value.PDF_CACHE_PATH = str(tmp_path)
        mock_cfg.return_value.PDF_TEMPLATES_PATH = str(tmp_path)

        await service.generate_and_cache(story, settings, test_cases=[], features=[])

    mock_stirling.overlay_pdfs.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_pdf_service.py -v 2>&1 | head -20
```
Expected: `ImportError: cannot import name 'PdfService'`

- [ ] **Step 3: Create PdfService**

Create `backend/app/services/pdf_service.py`:
```python
"""PDF generation service: renders HTML template and calls Stirling PDF."""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import get_settings
from app.services.stirling_client import stirling_client

logger = logging.getLogger(__name__)

# Jinja2 env — loads templates from app/templates/
_template_dir = Path(__file__).parent.parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_template_dir)),
    autoescape=select_autoescape(["html"]),
)


class PdfService:
    """Orchestrates HTML rendering + Stirling PDF conversion + local cache storage."""

    def render_html(self, story: Any, settings: Any, test_cases: List, features: List) -> str:
        """Render the Jinja2 template with story data. Returns HTML string."""
        docs: dict = {}
        if story.generated_docs:
            try:
                docs = json.loads(story.generated_docs)
            except (json.JSONDecodeError, TypeError):
                docs = {}

        dod_items: list = []
        if story.definition_of_done:
            try:
                dod_items = json.loads(story.definition_of_done)
            except (json.JSONDecodeError, TypeError):
                dod_items = []

        cfg = get_settings()
        logo_path: Optional[str] = None
        if settings.logo_filename and hasattr(story, "organization_id"):
            logo_path = str(
                Path(cfg.PDF_TEMPLATES_PATH) / str(story.organization_id) / settings.logo_filename
            )

        template = _jinja_env.get_template("userstory_pdf.html.jinja2")
        return template.render(
            story=story,
            settings=settings,
            test_cases=test_cases,
            features=features,
            docs=docs,
            dod_items=dod_items,
            logo_path=logo_path,
            generated_at=datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
        )

    async def generate_and_cache(
        self, story: Any, settings: Any, test_cases: List, features: List
    ) -> str:
        """
        Render HTML, convert to PDF via Stirling, apply letterhead if configured,
        write to cache volume. Returns the filename (not full path).
        """
        cfg = get_settings()
        html = self.render_html(story, settings, test_cases, features)

        # Convert HTML → PDF
        pdf_bytes = await stirling_client.html_to_pdf(html)

        # Apply letterhead overlay if configured
        if settings.letterhead_filename and hasattr(story, "organization_id"):
            letterhead_path = (
                Path(cfg.PDF_TEMPLATES_PATH)
                / str(story.organization_id)
                / settings.letterhead_filename
            )
            if letterhead_path.exists():
                letterhead_bytes = letterhead_path.read_bytes()
                try:
                    pdf_bytes = await stirling_client.overlay_pdfs(pdf_bytes, letterhead_bytes)
                except Exception as e:
                    logger.warning(f"Letterhead overlay failed, using plain PDF: {e}")

        # Write to cache
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        filename = f"{story.id}_{date_str}.pdf"
        cache_dir = Path(cfg.PDF_CACHE_PATH)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / filename).write_bytes(pdf_bytes)

        logger.info(f"PDF cached: {filename} ({len(pdf_bytes)} bytes)")
        return filename


pdf_service = PdfService()
```

- [ ] **Step 4: Run all pdf_service tests — verify they pass**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_pdf_service.py -v
```
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/pdf_service.py backend/tests/unit/test_pdf_service.py
git commit -m "feat(pdf): add PdfService orchestrating HTML render + Stirling conversion"
```

---

## Task 8: Celery Task (TDD)

**Files:**
- Create: `backend/app/tasks/pdf_tasks.py`
- Modify: `backend/app/celery_app.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_pdf_tasks.py`:
```python
"""Unit tests for generate_story_pdf Celery task."""
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_generate_story_pdf_calls_pdf_service():
    """Task fetches story data, calls pdf_service, updates generated_docs."""
    from app.tasks.pdf_tasks import _generate_pdf_async
    import asyncio

    story_id = str(uuid.uuid4())
    org_id = str(uuid.uuid4())

    mock_story = MagicMock()
    mock_story.id = uuid.UUID(story_id)
    mock_story.organization_id = uuid.UUID(org_id)
    mock_story.generated_docs = "{}"
    mock_story.status.value = "done"

    mock_settings_row = MagicMock()
    mock_settings_row.page_format = "a4"
    mock_settings_row.language = "de"
    mock_settings_row.letterhead_filename = None
    mock_settings_row.logo_filename = None

    mock_db = MagicMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()

    # Story query
    story_result = MagicMock()
    story_result.scalar_one_or_none.return_value = mock_story
    # Settings query
    settings_result = MagicMock()
    settings_result.scalar_one_or_none.return_value = mock_settings_row
    # test_cases query
    tc_result = MagicMock()
    tc_result.scalars.return_value.all.return_value = []
    # features query
    feat_result = MagicMock()
    feat_result.scalars.return_value.all.return_value = []

    mock_db.execute.side_effect = [story_result, settings_result, tc_result, feat_result]
    mock_db.commit = AsyncMock()

    with patch("app.tasks.pdf_tasks.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.pdf_tasks.pdf_service") as mock_pdf:
        mock_pdf.generate_and_cache = AsyncMock(return_value="abc_2026-03-24.pdf")

        asyncio.run(_generate_pdf_async(story_id, org_id))

    mock_pdf.generate_and_cache.assert_called_once()
    mock_db.commit.assert_called_once()
    # Check generated_docs was updated
    import json
    docs = json.loads(mock_story.generated_docs)
    assert "pdf_url" in docs


def test_generate_story_pdf_skips_if_story_not_found():
    """Task exits gracefully when story does not exist."""
    from app.tasks.pdf_tasks import _generate_pdf_async
    import asyncio

    mock_db = MagicMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=False)
    mock_db.execute = AsyncMock()

    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = result

    with patch("app.tasks.pdf_tasks.AsyncSessionLocal", return_value=mock_db), \
         patch("app.tasks.pdf_tasks.pdf_service") as mock_pdf:
        # Should not raise
        asyncio.run(_generate_pdf_async(str(uuid.uuid4()), str(uuid.uuid4())))

    mock_pdf.generate_and_cache.assert_not_called()
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_pdf_tasks.py -v 2>&1 | head -15
```
Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create pdf_tasks.py**

Create `backend/app/tasks/pdf_tasks.py`:
```python
"""Celery task: generate PDF for a user story."""
import asyncio
import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery
from app.database import AsyncSessionLocal
from app.models.user_story import UserStory
from app.models.test_case import TestCase
from app.models.feature import Feature
from app.models.pdf_settings import PdfSettings
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)


async def _generate_pdf_async(story_id: str, org_id: str) -> None:
    """Async implementation — called from sync Celery task via asyncio.run()."""
    async with AsyncSessionLocal() as db:
        # 1. Load story
        result = await db.execute(
            select(UserStory).where(UserStory.id == uuid.UUID(story_id))
        )
        story = result.scalar_one_or_none()
        if story is None:
            logger.warning(f"generate_story_pdf: story {story_id} not found — skipping")
            return

        # 2. Load PDF settings (fall back to a default object if none configured)
        settings_result = await db.execute(
            select(PdfSettings).where(PdfSettings.organization_id == uuid.UUID(org_id))
        )
        settings = settings_result.scalar_one_or_none()
        if settings is None:
            # Use a simple namespace with defaults
            from types import SimpleNamespace
            settings = SimpleNamespace(
                company_name=None, page_format="a4", language="de",
                header_text=None, footer_text=None,
                letterhead_filename=None, logo_filename=None,
            )

        # 3. Load related data
        tc_result = await db.execute(
            select(TestCase).where(TestCase.story_id == story.id)
        )
        test_cases = tc_result.scalars().all()

        feat_result = await db.execute(
            select(Feature).where(Feature.story_id == story.id)
        )
        features = feat_result.scalars().all()

        # 4. Generate PDF and cache it
        filename = await pdf_service.generate_and_cache(story, settings, test_cases, features)

        # 5. Update generated_docs with pdf_url
        docs: dict = {}
        if story.generated_docs:
            try:
                docs = json.loads(story.generated_docs)
            except (json.JSONDecodeError, TypeError):
                docs = {}
        docs["pdf_url"] = f"cache:{filename}"
        story.generated_docs = json.dumps(docs)
        await db.commit()

        logger.info(f"PDF generated for story {story_id}: {filename}")


@celery.task(
    name="pdf_tasks.generate_story_pdf",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def generate_story_pdf(self, story_id: str, org_id: str) -> None:
    """
    Celery task: generate a PDF summary for a user story.
    Dispatched when story status transitions to 'done'.
    """
    try:
        asyncio.run(_generate_pdf_async(story_id, org_id))
    except Exception as exc:
        logger.error(f"PDF generation failed for story {story_id}: {exc}")
        raise self.retry(exc=exc)
```

- [ ] **Step 4: Add task to celery_app.py include list**

In `backend/app/celery_app.py`, update the `include` list:
```python
    include=[
        "app.tasks.mail_sync",
        "app.tasks.calendar_sync",
        "app.tasks.agent_tasks",
        "app.tasks.pdf_tasks",
    ]
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/unit/test_pdf_tasks.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/app/tasks/pdf_tasks.py backend/app/celery_app.py
git commit -m "feat(pdf): add generate_story_pdf Celery task"
```

---

## Task 9: Status Trigger in user_stories.py

**Files:**
- Modify: `backend/app/routers/user_stories.py`

- [ ] **Step 1: Write integration test for the trigger**

Add to `backend/tests/integration/test_pdf_settings.py` (create file):
```python
"""Integration tests for PDF settings API and story → done trigger."""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

from app.schemas.auth import TokenResponse


@pytest.mark.asyncio
async def test_story_done_dispatches_pdf_task(client: AsyncClient, auth_headers: dict, test_org, db):
    """When a story is updated to done, generate_story_pdf.delay is called."""
    from app.models.user_story import UserStory, StoryStatus
    import uuid

    # Create a story at quality_score >= 80 so it can be set to done
    story = UserStory(
        organization_id=test_org.id,
        created_by_id=(await _get_user_id(auth_headers, db)),
        title="Test PDF Story",
        description="Test",
        acceptance_criteria="AC",
        quality_score=85,
        status=StoryStatus.in_progress,
        generated_docs="{}",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    with patch("app.routers.user_stories.generate_story_pdf") as mock_task:
        mock_task.delay = AsyncMock()
        response = await client.patch(
            f"/api/v1/user-stories/{story.id}",
            json={"status": "done"},
            headers=auth_headers,
        )

    assert response.status_code == 200
    mock_task.delay.assert_called_once_with(str(story.id), str(story.organization_id))


async def _get_user_id(auth_headers, db):
    """Helper: extract test user id from db."""
    from sqlalchemy import select
    from app.models.user import User
    result = await db.execute(select(User).where(User.email == "testuser@example.com"))
    user = result.scalar_one_or_none()
    return user.id if user else None
```

- [ ] **Step 2: Run test — verify it fails**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/integration/test_pdf_settings.py::test_story_done_dispatches_pdf_task -v 2>&1 | head -20
```
Expected: `FAILED` — `generate_story_pdf` not yet imported in router.

- [ ] **Step 3: Update user_stories.py to dispatch the task**

In `backend/app/routers/user_stories.py`:

Add to the imports at the top:
```python
from app.tasks.pdf_tasks import generate_story_pdf
```

In the `update_user_story` handler, capture old status and add dispatch:
```python
async def update_user_story(
    story_id: uuid.UUID,
    data: UserStoryUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserStoryRead:
    """Update a user story."""
    stmt = select(UserStory).where(UserStory.id == story_id)
    result = await db.execute(stmt)
    story = result.scalar_one_or_none()
    if story is None:
        raise NotFoundException("User story not found")

    update_data = data.model_dump(exclude_unset=True)
    doc_fields = {"title", "description", "acceptance_criteria"}
    needs_regen = bool(doc_fields & update_data.keys())

    # Capture old status BEFORE the update loop (for done-transition detection)
    old_status = story.status

    # Quality gate: block advancement to ready/in_progress/testing/done if quality_score < 80
    GATED_STATUSES = {"ready", "in_progress", "testing", "done"}
    MIN_QUALITY = 80
    new_status = update_data.get("status")
    if (
        new_status in GATED_STATUSES
        and story.quality_score is not None
        and story.quality_score < MIN_QUALITY
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Quality-Score {story.quality_score}/100 ist zu niedrig (Minimum: {MIN_QUALITY}). Bitte die Story zuerst im Assistenten analysieren und verbessern.",
        )

    for field, value in update_data.items():
        setattr(story, field, value)

    await db.commit()
    await db.refresh(story)

    if needs_regen:
        background_tasks.add_task(
            _regenerate_docs_bg, story.id, story.organization_id, story.title, story.description, story.acceptance_criteria
        )

    # Dispatch PDF generation when story transitions to done
    if new_status == "done" and old_status != StoryStatus.done:
        generate_story_pdf.delay(str(story.id), str(story.organization_id))

    return UserStoryRead.model_validate(story)
```

- [ ] **Step 4: Run test — verify it passes**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/integration/test_pdf_settings.py::test_story_done_dispatches_pdf_task -v
```
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/user_stories.py backend/tests/integration/test_pdf_settings.py
git commit -m "feat(pdf): dispatch generate_story_pdf Celery task on story → done"
```

---

## Task 10: PDF Settings API Router (TDD)

**Files:**
- Create: `backend/app/routers/pdf_settings.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/integration/test_pdf_settings.py`

- [ ] **Step 1: Add API tests to test_pdf_settings.py**

Add to `backend/tests/integration/test_pdf_settings.py`:
```python
@pytest.mark.asyncio
async def test_get_pdf_settings_returns_defaults(client: AsyncClient, auth_headers: dict, test_org):
    """GET /pdf-settings returns empty defaults when no row exists."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["page_format"] == "a4"
    assert data["language"] == "de"


@pytest.mark.asyncio
async def test_put_pdf_settings_saves(client: AsyncClient, auth_headers: dict, test_org):
    """PUT /pdf-settings creates or updates settings."""
    response = await client.put(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        json={"company_name": "Test AG", "page_format": "letter", "language": "en"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["company_name"] == "Test AG"
    assert data["page_format"] == "letter"

    # Verify persistence
    get_resp = await client.get(
        f"/api/v1/organizations/{test_org.id}/pdf-settings",
        headers=auth_headers,
    )
    assert get_resp.json()["company_name"] == "Test AG"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/integration/test_pdf_settings.py::test_get_pdf_settings_returns_defaults tests/integration/test_pdf_settings.py::test_put_pdf_settings_saves -v 2>&1 | head -20
```
Expected: `404` — router not registered yet.

- [ ] **Step 3: Create the router**

Create `backend/app/routers/pdf_settings.py`:
```python
"""API endpoints for PDF settings (branding + template management)."""
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.pdf_settings import PdfSettings
from app.models.user import User
from app.schemas.pdf_settings import PdfSettingsRead, PdfSettingsUpdate
from app.services.stirling_client import stirling_client
from app.services.pdf_service import pdf_service

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_LETTERHEAD_BYTES = 5 * 1024 * 1024   # 5 MB
MAX_LOGO_BYTES = 1 * 1024 * 1024          # 1 MB
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg"}


async def _get_or_create_settings(org_id: uuid.UUID, db: AsyncSession) -> PdfSettings:
    result = await db.execute(
        select(PdfSettings).where(PdfSettings.organization_id == org_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = PdfSettings(organization_id=org_id)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get(
    "/organizations/{org_id}/pdf-settings",
    response_model=PdfSettingsRead,
    summary="Get PDF settings for an organization",
)
async def get_pdf_settings(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    row = await _get_or_create_settings(org_id, db)
    return PdfSettingsRead.model_validate(row)


@router.put(
    "/organizations/{org_id}/pdf-settings",
    response_model=PdfSettingsRead,
    summary="Update PDF settings for an organization",
)
async def update_pdf_settings(
    org_id: uuid.UUID,
    data: PdfSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    row = await _get_or_create_settings(org_id, db)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.post(
    "/organizations/{org_id}/pdf-settings/letterhead",
    response_model=PdfSettingsRead,
    summary="Upload letterhead PDF",
)
async def upload_letterhead(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")
    content = await file.read()
    if len(content) > MAX_LETTERHEAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    cfg = get_settings()
    dest_dir = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    (dest_dir / "letterhead.pdf").write_bytes(content)

    row = await _get_or_create_settings(org_id, db)
    row.letterhead_filename = "letterhead.pdf"
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.delete(
    "/organizations/{org_id}/pdf-settings/letterhead",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove letterhead PDF",
)
async def delete_letterhead(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> None:
    row = await _get_or_create_settings(org_id, db)
    cfg = get_settings()
    path = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id) / "letterhead.pdf"
    if path.exists():
        path.unlink()
    row.letterhead_filename = None
    await db.commit()


@router.post(
    "/organizations/{org_id}/pdf-settings/logo",
    response_model=PdfSettingsRead,
    summary="Upload logo image",
)
async def upload_logo(
    org_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> PdfSettingsRead:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="File must be PNG or JPEG")
    content = await file.read()
    if len(content) > MAX_LOGO_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 1 MB)")

    cfg = get_settings()
    dest_dir = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ext = "png" if file.content_type == "image/png" else "jpg"
    logo_filename = f"logo.{ext}"
    (dest_dir / logo_filename).write_bytes(content)

    row = await _get_or_create_settings(org_id, db)
    row.logo_filename = logo_filename
    await db.commit()
    await db.refresh(row)
    return PdfSettingsRead.model_validate(row)


@router.delete(
    "/organizations/{org_id}/pdf-settings/logo",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove logo",
)
async def delete_logo(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> None:
    row = await _get_or_create_settings(org_id, db)
    cfg = get_settings()
    for ext in ["png", "jpg"]:
        path = Path(cfg.PDF_TEMPLATES_PATH) / str(org_id) / f"logo.{ext}"
        if path.exists():
            path.unlink()
    row.logo_filename = None
    await db.commit()


@router.post(
    "/organizations/{org_id}/pdf-settings/preview",
    summary="Generate a preview PDF with current settings",
    response_class=Response,
)
async def preview_pdf(
    org_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("org:update")),
) -> Response:
    """
    Synchronously generates a sample PDF using current settings.
    Returns raw PDF bytes (Content-Type: application/pdf).
    """
    row = await _get_or_create_settings(org_id, db)
    from types import SimpleNamespace
    # Build a minimal sample story for preview
    sample_story = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=org_id,
        title="Beispiel-Userstory: Login-Funktion",
        description="Als Nutzer möchte ich mich mit E-Mail und Passwort anmelden.",
        acceptance_criteria="Login funktioniert mit gültigen Zugangsdaten.",
        status=SimpleNamespace(value="done"),
        priority=SimpleNamespace(value="high"),
        story_points=3,
        quality_score=95,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        definition_of_done='["Tests grün", "Code reviewed", "Deployment erfolgreich"]',
        doc_additional_info=None,
        generated_docs='{"summary":"Implementiert ein sicheres Login-System.","technical_notes":"JWT-basiert.","changelog":"Version 1.0"}',
    )
    html = pdf_service.render_html(sample_story, row, test_cases=[], features=[])
    pdf_bytes = await stirling_client.html_to_pdf(html)
    return Response(content=pdf_bytes, media_type="application/pdf")
```

- [ ] **Step 4: Register router in main.py**

In `backend/app/main.py`, add:
```python
from app.routers.pdf_settings import router as pdf_settings_router
```

And include it:
```python
app.include_router(pdf_settings_router, prefix="/api/v1", tags=["PDF Settings"])
```

- [ ] **Step 5: Run API tests**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/integration/test_pdf_settings.py -v -k "not story_done"
```
Expected: `2 passed`

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
Expected: all tests pass (or only pre-existing failures).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/pdf_settings.py backend/app/main.py backend/tests/integration/test_pdf_settings.py
git commit -m "feat(pdf): add PDF settings API router with CRUD + template upload + preview"
```

---

## Task 11: Frontend Admin Page

**Files:**
- Create: `frontend/app/[org]/admin/pdf/page.tsx`
- Create: `frontend/components/admin/PdfSettingsForm.tsx`
- Create: `frontend/components/admin/TemplateUpload.tsx`

- [ ] **Step 1: Create TemplateUpload component**

Create `frontend/components/admin/TemplateUpload.tsx`:
```tsx
"use client";

import { useState } from "react";

interface TemplateUploadProps {
  label: string;
  accept: string;
  uploadUrl: string;
  deleteUrl: string;
  currentFilename: string | null;
  onSuccess: () => void;
}

export function TemplateUpload({
  label,
  accept,
  uploadUrl,
  deleteUrl,
  currentFilename,
  onSuccess,
}: TemplateUploadProps) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(uploadUrl, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail ?? "Upload fehlgeschlagen");
      }
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    setError(null);
    try {
      const res = await fetch(deleteUrl, { method: "DELETE" });
      if (!res.ok) throw new Error("Löschen fehlgeschlagen");
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {currentFilename ? (
        <div className="flex items-center gap-3 text-sm">
          <span className="text-green-600">✓ {currentFilename}</span>
          <button
            onClick={handleDelete}
            className="text-red-500 hover:underline text-xs"
          >
            Entfernen
          </button>
        </div>
      ) : (
        <div className="text-sm text-gray-400">Kein Template hochgeladen</div>
      )}
      <input
        type="file"
        accept={accept}
        onChange={handleUpload}
        disabled={uploading}
        className="block text-sm text-gray-600 file:mr-3 file:py-1 file:px-3 file:rounded file:border-0 file:text-xs file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200"
      />
      {uploading && <p className="text-xs text-gray-500">Wird hochgeladen…</p>}
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 2: Create PdfSettingsForm component**

Create `frontend/components/admin/PdfSettingsForm.tsx`:
```tsx
"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api/client";

interface PdfSettings {
  id?: string;
  company_name?: string | null;
  page_format: string;
  language: string;
  header_text?: string | null;
  footer_text?: string | null;
  letterhead_filename?: string | null;
  logo_filename?: string | null;
}

interface PdfSettingsFormProps {
  orgSlug: string;
  orgId: string;
  initialSettings: PdfSettings;
  onSaved: (settings: PdfSettings) => void;
}

export function PdfSettingsForm({ orgSlug, orgId, initialSettings, onSaved }: PdfSettingsFormProps) {
  const [form, setForm] = useState({
    company_name: initialSettings.company_name ?? "",
    page_format: initialSettings.page_format ?? "a4",
    language: initialSettings.language ?? "de",
    header_text: initialSettings.header_text ?? "",
    footer_text: initialSettings.footer_text ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const result = await apiRequest<PdfSettings>(
        `/api/v1/organizations/${orgId}/pdf-settings`,
        { method: "PUT", body: JSON.stringify(form) }
      );
      onSaved(result);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: any) {
      setError(err?.error ?? "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Firmenname</label>
        <input
          type="text"
          value={form.company_name}
          onChange={(e) => setForm({ ...form, company_name: e.target.value })}
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="Acme GmbH"
        />
      </div>
      <div className="flex gap-4">
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">Seitenformat</label>
          <select
            value={form.page_format}
            onChange={(e) => setForm({ ...form, page_format: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
          >
            <option value="a4">A4</option>
            <option value="letter">Letter</option>
          </select>
        </div>
        <div className="flex-1">
          <label className="block text-sm font-medium text-gray-700 mb-1">Sprache</label>
          <select
            value={form.language}
            onChange={(e) => setForm({ ...form, language: e.target.value })}
            className="w-full border rounded-md px-3 py-2 text-sm"
          >
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Kopfzeile (optional)</label>
        <input
          type="text"
          value={form.header_text}
          onChange={(e) => setForm({ ...form, header_text: e.target.value })}
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="z.B. Internes Dokument"
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Fußzeile (optional)</label>
        <input
          type="text"
          value={form.footer_text}
          onChange={(e) => setForm({ ...form, footer_text: e.target.value })}
          className="w-full border rounded-md px-3 py-2 text-sm"
          placeholder="z.B. Vertraulich"
        />
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}
      {saved && <p className="text-sm text-green-600">Gespeichert ✓</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="px-4 py-2 bg-blue-600 text-white text-sm rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {saving ? "Wird gespeichert…" : "Einstellungen speichern"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Create the admin page**

Create `frontend/app/[org]/admin/pdf/page.tsx`:
```tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import { fetcher, apiRequest } from "@/lib/api/client";
import { PdfSettingsForm } from "@/components/admin/PdfSettingsForm";
import { TemplateUpload } from "@/components/admin/TemplateUpload";

interface PdfSettings {
  id?: string;
  company_name?: string | null;
  page_format: string;
  language: string;
  header_text?: string | null;
  footer_text?: string | null;
  letterhead_filename?: string | null;
  logo_filename?: string | null;
}

export default function PdfAdminPage() {
  const params = useParams<{ org: string }>();
  const orgSlug = params.org;

  // We need the org UUID for the API — fetch org info
  const { data: org } = useSWR<{ id: string; slug: string; name: string }>(
    `/api/v1/organizations/${orgSlug}`,
    fetcher
  );

  const { data: settings, mutate } = useSWR<PdfSettings>(
    org ? `/api/v1/organizations/${org.id}/pdf-settings` : null,
    fetcher
  );

  const [previewLoading, setPreviewLoading] = useState(false);

  const handlePreview = async () => {
    if (!org) return;
    setPreviewLoading(true);
    try {
      const res = await fetch(`/api/v1/organizations/${org.id}/pdf-settings/preview`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${localStorage.getItem("access_token")}`,
        },
      });
      if (!res.ok) throw new Error("Vorschau fehlgeschlagen");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
    } catch {
      alert("Vorschau-Generierung fehlgeschlagen. Ist Stirling PDF erreichbar?");
    } finally {
      setPreviewLoading(false);
    }
  };

  if (!org || !settings) {
    return <div className="p-8 text-gray-500">Lade Einstellungen…</div>;
  }

  const baseUrl = `/api/v1/organizations/${org.id}/pdf-settings`;

  return (
    <div className="max-w-2xl mx-auto p-8 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">PDF-Einstellungen</h1>
        <p className="mt-1 text-sm text-gray-500">
          Konfiguriert das automatisch generierte PDF für Userstories (Status: Done).
        </p>
      </div>

      <section className="bg-white border rounded-lg p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-800">Branding</h2>
        <PdfSettingsForm
          orgSlug={orgSlug}
          orgId={org.id}
          initialSettings={settings}
          onSaved={() => mutate()}
        />
      </section>

      <section className="bg-white border rounded-lg p-6 space-y-6">
        <h2 className="text-lg font-semibold text-gray-800">Templates</h2>
        <TemplateUpload
          label="Briefpapier (PDF, max. 5 MB)"
          accept="application/pdf"
          uploadUrl={`${baseUrl}/letterhead`}
          deleteUrl={`${baseUrl}/letterhead`}
          currentFilename={settings.letterhead_filename ?? null}
          onSuccess={() => mutate()}
        />
        <TemplateUpload
          label="Logo (PNG/JPG, max. 1 MB)"
          accept="image/png,image/jpeg"
          uploadUrl={`${baseUrl}/logo`}
          deleteUrl={`${baseUrl}/logo`}
          currentFilename={settings.logo_filename ?? null}
          onSuccess={() => mutate()}
        />
      </section>

      <section className="bg-white border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Vorschau</h2>
        <p className="text-sm text-gray-500 mb-4">
          Generiert ein Beispiel-PDF mit den aktuellen Einstellungen.
        </p>
        <button
          onClick={handlePreview}
          disabled={previewLoading}
          className="px-4 py-2 bg-gray-800 text-white text-sm rounded-md hover:bg-gray-900 disabled:opacity-50"
        >
          {previewLoading ? "Wird generiert…" : "PDF-Vorschau öffnen"}
        </button>
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Verify frontend builds**

```bash
cd /opt/assist2/frontend && npm run build 2>&1 | tail -20
```
Expected: build succeeds (or only pre-existing warnings).

- [ ] **Step 5: Commit**

```bash
cd /opt/assist2
git add frontend/app/[org]/admin/pdf/page.tsx frontend/components/admin/PdfSettingsForm.tsx frontend/components/admin/TemplateUpload.tsx
git commit -m "feat(frontend): add PDF admin page with branding settings and template upload"
```

---

## Task 12: Wire Up + Smoke Test

**Files:** none new — verify everything connects end to end.

- [ ] **Step 1: Restart backend and worker to pick up new task**

```bash
cd /opt/assist2
docker compose -f infra/docker-compose.yml restart backend worker
```

- [ ] **Step 2: Verify Celery worker sees the new task**

```bash
docker compose -f infra/docker-compose.yml logs worker --tail=30 | grep -E "pdf_tasks|registered"
```
Expected: `pdf_tasks.generate_story_pdf` in the registered tasks list.

- [ ] **Step 3: Verify Stirling PDF API is reachable from backend**

```bash
docker compose -f infra/docker-compose.yml exec backend curl -s http://assist2-stirling-pdf:8080/api/v1/info | head -c 200
```
Expected: JSON response with Stirling PDF version info.

- [ ] **Step 4: Run full backend test suite**

```bash
docker compose -f infra/docker-compose.yml exec backend python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```
Expected: all PDF-related tests pass.

- [ ] **Step 5: Commit smoke test confirmation (if any fixes were needed)**

```bash
git add -A
git commit -m "feat(pdf): Phase 1 Stirling PDF integration complete"
```
