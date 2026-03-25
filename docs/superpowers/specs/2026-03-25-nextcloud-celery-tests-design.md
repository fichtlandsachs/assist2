# Design: Nextcloud Abschluss, Celery Tasks & Test-Coverage

**Datum:** 2026-03-25
**Status:** Approved
**Scope:** Items 1, 2, 4 aus dem Entwicklungsstand-Review (Wave 6 folgt separat)

---

## 1. Überblick

Drei unabhängige, aber zusammen deploybare Arbeitspakete:

| Paket | Ziel |
|---|---|
| Nextcloud Abschluss | Docs→Nextcloud-Save-Flow, Docker-Config, Commit |
| Celery Tasks | agent_tasks.py implementieren, Beat-Dispatcher, sync_interval_minutes per Verbindung |
| Test-Coverage | Nextcloud-Endpoints, Celery-Tasks, Workflow-Trigger — Integration + Unit |

---

## 2. Nextcloud Abschluss

### 2.1 Docs → Nextcloud Save

**Problem:** `docs/page.tsx` erwartet `nextcloud_path` im `DocsResult`-Response, aber der Docs-Router lädt die generierte PDF bisher nicht in Nextcloud hoch.

**Lösung:** Optionaler Upload-Schritt in `routers/user_stories.py`, Endpoint `POST /user-stories/{story_id}/docs/save`:

- `StoryDocsSave` (Request-Schema) bekommt: `save_to_nextcloud: bool = False`
- `StoryDocsRead` (Response-Schema) bekommt: `nextcloud_path: str | None = None`
- Im Handler: nach dem Confluence-Block, falls `data.save_to_nextcloud`:
  ```python
  nc_path = await nextcloud_service.upload_story_pdf(org.slug, story_id, docs_dict)
  # nextcloud_path im Response setzen
  ```

`NextcloudService` bekommt `upload_story_pdf(org_slug, story_id, docs_dict) -> str` — serialisiert Docs als Text-Datei oder PDF (via Stirling) und lädt unter `Organizations/{org_slug}/Docs/{story_id}.pdf` hoch, gibt Pfad zurück.

### 2.2 Docker & Dependencies

- `requirements.txt`: sicherstellen dass `httpx>=0.27` und `python-multipart` enthalten sind
- `docker-compose.yml`: Nextcloud-Service bekommt `NEXTCLOUD_TRUSTED_PROXIES` Env-Variable (Traefik-IP-Range), damit Reverse-Proxy-Forwarding korrekt funktioniert
- `config.py`: keine Änderungen nötig (alle Nextcloud-Settings bereits vorhanden)

### 2.3 Commit

Alle 11 aktuell geänderten Dateien werden in einem Commit zusammengefasst:
`feat(nextcloud): complete nextcloud integration with docs upload and docker config`

---

## 3. Celery Tasks

### 3.1 agent_tasks.py — Implementierung (Option C)

Zwei Tasks ersetzen den aktuellen Stub:

**Task 1: `analyze_story_task`**
```
Name:    agent_tasks.analyze_story
Args:    story_id: str, org_id: str
Action:  Lädt Story aus DB → ruft ai_story_service.get_story_suggestions() auf
         → speichert AiStep in DB (model, prompt_tokens, completion_tokens, response)
Retry:   max_retries=3, countdown=60s
```

**Task 2: `trigger_ai_delivery_task`**
```
Name:    agent_tasks.trigger_ai_delivery
Args:    story_id: str, org_id: str
Action:  Ruft n8n-Webhook "ai-delivery" via N8nClient auf
         → speichert WorkflowExecution in DB mit status=pending
Retry:   max_retries=3, countdown=30s
```

Beide Tasks werden in `celery_app.py` unter `include` bereits registriert.

### 3.2 Migration #018 — sync_interval_minutes

```sql
ALTER TABLE mail_connections ADD COLUMN sync_interval_minutes INTEGER NOT NULL DEFAULT 15;
ALTER TABLE calendar_connections ADD COLUMN sync_interval_minutes INTEGER NOT NULL DEFAULT 30;
```

Alembic-Migration: `0018_sync_interval_minutes.py`

### 3.3 Dispatcher-Pattern

Zwei neue Tasks in einer neuen Datei `app/tasks/sync_dispatcher.py`:

**`dispatch_mail_sync_task()`**
```
Lädt alle MailConnections wo:
  - is_active = True (oder imap_host IS NOT NULL)
  - last_sync_at IS NULL
    OR now() - last_sync_at >= sync_interval_minutes * interval '1 minute'
Für jede: sync_mailbox_task.delay(conn_id, org_id)
```

**`dispatch_calendar_sync_task()`**
```
Lädt alle CalendarConnections wo:
  - is_active = True
  - provider = google
  - access_token_enc IS NOT NULL
  - last_sync_at IS NULL
    OR now() - last_sync_at >= sync_interval_minutes * interval '1 minute'
Für jede: sync_calendar_task.delay(conn_id, org_id)
```

### 3.4 Beat-Schedule

`celery_app.py` bekommt `beat_schedule`:

```python
celery.conf.beat_schedule = {
    "dispatch-mail-sync": {
        "task": "sync_dispatcher.dispatch_mail_sync",
        "schedule": 60.0,  # jede Minute
    },
    "dispatch-calendar-sync": {
        "task": "sync_dispatcher.dispatch_calendar_sync",
        "schedule": 60.0,  # jede Minute
    },
}
```

Der Dispatcher läuft jede Minute und entscheidet anhand von `sync_interval_minutes` + `last_sync_at`, welche Verbindungen tatsächlich synchronisiert werden.

### 3.5 .env-Defaults

```
MAIL_SYNC_INTERVAL_MINUTES=15
CALENDAR_SYNC_INTERVAL_MINUTES=30
```

Werden in `Settings` aufgenommen. Beim Erstellen einer neuen Verbindung werden diese Defaults als `sync_interval_minutes` geschrieben.

### 3.6 UI — Sync-Intervall

**Mail-Verbindung** (`frontend/app/[org]/inbox/` oder Settings-Seite):
- Neues Dropdown-Feld: `Sync-Intervall` mit Optionen 5 / 15 / 30 / 60 Minuten
- Wird beim Speichern der Verbindung via `PATCH /api/v1/inbox/connections/{id}` übertragen

**Kalender-Verbindung** (`frontend/app/[org]/calendar/` Settings):
- Neues Dropdown-Feld: `Sync-Intervall` mit Optionen 15 / 30 / 60 / 120 Minuten
- Via `PATCH /api/v1/calendar/connections/{id}`

Backend-Schemas (`MailConnectionUpdate`, `CalendarConnectionUpdate`) bekommen `sync_interval_minutes: int | None = None`.

---

## 4. Test-Coverage

### 4.1 Integration-Tests (gegen Test-DB)

**`tests/integration/test_nextcloud.py`**
- `test_list_files_requires_membership` — GET ohne Membership → 403
- `test_list_files_success` — GET mit Membership, Nextcloud-Service gemockt → 200
- `test_download_requires_membership` — 403
- `test_download_proxies_file` — StreamingResponse korrekt
- `test_upload_org_folder` — POST multipart → 200, Pfad korrekt
- `test_upload_personal_folder` — POST personal → 200

**`tests/integration/test_agent_tasks_endpoint.py`**
- `test_invoke_agent_dispatches_task` — POST /agents/{id}/invoke → Task wird in Celery-Queue gestellt (mock `apply_async`)

**`tests/integration/test_workflows.py`**
- `test_trigger_workflow_success` — n8n-Webhook gemockt via `respx`, WorkflowExecution wird in DB angelegt
- `test_trigger_workflow_n8n_down` — n8n antwortet 500 → korrekter Fehler-Response

### 4.2 Unit-Tests (alles gemockt)

**`tests/unit/test_mail_sync.py`**
- `test_decode_header_mime_encoded` — RFC 2047 Header korrekt dekodiert
- `test_parse_date_valid` / `test_parse_date_invalid` — Datumsparsing
- `test_get_body_multipart` — Plaintext aus Multipart-Mail extrahiert
- `test_run_sync_connection_not_found` — Früher Return bei fehlendem Record
- `test_run_sync_imap_error` — IMAP4.error → status=error zurück
- `test_run_sync_saves_new_messages` — IMAP-Mock liefert 3 Mails, 3 werden gespeichert
- `test_run_sync_skips_duplicates` — bereits vorhandene external_id wird übersprungen

**`tests/unit/test_calendar_sync.py`**
- `test_parse_event_dt_datetime` / `test_parse_event_dt_date` / `test_parse_event_dt_none`
- `test_event_status_mapping` — tentative/cancelled/confirmed
- `test_run_sync_token_refresh` — Token abgelaufen → Refresh-Call wird gemacht
- `test_run_sync_upserts_events` — Google-API-Mock, 5 Events → 5 neue Rows
- `test_run_sync_updates_existing` — vorhandenes Event wird aktualisiert

**`tests/unit/test_agent_tasks_unit.py`**
- `test_analyze_story_task_calls_ai_service` — `ai_story_service.get_story_suggestions` wird aufgerufen, AiStep gespeichert
- `test_analyze_story_task_retries_on_error` — Exception → Celery-Retry wird ausgelöst
- `test_trigger_ai_delivery_calls_n8n` — `N8nClient.trigger_workflow` gemockt, WorkflowExecution angelegt

**`tests/unit/test_dispatch_tasks.py`**
- `test_dispatch_mail_due` — 2 von 3 Connections sind fällig → 2 `sync_mailbox_task.delay()` Calls
- `test_dispatch_mail_none_due` — alle frisch synchronisiert → 0 Dispatches
- `test_dispatch_calendar_due` — korrekte Filterung nach `sync_interval_minutes`

---

## 5. Datenfluss (Celery)

```
Celery Beat (jede Minute)
    └── dispatch_mail_sync_task()
            └── [für jede fällige MailConnection]
                    └── sync_mailbox_task(conn_id, org_id)
                            ├── IMAP fetch (50 Nachrichten)
                            ├── Persist neue Messages
                            ├── AI Clustering (cluster_messages_sync)
                            └── UPDATE last_sync_at

    └── dispatch_calendar_sync_task()
            └── [für jede fällige CalendarConnection]
                    └── sync_calendar_task(conn_id, org_id)
                            ├── Token-Refresh falls nötig
                            ├── Google Calendar API (30 Tage)
                            ├── Upsert CalendarEvents
                            └── UPDATE last_sync_at
```

---

## 6. Nicht in diesem Scope

- Wave 6 (Voice/Whisper/Vision) — eigener Spec-Zyklus
- GitHub/Apple OAuth — Wave 3+
- APM/Monitoring
- Frontend E2E-Tests

---

## 7. Reihenfolge der Umsetzung

1. Migration #018 (sync_interval_minutes)
2. `sync_dispatcher.py` + Beat-Schedule in `celery_app.py`
3. `agent_tasks.py` implementieren
4. Backend-Schemas + Routers für sync_interval_minutes
5. Nextcloud: `upload_story_pdf` + Docs-Router-Anbindung
6. Docker-Config (requirements.txt, docker-compose.yml)
7. Commit Nextcloud-Integration
8. Tests schreiben (Integration, dann Unit)
