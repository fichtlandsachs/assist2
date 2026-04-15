# VS Code Server — Authentik SSO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VS Code Server unter `admin.heykarl.app/code` hinter Authentik SSO (Gruppe `Coder`) absichern, Token-Auth entfernen.

**Architecture:** Authentik Embedded Outpost (ForwardAuth) via vorhandene Traefik-Middleware `authentik`. Drei Änderungen: (1) Authentik-Objekte per REST API anlegen, (2) Traefik-Config erweitern, (3) openvscode-server auf `--without-connection-token` umstellen.

**Tech Stack:** Authentik REST API v3, Traefik v3 (file provider), Docker Compose, gitpod/openvscode-server

---

### Task 1: Authentik-Objekte anlegen (Gruppe, Provider, Application, Policy)

**Files:**
- Kein File-Edit — alle Änderungen per Authentik REST API

Die Authentik-API ist von innen erreichbar unter `http://heykarl-authentik-server:9000/api/v3/`.
Der API-Token liegt als `AUTHENTIK_API_TOKEN` in `infra/.env` und ist in `heykarl-backend` verfügbar.
Der Authorization-Flow hat UUID `3ef32e4f-94d3-46e4-8bb1-79484c1b0856`.

- [ ] **Step 1: Gruppe `Coder` anlegen**

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, urllib.error, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode())

r = api('POST', '/core/groups/', {'name': 'Coder', 'is_superuser': False})
print('GROUP_UUID:', r['pk'])
"
```

Erwartetes Ergebnis: `GROUP_UUID: <uuid>` — UUID für Step 4 notieren.

- [ ] **Step 2: Proxy Provider anlegen**

`<GROUP_UUID>` durch den Wert aus Step 1 ersetzen:

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, urllib.error, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode())

r = api('POST', '/providers/proxy/', {
    'name': 'VS Code Server',
    'authorization_flow': '3ef32e4f-94d3-46e4-8bb1-79484c1b0856',
    'external_host': 'https://admin.heykarl.app',
    'mode': 'forward_single',
})
print('PROVIDER_PK:', r['pk'])
"
```

Erwartetes Ergebnis: `PROVIDER_PK: <integer>` — Zahl für Step 3 notieren.

- [ ] **Step 3: Application `vscode` anlegen**

`<PROVIDER_PK>` durch den Wert aus Step 2 ersetzen:

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, urllib.error, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode())

PROVIDER_PK = <PROVIDER_PK>   # <-- ersetzen

r = api('POST', '/core/applications/', {
    'name': 'VS Code Server',
    'slug': 'vscode',
    'provider': PROVIDER_PK,
})
print('APP_PK:', r['pk'])
"
```

Erwartetes Ergebnis: `APP_PK: <uuid>` — UUID für Step 5 notieren.

- [ ] **Step 4: Group-Membership-Policy anlegen**

`<GROUP_UUID>` durch den Wert aus Step 1 ersetzen:

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, urllib.error, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode())

GROUP_UUID = '<GROUP_UUID>'   # <-- ersetzen

r = api('POST', '/policies/group_membership/', {
    'name': 'VS Code Server — Coder only',
    'group': GROUP_UUID,
})
print('POLICY_PK:', r['pk'])
"
```

Erwartetes Ergebnis: `POLICY_PK: <uuid>` — UUID für Step 5 notieren.

- [ ] **Step 5: Policy Binding anlegen**

`<APP_PK>` aus Step 3, `<POLICY_PK>` aus Step 4 ersetzen:

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, urllib.error, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}

def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(BASE + path, data=body, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode())

APP_PK    = '<APP_PK>'     # <-- ersetzen
POLICY_PK = '<POLICY_PK>'  # <-- ersetzen

r = api('POST', '/policies/bindings/', {
    'target': APP_PK,
    'policy': POLICY_PK,
    'order': 0,
    'enabled': True,
})
print('BINDING_PK:', r['pk'])
"
```

Erwartetes Ergebnis: `BINDING_PK: <uuid>`

- [ ] **Step 6: Embedded Outpost prüft den neuen Provider auf**

```bash
docker exec heykarl-backend python3 -c "
import os, urllib.request, json

TOKEN = os.environ['AUTHENTIK_API_TOKEN']
BASE = 'http://heykarl-authentik-server:9000/api/v3'
HEADERS = {'Authorization': f'Bearer {TOKEN}'}

req = urllib.request.Request(BASE + '/outposts/instances/?managed=goauthentik.io%2Foutposts%2Fembedded', headers=HEADERS)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read())
for o in data.get('results', []):
    print(o['name'], '— providers:', o.get('providers', []))
"
```

Erwartetes Ergebnis: der Embedded Outpost listet jetzt den neuen Provider-PK auf.
Falls nicht: im Authentik-UI unter Admin → Outposts den Embedded Outpost bearbeiten und den Provider manuell hinzufügen.

---

### Task 2: Traefik-Config erweitern

**Files:**
- Modify: `infra/traefik/dynamic/assist2.yml`

- [ ] **Step 1: Router `authentik-outpost-admin` hinzufügen**

In `/opt/assist2/infra/traefik/dynamic/assist2.yml` nach dem Block `authentik-outpost:` (Zeile 54) folgenden Router einfügen:

```yaml
    # ── Authentik outpost callbacks auf admin.heykarl.app ────────────────
    authentik-outpost-admin:
      rule: "Host(`admin.heykarl.app`) && PathPrefix(`/outpost.goauthentik.io/`)"
      entryPoints: [websecure]
      service: authentik-outpost-svc
      priority: 200
      tls:
        certResolver: letsencrypt
```

- [ ] **Step 2: `authentik` Middleware zum vscode-Router hinzufügen**

Im vscode-Router-Block (aktuell Zeilen 76–83) `middlewares: [authentik]` ergänzen:

```yaml
    # ── VS Code Server ────────────────────────────────────────────────────
    vscode:
      rule: "Host(`admin.heykarl.app`) && PathPrefix(`/code`)"
      entryPoints: [websecure]
      service: vscode-svc
      middlewares: [authentik]
      priority: 100
      tls:
        certResolver: letsencrypt
```

- [ ] **Step 3: Traefik-Reload prüfen**

Traefik liest die Datei automatisch neu (file provider mit watch). Nach ~2 Sekunden:

```bash
docker logs heykarl-traefik --tail 5 2>/dev/null || docker logs assist2-traefik --tail 5
```

Erwartetes Ergebnis: keine Fehler, ggf. `"Loaded configuration from file"` Log-Zeile.

---

### Task 3: openvscode-server auf Token-free Auth umstellen

**Files:**
- Modify: `infra/docker-compose.yml` (vscode service)

Der aktuelle Entrypoint erstellt eine Token-Datei und startet openvscode-server mit `--connection-token-file`. Da Authentik jetzt die Authentifizierung übernimmt, entfällt der Token.

- [ ] **Step 1: Entrypoint und Env-Var in `infra/docker-compose.yml` ändern**

Aktueller Block (in `infra/docker-compose.yml`):

```yaml
    entrypoint: ["/bin/sh", "-c", "mkdir -p /config && echo \"$VSCODE_TOKEN\" > /tmp/vscode-token && exec /home/.openvscode-server/bin/openvscode-server --host 0.0.0.0 --server-base-path /code --connection-token-file /tmp/vscode-token --user-data-dir /config /opt"]
    environment:
      VSCODE_TOKEN: ${VSCODE_TOKEN}
```

Ersetzen durch:

```yaml
    entrypoint: ["/home/.openvscode-server/bin/openvscode-server", "--host", "0.0.0.0", "--server-base-path", "/code", "--without-connection-token", "--user-data-dir", "/config", "/opt"]
```

(Die gesamte `environment:`-Sektion des vscode-Service kann entfernt werden, sofern `VSCODE_TOKEN` der einzige Eintrag war.)

- [ ] **Step 2: YAML-Syntax prüfen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```

Erwartetes Ergebnis: kein Output, Exit-Code 0.

- [ ] **Step 3: Container neu erstellen und starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --force-recreate vscode
```

Erwartetes Ergebnis:
```
[+] Running 1/1
 ✔ Container heykarl-vscode  Started
```

- [ ] **Step 4: Logs prüfen**

```bash
docker logs heykarl-vscode --tail 10
```

Erwartetes Ergebnis (ungefähr):
```
[...]  info  HTTP server listening on http://0.0.0.0:3000/code
[...]  info  Using no-auth
```

Wenn `error` erscheint: Entrypoint-Syntax im YAML prüfen.

- [ ] **Step 5: SSO-Flow testen**

```bash
curl -s -o /dev/null -w "%{http_code}" https://admin.heykarl.app/code/
```

Erwartetes Ergebnis: `302` (Redirect zu Authentik Login-Page, **nicht** `200` oder `403`).

Im Browser: `https://admin.heykarl.app/code` öffnen → sollte zu `authentik.heykarl.app` weiterleiten.
Nach Login mit einem User der Gruppe `Coder`: VS Code öffnet sich ohne Token-Abfrage.
Nach Login mit einem User **ohne** Gruppe `Coder`: Authentik zeigt Zugriff verweigert.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2
git add infra/docker-compose.yml infra/traefik/dynamic/assist2.yml
git commit -m "feat: secure VS Code Server with Authentik SSO (Coder group)"
```
