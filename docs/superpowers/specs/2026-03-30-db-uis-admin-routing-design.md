# Design: Datenbank-UIs & Admin-Pfad-Routing

**Datum:** 2026-03-30
**Status:** Genehmigt

## Ziel

Spezialisierte Datenbank-UIs für alle installierten Datenbanken einrichten und den gesamten Tool-Zugriff von separaten Subdomains auf pfadbasiertes Routing unter `admin.fichtlworks.com/<appname>` umstellen.

## Neue Services (Datenbank-UIs)

### pgAdmin (`admin.fichtlworks.com/pgadmin`)
- **Image:** `dpage/pgadmin4`
- **Container:** `assist2-pgadmin`
- **Konfiguration:**
  - `SCRIPT_NAME=/pgadmin` — pgAdmin generiert alle URLs relativ zu diesem Pfad
  - `servers.json` Volume mit allen 3 PostgreSQL-Instanzen vorkonfiguriert:
    - `assist2-postgres` (platform_db, user: platform)
    - `assist2-authentik-db` (authentik, user: authentik)
    - `assist2-litellm-postgres` (litellm_db, user: litellm)
  - Login-Credentials via Env: `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD`
- **Netzwerke:** `internal` + `proxy`

### phpMyAdmin (`admin.fichtlworks.com/phpmyadmin`)
- **Image:** `phpmyadmin/phpmyadmin`
- **Container:** `assist2-phpmyadmin`
- **Konfiguration:**
  - `PMA_HOST=assist2-nextcloud-db`
  - `PMA_ABSOLUTE_URI=https://admin.fichtlworks.com/phpmyadmin/`
- **Netzwerke:** `internal` + `proxy`

### Redis Commander (`admin.fichtlworks.com/redis`)
- **Image:** `rediscommander/redis-commander`
- **Container:** `assist2-redis-commander`
- **Konfiguration:**
  - `REDIS_HOST=assist2-redis`
  - `REDIS_PASSWORD` aus `.env`
  - `URL_PREFIX=/redis`
- **Netzwerke:** `internal` + `proxy`

## Routing-Änderungen

### Neue Pfad-Routing-Tabelle

| Neuer Pfad | Interner Service | Strip-Prefix |
|---|---|---|
| `admin.fichtlworks.com/pgadmin` | `assist2-pgadmin:80` | `/pgadmin` |
| `admin.fichtlworks.com/phpmyadmin` | `assist2-phpmyadmin:80` | `/phpmyadmin` |
| `admin.fichtlworks.com/redis` | `assist2-redis-commander:8081` | `/redis` |
| `admin.fichtlworks.com/litellm` | `assist2-litellm:4000` | `/litellm` |
| `admin.fichtlworks.com/pdf` | `assist2-stirling-pdf:8080` | `/pdf` |
| `admin.fichtlworks.com/whisper` | `assist2-whisper:9000` | `/whisper` |
| `admin.fichtlworks.com/n8n` | `assist2-n8n:5678` | `/n8n` |
| `admin.fichtlworks.com/nextcloud` | `assist2-nextcloud:80` | `/nextcloud` |

### Entfernte Subdomains

Die folgenden Routen und Services in `routes.yml` werden entfernt:
- `litellm.fichtlworks.com`
- `pdf.fichtlworks.com`
- `whisper.fichtlworks.com`
- `nextcloud.fichtlworks.com`
- `assist2.fichtlworks.com/n8n` (PathPrefix-Route)

### Bestehend (unverändert)
- `admin.fichtlworks.com` → `assist2-admin:3001` (Catch-All, niedrigste Priority)
- `assist2.fichtlworks.com` → Hauptplattform (Frontend + API)
- `authentik.fichtlworks.com` → Authentik (zu komplex für Subpfad-Migration)

## App-Konfigurationsänderungen

### n8n
- `N8N_PATH=/n8n` bleibt — Host ändert sich auf `admin.fichtlworks.com`
- `N8N_HOST=admin.fichtlworks.com`
- `WEBHOOK_URL=https://admin.fichtlworks.com/n8n/`

### Nextcloud
- `OVERWRITEHOST=admin.fichtlworks.com`
- `OVERWRITEWEBROOT=/nextcloud`
- `OVERWRITEPROTOCOL=https`
- `NEXTCLOUD_TRUSTED_DOMAINS` ergänzen um `admin.fichtlworks.com`

### LiteLLM, Stirling PDF, Whisper
- Keine App-Konfigurationsänderung nötig (API-Services, keine absoluten HTML-Pfade)

## Traefik Middleware

Für jeden Tool-Pfad eine dedizierte `stripPrefix` Middleware:
```yaml
pdf-strip:
  stripPrefix:
    prefixes: [/pdf]
whisper-strip:
  stripPrefix:
    prefixes: [/whisper]
# usw.
```

Alle Pfad-Routen bekommen `priority: 10` (höher als Admin-Catch-All).
Alle Pfad-Routen bekommen `middlewares: [authentik]`.

## Authentik-Änderungen

### Bestehende Provider aktualisieren
- `stirling-pdf` Provider: `external_host` → `https://admin.fichtlworks.com/pdf`
- `whisper` Provider: `external_host` → `https://admin.fichtlworks.com/whisper`

### Neue Proxy Providers + Applications
- `pgadmin` → `https://admin.fichtlworks.com/pgadmin`
- `phpmyadmin` → `https://admin.fichtlworks.com/phpmyadmin`
- `redis-commander` → `https://admin.fichtlworks.com/redis`
- `n8n` → `https://admin.fichtlworks.com/n8n`
- `nextcloud-admin` → `https://admin.fichtlworks.com/nextcloud`
- `litellm` → `https://admin.fichtlworks.com/litellm`

Alle dem bestehenden Embedded Outpost hinzufügen.

## Backend-Änderungen (`superadmin.py`)

`COMPONENTS`-Liste aktualisieren:
- Alle `admin_url`-Felder auf neue Pfade setzen
- Neue Einträge für pgAdmin, phpMyAdmin, Redis Commander hinzufügen mit Health-Pfaden:
  - pgAdmin: `/pgadmin/misc/ping`
  - phpMyAdmin: `/phpmyadmin/`
  - Redis Commander: `/redis/`

## Nicht migriert

- **Authentik** (`authentik.fichtlworks.com`): Eigene URL-Logik für OIDC-Callbacks, SSO-Flows und Outpost-Kommunikation macht Subpfad-Migration nicht praktikabel.
