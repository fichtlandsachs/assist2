# 01 — Domain Model

Alle Entitäten folgen diesen Konventionen:
- `id`: UUID v4, Primärschlüssel
- `created_at` / `updated_at`: ISO 8601 Timestamps, serverseitig gesetzt
- Soft-Delete via `deleted_at` (nullable) wo angegeben
- Enums als `string` mit definierten Werten
- Alle Beziehungen sind explizit als Foreign Keys modelliert

---

## User

```
Entität: User
Tabelle: users
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| email | string (unique) | nein | Login-Identifikator |
| email_verified | boolean | nein | E-Mail-Verifizierung |
| password_hash | string | ja | null bei federated Accounts |
| display_name | string | nein | Anzeigename |
| avatar_url | string | ja | Profilbild-URL |
| locale | string | nein | Default: `de` |
| timezone | string | nein | Default: `Europe/Berlin` |
| is_active | boolean | nein | Account aktiv |
| is_superuser | boolean | nein | Plattform-Admin |
| last_login_at | timestamp | ja | Letzter Login |
| created_at | timestamp | nein | Erstellungszeitpunkt |
| updated_at | timestamp | nein | Letzter Update |
| deleted_at | timestamp | ja | Soft-Delete |

**Beziehungen:**
- `memberships`: 1:N → Membership
- `identity_links`: 1:N → IdentityLink
- `sessions`: 1:N → UserSession

**Regeln:**
- `email` ist global unique
- `password_hash` ist `null` bei OAuth-Only-Accounts
- `is_superuser` darf nur von Superusern gesetzt werden
- `[SECURITY]` Passwort-Hash niemals in API-Responses

---

## IdentityLink

```
Entität: IdentityLink
Tabelle: identity_links
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| user_id | UUID (FK→User) | nein | Zugehöriger User |
| provider | enum | nein | `google`, `github`, `apple` |
| provider_user_id | string | nein | Externe User-ID |
| provider_email | string | ja | E-Mail beim Provider |
| access_token | string (encrypted) | ja | [SECURITY] verschlüsselt |
| refresh_token | string (encrypted) | ja | [SECURITY] verschlüsselt |
| token_expires_at | timestamp | ja | Token-Ablauf |
| created_at | timestamp | nein | |

**Regeln:**
- `(user_id, provider)` unique
- `(provider, provider_user_id)` unique
- Token-Felder werden niemals in API-Responses exponiert

---

## Organization

```
Entität: Organization
Tabelle: organizations
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| slug | string (unique) | nein | URL-Identifier |
| name | string | nein | Anzeigename |
| description | string | ja | Beschreibung |
| logo_url | string | ja | Logo-URL |
| plan | enum | nein | `free`, `pro`, `enterprise` |
| is_active | boolean | nein | Org aktiv |
| max_members | integer | ja | null = unlimited |
| metadata | jsonb | ja | Erweiterbare Metadaten |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |
| deleted_at | timestamp | ja | Soft-Delete |

**Beziehungen:**
- `memberships`: 1:N → Membership
- `groups`: 1:N → Group
- `plugin_activations`: 1:N → OrganizationPluginActivation
- `workflow_definitions`: 1:N → WorkflowDefinition

**Regeln:**
- `slug` ist global unique, URL-safe (lowercase, hyphen)
- Alle domänengebundenen Objekte haben `organization_id`
- `[SECURITY]` Datenisolation via `organization_id` in ALLEN Queries

---

## Membership

```
Entität: Membership
Tabelle: memberships
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| user_id | UUID (FK→User) | nein | Mitglied |
| organization_id | UUID (FK→Organization) | nein | Organisation |
| status | enum | nein | `active`, `invited`, `suspended` |
| invited_by | UUID (FK→User) | ja | Einladender |
| invited_at | timestamp | ja | Einladungszeitpunkt |
| joined_at | timestamp | ja | Beitrittszeitpunkt |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**Beziehungen:**
- `membership_roles`: 1:N → MembershipRole
- Über MembershipRole → Role → Permission

**Regeln:**
- `(user_id, organization_id)` unique
- Ein User hat genau eine Membership pro Organisation
- Rollen werden über MembershipRole zugewiesen (N:M)

---

## Role

```
Entität: Role
Tabelle: roles
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| organization_id | UUID (FK→Organization) | ja | null = System-Rolle |
| name | string | nein | Rollenname |
| description | string | ja | Beschreibung |
| is_system | boolean | nein | System-Rolle (nicht löschbar) |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**System-Rollen (unveränderlich):**
- `org_owner` — volle Kontrolle
- `org_admin` — Administration ohne Owner-Transfer
- `org_member` — Standard-Mitglied
- `org_guest` — lesender Gast-Zugriff

**Beziehungen:**
- `permissions`: N:M → Permission (via RolePermission)
- `memberships`: N:M → Membership (via MembershipRole)

---

## Permission

```
Entität: Permission
Tabelle: permissions
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| resource | string | nein | Ressource, z.B. `story` |
| action | string | nein | Aktion, z.B. `create`, `read`, `update`, `delete` |
| description | string | ja | Beschreibung |

**Format:** `{resource}:{action}` z.B. `story:create`, `plugin:activate`

**Regeln:**
- Permissions sind statisch definiert (Code-First)
- `(resource, action)` unique
- Aggregation: alle Permissions aller aktiven Rollen eines Membership-Users

---

## MembershipRole

```
Entität: MembershipRole
Tabelle: membership_roles
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| membership_id | UUID (FK→Membership) | nein | |
| role_id | UUID (FK→Role) | nein | |
| assigned_by | UUID (FK→User) | ja | |
| assigned_at | timestamp | nein | |

---

## Group

```
Entität: Group
Tabelle: groups
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| organization_id | UUID (FK→Organization) | nein | Mandant |
| name | string | nein | Gruppenname |
| description | string | ja | |
| type | enum | nein | `team`, `department`, `project` |
| is_active | boolean | nein | |
| parent_group_id | UUID (FK→Group) | ja | Hierarchie |
| metadata | jsonb | ja | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**Beziehungen:**
- `members`: 1:N → GroupMember
- `children`: 1:N → Group (self-referential)

---

## GroupMember

```
Entität: GroupMember
Tabelle: group_members
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| group_id | UUID (FK→Group) | nein | |
| member_type | enum | nein | `user`, `agent` |
| user_id | UUID (FK→User) | ja | wenn member_type=user |
| agent_id | UUID (FK→Agent) | ja | wenn member_type=agent |
| role | enum | nein | `member`, `lead` |
| added_at | timestamp | nein | |

**Regeln:**
- Entweder `user_id` oder `agent_id` gesetzt, nicht beide
- `(group_id, user_id)` unique (wenn user_id gesetzt)
- `(group_id, agent_id)` unique (wenn agent_id gesetzt)

---

## Agent

```
Entität: Agent
Tabelle: agents
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| organization_id | UUID (FK→Organization) | nein | Mandant |
| name | string | nein | Agentenname |
| role | enum | nein | Agentenrolle (siehe AI Agents) |
| model | string | nein | Modell-ID, z.B. `claude-sonnet-4-6` |
| system_prompt_ref | string | ja | Pfad/Referenz zum System-Prompt |
| config | jsonb | nein | Modellparameter |
| is_active | boolean | nein | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**Enum `role`:** `scrum_master`, `architect`, `coding`, `security`, `performance`, `ux`, `database`, `network`, `deploy`, `testing`, `documentation_training`

---

## Plugin

```
Entität: Plugin
Tabelle: plugins
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | Primärschlüssel |
| slug | string (unique) | nein | Technischer Identifier |
| name | string | nein | Anzeigename |
| version | string | nein | Semver, z.B. `1.0.0` |
| type | enum | nein | `ui`, `provider`, `action`, `hybrid` |
| manifest | jsonb | nein | Vollständiges Plugin-Manifest |
| entry_point | string | nein | Relativer Pfad zum Entry-Modul |
| is_active | boolean | nein | Global aktiv/inaktiv |
| requires_config | boolean | nein | Benötigt Org-Konfiguration |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

---

## OrganizationPluginActivation

```
Entität: OrganizationPluginActivation
Tabelle: org_plugin_activations
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| plugin_id | UUID (FK→Plugin) | nein | |
| is_enabled | boolean | nein | |
| config | jsonb | ja | Org-spezifische Plugin-Konfiguration |
| activated_by | UUID (FK→User) | nein | |
| activated_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**Regeln:**
- `(organization_id, plugin_id)` unique
- Config wird validiert gegen `plugin.manifest.config_schema`

---

## WorkflowDefinition

```
Entität: WorkflowDefinition
Tabelle: workflow_definitions
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| name | string | nein | |
| slug | string | nein | Org-weit unique |
| version | integer | nein | Autoincrement |
| description | string | ja | |
| trigger_type | enum | nein | `webhook`, `schedule`, `event`, `manual` |
| n8n_workflow_id | string | nein | ID in n8n |
| definition | jsonb | nein | Vollständige n8n-Workflow-Definition |
| is_active | boolean | nein | |
| created_by | UUID (FK→User) | nein | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

**Regeln:**
- Bei Update wird `version` inkrementiert, alte Version archiviert
- `definition` enthält vollständiges n8n JSON inkl. Nodes und Verbindungen

---

## WorkflowExecution

```
Entität: WorkflowExecution
Tabelle: workflow_executions
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| definition_id | UUID (FK→WorkflowDefinition) | nein | |
| definition_version | integer | nein | Snapshot der Version |
| n8n_execution_id | string | nein | Ausführungs-ID in n8n |
| status | enum | nein | `pending`, `running`, `success`, `failed`, `cancelled` |
| triggered_by | UUID (FK→User) | ja | null bei automatisch |
| trigger_type | string | nein | Trigger-Typ |
| input_snapshot | jsonb | nein | Input zum Ausführungszeitpunkt |
| context_snapshot | jsonb | nein | Kontext (Org, User, etc.) |
| result_snapshot | jsonb | ja | Ergebnis nach Abschluss |
| error_message | string | ja | Fehler bei status=failed |
| started_at | timestamp | nein | |
| completed_at | timestamp | ja | |

**Regeln:**
- `input_snapshot` ist unveränderlich nach dem Start
- Ermöglicht vollständige Reproduzierbarkeit

---

## UserStory

```
Entität: UserStory
Tabelle: user_stories
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| title | string | nein | |
| description | text | ja | |
| status | enum | nein | `draft`, `ready`, `in_progress`, `in_review`, `done`, `cancelled` |
| priority | enum | nein | `low`, `medium`, `high`, `critical` |
| story_points | integer | ja | |
| assignee_id | UUID (FK→User) | ja | |
| reporter_id | UUID (FK→User) | nein | |
| group_id | UUID (FK→Group) | ja | zugeordnetes Team |
| parent_story_id | UUID (FK→UserStory) | ja | Epics |
| acceptance_criteria | jsonb | ja | Liste von ACs |
| metadata | jsonb | ja | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

---

## TestCase

```
Entität: TestCase
Tabelle: test_cases
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| story_id | UUID (FK→UserStory) | nein | |
| title | string | nein | |
| description | text | ja | |
| type | enum | nein | `unit`, `integration`, `e2e`, `manual` |
| status | enum | nein | `pending`, `passed`, `failed`, `skipped` |
| steps | jsonb | ja | Testschritte |
| expected_result | text | ja | |
| actual_result | text | ja | |
| created_by | UUID (FK→User) | nein | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

---

## MailConnection

```
Entität: MailConnection
Tabelle: mail_connections
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| user_id | UUID (FK→User) | nein | Eigentümer |
| provider | enum | nein | `gmail`, `outlook`, `imap` |
| email_address | string | nein | |
| display_name | string | ja | |
| access_token | string (encrypted) | ja | [SECURITY] |
| refresh_token | string (encrypted) | ja | [SECURITY] |
| token_expires_at | timestamp | ja | |
| last_sync_at | timestamp | ja | |
| sync_status | enum | nein | `active`, `error`, `paused` |
| is_active | boolean | nein | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

---

## Message

```
Entität: Message
Tabelle: messages
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| connection_id | UUID (FK→MailConnection) | nein | |
| external_id | string | nein | ID beim Provider |
| thread_id | string | ja | Thread-Gruppierung |
| subject | string | ja | |
| from_address | string | nein | |
| to_addresses | jsonb | nein | Array von Adressen |
| cc_addresses | jsonb | ja | |
| body_text | text | ja | |
| body_html | text | ja | |
| is_read | boolean | nein | |
| is_archived | boolean | nein | |
| received_at | timestamp | nein | |
| created_at | timestamp | nein | |

---

## CalendarConnection

```
Entität: CalendarConnection
Tabelle: calendar_connections
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| user_id | UUID (FK→User) | nein | |
| provider | enum | nein | `google`, `outlook`, `ical` |
| calendar_id | string | nein | Provider-seitige Kalender-ID |
| display_name | string | ja | |
| access_token | string (encrypted) | ja | [SECURITY] |
| refresh_token | string (encrypted) | ja | [SECURITY] |
| token_expires_at | timestamp | ja | |
| last_sync_at | timestamp | ja | |
| is_active | boolean | nein | |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |

---

## CalendarEvent

```
Entität: CalendarEvent
Tabelle: calendar_events
```

| Attribut | Typ | Nullable | Beschreibung |
|---|---|---|---|
| id | UUID | nein | |
| organization_id | UUID (FK→Organization) | nein | |
| connection_id | UUID (FK→CalendarConnection) | nein | |
| external_id | string | nein | Provider-ID |
| title | string | nein | |
| description | text | ja | |
| location | string | ja | |
| start_at | timestamp | nein | |
| end_at | timestamp | nein | |
| is_all_day | boolean | nein | |
| attendees | jsonb | ja | Array: {email, name, status} |
| recurrence_rule | string | ja | RFC 5545 RRULE |
| status | enum | nein | `confirmed`, `tentative`, `cancelled` |
| created_at | timestamp | nein | |
| updated_at | timestamp | nein | |
