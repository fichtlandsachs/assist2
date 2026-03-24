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
    → Authentik OIDC Resource Owner Password Grant
      (POST /application/o/{slug}/token/ mit grant_type=password)
      ← Authentik OIDC Token (access_token, refresh_token)
    ← Token ans Frontend (gleiche Struktur wie heute)

Browser → nextcloud.fichtlworks.com
  → "Login with Workplace" (Social Login App)
    → authentik.fichtlworks.com (OIDC Authorization Code Flow)
      ← Token
    ← Nextcloud-Session (User auto-created)
```

**Hinweis zum Login-Proxy:** Authentik unterstützt den OIDC Resource Owner Password Credentials (ROPC) Grant. Dieser muss am OAuth2 Provider in Authentik explizit aktiviert werden (`Allow machine-to-machine credentials`). Das Backend nutzt diesen Grant als Auth-Proxy — der User gibt Credentials in der eigenen Form ein, das Backend tauscht diese gegen Authentik-Tokens.

### Projektgliederung

| | Projekt 1 | Projekt 2 | Projekt 3 |
|---|---|---|---|
| **Was** | Authentik + Auth-Migration | Nextcloud + SSO | Plugin + Workflow |
| **Neue Container** | authentik-server, -worker, -db | nextcloud, nextcloud-db | — |
| **Backend-Änderungen** | Auth-Proxy, JWKS-Validierung | n8n-Trigger in Services | Nextcloud-Routes |
| **Frontend-Änderungen** | keine | keine | File-Widget |
| **Kritischer Pfad** | User-Migration + ROPC-Flow | OIDC-Config | n8n-Workflow |

---

## Projekt 1: Authentik + Backend Auth-Migration

### Docker-Infrastruktur

Neue Services in `infra/docker-compose.yml`:

```yaml
authentik-db:
  image: postgres:16-alpine
  volumes: [assist2_authentik_db_data]
  networks: [internal]
  environment:
    POSTGRES_DB: authentik
    POSTGRES_USER: authentik
    POSTGRES_PASSWORD: ${AUTHENTIK_DB_PASSWORD}

authentik-server:
  image: ghcr.io/goauthentik/server:2024.10
  command: server
  networks: [proxy, internal]
  # Traefik-Label: authentik.fichtlworks.com → :9000
  environment:
    AUTHENTIK_REDIS__HOST: assist2-redis
    AUTHENTIK_REDIS__PASSWORD: ${REDIS_PASSWORD}
    AUTHENTIK_REDIS__DB: 1
    AUTHENTIK_POSTGRESQL__HOST: authentik-db
    AUTHENTIK_POSTGRESQL__NAME: authentik
    AUTHENTIK_POSTGRESQL__USER: authentik
    AUTHENTIK_POSTGRESQL__PASSWORD: ${AUTHENTIK_DB_PASSWORD}
    AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
    AUTHENTIK_BOOTSTRAP_EMAIL: ${AUTHENTIK_BOOTSTRAP_EMAIL}
    AUTHENTIK_BOOTSTRAP_PASSWORD: ${AUTHENTIK_BOOTSTRAP_PASSWORD}
  volumes:
    - assist2_authentik_media:/media
    - assist2_authentik_templates:/templates

authentik-worker:
  image: ghcr.io/goauthentik/server:2024.10
  command: worker
  networks: [internal]
  environment:
    # Identisch mit authentik-server
    AUTHENTIK_REDIS__HOST: assist2-redis
    AUTHENTIK_REDIS__PASSWORD: ${REDIS_PASSWORD}
    AUTHENTIK_REDIS__DB: 1
    AUTHENTIK_POSTGRESQL__HOST: authentik-db
    AUTHENTIK_POSTGRESQL__NAME: authentik
    AUTHENTIK_POSTGRESQL__USER: authentik
    AUTHENTIK_POSTGRESQL__PASSWORD: ${AUTHENTIK_DB_PASSWORD}
    AUTHENTIK_SECRET_KEY: ${AUTHENTIK_SECRET_KEY}
  volumes:
    - assist2_authentik_media:/media       # Worker braucht dasselbe Volume
    - assist2_authentik_templates:/templates
```

Redis wird geteilt (bestehender `assist2-redis`, DB-Index `/1`). Bestehende assist2-Services nutzen DB `/0`.

**Neue Volumes:**
- `assist2_authentik_db_data`
- `assist2_authentik_media`
- `assist2_authentik_templates`

**Neue `.env`-Variablen:**
```bash
AUTHENTIK_SECRET_KEY=          # 64 Zeichen, random
AUTHENTIK_DB_PASSWORD=         # stark, random
AUTHENTIK_BOOTSTRAP_EMAIL=     # initiales Admin-Email
AUTHENTIK_BOOTSTRAP_PASSWORD=  # initiales Admin-Passwort
AUTHENTIK_API_TOKEN=           # Service-Account-Token (nach initialem Setup erstellt)
AUTHENTIK_FLOW_SLUG=backend-login   # ROPC-fähiger OAuth2 Provider Flow
AUTHENTIK_BACKEND_CLIENT_ID=        # OAuth2 Provider Client ID für Backend ROPC
AUTHENTIK_BACKEND_CLIENT_SECRET=    # OAuth2 Provider Client Secret
AUTHENTIK_JWKS_URL=https://authentik.fichtlworks.com/application/o/backend/jwks/
```

**Traefik-Routing:**
```
authentik.fichtlworks.com → authentik-server:9000
```

### Authentik Setup (einmalig nach erstem Start)

In der Authentik-Admin-UI (`https://authentik.fichtlworks.com`) wird einmalig konfiguriert:

1. **OAuth2 Provider `backend`** — für den ROPC-Grant (Backend-Proxy):
   - Grant Types: `Authorization Code` + `Resource Owner Password`
   - Redirect URIs: `https://assist2.fichtlworks.com/api/v1/auth/oauth/callback`
   - Scopes: `openid`, `email`, `profile`
   - `Allow machine-to-machine credentials`: aktiviert
   - Sub Mode: `Based on User's Email`

2. **Service Account + API Token** — für `authentik_client.create_user()` etc.

3. **Google/GitHub Social Sources** — bestehende OAuth-Provider werden als Authentik Social Sources konfiguriert (ersetzt `GET /auth/oauth/{provider}`).

### Backend-Änderungen

#### Implementierungsreihenfolge innerhalb P1

Die Reihenfolge ist kritisch, um keinen Downtime-Moment zu erzeugen:

```
1. Migration 0015_authentik_id (nur ADD COLUMN, kein DROP)
2. authentik_client.py (neu)
3. security.py (JWKS-Validierung, bestehende Funktionen bleiben als Fallback)
4. auth_service.py komplett umschreiben (UserSession-Referenzen entfernen)
5. routers/auth.py anpassen
6. deps.py anpassen
7. migrate_to_authentik.py ausführen
8. Migration 0016_drop_user_sessions (erst NACH User-Migration)
```

#### Neue Datei: `app/services/authentik_client.py`

```python
class AuthentikClient:
    async def authenticate_user(email: str, password: str) -> TokenResponse:
        """
        OIDC Resource Owner Password Credentials Grant.
        POST /application/o/{AUTHENTIK_FLOW_SLUG}/token/
        Body: grant_type=password&username=...&password=...
              &client_id=...&client_secret=...&scope=openid email profile
        Returns: {access_token, refresh_token, expires_in, token_type}
        Raises: UnauthorizedException bei 400/401
        """

    async def create_user(email: str, password: str, display_name: str) -> str:
        """
        POST /api/v3/core/users/
        Body: {username: email, email, name: display_name, is_active: true}
        Returns: authentik_id (str UUID)
        Raises: ConflictException wenn User bereits existiert
        """

    async def set_password(authentik_id: str, password: str) -> None:
        """POST /api/v3/core/users/{id}/set_password/"""

    async def refresh_token(refresh_token: str) -> TokenResponse:
        """
        POST /application/o/{slug}/token/
        Body: grant_type=refresh_token&refresh_token=...&client_id=...&client_secret=...
        """

    async def revoke_token(token: str) -> None:
        """POST /application/o/{slug}/revoke/"""

    async def get_user_by_email(email: str) -> dict | None:
        """GET /api/v3/core/users/?email={email}&type=internal"""
```

Alle Calls nutzen `httpx.AsyncClient`. `AUTHENTIK_API_TOKEN` im `Authorization: Bearer`-Header für Admin-Calls. HTTP-Fehler werden in die existierenden `app/core/exceptions`-Typen übersetzt.

#### Geändert: `app/core/security.py`

- **Entfernt:** `create_access_token()`, `create_refresh_token()`, `verify_password()`, `hash_password()`
- **Entfernt aus `requirements.txt`:** `bcrypt`, `python-jose[cryptography]` (wird durch PyJWT ersetzt; python-jose hat bekannte CVEs: CVE-2024-33664, CVE-2024-33663)
- **Neu hinzugefügt zu `requirements.txt`:** `PyJWT[crypto]` (für JWKS-Validierung), `httpx` (bereits vorhanden prüfen)
- **Neu:** `validate_authentik_token(token: str) -> dict`

```python
# JWKS-Caching mit functools.lru_cache (kein neues Package nötig)
# TTL via datetime-Check auf dem Cache-Ergebnis (5min)
_jwks_cache: dict | None = None
_jwks_fetched_at: datetime | None = None

async def _get_jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and _jwks_fetched_at and (datetime.now() - _jwks_fetched_at).seconds < 300:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        res = await client.get(settings.AUTHENTIK_JWKS_URL)
        res.raise_for_status()
        _jwks_cache = res.json()
        _jwks_fetched_at = datetime.now()
    return _jwks_cache

async def validate_authentik_token(token: str) -> dict:
    """Dekodiert und validiert ein Authentik OIDC JWT via JWKS."""
    jwks = await _get_jwks()
    # PyJWT dekodiert mit JWKS
    # Raises: UnauthorizedException bei ungültigem Token
```

#### Geändert: `app/services/auth_service.py`

`UserSession` und alle Referenzen darauf werden vollständig entfernt. `_create_token_pair()` entfällt.

| Methode | Vorher | Nachher |
|---|---|---|
| `login()` | bcrypt + UserSession + eigenes JWT | `authentik_client.authenticate_user()` |
| `register()` | bcrypt + User in DB + UserSession | `authentik_client.create_user()` → User in DB |
| `refresh()` | UserSession in DB | `authentik_client.refresh_token()` |
| `logout()` | UserSession revoken | `authentik_client.revoke_token()` |
| `google_oauth()` | IdentityLink + UserSession | **Entfernt** (→ Authentik Social Source) |

**`google_oauth()` und `IdentityLink`:** Die bestehenden Google-OAuth-Routen (`GET /auth/oauth/google`, `GET /auth/oauth/google/callback`) und `IdentityLink`-Tabelle werden in P1 **entfernt**. Google/GitHub-Login wird stattdessen als Authentik Social Source konfiguriert — der User authentifiziert sich dann über Authentik's eigene OAuth-Flow-Seite (Klick auf "Login with Google" auf der Nextcloud-Login-Seite, oder direkt über `authentik.fichtlworks.com`). Der `/login`-Screen der Workplace-App unterstützt nur Email+Passwort (unverändert).

#### Geändert: `app/deps.py` — `get_current_user`

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = await validate_authentik_token(credentials.credentials)
    authentik_id: str = payload.get("sub")
    email: str = payload.get("email")

    if not authentik_id or not email:
        raise UnauthorizedException(detail="Invalid token claims")

    # Suche per authentik_id (Normalfall)
    result = await db.execute(
        select(User).where(User.authentik_id == authentik_id, User.deleted_at.is_(None))
    )
    user = result.scalar_one_or_none()

    if not user:
        # Lazy-Migration: bestehender User ohne authentik_id
        result = await db.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        user = result.scalar_one_or_none()
        if user:
            user.authentik_id = authentik_id
            await db.commit()
            await db.refresh(user)

    if not user:
        raise UnauthorizedException(detail="User not found")

    if not user.is_active:
        raise UnauthorizedException(detail="Account is disabled")

    return user
```

#### Neue Migration: `0015_authentik_id.py`

```sql
ALTER TABLE users ADD COLUMN authentik_id VARCHAR UNIQUE;
CREATE INDEX ix_users_authentik_id ON users(authentik_id);
```

#### Neue Migration: `0016_drop_user_sessions.py`

Wird erst ausgeführt **nachdem** `migrate_to_authentik.py` erfolgreich durchgelaufen ist.

```sql
DROP TABLE user_sessions;
DROP TABLE identity_links;  -- Google OAuth entfernt
```

#### Migrationsskript: `backend/scripts/migrate_to_authentik.py`

Ablauf:
1. Alle aktiven User aus `users`-Tabelle lesen (`deleted_at IS NULL`)
2. Pro User: `authentik_client.get_user_by_email()` — existiert bereits? → `authentik_id` speichern
3. Falls nicht: `authentik_client.create_user()` mit zufälligem Temp-Passwort
4. `authentik_client.set_password()` setzt Password-Reset-Flag via Authentik API
5. `authentik_id` in lokaler DB speichern + committen

**User-Experience während Migration:**
- Bestehende User bekommen keine automatische E-Mail (Authentik-SMTP optional)
- Beim nächsten Login via `/login`: ROPC-Grant liefert 401 → Frontend zeigt "Bitte Passwort zurücksetzen unter authentik.fichtlworks.com"
- Reset-Link wird im Login-Fehlertext ergänzt (einzige Frontend-Änderung in P1)
- Nach Reset: Login funktioniert normal über den gewohnten `/login`-Screen

### Frontend-Änderungen (P1 — minimal)

**Einzige Änderung:** `app/(auth)/login/page.tsx` — Fehlermeldung bei `HTTP_401` ergänzt:

```tsx
setError(
  apiErr?.error === "Invalid email or password"
    ? "Ungültige Zugangsdaten. Falls du dein Passwort noch nicht zurückgesetzt hast: authentik.fichtlworks.com"
    : (apiErr?.error ?? "Login fehlgeschlagen.")
);
```

Alles andere (Form, Tokens, context.tsx, client.ts) bleibt unverändert.

---

## Projekt 2: Nextcloud + SSO

### Docker-Infrastruktur

```yaml
nextcloud-db:
  image: mariadb:10.11
  volumes: [assist2_nextcloud_db_data]
  networks: [internal]
  environment:
    MYSQL_ROOT_PASSWORD: ${NEXTCLOUD_DB_ROOT_PASSWORD}
    MYSQL_DATABASE: nextcloud
    MYSQL_USER: nextcloud
    MYSQL_PASSWORD: ${NEXTCLOUD_DB_PASSWORD}

nextcloud:
  image: nextcloud:28-apache
  volumes: [assist2_nextcloud_data:/var/www/html]
  networks: [proxy, internal]
  # Traefik-Label: nextcloud.fichtlworks.com → :80
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
    OVERWRITEHOST: nextcloud.fichtlworks.com
```

**Neue Volumes:**
- `assist2_nextcloud_data`
- `assist2_nextcloud_db_data`

**Neue `.env`-Variablen:**
```bash
NEXTCLOUD_ADMIN_USER=admin
NEXTCLOUD_ADMIN_PASSWORD=           # stark, random
NEXTCLOUD_DB_PASSWORD=              # stark, random
NEXTCLOUD_DB_ROOT_PASSWORD=         # stark, random
NEXTCLOUD_ADMIN_APP_PASSWORD=       # App Password für Backend + n8n API-Calls
NEXTCLOUD_URL=https://nextcloud.fichtlworks.com
NEXTCLOUD_OIDC_CLIENT_ID=           # aus Authentik OIDC Provider (Nextcloud)
NEXTCLOUD_OIDC_CLIENT_SECRET=       # aus Authentik OIDC Provider (Nextcloud)
```

**Traefik-Routing:**
```
nextcloud.fichtlworks.com → nextcloud:80
```

### Authentik OIDC Provider für Nextcloud (einmalig)

In Authentik zusätzlich zur Backend-App:

**OAuth2 Provider `nextcloud`:**
- Redirect URI: `https://nextcloud.fichtlworks.com/apps/sociallogin/custom_oidc/authentik`
- Grant Types: `Authorization Code` nur
- Scopes: `openid`, `email`, `profile`
- Sub Mode: `Based on User's Email`

### Nextcloud Setup (via `occ` nach erstem Start)

```bash
# Social Login App installieren
docker exec nextcloud php occ app:install sociallogin

# Group Folders App installieren
docker exec nextcloud php occ app:install groupfolders

# Social Login konfigurieren (OIDC zu Authentik)
docker exec nextcloud php occ config:app:set sociallogin custom_providers --value='
{
  "custom_oidc": [{
    "name": "authentik",
    "title": "Login with Workplace",
    "authorizeUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/authorize/",
    "tokenUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/token/",
    "userInfoUrl": "https://authentik.fichtlworks.com/application/o/nextcloud/userinfo/",
    "clientId": "NEXTCLOUD_OIDC_CLIENT_ID",
    "clientSecret": "NEXTCLOUD_OIDC_CLIENT_SECRET",
    "scope": "openid email profile",
    "uidClaim": "preferred_username",
    "displayNameClaim": "name",
    "emailClaim": "email",
    "autoCreate": true,
    "defaultGroup": "nextcloud-users"
  }]
}'
```

Diese Befehle werden in einem Init-Script (`infra/nextcloud/init.sh`) gebündelt, das einmalig nach dem ersten Container-Start ausgeführt wird.

### Org-Gruppenordner — Admin-Mitgliedschaft

Der Nextcloud-Admin-Account wird in **jede** Org-Gruppe aufgenommen. Dies ist notwendig, damit die Backend-WebDAV-Abfragen unter dem Admin-Account auf die Gruppenordner zugreifen können.

```
Nextcloud-Gruppe: org-{slug}
Mitglieder:       admin (immer), + alle Org-Mitglieder
Group Folder:     /Organizations/{slug}/  (gemountet für alle Gruppenmitglieder)
```

**WebDAV-Pfad für Backend (korrekt):**
```
/remote.php/dav/files/admin/Organizations/{org-slug}/
```
Funktioniert nur weil Admin explizit in `org-{slug}` ist. Diese Invariante wird vom n8n-Workflow sichergestellt (Admin wird bei `org_created` automatisch zur Gruppe hinzugefügt).

### Backend-Trigger (in bestehenden Services ergänzt)

**`app/services/org_service.py` — `create()`:**
```python
# Nach db.commit()
_fire_and_forget(n8n_client.trigger_workflow("nextcloud-provisioning", {
    "type": "org_created",
    "org": {"slug": org.slug, "name": org.name}
}))
```

**`app/services/membership_service.py` — `create_membership()` oder Inline in `memberships` Router:**
```python
# Nach db.commit(), nur wenn status="active"
_fire_and_forget(n8n_client.trigger_workflow("nextcloud-provisioning", {
    "type": "user_joined_org",
    "user": {"email": user.email, "display_name": user.display_name},
    "org": {"slug": org.slug, "name": org.name}
}))
```

Falls kein dedizierter `membership_service.add_member()` existiert, wird dieser als neues Service-Method angelegt und vom Memberships-Router verwendet.

---

## Projekt 3: Nextcloud-Plugin + n8n-Workflow

### n8n Workflow: `nextcloud-provisioning.json`

**Trigger:** `POST /webhook/nextcloud-provisioning`

**Payload-Schema:**
```json
// org_created
{ "type": "org_created", "org": { "slug": "...", "name": "..." } }

// user_created
{ "type": "user_created", "user": { "email": "...", "display_name": "..." } }

// user_joined_org
{
  "type": "user_joined_org",
  "user": { "email": "...", "display_name": "..." },
  "org": { "slug": "...", "name": "..." }
}
```

**Workflow-Knoten:**

```
Webhook (POST /webhook/nextcloud-provisioning)
  └─ Switch (field: type)
       │
       ├─ [org_created]
       │    ├─ HTTP: OCS — Gruppe anlegen
       │    │    POST /ocs/v1.php/cloud/groups  { groupid: "org-{slug}" }
       │    │    → Code Node: Parse OCS XML, prüfe statuscode 100 (ok) oder 102 (exists)
       │    ├─ HTTP: Group Folders API — Ordner anlegen
       │    │    POST /apps/groupfolders/folders  { mountpoint: "Organizations/{slug}" }
       │    │    → Code Node: Extract folder_id aus Response
       │    ├─ HTTP: Group Folders API — Gruppe zuweisen
       │    │    POST /apps/groupfolders/folders/{folder_id}/groups
       │    │    Body: { group: "org-{slug}", permissions: 31 }
       │    └─ HTTP: OCS — Admin zur Gruppe hinzufügen
       │         POST /ocs/v1.php/cloud/users/admin/groups
       │         Body: { groupid: "org-{slug}" }
       │
       ├─ [user_created]
       │    └─ HTTP: OCS — Nextcloud-User anlegen (falls nicht vorhanden)
       │         POST /ocs/v1.php/cloud/users
       │         Body: { userid: "{email-prefix}", email, displayname, password: random }
       │         → Code Node: Parse XML, statuscode 100 = ok, 102 = already exists (beide Success)
       │
       └─ [user_joined_org]
            ├─ HTTP: OCS — User zur Org-Gruppe hinzufügen
            │    POST /ocs/v1.php/cloud/users/{uid}/groups
            │    Body: { groupid: "org-{slug}" }
            │    → Code Node: statuscode 100 = ok, 102 = already member (beide Success)
            └─ (Gruppe + Ordner existieren bereits durch org_created-Event)
```

**OCS XML-Parsing (Code Node):**
Alle Nextcloud OCS API-Calls geben HTTP 200 mit XML-Body zurück, auch bei Fehlern. n8n's Standard-Error-Detection greift nicht. Jeder OCS-Call bekommt einen nachgelagerten Code Node der `ocs.meta.statuscode` ausliest:
- `100` → Success
- `102` → Already exists → wird als Success behandelt
- Andere → Error, Workflow schlägt fehl und loggt

Auth für alle Nextcloud-Calls: `NEXTCLOUD_ADMIN_APP_PASSWORD` als HTTP Basic Auth (`admin:{app_password}`), gespeichert in n8n-Credentials.

### Plugin-Struktur

```
plugins/nextcloud/
├── manifest.json
├── backend/
│   ├── routes.py       GET /organizations/{org_id}/nextcloud/files
│   ├── service.py      Nextcloud WebDAV Client
│   └── schemas.py      NextcloudFile, NextcloudFileList
└── frontend/
    ├── index.tsx        Plugin-Registrierung
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
  "config_schema": {}
}
```

`nextcloud_url` ist keine Per-Org-Konfiguration — der Wert kommt aus der Backend-Env-Variable `NEXTCLOUD_URL` und wird serverseitig eingesetzt.

**Backend `routes.py`:**

```python
@router.get("/organizations/{org_id}/nextcloud/files")
async def get_nextcloud_files(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NextcloudFileList:
    # 1. Membership prüfen: User muss aktives Mitglied von org_id sein
    membership = await db.execute(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.organization_id == org_id,
            Membership.status == "active",
        )
    )
    if not membership.scalar_one_or_none():
        raise ForbiddenException()

    # 2. Org-Slug holen
    org = await org_service.get_by_id(db, org_id)

    # 3. WebDAV PROPFIND
    return await nextcloud_service.list_files(org.slug)
```

Die Membership-Prüfung ist explizit und unabhängig von `require_permission`, um die Multi-Tenancy-Invariante sicherzustellen.

**Backend `service.py`:**

```python
class NextcloudService:
    async def list_files(self, org_slug: str) -> NextcloudFileList:
        """
        WebDAV PROPFIND auf:
        /remote.php/dav/files/admin/Organizations/{org_slug}/
        Auth: Basic admin:{NEXTCLOUD_ADMIN_APP_PASSWORD}
        Parst XML-Response (DAV: Namespace), gibt die 10 neuesten Dateien zurück.
        Fehler (Nextcloud down, Ordner nicht vorhanden) → leere Liste, kein App-Crash.
        """
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

- SWR-Fetch auf `/api/v1/organizations/{org_id}/nextcloud/files`, 60s Revalidierung
- Bei Fehler: leerer Zustand mit "Dateien momentan nicht verfügbar", kein Crash
- "Alle Dateien öffnen" → `https://nextcloud.fichtlworks.com` (aus Backend-Response)

---

## Fehlerbehandlung

| Szenario | Verhalten |
|---|---|
| Authentik nicht erreichbar beim Login | Backend gibt 503 zurück, Frontend zeigt "Dienst nicht verfügbar" |
| JWKS-Cache abgelaufen, Authentik down | Letzter Cache bis 5min TTL, danach 503 |
| Nextcloud-Widget-API schlägt fehl | Widget zeigt "Dateien momentan nicht verfügbar", kein App-Crash |
| n8n `org_created` Provisioning fehlgeschlagen | Fehler geloggt, User kann Org trotzdem nutzen; Nextcloud-Ordner fehlt bis manueller Retry |
| OCS gibt statuscode 102 (already exists) | Workflow behandelt als Success (Code Node) |
| User hat kein Nextcloud-Konto beim ersten Org-Join | `user_created` fehlt → `user_joined_org` schlägt fehl → OCS User-Create wird als Fallback in `user_joined_org`-Branch ergänzt |

---

## Implementierungsreihenfolge (vollständig)

```
P1: Authentik + Auth-Migration
  1.  infra/docker-compose.yml: authentik-db, authentik-server, authentik-worker
  2.  infra/.env: neue Variablen
  3.  Migration 0015_authentik_id
  4.  requirements: httpx (prüfen), PyJWT[crypto] hinzufügen, bcrypt + python-jose entfernen
  5.  app/services/authentik_client.py (neu)
  6.  app/core/security.py (JWKS-Validierung, alte Funktionen entfernen)
  7.  app/services/auth_service.py (UserSession + google_oauth entfernen, Authentik-Proxy)
  8.  app/routers/auth.py (OAuth-Google-Routen entfernen)
  9.  app/deps.py (get_current_user auf JWKS)
  10. app/(auth)/login/page.tsx (Fehlermeldung Passwort-Reset-Hinweis)
  11. backend/scripts/migrate_to_authentik.py ausführen
  11b. ORM-Klassen `UserSession` und `IdentityLink` aus `app/models/user.py` entfernen
  12. Migration 0016_drop_user_sessions

P2: Nextcloud + SSO
  1.  infra/docker-compose.yml: nextcloud-db, nextcloud
  2.  infra/.env: neue Variablen
  3.  infra/nextcloud/init.sh (occ-Befehle)
  4.  Authentik: OIDC Provider Application "nextcloud" anlegen
  5.  n8n-Trigger in org_service.create()
  6.  membership_service.py: add_member() + n8n-Trigger
  7.  Group Folders App + Admin-Gruppen-Invariante dokumentieren

P3: Plugin + Workflow
  1.  workflows/nextcloud-provisioning.json
  2.  plugins/nextcloud/manifest.json
  3.  plugins/nextcloud/backend/schemas.py
  4.  plugins/nextcloud/backend/service.py
  5.  plugins/nextcloud/backend/routes.py
  6.  plugins/nextcloud/frontend/components/RecentFilesWidget.tsx
  7.  plugins/nextcloud/frontend/index.tsx
  8.  Plugin in Backend-Main registrieren
```
