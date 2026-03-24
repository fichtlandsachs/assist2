# 05 — Docker Infrastructure

## Netzwerke

```yaml
networks:
  proxy:
    name: proxy
    driver: bridge
    # Traefik ist der einzige Service in diesem Netzwerk + alle extern exponierten Services

  internal:
    name: internal
    driver: bridge
    # Alle internen Services kommunizieren hier
    internal: true  # kein direkter Internet-Zugang
```

---

## Volumes

```yaml
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  n8n_data:
    driver: local
  traefik_certs:
    driver: local
  authentik_media:
    driver: local
```

---

## Docker Compose — Vollstruktur

```yaml
# infra/docker-compose.yml
version: "3.9"

services:

  # ─── TRAEFIK ───────────────────────────────────────────────
  traefik:
    image: traefik:v3.0
    container_name: traefik
    restart: unless-stopped
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--providers.docker.network=proxy"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.web.http.redirections.entrypoint.scheme=https"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=${ACME_EMAIL}"
      - "--certificatesresolvers.letsencrypt.acme.storage=/certs/acme.json"
      - "--log.level=INFO"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik_certs:/certs
    networks:
      - proxy
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik-dashboard.rule=Host(`traefik.${DOMAIN}`)"
      - "traefik.http.routers.traefik-dashboard.tls.certresolver=letsencrypt"
      - "traefik.http.routers.traefik-dashboard.middlewares=auth-basic"
      - "traefik.http.middlewares.auth-basic.basicauth.users=${TRAEFIK_BASIC_AUTH}"

  # ─── POSTGRES ──────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    networks:
      - internal
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── REDIS ─────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    container_name: redis
    restart: unless-stopped
    command: redis-server --requirepass ${REDIS_PASSWORD} --save 60 1
    volumes:
      - redis_data:/data
    networks:
      - internal
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ─── BACKEND ───────────────────────────────────────────────
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    container_name: backend
    restart: unless-stopped
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      JWT_SECRET: ${JWT_SECRET}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
      N8N_WEBHOOK_URL: http://n8n:5678
      N8N_API_KEY: ${N8N_API_KEY}
      ENVIRONMENT: ${ENVIRONMENT:-production}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal
      - proxy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 15s
      timeout: 5s
      retries: 3
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.${DOMAIN}`)"
      - "traefik.http.routers.backend.tls.certresolver=letsencrypt"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"
      - "traefik.docker.network=proxy"

  # ─── WORKER ────────────────────────────────────────────────
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    container_name: worker
    restart: unless-stopped
    command: celery -A app.worker worker --loglevel=info --concurrency=4
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://:${REDIS_PASSWORD}@redis:6379/0
      SECRET_KEY: ${SECRET_KEY}
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal

  # ─── FRONTEND ──────────────────────────────────────────────
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: production
    container_name: frontend
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: https://api.${DOMAIN}
      NEXT_PUBLIC_APP_URL: https://app.${DOMAIN}
    depends_on:
      - backend
    networks:
      - internal
      - proxy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000"]
      interval: 15s
      timeout: 5s
      retries: 3
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`app.${DOMAIN}`)"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.frontend.loadbalancer.server.port=3000"
      - "traefik.docker.network=proxy"

  # ─── N8N ───────────────────────────────────────────────────
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: n8n_db
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      N8N_HOST: n8n.${DOMAIN}
      N8N_PORT: 5678
      N8N_PROTOCOL: https
      WEBHOOK_URL: https://n8n.${DOMAIN}/
      EXECUTIONS_DATA_SAVE_ON_ERROR: all
      EXECUTIONS_DATA_SAVE_ON_SUCCESS: all
      EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS: true
    volumes:
      - n8n_data:/home/node/.n8n
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal
      - proxy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5678/healthz"]
      interval: 15s
      timeout: 5s
      retries: 3
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`n8n.${DOMAIN}`)"
      - "traefik.http.routers.n8n.tls.certresolver=letsencrypt"
      - "traefik.http.routers.n8n.middlewares=n8n-auth"
      - "traefik.http.middlewares.n8n-auth.forwardauth.address=http://backend:8000/api/v1/auth/verify"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
      - "traefik.docker.network=proxy"
```

---

## Umgebungsvariablen (.env Vorlage)

```bash
# infra/.env.example
# [SECURITY] Diese Datei niemals in Git committen!

DOMAIN=example.com
ENVIRONMENT=production
ACME_EMAIL=admin@example.com

# PostgreSQL
POSTGRES_USER=platform
POSTGRES_PASSWORD=CHANGE_ME_STRONG_PASSWORD
POSTGRES_DB=platform_db

# Redis
REDIS_PASSWORD=CHANGE_ME_REDIS_PASSWORD

# Backend Secrets
SECRET_KEY=CHANGE_ME_64_CHARS_MIN
JWT_SECRET=CHANGE_ME_64_CHARS_MIN
ENCRYPTION_KEY=CHANGE_ME_32_BYTES_BASE64  # für verschlüsselte Felder

# n8n
N8N_ENCRYPTION_KEY=CHANGE_ME_32_CHARS
N8N_API_KEY=CHANGE_ME_N8N_API_KEY

# Traefik Dashboard
TRAEFIK_BASIC_AUTH=admin:$$apr1$$...  # htpasswd format

# OAuth Providers (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
```

---

## Traefik Routing Übersicht

| Route | Service | Auth |
|---|---|---|
| `app.{DOMAIN}` | frontend | keine (App-Auth) |
| `api.{DOMAIN}` | backend | JWT (App-intern) |
| `n8n.{DOMAIN}` | n8n | ForwardAuth via Backend |
| `traefik.{DOMAIN}` | traefik-dashboard | BasicAuth |
| `auth.{DOMAIN}` | authentik (optional) | keine |

---

## Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.12-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

FROM base AS dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM dependencies AS production
COPY . .
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS base
WORKDIR /app

FROM base AS dependencies
COPY package.json package-lock.json ./
RUN npm ci --only=production

FROM base AS builder
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM base AS production
COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY package.json .
RUN adduser --disabled-password appuser && chown -R appuser /app
USER appuser
EXPOSE 3000
HEALTHCHECK CMD curl -f http://localhost:3000 || exit 1
CMD ["npm", "start"]
```

---

## PostgreSQL Init Script

```sql
-- infra/postgres/init.sql
-- Erstellt separate Datenbanken für Backend und n8n

CREATE DATABASE n8n_db;
GRANT ALL PRIVILEGES ON DATABASE n8n_db TO platform;

-- UUID Extension für alle Datenbanken
\c platform_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

\c n8n_db
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

---

## Deployment-Prinzipien

1. **Kein manuelles Eingreifen** — alle Services via Compose steuerbar
2. **Rollback** via `docker compose up -d --scale backend=0` + Image-Wechsel
3. **Healthchecks** vor jedem Traffic-Routing (Traefik wartet auf Healthy)
4. **Secrets nur via `.env`** — niemals hardcoded
5. **`internal: true`** Netzwerk — DB und Redis niemals direkt erreichbar
6. **Least Privilege** — Container laufen als non-root User
7. **[TRADE-OFF]** Kein Kubernetes in Wave 1-3 — Docker Compose ist ausreichend und einfacher
