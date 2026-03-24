# Design: Nextcloud + Authentik SSO Integration

**Datum:** 2026-03-24
**Status:** Approved
**Scope:** 3 Projekte (P1 → P2 → P3, sequenziell)

---

## Übersicht

Integration von Nextcloud als Datei-Workspace in die assist2-Plattform. Authentik wird als zentraler Identity Provider (IdP) eingeführt und ersetzt den bisherigen JWT-Auth-Stack im Backend. Das bestehende Login-Design (custom `/login`-Form) bleibt visuell unverändert — das Backend wird zum Auth-Proxy.

### Gesamtarchitektur

```
Browser (gleiche /login-Form)
  → POST /api/v1/auth/login (Backend)
    → Authentik Flow Executor API (headless)
      ← Authentik OIDC Token
    ← Token ans Frontend (gleiche Struktur wie heute)

Browser → nextcloud.fichtlworks.com
  → "Login with Workplace" (Social Login App)
    → authentik.fichtlworks.com (OIDC)
      ← Token
    ← Nextcloud-Session (User auto-created)
```

### Projektgliederung

| | Projekt 1 | Projekt 2 | Projekt 3 |
|---|---|---|---|
| **Was** | Authentik + Auth-Migration | Nextcloud + SSO | Plugin + Workflow |
| **Neue Container** | authentik-server, -worker, -db | nextcloud, nextcloud-db | — |
| **Backend-Änderungen** | Auth-Proxy, JWKS-Validierung | n8n-Trigger in Services | Nextcloud-Routes |
| **Frontend-Änderungen** | keine | keine | File-Widget |
| **Kritischer Pfad** | User-Migration | OIDC-Config | n8n-Workflow |

---

## Projekt 1: Authentik + Backend Auth-Migration

### Docker-Infrastruktur

Neue Services in `infra/docker-compose.yml`:

```yaml
authentik-db:
  image: postgres:16-alpine
  volumes: [assist2_authentik_db_data]
  networks: [internal]

authentik-server:
  image: ghcr.io/goauthentik/server:latest
  command: server
  ports: (nur intern, Traefik-Label: authentik.fichtlworks.com → :9000)
  networks: [proxy, internal]

authentik-worker:
  image: ghcr.io/goauthentik/server:latest
  command: worker
  networks: [internal]
```

Redis wird geteilt (bestehender assist2-Redis, DB `/1`).

**Neue Volumes:**
- `assist2_authentik_db_data`
- `assist2_authentik_media`

**Neue `.env`-Variablen:**
```bash
AUTHENTIK_SECRET_KEY=          # 64 Zeichen, random
AUTHENTIK_DB_PASSWORD=         # stark, random
AUTHENTIK_BOOTSTRAP_EMAIL=     # initiales Admin-Email
AUTHENTIK_BOOTSTRAP_PASSWORD=  # initiales Admin-Passwort
```

**Traefik-Routing:**
```
authentik.fichtlworks.com → authentik-server:9000
```

### Backend-Änderungen

#### Neue Datei: `app/services/authentik_client.py`

Kapselung aller Authentik-API-Aufrufe:

```python
class AuthentikClient:
    async def authenticate_user(email, password) -> TokenResponse
        # POST /api/v3/flows/executor/{flow-slug}/
        # Returns: access_token, refresh_token, expires_in

    async def create_user(email, password, display_name) -> AuthentikUser
        # POST /api/v3/core/users/
        # Sets: username=email, name=display_name, email=email

    async def refresh_token(refresh_token) -> TokenResponse
        # POST /application/o/token/ (OIDC Token Endpoint)

    async def revoke_token(token) -> None
        # POST /application/o/revoke/

    async def get_user_by_email(email) -> AuthentikUser | None
        # GET /api/v3/core/users/?email=...
```

Konfiguration via `.env`:
```bash
AUTHENTIK_URL=http://authentik-server:9000
AUTHENTIK_API_TOKEN=           # Service-Account-Token
AUTHENTIK_FLOW_SLUG=           # Login-Flow-Slug (z.B. "default-authentication-flow")
AUTHENTIK_CLIENT_ID=           # OAuth2 Provider Client ID für Backend
AUTHENTIK_CLIENT_SECRET=       # OAuth2 Provider Client Secret
AUTHENTIK_JWKS_URL=            # https://authentik.fichtlworks.com/application/o/backend/jwks/
```

#### Geändert: `app/core/security.py`

- **Entfernt:** `create_access_token()`, `create_refresh_token()`, `verify_password()`, `hash_password()`
- **Entfernt:** `bcrypt`-Abhängigkeit
- **Neu:** `validate_authentik_token(token: str) -> dict` — dekodiert JWT via JWKS (cached, 5min TTL mit `cachetools`)

#### Geändert: `app/routers/auth.py`

| Endpunkt | Vorher | Nachher |
|---|---|---|
| `POST /auth/login` | bcrypt verify + JWT erstellen | `authentik_client.authenticate_user()` |
| `POST /auth/register` | User in DB + JWT | `authentik_client.create_user()` + User in DB |
| `POST /auth/refresh` | UserSession in DB | `authentik_client.refresh_token()` |
| `POST /auth/logout` | UserSession revoken | `authentik_client.revoke_token()` |
| `GET /auth/me` | unverändert | unverändert |

#### Geändert: `app/deps.py` — `get_current_user`

```python
async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    payload = validate_authentik_token(token)  # JWKS-Validierung
    authentik_id = payload["sub"]
    email = payload["email"]

    user = await db.execute(select(User).where(User.authentik_id == authentik_id))
    if not user:
        # Lazy-create für migrierte User
        user = await db.execute(select(User).where(User.email == email))
        if user:
            user.authentik_id = authentik_id
    return user
```

#### Neue Migration: `0015_authentik_id.py`

```sql
ALTER TABLE users ADD COLUMN authentik_id VARCHAR UNIQUE;
CREATE INDEX ix_users_authentik_id ON users(authentik_id);
```

#### Entfernte Migration-abhängige Tabelle: `user_sessions`

`UserSession`-Modell und -Tabelle werden in dieser Migration gedroppt (Sessions liegen in Authentik).

#### Migrationsskript: `backend/scripts/migrate_to_authentik.py`

Einmalig ausgeführt:
1. Alle aktiven User aus `users`-Tabelle lesen
2. Jeden User in Authentik anlegen via API (`create_user()`)
3. `authentik_id` in lokaler DB speichern
4. Passwort-Reset-Flag in Authentik setzen (User muss Passwort beim nächsten Login setzen)

### Frontend-Änderungen

**Keine.** Die `/login`-Seite, `lib/auth/context.tsx` und `lib/api/client.ts` bleiben unverändert. Die Token-Struktur (`access_token`, `refresh_token`) ist identisch — nur der Aussteller wechselt von Backend-JWT zu Authentik-OIDC-Token.

---

## Projekt 2: Nextcloud + SSO

### Docker-Infrastruktur

```yaml
nextcloud-db:
  image: mariadb:10.11
  volumes: [assist2_nextcloud_db_data]
  networks: [internal]

nextcloud:
  image: nextcloud:28-apache
  volumes: [assist2_nextcloud_data]
  networks: [proxy, internal]
  environment:
    NEXTCLOUD_TRUSTED_DOMAINS: nextcloud.fichtlworks.com
    NEXTCLOUD_ADMIN_USER: ${NEXTCLOUD_ADMIN_USER}
    NEXTCLOUD_ADMIN_PASSWORD: ${NEXTCLOUD_ADMIN_PASSWORD}
    MYSQL_HOST: nextcloud-db
    MYSQL_DATABASE: nextcloud
    MYSQL_USER: nextcloud
    MYSQL_PASSWORD: ${NEXTCLOUD_DB_PASSWORD}
    OVERWRITEPROTOCOL: https
    OVERWRITECLIURL: https://nextcloud.fichtlworks.com
```

**Neue Volumes:**
- `assist2_nextcloud_data`
- `assist2_nextcloud_db_data`

**Neue `.env`-Variablen:**
```bash
NEXTCLOUD_ADMIN_USER=admin
NEXTCLOUD_ADMIN_PASSWORD=        # stark, random
NEXTCLOUD_DB_PASSWORD=           # stark, random
NEXTCLOUD_ADMIN_APP_PASSWORD=    # App Password für n8n + Backend API-Calls
```

**Traefik-Routing:**
```
nextcloud.fichtlworks.com → nextcloud:80
```

### Authentik OIDC Provider für Nextcloud

In Authentik wird eine **OAuth2/OIDC Provider Application** `nextcloud` angelegt:

```
Name:           nextcloud
Redirect URI:   https://nextcloud.fichtlworks.com/apps/sociallogin/custom_oidc/authentik
Scopes:         openid, email, profile, groups
Sub Mode:       Based on User's Email
Issuer Mode:    Per Provider
```

### Nextcloud Social Login App — OIDC-Konfiguration

```json
{
  "custom_oidc": [{
    "name": "authentik",
    "title": "Login with Workplace",
    "authorizeUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/authorize/",
    "tokenUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/token/",
    "userInfoUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/userinfo/",
    "clientId": "<NEXTCLOUD_OIDC_CLIENT_ID>",
    "clientSecret": "<NEXTCLOUD_OIDC_CLIENT_SECRET>",
    "scope": "openid email profile",
    "uidClaim": "preferred_username",
    "displayNameClaim": "name",
    "emailClaim": "email",
    "autoCreate": true,
    "defaultGroup": "nextcloud-users"
  }]
}
```

### Org-Gruppenordner

**Struktur:**
```
/Organizations/{org-slug}/     ← Group Folder (Nextcloud Group Folders App)
  Gruppe: org-{slug}
  Berechtigungen: Read/Write
```

**Nextcloud-Gruppe pro Org:** `org-{slug}` (erstellt via n8n-Workflow bei Org-Erstellung).

### Backend-Trigger

In `app/services/org_service.py`:
- `create()` → feuert n8n-Webhook `nextcloud-provisioning` mit `type: "org_created"`
- `add_member()` → feuert n8n-Webhook `nextcloud-provisioning` mit `type: "user_joined_org"`

In `app/services/auth_service.py`:
- `register()` → feuert n8n-Webhook `nextcloud-provisioning` mit `type: "user_created"` (nach P1 übernimmt `authentik_client.create_user()` die User-Erstellung, n8n-Trigger bleibt)

---

## Projekt 3: Nextcloud-Plugin + n8n-Workflow

### n8n Workflow: `nextcloud-provisioning.json`

**Trigger:** `POST /webhook/nextcloud-provisioning`

**Payload-Schema:**
```json
{
  "type": "user_created" | "user_joined_org",
  "user": { "email": "...", "display_name": "..." },
  "org": { "slug": "...", "name": "..." }  // nur bei user_joined_org
}
```

**Workflow-Knoten:**

```
Webhook
  └─ Switch (type)
       ├─ user_created
       │    └─ HTTP: Nextcloud OCS — User anlegen
       │         POST /ocs/v1.php/cloud/users
       │         { userid, email, displayname, password: random }
       │         (Auth: Admin App Password)
       │
       └─ user_joined_org
            ├─ HTTP: Nextcloud OCS — Gruppe anlegen (idempotent)
            │    POST /ocs/v1.php/cloud/groups  { groupid: "org-{slug}" }
            ├─ HTTP: Group Folders API — Ordner anlegen (idempotent)
            │    POST /apps/groupfolders/folders  { mountpoint: "Organizations/{slug}" }
            │    PATCH /apps/groupfolders/folders/{id}/groups  { group: "org-{slug}" }
            └─ HTTP: Nextcloud OCS — User zur Gruppe hinzufügen
                 POST /ocs/v1.php/cloud/users/{uid}/groups  { groupid: "org-{slug}" }
```

Alle HTTP-Requests nutzen `NEXTCLOUD_ADMIN_APP_PASSWORD` aus n8n-Credentials.

### Plugin-Struktur

```
plugins/nextcloud/
├── manifest.json
├── backend/
│   ├── routes.py       # GET /organizations/{org_id}/nextcloud/files
│   ├── service.py      # Nextcloud WebDAV + OCS Client
│   └── schemas.py      # NextcloudFile, NextcloudFileList
└── frontend/
    ├── index.tsx        # Plugin-Registrierung
    └── components/
        └── RecentFilesWidget.tsx
```

**`manifest.json`:**
```json
{
  "slug": "nextcloud",
  "name": "Nextcloud Files",
  "version": "1.0.0",
  "type": "hybrid",
  "capabilities": ["file_upload"],
  "nav": [{
    "id": "nextcloud",
    "label": "Dateien",
    "icon": "folder",
    "route": "/nextcloud",
    "slot": "sidebar",
    "position": 50
  }],
  "slots": [{
    "slotId": "dashboard.widgets",
    "component": "RecentFilesWidget",
    "position": 10
  }],
  "config_schema": {
    "nextcloud_url": { "type": "string", "required": true }
  }
}
```

**Backend `routes.py`:**
```
GET /organizations/{org_id}/nextcloud/files
  → WebDAV PROPFIND auf /remote.php/dav/files/admin/Organizations/{org-slug}/
  → Auth: NEXTCLOUD_ADMIN_APP_PASSWORD
  → Response: NextcloudFileList { items: NextcloudFile[], nextcloud_url: str }
```

**Frontend `RecentFilesWidget.tsx`:**
```
┌─────────────────────────────────────┐
│ 📁 Nextcloud — Org-Dateien          │
├─────────────────────────────────────┤
│ 📄 Projektplan.docx        heute    │
│ 📊 Q1-Report.xlsx          gestern  │
│ 📝 Meeting-Notes.md        Mo.      │
├─────────────────────────────────────┤
│ → Alle Dateien öffnen               │
└─────────────────────────────────────┘
```

SWR-fetch auf `/api/v1/organizations/{org_id}/nextcloud/files`, 60s Revalidierung. "Alle Dateien öffnen" → Link zu `https://nextcloud.fichtlworks.com`.

---

## Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| Authentik nicht erreichbar beim Login | Backend gibt 503 zurück, Frontend zeigt "Dienst nicht verfügbar" |
| JWKS-Cache abgelaufen, Authentik down | Letzter gültiger Cache wird für max. 5min verwendet |
| Nextcloud-Widget-API schlägt fehl | Widget zeigt "Dateien momentan nicht verfügbar", kein App-Crash |
| n8n-Provisioning schlägt fehl | Webhook-Fehler wird geloggt, User kann sich trotzdem einloggen |
| User existiert bereits in Nextcloud | OCS API gibt 102 (bereits vorhanden), Workflow behandelt als Success |

---

## Offene Punkte / Entscheidungen

1. **Authentik-Flow-Slug** für headless Login muss nach Authentik-Setup konfiguriert werden (Standard: `default-authentication-flow`)
2. **Nextcloud Group Folders App** muss manuell oder via `occ`-Befehl nach dem ersten Start aktiviert werden
3. **User-Migration**: Bestehende Passwörter können nicht migriert werden (bcrypt-Hashes) — alle User bekommen ein Passwort-Reset-Email via Authentik
4. **Nextcloud App Password** für Backend-API-Calls wird initial manuell erstellt und in `.env` eingetragen

---

## Implementierungsreihenfolge

```
P1: Authentik
  1. Docker: authentik-db, authentik-server, authentik-worker
  2. Migration 0015_authentik_id
  3. authentik_client.py Service
  4. security.py (JWKS-Validierung)
  5. routers/auth.py (Auth-Proxy)
  6. deps.py (get_current_user)
  7. migrate_to_authentik.py Script
  8. UserSession-Tabelle droppen

P2: Nextcloud
  1. Docker: nextcloud-db, nextcloud
  2. Authentik OIDC Provider Application
  3. Nextcloud Social Login konfigurieren
  4. n8n-Trigger in org_service + auth_service
  5. Group Folders App aktivieren

P3: Plugin + Workflow
  1. n8n Workflow nextcloud-provisioning.json
  2. plugins/nextcloud/ Struktur
  3. Backend routes + service + schemas
  4. Frontend RecentFilesWidget
  5. Plugin in Backend registrieren
```
