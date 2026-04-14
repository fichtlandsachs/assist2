# VS Code Server — Design Spec

**Datum:** 2026-04-14  
**Status:** Approved

## Ziel

Einen browserbasierten VS Code Server (code-server) als dauerhaft laufenden Docker-Service in den bestehenden Stack integrieren, erreichbar unter `admin.heykarl.app/code`.

## Entscheidungen

| Frage | Entscheidung |
|---|---|
| Image | `codercom/code-server:latest` |
| Zugriffspfad | `admin.heykarl.app/code` |
| Authentifizierung | Built-in Passwort (`VSCODE_PASSWORD`) |
| Workspace | `/opt` (gesamtes Verzeichnis) |
| Verfügbarkeit | Dauerhaft (`restart: unless-stopped`) |

## Architektur

```
Internet → Traefik → admin.heykarl.app/code → heykarl-vscode:8080
```

code-server wird mit `--base-path /code` gestartet, sodass alle Assets und Redirects unter dem Subpfad korrekt funktionieren — kein StripPrefix-Middleware in Traefik nötig. Das Muster ist konsistent mit pgadmin (`SCRIPT_NAME`) und nextcloud (`OVERWRITEWEBROOT`).

## Service-Definition

```yaml
vscode:
  image: codercom/code-server:latest
  pull_policy: never
  container_name: heykarl-vscode
  restart: unless-stopped
  environment:
    PASSWORD: ${VSCODE_PASSWORD}
  command: ["--bind-addr", "0.0.0.0:8080", "--base-path", "/code", "/opt"]
  volumes:
    - /opt:/opt
    - heykarl_vscode_config:/home/coder/.config
  networks:
    - proxy
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.vscode.rule=Host(`admin.${DOMAIN}`) && PathPrefix(`/code`)"
    - "traefik.http.routers.vscode.entrypoints=websecure"
    - "traefik.http.routers.vscode.tls.certresolver=letsencrypt"
    - "traefik.http.services.vscode.loadbalancer.server.port=8080"
```

## Volumes

- `heykarl_vscode_config` — persistente Speicherung von Extensions, Settings und Themes
- `/opt` (bind mount) — Workspace, read-write

## Netzwerk

Nur `proxy`-Netz — kein Zugriff auf das `internal`-Netz (kein direkter DB-Zugriff).

## Änderungen an bestehenden Dateien

| Datei | Änderung |
|---|---|
| `infra/docker-compose.yml` | Service `vscode` + Volume `heykarl_vscode_config` hinzufügen |
| `infra/.env` | `VSCODE_PASSWORD` ist bereits gesetzt |

## Scope

Keine weiteren Änderungen. Kein Healthcheck notwendig (code-server hat kein stabiles `/healthz`-Endpoint ohne Auth).
