# LiteLLM Admin UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** LiteLLM Admin UI aktivieren unter `litellm.fichtlworks.com` mit separater PostgreSQL-Instanz und Traefik Basic Auth.

**Architecture:** Ein neuer `litellm-postgres` Container (postgres:16-alpine, nur `internal`-Netzwerk) dient als persistente DB für LiteLLM. Der bestehende `litellm` Service erhält `DATABASE_URL`, `depends_on` mit Healthcheck sowie Traefik-Labels inkl. Basic Auth Middleware. In `litellm/config.yaml` wird `ui_access_mode: username_password` gesetzt.

**Tech Stack:** Docker Compose, Traefik v3, PostgreSQL 16, LiteLLM (ghcr.io/berriai/litellm:main-latest)

---

## File Map

| File | Aktion |
|------|--------|
| `infra/docker-compose.yml` | Neuer Service `litellm-postgres`, Änderungen an `litellm` |
| `infra/.env` | `LITELLM_DB_PASSWORD` und `LITELLM_UI_AUTH` hinzufügen |
| `litellm/config.yaml` | `ui_access_mode: username_password` hinzufügen |

---

### Task 1: `.env` um Credentials erweitern

**Files:**
- Modify: `infra/.env`

- [ ] **Step 1: Passwörter generieren**

```bash
# LiteLLM DB Password
openssl rand -base64 32

# Traefik Basic Auth Hash (htpasswd-Format, bcrypt)
# Wähle ein UI-Passwort, dann hash es:
htpasswd -nbB admin '<DEIN_PASSWORT>'
# Falls htpasswd nicht verfügbar:
docker run --rm httpd:alpine htpasswd -nbB admin '<DEIN_PASSWORT>'
```

- [ ] **Step 2: `.env` ergänzen**

Folgende Zeilen ans Ende von `infra/.env` anhängen. `$`-Zeichen in htpasswd-Hashes müssen als `$$` escaped werden (Docker Compose interpolation):

```dotenv
# LiteLLM Admin UI
LITELLM_DB_PASSWORD=<generiertes-passwort>
LITELLM_UI_AUTH=admin:$$2y$$05$$<rest-des-bcrypt-hashes>
```

Beispiel: Wenn htpasswd `admin:$2y$05$abc123...xyz` ausgibt, wird daraus `admin:$$2y$$05$$abc123...xyz`.

- [ ] **Step 3: Prüfen dass .env nicht committed wird**

```bash
cd /opt/assist2 && git status infra/.env
```
Expected: `infra/.env` erscheint nicht in `git status` (steht in `.gitignore`).

---

### Task 2: `litellm-postgres` Service in `docker-compose.yml` hinzufügen

**Files:**
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: Volume deklarieren**

In `infra/docker-compose.yml` unter `volumes:` hinzufügen:

```yaml
  assist2_litellm_db_data:
```

(Alphabetisch einsortieren neben den anderen `assist2_*` Volumes.)

- [ ] **Step 2: `litellm-postgres` Service hinzufügen**

In `infra/docker-compose.yml` unter `services:` nach dem bestehenden `litellm` Service einfügen:

```yaml
  litellm-postgres:
    image: postgres:16-alpine
    container_name: assist2-litellm-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: litellm_db
      POSTGRES_USER: litellm
      POSTGRES_PASSWORD: ${LITELLM_DB_PASSWORD}
    volumes:
      - assist2_litellm_db_data:/var/lib/postgresql/data
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U litellm -d litellm_db"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
```

- [ ] **Step 3: Syntax validieren**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```
Expected: Kein Output (kein Fehler).

---

### Task 3: `litellm` Service aktualisieren

**Files:**
- Modify: `infra/docker-compose.yml`

- [ ] **Step 1: `DATABASE_URL` und `depends_on` hinzufügen**

Den bestehenden `litellm` Service in `docker-compose.yml` so anpassen:

```yaml
  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: assist2-litellm
    restart: unless-stopped
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LITELLM_MASTER_KEY: ${LITELLM_API_KEY:-sk-assist2}
      DATABASE_URL: postgresql://litellm:${LITELLM_DB_PASSWORD}@assist2-litellm-postgres:5432/litellm_db
    command:
      - "--config"
      - "/app/config.yaml"
      - "--port"
      - "4000"
    volumes:
      - ../litellm/config.yaml:/app/config.yaml:ro
    networks:
      - proxy
      - internal
    depends_on:
      litellm-postgres:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4000/health/liveliness"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.litellm.rule=Host(`litellm.fichtlworks.com`)"
      - "traefik.http.routers.litellm.entrypoints=websecure"
      - "traefik.http.routers.litellm.tls.certresolver=letsencrypt"
      - "traefik.http.services.litellm.loadbalancer.server.port=4000"
      - "traefik.http.routers.litellm.middlewares=litellm-auth@docker"
      - "traefik.http.middlewares.litellm-auth.basicauth.users=${LITELLM_UI_AUTH}"
```

- [ ] **Step 2: Syntax validieren**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```
Expected: Kein Output.

---

### Task 4: `litellm/config.yaml` aktualisieren

**Files:**
- Modify: `litellm/config.yaml`

- [ ] **Step 1: `ui_access_mode` in `general_settings` setzen**

`litellm/config.yaml` so anpassen:

```yaml
model_list:
  - model_name: claude-sonnet-4-6
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-haiku-4-5
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: claude-opus-4-6
    litellm_params:
      model: anthropic/claude-opus-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  ui_access_mode: "username_password"
```

---

### Task 5: Deployment und Verifikation

**Files:** keine neuen Dateien

- [ ] **Step 1: `litellm-postgres` starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d litellm-postgres
```
Expected: `Container assist2-litellm-postgres  Started`

- [ ] **Step 2: Auf DB-Healthcheck warten**

```bash
docker inspect --format='{{.State.Health.Status}}' assist2-litellm-postgres
```
Expected: `healthy` (ggf. 30s warten und wiederholen)

- [ ] **Step 3: `litellm` neu starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build litellm
```
Expected: `Container assist2-litellm  Started`

- [ ] **Step 4: LiteLLM Logs auf DB-Migration prüfen**

```bash
docker logs assist2-litellm --tail 30
```
Expected: Zeilen wie `Running DB migrations...` oder `LiteLLM: Proxy initialized` ohne Errors.

- [ ] **Step 5: Health-Endpoint direkt testen**

```bash
docker exec assist2-litellm curl -sf http://localhost:4000/health/liveliness
```
Expected: `{"status":"healthy"}`

- [ ] **Step 6: Admin UI im Browser aufrufen**

URL: `https://litellm.fichtlworks.com/ui`

1. Browser fragt nach Basic Auth → Credentials aus `LITELLM_UI_AUTH` (admin + gewähltes Passwort) eingeben
2. LiteLLM Login-Screen erscheint → Master Key aus `LITELLM_API_KEY` als Passwort eingeben
3. Dashboard mit Modellen und Usage-Stats sichtbar

- [ ] **Step 7: Commit**

```bash
cd /opt/assist2
git add litellm/config.yaml infra/docker-compose.yml
git commit -m "feat(litellm): enable Admin UI with separate postgres and traefik basic auth"
```

---

## Troubleshooting

**LiteLLM startet nicht / DB-Verbindungsfehler:**
```bash
docker logs assist2-litellm --tail 50
# Häufig: DATABASE_URL falsch oder litellm-postgres noch nicht healthy
docker inspect --format='{{.State.Health.Status}}' assist2-litellm-postgres
```

**Basic Auth funktioniert nicht:**
```bash
# Prüfe ob $$ korrekt escaped in .env
grep LITELLM_UI_AUTH infra/.env
# Traefik Middleware Logs
docker logs <traefik-container> 2>&1 | grep litellm
```

**UI zeigt "Not connected to DB":**
LiteLLM benötigt `DATABASE_URL` und laufende DB. Prüfe:
```bash
docker exec assist2-litellm env | grep DATABASE_URL
```
