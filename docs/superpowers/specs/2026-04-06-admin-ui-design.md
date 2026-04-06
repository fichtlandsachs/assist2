# Admin UI — Settings Management Design

**Date:** 2026-04-06
**Status:** Approved

---

## 1. Architecture

**Approach:** Rebuild the settings section in-place inside the existing `admin-frontend` service. No new Docker container, no new Traefik route. The admin UI continues to be served at `admin.karlapp` / `https://admin.fichtlworks.com`.

**What stays untouched:**
- `/dashboard` — component health grid (existing)
- `/resources` — org resource overview (existing)
- Login/callback/auth flow via Authentik OIDC (existing)

**What is added:**
- `/settings/system` — global system configuration page
- `/settings/orgs/[slug]` — per-org configuration page (Phase 2, deferred)
- New backend endpoints under `/api/v1/superadmin/config/` secured by the existing `get_admin_user` dependency (validates Authentik OIDC token, checks `is_superuser`)
- New DB table `system_config` — key/value store with encrypted values (one row per config key)

**Secret storage:** All sensitive values (API keys, client secrets, passwords) are encrypted at rest using the existing `encrypt_value` / `decrypt_value` helpers from `app.core.security`. The API never returns decrypted secret values — only a boolean `is_set: true/false` flag. Write endpoints accept a new value or `null` to clear.

**No per-org config in this phase.** Per-org Jira/Confluence/Atlassian/GitHub settings are deferred to Phase 2. The workspace `/[org]/settings` page remains the place for user-side org configuration and is not touched.

---

## 2. Navigation

**Layout:** Two-column layout replaces the existing single-column `<main>` for all `/settings/*` routes:

```
┌─────────────────────────────────────────────────────────┐
│  header (existing — "assist2 Admin" + nav + logout)     │
├──────────────┬──────────────────────────────────────────┤
│  Sidebar     │  Content panel                           │
│  (240px)     │                                          │
│              │                                          │
│  ● System    │  [tool sections as collapsible cards]    │
│              │                                          │
│  Organisati- │                                          │
│  onen        │                                          │
│  [search]    │                                          │
│  · acme      │                                          │
│  · demo-org  │                                          │
└──────────────┴──────────────────────────────────────────┘
```

**Sidebar entries:**
- **System** — top-level item, navigates to `/settings/system`
- **Organisationen** (section header, not clickable) — searchable list of all orgs by name/slug, each navigates to `/settings/orgs/[slug]`

**Active state:** selected item highlighted with `var(--accent-red)` left border and muted background.

**Desktop-only:** The settings UI is not designed for mobile. No responsive breakpoints needed. The existing `/dashboard` and `/resources` pages keep their own layout.

**Existing header nav:** Add a "Einstellungen" link pointing to `/settings/system` alongside the existing "Komponenten" and "Ressourcen" links.

---

## 3. System Page — Tool Sections

Route: `/settings/system`

The page renders a vertical stack of collapsible `<ToolSection>` cards. Each section has a title, optional description, a set of form fields, and a "Speichern" button that PATCHes only that section's keys.

### 3.1 LiteLLM

| Label | Config key | Type | Notes |
|---|---|---|---|
| URL | `litellm.url` | string | Internal Docker URL |
| Master API Key | `litellm.api_key` | secret | write-only; shows `is_set` badge |

### 3.2 Nextcloud

| Label | Config key | Type | Notes |
|---|---|---|---|
| URL | `nextcloud.url` | string | |
| Admin-Benutzer | `nextcloud.admin_user` | string | |
| Admin-Passwort | `nextcloud.admin_password` | secret | write-only |

### 3.3 n8n

| Label | Config key | Type | Notes |
|---|---|---|---|
| URL | `n8n.url` | string | |
| API Key | `n8n.api_key` | secret | write-only |

### 3.4 Auth-Provider

Two sub-sections, each with an enable/disable toggle + credentials:

**Atlassian SSO**

| Label | Config key | Type |
|---|---|---|
| Aktiviert | `atlassian.sso_enabled` | boolean |
| Client ID | `atlassian.client_id` | string |
| Client Secret | `atlassian.client_secret` | secret |

**GitHub SSO**

| Label | Config key | Type |
|---|---|---|
| Aktiviert | `github.sso_enabled` | boolean |
| Client ID | `github.client_id` | string |
| Client Secret | `github.client_secret` | secret |

### 3.5 KI-Provider (AI Provider Defaults)

| Label | Config key | Type |
|---|---|---|
| Anthropic API Key | `ai.anthropic_api_key` | secret |
| OpenAI API Key | `ai.openai_api_key` | secret |
| IONOS AI Key | `ai.ionos_api_key` | secret |

---

## 4. Backend API

### 4.1 DB Model: `SystemConfig`

Table: `system_config`

```python
class SystemConfig(Base):
    __tablename__ = "system_config"
    key: Mapped[str]            # primary key, e.g. "litellm.api_key"
    value: Mapped[str | None]   # encrypted if is_secret=True, plaintext otherwise
    is_secret: Mapped[bool]     # True → value is encrypted
    updated_at: Mapped[datetime]
    updated_by_id: Mapped[uuid.UUID | None]  # FK → users.id
```

### 4.2 Endpoints

All under `/api/v1/superadmin/config/`, all require `get_admin_user`.

**`GET /api/v1/superadmin/config/`**
Returns all config keys as a flat object:
```json
{
  "litellm.url": { "value": "http://assist2-litellm:4000", "is_secret": false },
  "litellm.api_key": { "value": null, "is_set": true, "is_secret": true },
  "atlassian.sso_enabled": { "value": "true", "is_secret": false },
  ...
}
```
For secret keys: `value` is always `null`; `is_set` indicates whether a non-null encrypted value exists.

**`PATCH /api/v1/superadmin/config/`**
Body: `{ "key": "litellm.api_key", "value": "sk-..." }` — sets or updates one key.
Body: `{ "key": "litellm.api_key", "value": null }` — clears the key.
Returns `204 No Content`.

Validation: key must be in the allowed set (hard-coded whitelist). Unknown keys → 400.

### 4.3 Migration

New migration `0027_system_config.py`:
- Creates `system_config` table with `key` (VARCHAR PK), `value` (TEXT), `is_secret` (BOOLEAN), `updated_at` (TIMESTAMPTZ), `updated_by_id` (UUID FK nullable)

---

## 5. Frontend Implementation Notes

**Auth:** Uses existing `getSession()` from `admin-frontend/lib/auth.ts`. All API calls attach the Bearer token from session.

**API helper:** Extend `admin-frontend/lib/api.ts` with `fetchConfig()` and `patchConfig(key, value)`.

**State per section:** Each tool section manages its own dirty/saving state independently. Saving one section does not affect others.

**Secret fields:** Rendered as `<input type="password">`. If `is_set: true`, show a muted "●●●● gesetzt" placeholder and a "Ändern" button that clears the placeholder and activates the field. Saving `null` value clears the secret.

**Collapsible sections:** Default open on first load. Collapse state stored in component local state (not persisted).

**CSS conventions:** Follow existing admin-frontend style — `var(--ink)`, `var(--paper-warm)`, `var(--paper-rule)`, `var(--accent-red)`, `var(--ink-faint)` CSS variables. Same font, same border-radius (`rounded-sm`).

---

## 6. Phase 2 (Deferred)

Per-org settings page at `/settings/orgs/[slug]` will expose:

- Jira (URL, email, API token, project key, enabled toggle)
- Confluence (URL, API token, enabled toggle)
- Atlassian per-org credentials (if different from system-level)
- GitHub per-org credentials

This phase is explicitly out of scope for the current implementation. The sidebar will show org entries but they will display a "Noch nicht verfügbar" placeholder for now.

---

## 7. Out of Scope

- Mobile/responsive layout for settings pages
- Role-based access within the admin UI (all admin users see all settings)
- Audit log for config changes (tracked via `updated_by_id` in DB, no UI yet)
- LiteLLM model management (already has its own UI at `/litellm/ui`)
- Any changes to `/[org]/settings` in the main workspace
