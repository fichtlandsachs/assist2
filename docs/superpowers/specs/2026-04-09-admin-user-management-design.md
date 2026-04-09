# Design: Admin User Management & Self-Service Account Deletion

**Date:** 2026-04-09
**Status:** Approved

---

## Overview

Zwei neue Features:

1. **Admin User Management** — neue Seite in `admin.heykarl.app` mit vollständiger Nutzerliste und konsistenter Löschung über alle Systeme.
2. **Self-Service Account-Löschung** — Nutzer können ihren eigenen Account in den Einstellungen des Hauptfrontends löschen.

---

## Systeme & Lösch-Scope

| System | Aktion bei Löschung |
|---|---|
| assist2 PostgreSQL | Hard-Delete User-Row + Cascade (Memberships, MembershipRoles, story_embeddings, alle FK-CASCADE-Tabellen) |
| Authentik | REST-API `DELETE /api/v3/core/users/{id}/` (via authentik_id) |
| Nextcloud | OCS-API `DELETE /ocs/v1.php/cloud/users/{username}` (username = E-Mail) |
| Atlassian | Nur Unlink (atlassian_account_id = NULL) — externer Account bleibt |
| GitHub | Nur Unlink (github_id = NULL) — externer Account bleibt |
| Vektor-DB | `DELETE FROM story_embeddings WHERE user_id = ?` vor DB-Löschung |

**Orchestrierungs-Strategie: Best-Effort (Option A)**
Reihenfolge: Authentik → Nextcloud → DB (DB immer zuletzt).
Bei Fehlern in externen Systemen wird weitergemacht. Ergebnis pro System wird zurückgegeben.
DB-Löschung passiert immer (außer DB-Fehler selbst).

---

## Backend

### 1. `GET /api/v1/superadmin/users`

Gibt alle User zurück (nicht soft-deleted). Response pro User:

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "Max Mustermann",
  "avatar_url": "https://...",
  "is_active": true,
  "last_login_at": "2026-04-01T10:00:00Z",
  "created_at": "2025-01-01T00:00:00Z",
  "has_authentik": true,
  "has_nextcloud": true,
  "has_atlassian": false,
  "has_github": true,
  "embedding_count": 42,
  "organizations": [
    { "id": "uuid", "name": "Acme GmbH", "slug": "acme", "role": "admin" }
  ]
}
```

In `backend/app/routers/superadmin.py` ergänzt (bestehende Datei).

### 2. `DELETE /api/v1/superadmin/users/{user_id}`

Superadmin-only. Löscht konsistent, best-effort. Response:

```json
{
  "user_id": "uuid",
  "results": {
    "authentik": { "success": true },
    "nextcloud": { "success": false, "error": "User not found" },
    "database": { "success": true, "deleted_embeddings": 42 }
  }
}
```

### 3. `DELETE /api/v1/users/me`

Authentifizierter User löscht sich selbst. Gleiche Orchestrierungslogik.
Response: identisch mit Superadmin-Endpoint.
Nach erfolgreicher DB-Löschung: JWT wird invalidiert (Redis-Blacklist).

**Gemeinsamer Service:** Beide Endpoints nutzen eine gemeinsame `UserDeletionService`-Funktion in `backend/app/services/user_deletion_service.py`.

---

## Admin-Frontend (`admin-frontend/`)

### Neue Seite: `app/(protected)/users/page.tsx`

Nav-Eintrag "Nutzer" wird in `app/(protected)/layout.tsx` ergänzt.

**Userliste:**
- Tabelle: Avatar + Name/Email | System-Badges | Orgs | Letzter Login | Löschen-Button
- System-Badges: `authentik`, `nextcloud`, `atlassian`, `github` — farbig wenn verknüpft, grau wenn nicht
- Clientseitiges Suchfeld (Name/Email)

**2-stufige Lösch-Bestätigung:**

*Stufe 1 — Confirmation Modal:*
> "User `Max Mustermann (max@example.com)` endgültig löschen? Der Account wird aus allen Systemen entfernt: assist2, Authentik, Nextcloud sowie alle Memberships und Embeddings."
> [Abbrechen] [Weiter →]

*Stufe 2 — Email-Eingabe Modal:*
> "Bitte E-Mail-Adresse zur Bestätigung eingeben:"
> Input-Feld — muss exakt `max@example.com` matchen
> [Abbrechen] [Endgültig löschen]

**Nach Löschung:**
- Ergebnis-Summary im Modal: pro System ✓ / ✗ mit Fehlermeldung
- User wird aus Liste entfernt wenn DB-Löschung erfolgreich
- Bei partiellen Fehlern: User bleibt mit Warnung sichtbar

---

## Hauptfrontend (`frontend/`)

### Danger-Zone in User-Einstellungen

In der bestehenden Settings-Seite (`app/[org]/settings` o.ä.) ganz unten neue Sektion "Danger Zone":

- Überschrift + Erklärtext was gelöscht wird
- Gleiche 2-stufige Bestätigung (Stufe 1: Modal-Warnung, Stufe 2: E-Mail eingeben)
- Nach erfolgreicher Löschung: Session leeren + Redirect auf `/login`

---

## Dateiübersicht

### Neu erstellen
- `backend/app/services/user_deletion_service.py` — Orchestrierungslogik
- `admin-frontend/app/(protected)/users/page.tsx` — Nutzerliste
- `admin-frontend/components/UserDeleteModal.tsx` — 2-stufiger Bestätigungs-Dialog

### Modifizieren
- `backend/app/routers/superadmin.py` — GET /users + DELETE /users/{id}
- `backend/app/routers/users.py` — DELETE /me
- `backend/app/main.py` — ggf. Router-Import falls nötig
- `admin-frontend/app/(protected)/layout.tsx` — Nav-Eintrag "Nutzer"
- `frontend/app/[org]/settings/...` — Danger-Zone-Sektion

---

## Offene Punkte / Constraints

- Nextcloud-Username entspricht der E-Mail-Adresse des Users (Standardkonfiguration).
- Authentik-User-ID kommt aus `user.authentik_id`.
- JWT-Invalidierung bei Self-Delete nutzt bestehende Redis-Blacklist-Logik aus `app/core/security.py`.
- Superadmin kann sich nicht selbst über diesen Endpoint löschen (Guard im Backend).
