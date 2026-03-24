# 03 — Plugin Architecture

## Konzept

Plugins sind First-Class-Erweiterungen der Plattform. Sie werden pro Organisation aktiviert,
haben einen definierten Lifecycle und integrieren sich nahtlos in die Workspace Shell.

Jedes Plugin ist atomar — es bringt eigene:
- UI-Komponenten (mount in Shell-Slots)
- API-Routen (eigener Namespace `/api/v1/plugins/{slug}/...`)
- Datenmodelle (eigene DB-Tabellen mit `organization_id`)
- Workflow-Hooks (n8n-Trigger registrieren)

---

## Plugin-Typen

| Typ | Beschreibung | Beispiel |
|---|---|---|
| `ui` | Reine UI-Erweiterung, kein eigenes Backend | Dashboard-Widget |
| `provider` | Datenintegration/Sync, kein eigenes UI | Gmail-Sync, Kalender-Sync |
| `action` | Führt Aktionen aus, reagiert auf Events | Webhook-Handler, AI-Trigger |
| `hybrid` | UI + Backend + Daten | User Story Plugin, Inbox Plugin |

---

## Plugin Manifest (JSON)

```json
{
  "$schema": "https://platform.local/schemas/plugin-manifest.v1.json",
  "slug": "user-story",
  "name": "User Story",
  "version": "1.2.0",
  "type": "hybrid",
  "author": "Platform Team",
  "description": "Agile User Story Management mit AI-Unterstützung",
  "min_platform_version": "1.0.0",
  "entry_point": "plugins/user-story/index.py",
  "frontend_entry": "plugins/user-story/frontend/index.tsx",

  "permissions_required": [
    "story:create", "story:read", "story:update", "story:delete",
    "workflow:execute", "agent:invoke"
  ],

  "nav_entries": [
    {
      "id": "user-story-list",
      "label": "User Stories",
      "icon": "BookOpen",
      "route": "/stories",
      "slot": "sidebar_main",
      "position": 10
    }
  ],

  "slots": [
    {
      "id": "story-detail-panel",
      "slot": "panel_right",
      "component": "StoryDetailPanel",
      "trigger": "route:/stories/:id"
    }
  ],

  "api_routes": [
    {
      "prefix": "/api/v1/plugins/user-story",
      "module": "plugins.user_story.routes"
    }
  ],

  "db_migrations": [
    "plugins/user-story/migrations/"
  ],

  "workflow_hooks": [
    {
      "event": "story.status_changed",
      "workflow_slug": "story-lifecycle"
    }
  ],

  "config_schema": {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
      "default_priority": {
        "type": "string",
        "enum": ["low", "medium", "high"],
        "default": "medium"
      },
      "ai_assistance_enabled": {
        "type": "boolean",
        "default": true
      },
      "default_story_points": {
        "type": "integer",
        "minimum": 1,
        "maximum": 13
      }
    },
    "required": ["default_priority"]
  },

  "capabilities": [
    "ai_assistance",
    "workflow_integration",
    "group_assignment"
  ]
}
```

---

## Plugin Lifecycle

```
REGISTERED → INSTALLED → ACTIVATED (per Org) → ENABLED → DISABLED → DEACTIVATED
```

| Phase | Beschreibung | Akteur |
|---|---|---|
| `REGISTERED` | Plugin im Registry bekannt | Platform Admin |
| `INSTALLED` | Migrations ausgeführt, Backend bereit | System |
| `ACTIVATED` | Für eine Org aktiviert, Config gesetzt | Org Admin |
| `ENABLED` | Aktiv nutzbar | Org Admin / User |
| `DISABLED` | Temporär deaktiviert (Daten bleiben) | Org Admin |
| `DEACTIVATED` | Org-Aktivierung aufgehoben | Org Admin |

**Lifecycle-Hooks (serverseitig):**
```python
# Interface: jedes Plugin implementiert diese Hooks optional
class PluginLifecycle:
    async def on_activate(org_id: UUID, config: dict) -> None: ...
    async def on_deactivate(org_id: UUID) -> None: ...
    async def on_config_update(org_id: UUID, old_config: dict, new_config: dict) -> None: ...
    async def on_install() -> None: ...
    async def on_uninstall() -> None: ...
```

---

## Plugin Routing

### Backend Routing

```python
# FastAPI Plugin-Router-Integration
# Jedes Plugin registriert einen Sub-Router:

from fastapi import APIRouter

router = APIRouter(
    prefix="/api/v1/plugins/user-story",
    tags=["user-story"],
    dependencies=[Depends(require_plugin_active("user-story"))]
)

@router.get("/stories")
async def list_stories(org: Organization = Depends(get_current_org)):
    ...
```

### Frontend Routing

```typescript
// Next.js App Router: Plugin-Routen werden dynamisch registriert
// Workspace Shell lädt Plugin-Routen aus der Plugin-Registry

// apps/frontend/app/[org]/plugins/[plugin-slug]/[...path]/page.tsx
// Jedes Plugin liefert seine Seiten als Komponenten
```

---

## Plugin Activation API

```
POST /api/v1/organizations/{org_id}/plugins/{plugin_id}/activate
→ Validiert config gegen config_schema
→ Ruft plugin.on_activate() auf
→ Setzt OrganizationPluginActivation.is_enabled = true
→ Triggert "plugin.activated" Event

PATCH /api/v1/organizations/{org_id}/plugins/{plugin_id}/config
→ Validiert neue config gegen config_schema
→ Ruft plugin.on_config_update() auf

DELETE /api/v1/organizations/{org_id}/plugins/{plugin_id}/deactivate
→ Ruft plugin.on_deactivate() auf
→ Setzt is_enabled = false (Daten bleiben erhalten)
```

---

## UI-Einbindung: Shell Slots

Die Workspace Shell definiert feste Slot-Positionen, in die Plugins Komponenten einbinden:

| Slot-ID | Position | Beschreibung |
|---|---|---|
| `sidebar_main` | Linke Sidebar | Haupt-Navigation |
| `sidebar_bottom` | Sidebar unten | Utility-Links |
| `topbar_right` | Topbar rechts | Actions, Notifications |
| `panel_right` | Rechtes Panel | Kontext-Details |
| `panel_bottom` | Unteres Panel | Terminal, Log, Preview |
| `dashboard_widget` | Dashboard Grid | Widgets |
| `command_palette` | Command Palette | Befehle registrieren |
| `context_menu` | Kontext-Menü | Zusatz-Aktionen |

```typescript
// Shell lädt aktive Plugins und mounted ihre Slot-Komponenten:
interface PluginSlotMount {
  pluginSlug: string;
  slotId: string;
  component: React.ComponentType<SlotProps>;
  position: number;
}

// Workspace Shell iteriert über alle aktiven Plugins der Org
// und rendert deren Slot-Komponenten in die definierten Positionen
```

---

## Provider Integration

Provider Plugins verbinden externe Dienste:

```python
# Abstrakte Provider-Basis
class ProviderPlugin(ABC):
    @abstractmethod
    async def authenticate(self, org_id: UUID, auth_code: str) -> ProviderCredentials:
        """OAuth2 Flow abschließen, Tokens verschlüsselt speichern"""
        ...

    @abstractmethod
    async def sync(self, connection_id: UUID) -> SyncResult:
        """Daten vom Provider holen"""
        ...

    @abstractmethod
    async def refresh_token(self, connection_id: UUID) -> None:
        """Token erneuern falls abgelaufen"""
        ...
```

---

## Integrierte Plugins (Plattform-Standard)

| Plugin Slug | Typ | Beschreibung | Wave |
|---|---|---|---|
| `user-story` | hybrid | Agile Story Management | 4 |
| `unified-inbox` | hybrid | E-Mail Unified Inbox | 5 |
| `calendar` | hybrid | Kalender-Integration | 5 |
| `voice-input` | action | Spracheingabe | 6 |
| `ai-assistant` | action | Generischer AI-Chat | 3 |

---

## Capability Binding

Plugins deklarieren ihre Capabilities — die Shell nutzt diese für Feature-Flags:

```typescript
type PluginCapability =
  | "ai_assistance"
  | "workflow_integration"
  | "group_assignment"
  | "notification_push"
  | "file_upload"
  | "real_time_updates"
  | "export_pdf"
  | "import_csv";

// Beispiel: AI-Button nur anzeigen wenn Capability vorhanden
const canUseAI = hasCapability(activePlugins, "ai_assistance");
```

---

## Sicherheitsregeln für Plugins

1. `[SECURITY]` Plugins können nur Daten der eigenen Organisation lesen/schreiben
2. `[SECURITY]` Plugin-API-Routen durchlaufen denselben Auth/Permission-Middleware wie Core-Routen
3. `[SECURITY]` Plugin-Config wird gegen `config_schema` validiert — kein freies JSON
4. `[SECURITY]` Plugin-Migrationen werden in einer Transaktion ausgeführt
5. `[SECURITY]` Plugin-Tokens/Secrets werden mit demselben Verschlüsselungskey wie Core gespeichert
6. `[ANNAHME]` Plugins werden serverseitig ausgeführt, kein Plugin-Code läuft im Browser ohne Review
