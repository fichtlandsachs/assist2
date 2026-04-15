# VS Code Server — Authentik SSO Design

**Datum:** 2026-04-14  
**Status:** Approved

## Ziel

Den VS Code Server (`admin.heykarl.app/code`) über Authentik SSO absichern. Zugriff erhalten nur Mitglieder der Authentik-Gruppe `Coder`. Der bisherige Connection-Token entfällt.

## Entscheidungen

| Frage | Entscheidung |
|---|---|
| SSO-Mechanismus | Authentik Embedded Outpost (ForwardAuth) |
| Zugriffskontrolle | Authentik-Gruppe `Coder` (neu) |
| Token-Auth | Entfernt (`--without-connection-token`) |

## Architektur

```
Browser → Traefik → [authentik ForwardAuth] → heykarl-vscode:3000
                         ↓ (nicht eingeloggt)
                    authentik.heykarl.app (Login-Flow)
                         ↓ (eingeloggt, Gruppe Coder)
                    heykarl-vscode:3000
```

## Änderungen

### 1. Authentik (via API)

Folgende Objekte werden via Authentik REST API (`http://heykarl-authentik-server:9000/api/v3/`) mit dem `AUTHENTIK_API_TOKEN` angelegt:

| Typ | Details |
|---|---|
| Gruppe | Name: `Coder` |
| Proxy Provider | Typ: Forward Auth (single application), External Host: `https://admin.heykarl.app`, Name: `VS Code Server` |
| Application | Slug: `vscode`, Name: `VS Code Server`, Provider: s.o. |
| Policy | Typ: Group Membership, Gruppe: `Coder` |
| Policy Binding | Application: `vscode`, Policy: s.o., Order: 0 |

### 2. Traefik (`infra/traefik/dynamic/assist2.yml`)

**Neuer Router** für Authentik-Outpost-Callbacks auf `admin.heykarl.app`:

```yaml
authentik-outpost-admin:
  rule: "Host(`admin.heykarl.app`) && PathPrefix(`/outpost.goauthentik.io/`)"
  entryPoints: [websecure]
  service: authentik-outpost-svc
  priority: 200
  tls:
    certResolver: letsencrypt
```

**Bestehender vscode-Router** erhält die `authentik` Middleware:

```yaml
vscode:
  middlewares: [authentik]
```

### 3. openvscode-server (`infra/docker-compose.yml`)

- Entrypoint: `--connection-token-file` → `--without-connection-token`
- Env-Var `VSCODE_TOKEN` entfernen
- Container neu starten

## Nicht im Scope

- Kein dedizierter Outpost-Container
- Keine Änderung an anderen geschützten Services
- `VSCODE_TOKEN` aus `.env` kann manuell gelöscht werden
