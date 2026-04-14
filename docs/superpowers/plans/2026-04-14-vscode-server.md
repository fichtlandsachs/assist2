# VS Code Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** code-server als dauerhaft laufenden Docker-Service unter `admin.heykarl.app/code` einbinden.

**Architecture:** Neuer Service `vscode` in `docker-compose.yml` mit `codercom/code-server`, `--base-path /code` für Subpath-Routing ohne StripPrefix-Middleware, Passwort-Auth via `VSCODE_PASSWORD`-Umgebungsvariable.

**Tech Stack:** codercom/code-server:latest, Traefik v3, Docker Compose

---

### Task 1: Volume und Service in docker-compose.yml eintragen

**Files:**
- Modify: `infra/docker-compose.yml:10-24` (volumes section)
- Modify: `infra/docker-compose.yml` (services section, ans Ende anhängen)

- [ ] **Step 1: Volume `heykarl_vscode_config` in der volumes-Sektion ergänzen**

In `infra/docker-compose.yml` Zeile 24 (nach `heykarl_pgadmin_data:`) folgende Zeile einfügen:

```yaml
  heykarl_vscode_config:
```

Die vollständige volumes-Sektion sieht danach so aus:

```yaml
volumes:
  assist2_postgres_data:
  heykarl_postgres_data:
  heykarl_redis_data:
  heykarl_n8n_data:
  heykarl_authentik_db_data:
  heykarl_authentik_media:
  heykarl_authentik_templates:
  heykarl_pdf_templates:
  heykarl_pdf_cache:
  heykarl_nextcloud_data:
  heykarl_litellm_db_data:
  heykarl_nextcloud_db_data:
  heykarl_openwebui_data:
  heykarl_pgadmin_data:
  heykarl_vscode_config:
```

- [ ] **Step 2: Service `vscode` ans Ende der services-Sektion anhängen**

In `infra/docker-compose.yml` nach dem letzten Service (`openwebui`) folgenden Block einfügen:

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

- [ ] **Step 3: YAML-Syntax prüfen**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```

Erwartetes Ergebnis: kein Output, Exit-Code 0. Bei Fehlern YAML-Einrückung kontrollieren (2 Spaces pro Ebene).

- [ ] **Step 4: Image pullen**

```bash
cd /opt/assist2/infra && docker pull codercom/code-server:latest
```

Dann Image in lokales Registry-Cache taggen (damit `pull_policy: never` greift):

```bash
docker tag codercom/code-server:latest codercom/code-server:latest
```

*(Dieser Schritt ist nur nötig wenn das Image nicht bereits lokal vorhanden ist. `docker images | grep code-server` zeigt ob es schon da ist.)*

- [ ] **Step 5: Service starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d vscode
```

Erwartetes Ergebnis:
```
[+] Running 2/2
 ✔ Volume "heykarl_vscode_config" Created
 ✔ Container heykarl-vscode    Started
```

- [ ] **Step 6: Logs prüfen — Service läuft**

```bash
docker logs heykarl-vscode --tail 20
```

Erwartetes Ergebnis (ungefähr):
```
[2026-04-14T...] info  code-server 4.x.x ...
[2026-04-14T...] info  Using config file ...
[2026-04-14T...] info  HTTP server listening on http://0.0.0.0:8080/code
[2026-04-14T...] info    - Authentication is enabled
[2026-04-14T...] info      - Using password from $PASSWORD
```

Wenn stattdessen `error` erscheint: `VSCODE_PASSWORD` in `infra/.env` prüfen.

- [ ] **Step 7: Erreichbarkeit über Traefik prüfen**

```bash
curl -s -o /dev/null -w "%{http_code}" https://admin.heykarl.app/code/login
```

Erwartetes Ergebnis: `200`

Bei `404`: Traefik-Logs prüfen mit `docker logs assist2-traefik --tail 20` (oder wie der Traefik-Container heißt).

- [ ] **Step 8: Commit**

```bash
cd /opt/assist2
git add infra/docker-compose.yml
git commit -m "feat: add code-server at admin.heykarl.app/code"
```
