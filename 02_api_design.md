# 02 — API Design

## Konventionen

- Base URL: `/api/v1`
- Authentifizierung: Bearer JWT in `Authorization` Header
- Content-Type: `application/json`
- Tenant-Isolation: `organization_id` aus JWT-Kontext (kein Param nötig für org-gebundene Endpoints)
- Paginierung: `?page=1&page_size=20`, Response enthält `total`, `page`, `page_size`, `items`
- Fehlerformat: `{"error": "...", "code": "...", "details": {}}`
- `[SECURITY]` = serverseitige Permissions-Prüfung zwingend

---

## Auth

### POST /api/v1/auth/register
**Zweck**: Neuen User registrieren (intern)
**Permission**: keine (öffentlich)
```json
Request:
{
  "email": "user@example.com",
  "password": "...",
  "display_name": "Max Mustermann"
}

Response 201:
{
  "user": { "id": "...", "email": "...", "display_name": "..." },
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

### POST /api/v1/auth/login
**Zweck**: Login mit E-Mail + Passwort
**Permission**: keine
```json
Request: { "email": "...", "password": "..." }
Response 200: { "access_token": "...", "refresh_token": "...", "token_type": "bearer" }
```

### POST /api/v1/auth/refresh
**Zweck**: Access Token erneuern
```json
Request: { "refresh_token": "..." }
Response 200: { "access_token": "...", "refresh_token": "..." }
```

### POST /api/v1/auth/logout
**Zweck**: Session invalidieren (JWT in Blacklist)
**Permission**: authentifiziert
```json
Request: { "refresh_token": "..." }
Response 204: (no content)
```

### GET /api/v1/auth/oauth/{provider}
**Zweck**: OAuth2 Redirect initiieren
**Provider**: `google`, `github`, `apple`
```
Response 302: Redirect zu Provider OAuth URL
```

### GET /api/v1/auth/oauth/{provider}/callback
**Zweck**: OAuth2 Callback verarbeiten
```json
Response 200: { "access_token": "...", "refresh_token": "..." }
```

### GET /api/v1/auth/me
**Zweck**: Eigenes Profil abrufen
**Permission**: authentifiziert
```json
Response 200:
{
  "id": "...", "email": "...", "display_name": "...",
  "avatar_url": "...", "locale": "de", "timezone": "Europe/Berlin",
  "identity_links": [{ "provider": "google", "provider_email": "..." }]
}
```

---

## Users

### GET /api/v1/users/me
**Zweck**: Eigenes Profil
**Permission**: authentifiziert
```json
Response 200: { "id": "...", "email": "...", "display_name": "...", ... }
```

### PATCH /api/v1/users/me
**Zweck**: Eigenes Profil aktualisieren
```json
Request: { "display_name": "...", "locale": "en", "timezone": "UTC" }
Response 200: { ...updated user... }
```

### GET /api/v1/users/{user_id}
**Zweck**: User-Profil abrufen (org-kontextuell)
**Permission**: `org_member` (eigene Org)
```json
Response 200: { "id": "...", "display_name": "...", "avatar_url": "...", "email": "..." }
```

---

## Organizations

### POST /api/v1/organizations
**Zweck**: Organisation erstellen
**Permission**: authentifiziert
```json
Request: { "name": "Acme Corp", "slug": "acme-corp" }
Response 201:
{
  "id": "...", "slug": "acme-corp", "name": "Acme Corp",
  "plan": "free", "created_at": "..."
}
```

### GET /api/v1/organizations
**Zweck**: Eigene Organisationen auflisten
**Permission**: authentifiziert
```json
Response 200: { "items": [...], "total": 2 }
```

### GET /api/v1/organizations/{org_id}
**Permission**: `org:read` (Mitglied)
```json
Response 200: { "id": "...", "slug": "...", "name": "...", "plan": "...", ... }
```

### PATCH /api/v1/organizations/{org_id}
**Permission**: `org:update` (org_admin)
```json
Request: { "name": "...", "description": "...", "logo_url": "..." }
Response 200: { ...updated org... }
```

### DELETE /api/v1/organizations/{org_id}
**Permission**: `org:delete` (org_owner)
```json
Response 204: (Soft-Delete)
```

---

## Memberships

### GET /api/v1/organizations/{org_id}/members
**Permission**: `membership:read`
```json
Response 200:
{
  "items": [
    {
      "id": "...", "user": { "id": "...", "display_name": "...", "email": "..." },
      "status": "active", "roles": ["org_admin"], "joined_at": "..."
    }
  ],
  "total": 5
}
```

### POST /api/v1/organizations/{org_id}/members/invite
**Permission**: `membership:invite`
```json
Request: { "email": "user@example.com", "role_ids": ["..."] }
Response 201: { "membership_id": "...", "status": "invited", "invited_at": "..." }
```

### PATCH /api/v1/organizations/{org_id}/members/{membership_id}
**Permission**: `membership:update` (org_admin)
```json
Request: { "status": "suspended" }
Response 200: { ...updated membership... }
```

### DELETE /api/v1/organizations/{org_id}/members/{membership_id}
**Permission**: `membership:delete` (org_admin oder Self)
```json
Response 204
```

---

## Roles & Permissions

### GET /api/v1/organizations/{org_id}/roles
**Permission**: `role:read`
```json
Response 200: { "items": [{ "id": "...", "name": "...", "is_system": true, "permissions": [...] }] }
```

### POST /api/v1/organizations/{org_id}/roles
**Permission**: `role:create` (org_admin)
```json
Request: { "name": "Developer", "permission_ids": ["..."] }
Response 201: { "id": "...", "name": "...", "permissions": [...] }
```

### GET /api/v1/permissions
**Zweck**: Alle verfügbaren Permissions auflisten
**Permission**: authentifiziert
```json
Response 200: { "items": [{ "id": "...", "resource": "story", "action": "create" }] }
```

### POST /api/v1/organizations/{org_id}/members/{membership_id}/roles
**Zweck**: Rolle zuweisen
**Permission**: `role:assign`
```json
Request: { "role_id": "..." }
Response 200: { "membership_id": "...", "roles": [...] }
```

---

## Groups

### GET /api/v1/organizations/{org_id}/groups
**Permission**: `group:read`
```json
Response 200: { "items": [{ "id": "...", "name": "...", "type": "team", "member_count": 5 }] }
```

### POST /api/v1/organizations/{org_id}/groups
**Permission**: `group:create`
```json
Request: { "name": "Backend Team", "type": "team", "description": "..." }
Response 201: { "id": "...", "name": "...", ... }
```

### POST /api/v1/organizations/{org_id}/groups/{group_id}/members
**Permission**: `group:manage`
```json
Request: { "member_type": "user", "user_id": "...", "role": "member" }
Response 201: { "id": "...", "member_type": "user", "user": {...} }
```

### DELETE /api/v1/organizations/{org_id}/groups/{group_id}/members/{member_id}
**Permission**: `group:manage`
```json
Response 204
```

---

## Plugins

### GET /api/v1/plugins
**Zweck**: Alle verfügbaren Plugins
**Permission**: authentifiziert
```json
Response 200: { "items": [{ "id": "...", "slug": "user-story", "name": "User Story", "type": "hybrid", "version": "1.0.0" }] }
```

### GET /api/v1/organizations/{org_id}/plugins
**Zweck**: Aktivierte Plugins der Organisation
**Permission**: `plugin:read`
```json
Response 200: { "items": [{ "plugin": {...}, "is_enabled": true, "config": {} }] }
```

### POST /api/v1/organizations/{org_id}/plugins/{plugin_id}/activate
**Permission**: `plugin:activate` (org_admin)
```json
Request: { "config": { "key": "value" } }
Response 200: { "plugin_id": "...", "is_enabled": true, "activated_at": "..." }
```

### PATCH /api/v1/organizations/{org_id}/plugins/{plugin_id}/config
**Permission**: `plugin:configure` (org_admin)
```json
Request: { "config": { "key": "new_value" } }
Response 200: { "plugin_id": "...", "config": {...} }
```

### DELETE /api/v1/organizations/{org_id}/plugins/{plugin_id}/deactivate
**Permission**: `plugin:deactivate` (org_admin)
```json
Response 204
```

---

## Workflows

### GET /api/v1/organizations/{org_id}/workflows
**Permission**: `workflow:read`
```json
Response 200: { "items": [{ "id": "...", "name": "...", "version": 3, "is_active": true }] }
```

### POST /api/v1/organizations/{org_id}/workflows
**Permission**: `workflow:create`
```json
Request: { "name": "...", "slug": "...", "trigger_type": "webhook", "definition": {...} }
Response 201: { "id": "...", "version": 1, ... }
```

### POST /api/v1/organizations/{org_id}/workflows/{workflow_id}/trigger
**Zweck**: Workflow manuell starten
**Permission**: `workflow:execute`
```json
Request: { "input": { "key": "value" } }
Response 202: { "execution_id": "...", "status": "pending" }
```

### GET /api/v1/organizations/{org_id}/workflows/{workflow_id}/executions
**Permission**: `workflow:read`
```json
Response 200: { "items": [{ "id": "...", "status": "success", "started_at": "...", "completed_at": "..." }] }
```

### GET /api/v1/organizations/{org_id}/workflows/executions/{execution_id}
**Permission**: `workflow:read`
```json
Response 200:
{
  "id": "...", "status": "success",
  "input_snapshot": {...}, "context_snapshot": {...}, "result_snapshot": {...}
}
```

---

## User Stories

### GET /api/v1/organizations/{org_id}/stories
**Permission**: `story:read`
```json
Query: ?status=in_progress&assignee_id=...&group_id=...
Response 200: { "items": [...], "total": 42 }
```

### POST /api/v1/organizations/{org_id}/stories
**Permission**: `story:create`
```json
Request:
{
  "title": "Als User möchte ich...",
  "description": "...",
  "priority": "high",
  "acceptance_criteria": ["AC1", "AC2"],
  "group_id": "...",
  "story_points": 5
}
Response 201: { "id": "...", "status": "draft", ... }
```

### PATCH /api/v1/organizations/{org_id}/stories/{story_id}
**Permission**: `story:update`
```json
Request: { "status": "in_progress", "assignee_id": "..." }
Response 200: { ...updated story... }
```

### GET /api/v1/organizations/{org_id}/stories/{story_id}/test-cases
**Permission**: `story:read`
```json
Response 200: { "items": [{ "id": "...", "title": "...", "status": "pending" }] }
```

---

## Inbox (Unified Inbox)

### GET /api/v1/organizations/{org_id}/inbox/connections
**Permission**: `inbox:read`
```json
Response 200: { "items": [{ "id": "...", "provider": "gmail", "email_address": "...", "sync_status": "active" }] }
```

### POST /api/v1/organizations/{org_id}/inbox/connections
**Zweck**: Mail-Verbindung hinzufügen
**Permission**: `inbox:manage`
```json
Request: { "provider": "gmail", "auth_code": "..." }
Response 201: { "id": "...", "email_address": "...", "sync_status": "active" }
```

### GET /api/v1/organizations/{org_id}/inbox/messages
**Permission**: `inbox:read`
```json
Query: ?connection_id=...&is_read=false&page=1&page_size=20
Response 200: { "items": [...], "total": 150 }
```

### PATCH /api/v1/organizations/{org_id}/inbox/messages/{message_id}
**Permission**: `inbox:update`
```json
Request: { "is_read": true, "is_archived": false }
Response 200: { ...updated message... }
```

---

## Calendar

### GET /api/v1/organizations/{org_id}/calendar/connections
**Permission**: `calendar:read`
```json
Response 200: { "items": [{ "id": "...", "provider": "google", "display_name": "Work Calendar" }] }
```

### POST /api/v1/organizations/{org_id}/calendar/connections
**Permission**: `calendar:manage`
```json
Request: { "provider": "google", "auth_code": "..." }
Response 201: { "id": "...", "provider": "google", "calendar_id": "..." }
```

### GET /api/v1/organizations/{org_id}/calendar/events
**Permission**: `calendar:read`
```json
Query: ?connection_id=...&start=2026-03-01&end=2026-03-31
Response 200: { "items": [...], "total": 25 }
```

### POST /api/v1/organizations/{org_id}/calendar/events
**Permission**: `calendar:create`
```json
Request:
{
  "connection_id": "...", "title": "...", "start_at": "...", "end_at": "...",
  "attendees": [{ "email": "...", "name": "..." }]
}
Response 201: { "id": "...", "external_id": "...", ... }
```

---

## Agents

### GET /api/v1/organizations/{org_id}/agents
**Permission**: `agent:read`
```json
Response 200: { "items": [{ "id": "...", "name": "...", "role": "coding", "model": "...", "is_active": true }] }
```

### POST /api/v1/organizations/{org_id}/agents
**Permission**: `agent:create` (org_admin)
```json
Request: { "name": "CodingAgent v1", "role": "coding", "model": "claude-sonnet-4-6", "config": {} }
Response 201: { "id": "...", ... }
```

### POST /api/v1/organizations/{org_id}/agents/{agent_id}/invoke
**Zweck**: Agenten direkt aufrufen
**Permission**: `agent:invoke`
```json
Request: { "input": { "task": "...", "context": {} } }
Response 202: { "invocation_id": "...", "status": "running" }
```
