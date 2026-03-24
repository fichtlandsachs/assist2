# Stirling PDF — Userstory Export Design

**Date:** 2026-03-24
**Status:** Approved
**Integrates with:** P1 (Authentik), P2 (Nextcloud + SSO), P3 (Nextcloud Plugin)

---

## Overview

Add Stirling PDF as an internal Docker service. When a user story transitions to `done`, a Celery background task automatically generates a structured PDF summary of all story contents and stores it in Nextcloud under `Userstories_generated/{story_id}_{YYYY-MM-DD}.pdf`. Org admins configure branding and templates via a dedicated admin page in the Assist2 platform.

---

## Goals

- Automatic PDF generation on story `done` — no user action required
- Admin-configurable branding (logo, letterhead, company name, format, language)
- Storage in Nextcloud (activated after P2 completion)
- No external exposure of Stirling PDF — internal service only
- Graceful degradation: works without Nextcloud (local cache), works without org settings (defaults)

---

## Non-Goals

- No manual PDF export button for regular users
- No per-user PDF configuration
- No real-time PDF preview in the story detail view (Phase 3 only)
- No external Stirling PDF UI accessible to users (admin-only)

---

## Architecture

### Components

```
Assist2 Platform
  ├── Frontend: /[org]/admin/pdf  (admin branding + template upload)
  ├── Backend:
  │     ├── app/routers/pdf_settings.py     (CRUD + file upload endpoints)
  │     ├── app/services/stirling_client.py  (Stirling PDF REST API client)
  │     ├── app/services/pdf_service.py      (orchestrates render → convert → store)
  │     ├── app/models/pdf_settings.py       (ORM: pdf_settings table)
  │     ├── app/schemas/pdf_settings.py      (Pydantic request/response schemas)
  │     ├── app/tasks/pdf_tasks.py           (Celery task: generate_story_pdf)
  │     └── app/templates/userstory_pdf.html.jinja2
  └── Infrastructure:
        ├── Docker: assist2-stirling-pdf (internal only, port 8080)
        └── Volume: assist2_pdf_templates + assist2_pdf_cache
```

### Docker Service

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

Volume mounts:
- `assist2_pdf_templates` → `/app/pdf_templates` — per-org template files (`{org_id}/letterhead.pdf`, `{org_id}/logo.png`)
- `assist2_pdf_cache` → `/app/pdf_cache` — locally cached generated PDFs before Nextcloud is available

Not exposed via Traefik — only reachable by the backend over the `internal` network.

---

## Data Model

### New Table: `pdf_settings`

```sql
CREATE TABLE pdf_settings (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id     UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
  company_name        VARCHAR(255),
  page_format         VARCHAR(10) NOT NULL DEFAULT 'a4',  -- 'a4' | 'letter'
  language            VARCHAR(10) NOT NULL DEFAULT 'de',   -- 'de' | 'en'
  header_text         VARCHAR(500),
  footer_text         VARCHAR(500),
  letterhead_filename VARCHAR(255),  -- stored at /app/pdf_templates/{org_id}/letterhead.pdf
  logo_filename       VARCHAR(255),  -- stored at /app/pdf_templates/{org_id}/logo.png
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Template files are stored on a Docker volume at `/app/pdf_templates/{org_id}/`, not in the database.

### Modified: `user_stories.generated_docs`

The existing JSON field gains a new key:
```json
{
  "summary": "...",
  "changelog": "...",
  "pdf_outline": [...],
  "technical_notes": "...",
  "pdf_url": "Userstories_generated/abc123_2026-03-24.pdf"
}
```

---

## API Endpoints

All under `/api/v1/organizations/{org_id}/pdf-settings`. Require `org:update` permission (org owner/admin only).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/pdf-settings` | Load current settings |
| `PUT` | `/pdf-settings` | Save settings (company_name, page_format, language, header_text, footer_text) |
| `POST` | `/pdf-settings/letterhead` | Upload letterhead PDF (multipart, max 5 MB) |
| `DELETE` | `/pdf-settings/letterhead` | Remove letterhead |
| `POST` | `/pdf-settings/logo` | Upload logo (PNG/JPG, max 1 MB) |
| `DELETE` | `/pdf-settings/logo` | Remove logo |
| `POST` | `/pdf-settings/preview` | Generate and return a sample PDF (returns PDF bytes, Content-Type: application/pdf) |

---

## PDF Generation Flow

### Trigger Point

Status changes are handled directly in `backend/app/routers/user_stories.py` in the `update_user_story` PATCH handler. After persisting the update, the handler checks if `status` transitioned to `"done"` and, if so, dispatches the Celery task:

```python
# In update_user_story (routers/user_stories.py)
# Capture old status BEFORE the setattr update loop:
old_status = story.status

# ... existing update loop (setattr / db.commit) ...

# After db.commit(), dispatch if status just transitioned to done:
if data.status == UserStoryStatus.done and old_status != UserStoryStatus.done:
    generate_story_pdf.delay(str(story.id), str(story.organization_id))
```

This is an intentional switch from the existing `BackgroundTasks` pattern used for `_regenerate_docs_bg` to Celery `.delay()`, because PDF generation requires retry semantics. The task module must be added to `celery_app.py`'s `include` list (see Modified Files).

### `generated_docs` is a JSON String

The ORM column `user_stories.generated_docs` is `Mapped[Optional[str]]` — a JSON-serialized string, not a dict. All reads/writes follow this pattern (as used in `routers/user_stories.py`):

```python
docs = json.loads(story.generated_docs or "{}")
docs["pdf_url"] = "Userstories_generated/..."
story.generated_docs = json.dumps(docs)
await db.commit()
```

The Celery task must follow this same pattern when writing `pdf_url`.

### Task Flow

```
PATCH /user-stories/{id}  (status → done)
  → update_user_story router handler detects status transition
  → generate_story_pdf.delay(story_id, org_id)

Celery Task: generate_story_pdf(story_id, org_id)
  1. Load story + test_cases + features from DB
  2. Parse generated_docs: docs = json.loads(story.generated_docs or "{}")
  3. Load pdf_settings for org_id (fallback to defaults if not set)
  4. Render Jinja2 template → HTML string
  5. POST HTML to Stirling PDF /api/v1/misc/html-to-pdf → PDF bytes
  6. If letterhead configured:
       POST [generated.pdf, letterhead.pdf] to /api/v1/general/overlay-pdfs → final PDF
  7. Determine storage:
       Phase 1 (Nextcloud not yet set up):
         Write PDF to /app/pdf_cache/{story_id}_{date}.pdf
         docs["pdf_url"] = "cache:{story_id}_{date}.pdf"
       Phase 2+ (Nextcloud available, NEXTCLOUD_URL set in settings):
         WebDAV PUT → /Userstories_generated/{story_id}_{date}.pdf
         docs["pdf_url"] = "Userstories_generated/{story_id}_{date}.pdf"
  8. story.generated_docs = json.dumps(docs)
     await db.commit()
```

**Note on Phase 1 → Phase 2 migration of cached PDFs:** PDFs written to the local cache during Phase 1 are not automatically re-uploaded when Nextcloud becomes available. A one-time migration script (similar to `migrate_to_authentik.py`) will be provided in Phase 2 to upload cached PDFs to Nextcloud and update `pdf_url` values. No automatic retry-on-update mechanism is implemented.

### Preview Endpoint

`POST /pdf-settings/preview` calls `StirlingPDFClient` **synchronously** (direct `httpx` call in the router handler, not via Celery) and returns the PDF bytes as `application/pdf`. This is acceptable for a low-frequency admin operation.

---

## PDF Template Structure

`backend/app/templates/userstory_pdf.html.jinja2` — rendered with:
- `story`: UserStory ORM object
- `settings`: PdfSettings ORM object (or defaults)
- `test_cases`: list of TestCase
- `features`: list of Feature
- `docs`: parsed generated_docs dict

**Sections:**
1. **Cover Page** — logo (top right), company name, story title, status badge, priority, story points, created date
2. **Summary** — `docs.summary` (2–3 sentences)
3. **Description & Acceptance Criteria** — raw text + bulleted list
4. **Definition of Done** — checkboxes grouped by category
5. **Test Cases** — table: title / steps / expected result / status
6. **Features** — list with title, description, story points
7. **Technical Notes** — `docs.technical_notes`
8. **Changelog Entry** — `docs.changelog`
9. **Footer** — org name, generation date, footer_text (e.g. "Vertraulich")

---

## Error Handling

| Failure | Behavior |
|---------|----------|
| Stirling PDF unreachable | Celery retry ×3, 60 s apart; after 3 failures: log error at ERROR level, story stays `done`, no PDF |
| Nextcloud unreachable (Phase 2+) | PDF saved to local cache volume; manual migration script in Phase 2 handles re-upload |
| HTML render error | Task fails immediately; error logged via Python `logger.error()` |
| No `pdf_settings` for org | Defaults used (A4, German, no logo/letterhead) — always functional |
| PDF already exists in Nextcloud | Overwritten (latest version wins) |

---

## Rollout Phases

### Phase 1 — Now (added to P1 implementation)
- Stirling PDF Docker container
- `pdf_settings` migration + ORM + API
- Admin frontend page `/[org]/admin/pdf`
- `StirlingPDFClient` service + Jinja2 template
- Celery task (PDF to local cache volume until Nextcloud ready)

### Phase 2 — After P2 (Nextcloud + SSO complete)
- Activate WebDAV upload in `generate_story_pdf` task
- Remove local-cache fallback path

### Phase 3 — After P3 (Nextcloud Plugin complete)
- Link to PDF visible in dashboard widget
- "Last generated PDF" shown in story detail view

---

## File Map

### New Files
| File | Purpose |
|------|---------|
| `backend/app/models/pdf_settings.py` | ORM model for pdf_settings table |
| `backend/app/schemas/pdf_settings.py` | Pydantic request/response schemas |
| `backend/app/routers/pdf_settings.py` | API endpoints (CRUD + uploads) |
| `backend/app/services/stirling_client.py` | HTTP client for Stirling PDF REST API |
| `backend/app/services/pdf_service.py` | Orchestrates render → convert → store |
| `backend/app/tasks/pdf_tasks.py` | Celery task: generate_story_pdf |
| `backend/app/templates/userstory_pdf.html.jinja2` | HTML template for story PDF |
| `backend/tests/unit/test_stirling_client.py` | Unit tests for StirlingPDFClient |
| `backend/tests/unit/test_pdf_service.py` | Unit tests for PdfService |
| `backend/tests/integration/test_pdf_settings.py` | Integration tests for API |
| `backend/migrations/versions/0017_pdf_settings.py` | Migration: create pdf_settings table (depends on P1 migrations 0015 + 0016 landing first; renumber if needed) |

### New Frontend Files
| File | Purpose |
|------|---------|
| `frontend/app/[org]/admin/pdf/page.tsx` | Admin page: PDF settings + template upload |
| `frontend/components/admin/PdfSettingsForm.tsx` | Settings form (company name, format, language, header/footer) |
| `frontend/components/admin/TemplateUpload.tsx` | File upload component (letterhead PDF + logo) |

### Modified Files
| File | Changes |
|------|---------|
| `infra/docker-compose.yml` | Add stirling-pdf service + 2 volumes; add `STIRLING_PDF_URL` to both `backend` and `worker` service env blocks |
| `infra/.env.example` | Add STIRLING_PDF_URL |
| `backend/app/config.py` | Add `STIRLING_PDF_URL: str = "http://assist2-stirling-pdf:8080"`, `PDF_TEMPLATES_PATH: str = "/app/pdf_templates"`, `PDF_CACHE_PATH: str = "/app/pdf_cache"` |
| `backend/app/celery_app.py` | Add `"app.tasks.pdf_tasks"` to `include` list |
| `backend/app/main.py` | Register pdf_settings router |
| `backend/app/routers/user_stories.py` | Capture `old_status = story.status` before update loop; dispatch `generate_story_pdf.delay()` after commit if status transitioned to `done` |

---

## Security

- API endpoints require `org:update` permission — regular users cannot access
- Template files isolated per org (`/app/pdf_templates/{org_id}/`)
- Stirling PDF not reachable from outside the Docker network
- File upload validation: MIME type check + size limits (PDF max 5 MB, image max 1 MB)
- No user-provided data injected into shell commands — HTML rendered via Jinja2 with auto-escaping

---

## Testing Strategy

- **Unit tests**: `StirlingPDFClient` — all HTTP calls mocked with httpx
- **Unit tests**: `PdfService` — mock StirlingPDFClient + DB session
- **Unit tests**: Jinja2 template rendering — assert key sections present in output HTML
- **Integration tests**: API endpoints — file upload, settings CRUD, preview generation
- **No Stirling PDF in CI**: client mocked everywhere; integration tests skip actual conversion
