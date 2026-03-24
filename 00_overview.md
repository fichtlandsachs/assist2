# 00 — System Overview & Service Landscape

## Executive Technical Summary

Die AI-Native Workspace Platform ist eine mandantenfähige, pluginbasierte Delivery-Plattform.
Sie kombiniert klassische SaaS-Architektur mit AI-Agenten-Orchestrierung und strukturiertem Workflow-Management.

Kernprinzipien:
- **Multi-Tenant First** — alle Daten sind organisationsgebunden
- **API-First** — keine Geschäftslogik im UI
- **Plugin-First** — Features sind gekapselte Erweiterungen
- **AI-Native** — Agenten sind First-Class-Citizens im Delivery-Prozess
- **Security by Design** — Permissions serverseitig, keine Secrets im Code

---

## Zielarchitektur (Überblick)

```
Internet
   │
[Traefik] ─── SSL-Termination, Routing, Middleware
   │
   ├── [Frontend]       Next.js/TypeScript – Workspace Shell
   ├── [Backend]        FastAPI/Python – Core API
   ├── [n8n]            Workflow Engine – Orchestrierung
   └── [Authentik]      Identity Provider (optional, federated)

[Backend] ──── [PostgreSQL]   Primärdatenbank
           ──── [Redis]        Cache + Queue + Session
           ──── [n8n]          Workflow-Trigger (intern)
```

---

## Hauptkomponenten

| Komponente | Technologie | Verantwortung |
|---|---|---|
| Workspace Shell | Next.js + TypeScript | UI-Host, Plugin-Mount, Navigation |
| Core API | FastAPI + Python | Business Logic, Auth, Domain |
| Identity Provider | Authentik (optional) | SSO, Federation, User Sync |
| Workflow Engine | n8n | Orchestrierung, AI-Steps, Automation |
| Datenbank | PostgreSQL 16 | Persistenz aller Domänendaten |
| Cache/Queue | Redis 7 | Sessions, Job-Queue, Pub/Sub |
| Reverse Proxy | Traefik v3 | Routing, TLS, Auth-Middleware |

---

## Service Landscape

### traefik

- **Zweck**: Zentraler Reverse Proxy und Edge Router
- **Verantwortung**: TLS-Termination, Host-basiertes Routing, Rate Limiting, Auth-Forward
- **Netzwerk**: `proxy` (extern), `internal` (intern)
- **Abhängigkeiten**: keine
- **Extern**: ja (Port 80/443)
- **Labels**: konfiguriert alle anderen Services via Docker Labels

---

### frontend

- **Zweck**: Workspace Shell – die einzige UI des Systems
- **Verantwortung**: Plugin-Mounting, Navigation, Auth-State, Theme, Routing
- **Technologie**: Next.js 14 App Router + TypeScript
- **Netzwerk**: `internal`
- **Abhängigkeiten**: `backend`
- **Extern**: ja (via Traefik, `app.{DOMAIN}`)
- **Regeln**:
  - Keine Geschäftslogik
  - Keine direkten DB-Zugriffe
  - Alle Daten via Backend-API

---

### backend

- **Zweck**: Zentrales API-Gateway und Business Logic Layer
- **Verantwortung**: Auth, Domain-Logik, Permission-Prüfung, Plugin-Registry, Workflow-Trigger
- **Technologie**: FastAPI + Python 3.12 + SQLAlchemy + Alembic
- **Netzwerk**: `internal`
- **Abhängigkeiten**: `postgres`, `redis`, `n8n`
- **Extern**: ja (via Traefik, `api.{DOMAIN}`)
- **[SECURITY]**: Alle Permissions werden hier geprüft, niemals im Frontend

---

### postgres

- **Zweck**: Primäre relationale Datenbank
- **Verantwortung**: Persistenz aller Domänendaten
- **Technologie**: PostgreSQL 16
- **Netzwerk**: `internal`
- **Abhängigkeiten**: keine
- **Extern**: nein
- **Volumes**: `postgres_data`
- **[SECURITY]**: Credentials nur via Umgebungsvariablen

---

### redis

- **Zweck**: Cache, Session Store, Message Queue
- **Verantwortung**: JWT-Blacklist, Session-TTLs, Celery-Queue, Pub/Sub für Events
- **Technologie**: Redis 7
- **Netzwerk**: `internal`
- **Abhängigkeiten**: keine
- **Extern**: nein
- **Volumes**: `redis_data`

---

### n8n

- **Zweck**: Zentrale Workflow-Orchestrierungsinstanz
- **Verantwortung**: Workflow-Ausführung, AI-Step-Integration, Provisioning, Delivery
- **Technologie**: n8n (selbstgehostet)
- **Netzwerk**: `internal`
- **Abhängigkeiten**: `postgres` (eigene DB), `redis`
- **Extern**: ja (via Traefik, `n8n.{DOMAIN}`, intern gesperrt per Auth-Middleware)
- **Volumes**: `n8n_data`
- **[ANNAHME]**: n8n verwendet eine eigene PostgreSQL-Datenbank (`n8n_db`)

---

### authentik *(optional, Wave 3+)*

- **Zweck**: Identity Provider mit Federation-Support
- **Verantwortung**: SSO, Google/GitHub/Apple OAuth, SAML, SCIM, User Sync
- **Technologie**: Authentik
- **Netzwerk**: `internal`
- **Abhängigkeiten**: `postgres` (eigene DB), `redis`
- **Extern**: ja (via Traefik, `auth.{DOMAIN}`)
- **[TRADE-OFF]**: Alternativ kann das Backend direkt OAuth2 implementieren (Wave 1 Default)

---

### worker *(Hintergrundprozess)*

- **Zweck**: Asynchrone Task-Verarbeitung
- **Verantwortung**: E-Mail-Sync, Kalender-Sync, Background-Jobs
- **Technologie**: Celery + Python (gleicher Code wie Backend)
- **Netzwerk**: `internal`
- **Abhängigkeiten**: `postgres`, `redis`, `backend`
- **Extern**: nein

---

## Netzwerktopologie

```
proxy-network (extern):
  traefik ←→ Internet

internal-network:
  traefik ←→ frontend
  traefik ←→ backend
  traefik ←→ n8n
  traefik ←→ authentik
  backend ←→ postgres
  backend ←→ redis
  backend ←→ n8n
  worker  ←→ postgres
  worker  ←→ redis
  n8n     ←→ postgres (n8n_db)
  n8n     ←→ redis
```

---

## Domänen-Übersicht

| Domäne | Modul | Beschreibung |
|---|---|---|
| User | Identity & Access | Nutzerkonten, Auth, Profile |
| Organization | Core Domain | Mandanten-Einheiten |
| Membership | Core Domain | User↔Org-Zuordnung |
| Role + Permission | Core Domain | RBAC |
| Group + GroupMember | Core Domain | Operative Teams |
| Agent | AI Delivery | AI-Agentenrollen |
| Plugin | Plugin Framework | Erweiterungsmodule |
| WorkflowDefinition | Workflow Engine | Workflow-Blueprints |
| WorkflowExecution | Workflow Engine | Ausführungsinstanzen |
| UserStory | User Story Plugin | Agile Arbeitspakete |
| TestCase | User Story Plugin | Testfälle zu Stories |
| MailConnection + Message | Unified Inbox | E-Mail-Integration |
| CalendarConnection + CalendarEvent | Calendar | Kalender-Integration |
