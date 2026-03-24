# 07 — Implementation Waves

## Übersicht

| Wave | Name | Focus | Voraussetzung |
|---|---|---|---|
| 1 | Platform & Core | Infrastruktur, Auth, Domain | – |
| 2 | Workspace Shell + Plugin Framework | UI, Plugin-System | Wave 1 |
| 3 | Workflows + Provisioning | n8n, AI-Delivery-Grundlage | Wave 1+2 |
| 4 | User Story Plugin | Erster vollständiger Plugin | Wave 2+3 |
| 5 | Inbox + Calendar | Provider-Plugins | Wave 2+3 |
| 6 | Voice / Image / Training | Multimodale Eingabe | Wave 4+5 |

---

## Wave 1 — Platform & Core

**Ziel:** Lauffähige Infrastruktur mit Auth, User, Org, RBAC

### Deliverables

- [ ] Docker Compose Stack (Traefik, Postgres, Redis, Backend)
- [ ] PostgreSQL Schema (alle Core-Tabellen via Alembic)
- [ ] FastAPI Backend Grundstruktur
- [ ] Auth: Register, Login, Logout, JWT Refresh
- [ ] Auth: Google OAuth2 (minimal)
- [ ] User API: CRUD + Profil
- [ ] Organization API: CRUD
- [ ] Membership API: Invite, Accept, List
- [ ] Role + Permission: System-Rollen, RBAC-Middleware
- [ ] Group API: CRUD + Members
- [ ] Health Endpoint: `/health`
- [ ] Redis Session Store + JWT Blacklist
- [ ] `.env.example` vollständig
- [ ] Alembic Migration Initial

### Abhängigkeiten
- keine

### Kritische Pfade
- Permission-Middleware muss vor allen Domain-Endpoints fertig sein
- `organization_id`-Tenant-Isolation muss ab dem ersten Commit korrekt sein

### Tests (Wave 1)
- Auth: Login, Register, Token-Refresh, Logout
- Permission-Check: Forbidden vs. Allowed
- Tenant-Isolation: User aus Org A kann Org B nicht sehen

---

## Wave 2 — Workspace Shell + Plugin Framework

**Ziel:** Next.js Shell mit Plugin-System und API-Integration

### Deliverables

- [ ] Next.js App Router Setup
- [ ] Auth-Seiten: Login, Register, OAuth-Redirect
- [ ] Org-Shell: Sidebar, Topbar, Layout
- [ ] API-Client (fetch-Wrapper, Token-Handling)
- [ ] Plugin-Registry (Frontend): Lädt aktive Plugins der Org
- [ ] Plugin-Slot-System: Slot-Renderer für alle definierten Slots
- [ ] Plugin API: Backend-Endpoints für Aktivierung/Deaktivierung
- [ ] Plugin-Manifest-Validierung (Backend)
- [ ] Beispiel-Plugin: `hello-world` (UI-Only, kein Backend)
- [ ] Basis-Dashboard (Widget-Slots)
- [ ] Settings-Seite für Plugins (Org Admin)

### Abhängigkeiten
- Wave 1 vollständig

### Kritische Pfade
- Plugin-Slot-System muss erweiterbar ohne Re-Deploy sein (dynamische Imports)
- Auth-State muss über alle Org-Routen konsistent sein

---

## Wave 3 — Workflows + AI-Delivery-Grundlage

**Ziel:** n8n läuft, erste Workflows, Agent-Infrastruktur

### Deliverables

- [ ] n8n in Docker Compose integriert
- [ ] n8n Authentifizierung via ForwardAuth (Traefik → Backend)
- [ ] WorkflowDefinition / WorkflowExecution Datenmodell
- [ ] Workflow API: Trigger, List, Execution-Detail
- [ ] User Provisioning Workflow (n8n)
- [ ] Story Lifecycle Workflow (n8n, stub)
- [ ] Agent-Datenmodell + API
- [ ] Agent Invoke Endpoint (Backend → AI-API)
- [ ] AI-Step Persistenz-Middleware (Modell, Prompt, Tokens speichern)
- [ ] ScrumMasterAI Prompt + DoR-Check implementiert
- [ ] AI Delivery Workflow Struktur (n8n, ohne alle Agenten)

### Abhängigkeiten
- Wave 1 vollständig
- Wave 2 für UI-Anzeige (optional)

### Kritische Pfade
- n8n Webhook-URLs müssen intern erreichbar sein (Backend → n8n)
- Workflow-Execution-Snapshot muss atomar geschrieben werden

---

## Wave 4 — User Story Plugin

**Ziel:** Vollständiger erster Hybrid-Plugin

### Deliverables

- [ ] UserStory Datenmodell + Migrations
- [ ] TestCase Datenmodell + Migrations
- [ ] User Story API (CRUD, Status-Transition)
- [ ] User Story Plugin Manifest
- [ ] Plugin-Backend: Routen, Service, Validierung
- [ ] Plugin-Frontend: Story-Liste, Story-Detail, Story-Board
- [ ] Story Lifecycle Workflow vollständig (alle Status-Übergänge)
- [ ] ScrumMasterAI: vollständiger DoR-Check
- [ ] AI Delivery Workflow: alle Agenten integriert
- [ ] Gate-Decision Logik implementiert
- [ ] Rework-Schleifen implementiert
- [ ] TestCase API + UI
- [ ] Story Plugin Aktivierung in Org-Settings

### Abhängigkeiten
- Wave 1, 2, 3 vollständig

---

## Wave 5 — Unified Inbox + Calendar

**Ziel:** Zwei Provider-Plugins mit OAuth und Sync

### Deliverables

**Unified Inbox:**
- [ ] MailConnection Datenmodell
- [ ] Message Datenmodell
- [ ] Gmail OAuth2 Integration
- [ ] Outlook OAuth2 Integration (optional)
- [ ] Mail-Sync Celery Task
- [ ] Inbox API (Connections, Messages, Read/Archive)
- [ ] Inbox Plugin Manifest + Frontend

**Calendar:**
- [ ] CalendarConnection Datenmodell
- [ ] CalendarEvent Datenmodell
- [ ] Google Calendar OAuth2 Integration
- [ ] Calendar-Sync Celery Task
- [ ] Calendar API (Connections, Events, Create)
- [ ] Calendar Plugin Manifest + Frontend

**Gemeinsam:**
- [ ] Token-Refresh-Mechanismus für alle Provider
- [ ] Verschlüsselung aller OAuth-Tokens (Encryption Key)
- [ ] Authentik Integration (optional, Wave 5+)

### Abhängigkeiten
- Wave 1, 2 vollständig
- Wave 3 für Workflow-Trigger

---

## Wave 6 — Voice / Image / Training

**Ziel:** Multimodale Eingabe, Wissensbasis, Trainingsdokumentation

### Deliverables

**Voice Input:**
- [ ] WebRTC / MediaRecorder Frontend-Integration
- [ ] Whisper API Integration (Transkription)
- [ ] Voice Command → Story/Task Erstellen
- [ ] Voice Action Plugin Manifest

**Image Input:**
- [ ] Screenshot/Upload-Handling
- [ ] AI Vision: Screenshot → Story/Bug-Report
- [ ] Image Annotation UI

**Documentation & Training:**
- [ ] DocumentationTrainingAI vollständig
- [ ] Confluence-Export-Integration (optional, via MCP)
- [ ] Auto-generierte PDF-Outline aus Story
- [ ] Video-Script-Generator aus Story
- [ ] Questionnaire-Generator

**[ANNAHME]** Wave 6 setzt externe AI-APIs voraus (Whisper, Vision).
**[TRADE-OFF]** Voice/Image sind optionale Erweiterungen — die Kernplattform ist ohne diese vollständig nutzbar.

---

## Meilenstein-Übersicht

```
Wave 1:  Auth + Core Domain + Docker
Wave 2:  Shell + Plugin-System (visuell nutzbar)
Wave 3:  n8n + AI-Grundlage (erste Automatisierung)
Wave 4:  User Stories (erstes echtes Feature)
Wave 5:  Inbox + Calendar (Provider-Anbindung)
Wave 6:  Voice + Training (Premium-Features)
```

## Reihenfolge-Regeln

1. Sicherheits-kritische Funktionen (Auth, Permissions) kommen immer zuerst
2. Jede Wave muss eigenständig testbar sein
3. Keine Wave führt Breaking Changes an vorherigen APIs ein ohne Migration
4. Plugin-System-Änderungen sind rückwärtskompatibel (Manifest-Versionierung)
