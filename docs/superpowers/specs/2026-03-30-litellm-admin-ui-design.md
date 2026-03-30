# LiteLLM Admin UI — Design Spec

**Date:** 2026-03-30
**Status:** Approved

## Ziel

Das LiteLLM Admin UI aktivieren, um Modelle, API-Keys und Nutzungsstatistiken über eine Web-Oberfläche zu verwalten. Das UI ist unter `litellm.fichtlworks.com` erreichbar, jedoch nur mit HTTP Basic Auth geschützt (nicht öffentlich zugänglich).

## Architektur

```
Internet → Traefik → [Basic Auth Middleware] → litellm:4000/ui
                                                     ↓
                                             litellm-postgres:5432
                                             (separate Instanz)
```

## Komponenten

### Neuer Service: `litellm-postgres`

- Image: `postgres:16-alpine`
- Container: `assist2-litellm-postgres`
- Volume: `assist2_litellm_db_data`
- Netzwerk: `internal` only
- Healthcheck: `pg_isready -U litellm -d litellm_db`
- Umgebungsvariablen:
  - `POSTGRES_DB=litellm_db`
  - `POSTGRES_USER=litellm`
  - `POSTGRES_PASSWORD=${LITELLM_DB_PASSWORD}`

### Änderungen am `litellm` Service

- Neue Umgebungsvariable: `DATABASE_URL=postgresql://litellm:${LITELLM_DB_PASSWORD}@assist2-litellm-postgres:5432/litellm_db`
- `depends_on: litellm-postgres: condition: service_healthy`
- Traefik Labels:
  - Router: `litellm.fichtlworks.com`, Entrypoint `websecure`, TLS Let's Encrypt
  - Middleware: `litellm-auth` (Basic Auth)
  - Service Port: 4000

### `litellm/config.yaml` Erweiterung

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  ui_access_mode: "username_password"
```

`ui_access_mode: username_password` aktiviert den LiteLLM-eigenen Login-Screen (Master Key als Passwort).

### `.env` Erweiterungen

```
LITELLM_DB_PASSWORD=<zufällig generiert>
LITELLM_UI_AUTH=admin:$$1$$...   # bcrypt-Hash für Traefik Basic Auth
```

## Sicherheit

- Traefik Basic Auth als erste Schutzschicht (wie Traefik-Dashboard)
- LiteLLM Master Key als zweite Schutzschicht im UI selbst
- `litellm-postgres` nur im `internal`-Netzwerk, nicht von außen erreichbar
- TLS über Let's Encrypt

## Datenpersistenz

LiteLLM speichert in der DB: virtuelle Keys, Teams, Spend-Tracking, Request-Logs. Das Volume `assist2_litellm_db_data` wird wie alle anderen DB-Volumes behandelt.

## Keine Änderungen an

- `infra/postgres/init.sql` (separate Instanz, kein gemeinsames Init)
- Backend/Frontend-Services (keine Abhängigkeit auf LiteLLM-DB)
- Bestehende `litellm/config.yaml` Modell-Definitionen

## Deployment

1. `.env` um `LITELLM_DB_PASSWORD` und `LITELLM_UI_AUTH` ergänzen
2. `docker-compose.yml` anpassen
3. `litellm/config.yaml` anpassen
4. `docker compose up -d litellm-postgres litellm` ausführen
5. LiteLLM führt DB-Migrationen beim ersten Start automatisch durch
