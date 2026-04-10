# Design: Admin User Management UI

**Date:** 2026-04-10
**Status:** Approved

---

## Overview

Zwei neue UI-Bereiche für die Benutzerverwaltung:

1. **`/[org]/settings/members`** — Org-Admins verwalten Mitglieder ihrer Organisation (einladen, entfernen, Rollen/Gruppen zuweisen, suspendieren, Bulk-Aktionen, Einladungslink).
2. **`admin.karl.app` → `/superadmin`** — Superuser-Panel als Route-Group `app/(superadmin)/` im bestehenden Frontend mit globaler Übersicht über alle User und Organisationen, voller CRUD, Impersonation und System-Status.

Grundlage: Die bestehenden Backend-Endpoints für Memberships (`/api/v1/organizations/{id}/members/...`) sind vollständig. Der `superadmin.py` Router existiert, nutzt aber aktuell einen OIDC-Token — er wird auf Standard-JWT mit `is_superuser`-Check umgestellt und um fehlende Endpoints erweitert.

---

## Teil 1: Backend

### 1.1 Auth-Umstellung `superadmin.py`

`get_admin_user` Dependency wird ersetzt: statt `validate_admin_token` (OIDC) wird der normale `get_current_user` Dep genutzt, plus `is_superuser=True` Check. Der `_security = HTTPBearer()` Overhead fällt weg.

```python
async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required")
    return current_user
```

Bestehende Endpoints `/superadmin/status` und `/superadmin/organizations` (Overview) erhalten nur die neue Dependency, keine sonstigen Änderungen.

### 1.2 Neue Superadmin-Endpoints

**User-Management:**

| Method | Path | Beschreibung |
|---|---|---|
| `GET` | `/superadmin/users` | Alle User, filterbar: `?search=&org_id=&page=&page_size=` |
| `PATCH` | `/superadmin/users/{id}` | `is_active`, `is_superuser` ändern |
| `DELETE` | `/superadmin/users/{id}` | Soft-Delete (`deleted_at`) |
| `POST` | `/superadmin/users/{id}/impersonate` | Gibt kurz-lebiges JWT zurück (15 min, Claim `impersonated_by`) |

**Org-Management:**

| Method | Path | Beschreibung |
|---|---|---|
| `POST` | `/superadmin/organizations` | Neue Org anlegen (name, slug, plan) |
| `PATCH` | `/superadmin/organizations/{id}` | `is_active`, `plan`, `name` ändern |
| `DELETE` | `/superadmin/organizations/{id}` | Soft-Delete |
| `GET` | `/superadmin/organizations/{id}/members` | Mitglieder einer Org (Drill-Down) |

**Response `GET /superadmin/users`:**
```json
{
  "items": [
    {
      "id": "uuid",
      "email": "user@example.com",
      "display_name": "Max Mustermann",
      "is_active": true,
      "is_superuser": false,
      "created_at": "2025-01-01T00:00:00Z",
      "organizations": [{ "id": "uuid", "name": "Acme GmbH", "slug": "acme" }]
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

**Impersonate:** Backend erstellt JWT mit zusätzlichem Claim `"impersonated_by": "<superuser_id>"`, Expiry 15 min. Frontend öffnet neuen Tab mit diesem Token im Session-Storage.

### 1.3 Neuer Endpoint: Einladungslink

| Method | Path | Beschreibung |
|---|---|---|
| `POST` | `/organizations/{id}/invite-link` | Generiert Token-basierten Einladungslink (24h gültig) |
| `GET` | `/invite/{token}` | Löst Einladungslink ein → Membership anlegen |

Einladungslink-Token wird in Redis gespeichert (`invite:{token}` → `org_id`, TTL 24h).

---

## Teil 2: `/[org]/settings/members`

### 2.1 Routing

- Neue Datei: `frontend/app/[org]/settings/members/page.tsx`
- Sidebar-Eintrag `settings-user` in `Sidebar.tsx` wird von `/settings?tab=user` auf `/settings/members` umgebogen
- Der bisherige `MembersSection` Block in `settings/page.tsx` wird entfernt

### 2.2 Seitenstruktur

```
[Header: "Mitglieder (42)"]                    [+ Mitglied einladen]

[Suche: Name oder E-Mail...]

[Tabelle]
☐  Avatar  Name/Email             Rollen         Status    Beigetreten    ⋯
☐  ●       Max Mustermann         [Admin]        Aktiv     01.01.2026     ⋯
☐  ●       anna@example.com       [Member]       Eingeladen —             ⋯

[Floating-Bar wenn Checkboxen aktiv]
  "3 ausgewählt"  [Suspendieren]  [Entfernen]

[Abschnitt: Einladungslink]
  [Link generieren]  → https://app.karl.app/invite/abc123  [Kopieren]
```

### 2.3 Aktionen-Menü (⋯ pro Zeile)

- **Rollen bearbeiten** — Inline-Dropdown mit allen Org-Rollen (Multi-Select), sofort speichern via `POST /organizations/{id}/members/{mid}/roles`
- **Gruppe zuweisen** — Dropdown der Org-Gruppen (`GET /organizations/{id}/groups`)
- **Suspendieren / Reaktivieren** — `PATCH /organizations/{id}/members/{mid}` mit `{ status: "suspended" | "active" }`
- **Entfernen** — Bestätigungs-Dialog, dann `DELETE /organizations/{id}/members/{mid}`

### 2.4 Invite-Modal

Felder:
- E-Mail (required, EmailStr-validiert)
- Rollen (Multi-Select, Optionen aus `GET /organizations/{id}/roles`)

Submit → `POST /organizations/{id}/members/invite`

### 2.5 Bulk-Aktionen

Checkboxen in jeder Zeile + Header-Checkbox (alle). Floating-Bar erscheint sobald ≥1 ausgewählt. Aktionen: Suspendieren, Reaktivieren, Entfernen (mit Sammel-Bestätigung).

Implementierung: sequentielle API-Calls (kein Bulk-Endpoint nötig).

---

## Teil 3: Superuser-Panel `admin.karl.app`

### 3.1 Routing & Layout

- Route-Group: `frontend/app/(superadmin)/`
- Layout: `frontend/app/(superadmin)/layout.tsx` — eigene Sidebar (keine Org-Context-Abhängigkeit), prüft `user.is_superuser` → redirect auf `/` wenn false
- Traefik-Route: `admin.karl.app` → bestehender Frontend-Container, Prefix `/superadmin`

Routen:
| URL | Komponente |
|---|---|
| `/superadmin` | Dashboard |
| `/superadmin/users` | User-Tabelle |
| `/superadmin/organizations` | Org-Tabelle |
| `/superadmin/organizations/[id]` | Org-Detail + Mitglieder |

### 3.2 Dashboard (`/superadmin`)

Kennzahlen-Karten:
- Gesamt-User (aktive / gesamt)
- Aktive Orgs
- Stories gesamt

Darunter: Component-Status-Tabelle (Authentik, n8n, LiteLLM, Nextcloud, etc.) aus bestehendem `GET /superadmin/status`.

### 3.3 User-Tabelle (`/superadmin/users`)

- Suchfeld (Name/E-Mail)
- Org-Filter-Dropdown
- Pagination

Spalten: Avatar/Name, E-Mail, Orgs (Badges), `is_superuser` Toggle, Status-Badge, Registriert am, Aktionen

Aktionen pro Zeile:
- Deaktivieren / Aktivieren (`PATCH /superadmin/users/{id}`)
- `is_superuser` umschalten
- **Impersonate** — öffnet App in neuem Tab mit kurzlebigem JWT
- Löschen (2-stufige Bestätigung: Warnung → E-Mail eingeben)

### 3.4 Org-Tabelle (`/superadmin/organizations`)

- Suchfeld (Name/Slug)
- Plan-Filter

Spalten: Name, Slug, Plan (Badge), Mitglieder, Stories (Usage-Bar), Status, Erstellt am, Aktionen

Aktionen pro Zeile:
- Plan ändern (Dropdown: free / pro / enterprise)
- Deaktivieren / Aktivieren
- Löschen (mit Bestätigung)
- "Mitglieder anzeigen" → `/superadmin/organizations/[id]`

Button "Neue Organisation" → Modal mit Name, Slug, Plan.

### 3.5 Org-Detail (`/superadmin/organizations/[id]`)

Mitgliederliste der Org (read-only aus `GET /superadmin/organizations/{id}/members`). Zeigt Name, E-Mail, Rollen, Status.

---

## Dateiübersicht

### Backend — modifizieren
- `backend/app/routers/superadmin.py` — Auth-Umstellung + neue Endpoints (users CRUD, org CRUD, impersonate)

### Backend — neu erstellen
- *(kein separates File nötig, alles in superadmin.py)*

### Frontend — neu erstellen
- `frontend/app/[org]/settings/members/page.tsx` — Members-Seite
- `frontend/app/(superadmin)/layout.tsx` — Superadmin-Layout + Guard
- `frontend/app/(superadmin)/page.tsx` — Dashboard
- `frontend/app/(superadmin)/users/page.tsx` — User-Tabelle
- `frontend/app/(superadmin)/organizations/page.tsx` — Org-Tabelle
- `frontend/app/(superadmin)/organizations/[id]/page.tsx` — Org-Detail

### Frontend — modifizieren
- `frontend/components/shell/Sidebar.tsx` — `settings-user` Route auf `/settings/members` umbiegen
- `frontend/app/[org]/settings/page.tsx` — `MembersSection` und `tab=user` entfernen

### Infrastruktur — modifizieren
- `infra/docker-compose.yml` (und dev-Variante) — Traefik-Route für `admin.karl.app` → `/superadmin`

---

## Offene Punkte / Constraints

- Einladungslink-Token nutzt Redis, gleiche Instanz wie JWT-Blacklist. Key-Prefix: `invite:`.
- Impersonate-JWT hat Expiry 15 min und wird nicht in die Blacklist aufgenommen — Ablauf ist ausreichend.
- Superadmin kann sich nicht selbst löschen (Guard im Backend).
- Gruppen-Zuweisung über `/organizations/{id}/members/{mid}/groups` — dieser Endpoint fehlt noch im Memberships-Router und muss ergänzt werden.
- Bulk-Aktionen nutzen sequentielle Calls; bei partiellen Fehlern wird pro Item ein Fehler-Toast gezeigt.
- `MembersSection` im alten `settings/page.tsx` wird vollständig entfernt, nicht refactored.
