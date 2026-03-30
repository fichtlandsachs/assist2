# DB UIs & Admin Path Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install pgAdmin, phpMyAdmin, and Redis Commander; migrate all admin tool access from per-service subdomains to path-based routing under `admin.fichtlworks.com/<appname>`.

**Architecture:** Three new DB UI containers join the `internal`+`proxy` networks, each configured with a base-path env var so they generate correct absolute URLs. Traefik routes in `routes.yml` get per-path rules with `stripPrefix` middlewares. Existing tools (n8n, Nextcloud, LiteLLM, Stirling PDF, Whisper) are updated with new host/path env vars where required. Old subdomain routes are removed. Authentik gets new proxy providers for each tool.

**Tech Stack:** Docker Compose, Traefik v3, pgAdmin 4 (`dpage/pgadmin4`), phpMyAdmin (`phpmyadmin/phpmyadmin`), Redis Commander (`rediscommander/redis-commander`), Authentik API, FastAPI (backend)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `infra/docker-compose.yml` | Modify | Add pgAdmin, phpMyAdmin, Redis Commander; update n8n + Nextcloud env vars |
| `infra/pgadmin/servers.json` | Create | Pre-configure all 3 PostgreSQL servers in pgAdmin |
| `infra/traefik/dynamic/routes.yml` | Modify | Add path routes + strip-prefix middlewares; remove old subdomain routes |
| `backend/app/routers/superadmin.py` | Modify | Update admin_urls; add new DB tool entries |

---

## Task 1: Add secrets to `.env`

**Files:** Modify `infra/.env`

- [ ] **Step 1: Append pgAdmin credentials**

Open `infra/.env` and add at the end:

```bash
# pgAdmin
PGADMIN_EMAIL=admin@fichtlworks.com
PGADMIN_PASSWORD=<generate with: openssl rand -base64 24>
```

Generate the password:
```bash
openssl rand -base64 24
```

- [ ] **Step 2: Verify vars are present**

```bash
grep "PGADMIN" infra/.env
```

Expected: two lines with `PGADMIN_EMAIL` and `PGADMIN_PASSWORD`.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add infra/.env
git commit -m "chore: add pgAdmin credentials to .env"
```

---

## Task 2: Create pgAdmin server definitions

**Files:** Create `infra/pgadmin/servers.json`

- [ ] **Step 1: Create directory and file**

```bash
mkdir -p /opt/assist2/infra/pgadmin
```

Create `/opt/assist2/infra/pgadmin/servers.json`:

```json
{
  "Servers": {
    "1": {
      "Name": "Platform DB",
      "Group": "assist2",
      "Host": "assist2-postgres",
      "Port": 5432,
      "MaintenanceDB": "platform_db",
      "Username": "platform",
      "SSLMode": "prefer"
    },
    "2": {
      "Name": "Authentik DB",
      "Group": "assist2",
      "Host": "assist2-authentik-db",
      "Port": 5432,
      "MaintenanceDB": "authentik",
      "Username": "authentik",
      "SSLMode": "prefer"
    },
    "3": {
      "Name": "LiteLLM DB",
      "Group": "assist2",
      "Host": "assist2-litellm-postgres",
      "Port": 5432,
      "MaintenanceDB": "litellm_db",
      "Username": "litellm",
      "SSLMode": "prefer"
    }
  }
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -m json.tool /opt/assist2/infra/pgadmin/servers.json
```

Expected: formatted JSON output with no errors.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add infra/pgadmin/servers.json
git commit -m "feat(pgadmin): add pre-configured server definitions"
```

---

## Task 3: Add DB UI containers to docker-compose.yml

**Files:** Modify `infra/docker-compose.yml`

- [ ] **Step 1: Add pgAdmin service**

In `infra/docker-compose.yml`, after the `whisper:` service block, add:

```yaml
  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: assist2-pgadmin
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
      PGADMIN_CONFIG_SERVER_MODE: "False"
      SCRIPT_NAME: /pgadmin
    volumes:
      - assist2_pgadmin_data:/var/lib/pgadmin
      - ./pgadmin/servers.json:/pgadmin4/servers.json:ro
    networks:
      - internal
      - proxy

  phpmyadmin:
    image: phpmyadmin/phpmyadmin:latest
    container_name: assist2-phpmyadmin
    restart: unless-stopped
    environment:
      PMA_HOST: assist2-nextcloud-db
      PMA_PORT: 3306
      PMA_ABSOLUTE_URI: https://admin.fichtlworks.com/phpmyadmin/
    networks:
      - internal
      - proxy

  redis-commander:
    image: rediscommander/redis-commander:latest
    container_name: assist2-redis-commander
    restart: unless-stopped
    environment:
      REDIS_HOST: assist2-redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      URL_PREFIX: /redis
      HTTP_USER: admin
      HTTP_PASSWORD: ${PGADMIN_PASSWORD}
    networks:
      - internal
      - proxy
```

- [ ] **Step 2: Add pgadmin volume to volumes section**

In the `volumes:` section at the bottom of `docker-compose.yml`, add:

```yaml
  assist2_pgadmin_data:
```

- [ ] **Step 3: Verify compose syntax**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```

Expected: no output (silent success). Any output means a syntax error.

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add infra/docker-compose.yml
git commit -m "feat: add pgAdmin, phpMyAdmin, Redis Commander services"
```

---

## Task 4: Update n8n and Nextcloud configuration

**Files:** Modify `infra/docker-compose.yml`

- [ ] **Step 1: Update n8n host and webhook URL**

In the `n8n:` service `environment:` block, change:

```yaml
      N8N_HOST: assist2.${DOMAIN}
      N8N_PATH: /n8n/
      WEBHOOK_URL: https://assist2.${DOMAIN}/n8n/
```

To:

```yaml
      N8N_HOST: admin.${DOMAIN}
      N8N_PATH: /n8n/
      WEBHOOK_URL: https://admin.${DOMAIN}/n8n/
```

- [ ] **Step 2: Update Nextcloud trusted domains and overwrite settings**

In the `nextcloud:` service `environment:` block, change:

```yaml
      NEXTCLOUD_TRUSTED_DOMAINS: nextcloud.${DOMAIN}
```

To:

```yaml
      NEXTCLOUD_TRUSTED_DOMAINS: nextcloud.${DOMAIN} admin.${DOMAIN}
      OVERWRITEHOST: admin.${DOMAIN}
      OVERWRITEPROTOCOL: https
      OVERWRITEWEBROOT: /nextcloud
      OVERWRITECLIURL: https://admin.${DOMAIN}/nextcloud
```

- [ ] **Step 3: Verify compose syntax**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml config --quiet
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add infra/docker-compose.yml
git commit -m "feat: update n8n and Nextcloud config for admin path routing"
```

---

## Task 5: Update Traefik routes

**Files:** Modify `infra/traefik/dynamic/routes.yml` (at `/opt/assist/infra/traefik/dynamic/routes.yml`)

- [ ] **Step 1: Remove old subdomain routers**

Remove these router blocks entirely:
- `litellm:` (Host `litellm.fichtlworks.com`)
- `stirling-pdf:` (Host `pdf.fichtlworks.com`)
- `whisper:` (Host `whisper.fichtlworks.com`)
- `nextcloud:` (Host `nextcloud.fichtlworks.com`)
- `assist2-n8n:` (Host `assist2.fichtlworks.com` + PathPrefix `/n8n`)

Remove these service blocks:
- `litellm:` (url: `http://assist2-litellm:4000`)
- `stirling-pdf:` (url: `http://assist2-stirling-pdf:8080`)
- `whisper:` (url: `http://assist2-whisper:9000`)
- `nextcloud:` (url: `http://assist2-nextcloud:80`)
- `assist2-n8n:` (url: `http://assist2-n8n:5678`)

Remove these middleware blocks:
- `litellm-auth:`
- `n8n-strip:`

- [ ] **Step 2: Add path-based routers under admin.fichtlworks.com**

In the `routers:` section, after the `assist2-admin:` router, add:

```yaml
    # ── Admin tools (path-based, all behind Authentik) ────────────────────────
    admin-pgadmin:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/pgadmin`)"
      entryPoints: [websecure]
      service: pgadmin
      middlewares: [authentik, pgadmin-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-phpmyadmin:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/phpmyadmin`)"
      entryPoints: [websecure]
      service: phpmyadmin
      middlewares: [authentik, phpmyadmin-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-redis:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/redis`)"
      entryPoints: [websecure]
      service: redis-commander
      middlewares: [authentik, redis-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-litellm:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/litellm`)"
      entryPoints: [websecure]
      service: litellm
      middlewares: [authentik, litellm-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-pdf:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/pdf`)"
      entryPoints: [websecure]
      service: stirling-pdf
      middlewares: [authentik, pdf-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-whisper:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/whisper`)"
      entryPoints: [websecure]
      service: whisper
      middlewares: [authentik, whisper-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-n8n:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/n8n`)"
      entryPoints: [websecure]
      service: n8n
      middlewares: [authentik, n8n-strip]
      priority: 10
      tls:
        certResolver: letsencrypt

    admin-nextcloud:
      rule: "Host(`admin.fichtlworks.com`) && PathPrefix(`/nextcloud`)"
      entryPoints: [websecure]
      service: nextcloud
      middlewares: [authentik, nextcloud-strip]
      priority: 10
      tls:
        certResolver: letsencrypt
```

- [ ] **Step 3: Add new service backends**

In the `services:` section, add:

```yaml
    pgadmin:
      loadBalancer:
        servers:
          - url: "http://assist2-pgadmin:80"

    phpmyadmin:
      loadBalancer:
        servers:
          - url: "http://assist2-phpmyadmin:80"

    redis-commander:
      loadBalancer:
        servers:
          - url: "http://assist2-redis-commander:8081"

    litellm:
      loadBalancer:
        servers:
          - url: "http://assist2-litellm:4000"

    stirling-pdf:
      loadBalancer:
        servers:
          - url: "http://assist2-stirling-pdf:8080"

    whisper:
      loadBalancer:
        servers:
          - url: "http://assist2-whisper:9000"

    n8n:
      loadBalancer:
        servers:
          - url: "http://assist2-n8n:5678"

    nextcloud:
      loadBalancer:
        servers:
          - url: "http://assist2-nextcloud:80"
```

- [ ] **Step 4: Add strip-prefix middlewares**

In the `middlewares:` section, add:

```yaml
    pgadmin-strip:
      stripPrefix:
        prefixes: [/pgadmin]

    phpmyadmin-strip:
      stripPrefix:
        prefixes: [/phpmyadmin]

    redis-strip:
      stripPrefix:
        prefixes: [/redis]

    litellm-strip:
      stripPrefix:
        prefixes: [/litellm]

    pdf-strip:
      stripPrefix:
        prefixes: [/pdf]

    whisper-strip:
      stripPrefix:
        prefixes: [/whisper]

    n8n-strip:
      stripPrefix:
        prefixes: [/n8n]

    nextcloud-strip:
      stripPrefix:
        prefixes: [/nextcloud]
```

- [ ] **Step 5: Verify Traefik accepts the config**

```bash
docker exec assist-traefik traefik version 2>/dev/null; \
docker logs assist-traefik --tail 5 2>&1
```

Wait 10 seconds then check for errors:

```bash
sleep 10 && docker logs assist-traefik --tail 10 2>&1 | grep -i "error\|warn" | grep -v "WARN.*acme"
```

Expected: no errors related to routing or config parsing.

- [ ] **Step 6: Commit**

```bash
cd /opt/assist2
git add infra/traefik/dynamic/routes.yml 2>/dev/null || \
  git -C /opt/assist add infra/traefik/dynamic/routes.yml
git commit -m "feat: migrate admin tools to path-based routing under admin.fichtlworks.com"
```

Note: `routes.yml` is in `/opt/assist/infra/traefik/dynamic/routes.yml` — use the correct repo path.

---

## Task 6: Update Authentik providers and applications

**No files** — API calls only. Token: see `infra/.env` → `AUTHENTIK_API_TOKEN`.

- [ ] **Step 1: Update existing stirling-pdf provider**

```bash
curl -s -X PATCH \
  -H "Authorization: Bearer e5ZZ3oETS4o0LfKceZqvX9JKwBThYBYdNbB9NnjLCAvUv5xgUDHQnXrqzrXc" \
  -H "Content-Type: application/json" \
  "https://authentik.fichtlworks.com/api/v3/providers/proxy/4/" \
  -d '{"external_host": "https://admin.fichtlworks.com/pdf"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d.get('external_host'))"
```

Expected: `OK: https://admin.fichtlworks.com/pdf`

- [ ] **Step 2: Update existing whisper provider**

```bash
curl -s -X PATCH \
  -H "Authorization: Bearer e5ZZ3oETS4o0LfKceZqvX9JKwBThYBYdNbB9NnjLCAvUv5xgUDHQnXrqzrXc" \
  -H "Content-Type: application/json" \
  "https://authentik.fichtlworks.com/api/v3/providers/proxy/5/" \
  -d '{"external_host": "https://admin.fichtlworks.com/whisper"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('OK:', d.get('external_host'))"
```

Expected: `OK: https://admin.fichtlworks.com/whisper`

- [ ] **Step 3: Create new proxy providers**

Run this script to create all 6 new providers at once:

```bash
TOKEN="e5ZZ3oETS4o0LfKceZqvX9JKwBThYBYdNbB9NnjLCAvUv5xgUDHQnXrqzrXc"
BASE="https://authentik.fichtlworks.com"
AUTH_FLOW="9a8c8d84-33b0-4a23-96e5-823c125be234"
INV_FLOW="91867805-7a8f-4218-83a4-340104fae6b0"

for entry in "pgadmin|https://admin.fichtlworks.com/pgadmin" \
             "phpmyadmin|https://admin.fichtlworks.com/phpmyadmin" \
             "redis-commander|https://admin.fichtlworks.com/redis" \
             "n8n|https://admin.fichtlworks.com/n8n" \
             "nextcloud|https://admin.fichtlworks.com/nextcloud" \
             "litellm|https://admin.fichtlworks.com/litellm"; do
  NAME="${entry%%|*}"
  HOST="${entry##*|}"
  RESULT=$(curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "$BASE/api/v3/providers/proxy/" \
    -d "{
      \"name\": \"$NAME\",
      \"authorization_flow\": \"$AUTH_FLOW\",
      \"invalidation_flow\": \"$INV_FLOW\",
      \"external_host\": \"$HOST\",
      \"mode\": \"forward_single\",
      \"access_token_validity\": \"hours=24\",
      \"refresh_token_validity\": \"days=30\",
      \"basic_auth_enabled\": false
    }")
  PK=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin).get('pk','ERR'))")
  echo "Created $NAME → pk=$PK"
done
```

Expected output (pks will differ):
```
Created pgadmin → pk=6
Created phpmyadmin → pk=7
Created redis-commander → pk=8
Created n8n → pk=9
Created nextcloud → pk=10
Created litellm → pk=11
```

Note the pk values — needed in the next step.

- [ ] **Step 4: Create applications for each new provider**

```bash
TOKEN="e5ZZ3oETS4o0LfKceZqvX9JKwBThYBYdNbB9NnjLCAvUv5xgUDHQnXrqzrXc"
BASE="https://authentik.fichtlworks.com"

# Get provider PKs by name
for NAME in pgadmin phpmyadmin redis-commander n8n nextcloud litellm; do
  PK=$(curl -s -H "Authorization: Bearer $TOKEN" \
    "$BASE/api/v3/providers/proxy/?search=$NAME" \
    | python3 -c "import sys,json; r=json.load(sys.stdin)['results']; print(next((p['pk'] for p in r if p['name']=='$NAME'), 'NOT_FOUND'))")

  SLUG=$(echo $NAME | tr '-' '_')
  LAUNCH="https://admin.fichtlworks.com/${NAME//_/-}"
  # fix redis-commander slug/launch
  [ "$NAME" = "redis-commander" ] && LAUNCH="https://admin.fichtlworks.com/redis"

  curl -s -X POST \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    "$BASE/api/v3/core/applications/" \
    -d "{
      \"name\": \"$NAME\",
      \"slug\": \"$NAME\",
      \"provider\": $PK,
      \"meta_launch_url\": \"$LAUNCH\"
    }" | python3 -c "import sys,json; d=json.load(sys.stdin); print('App:', d.get('slug','ERR'), d.get('detail',''))"
done
```

Expected: one `App: <name>` line per provider, no errors.

- [ ] **Step 5: Add all new providers to the outpost**

```bash
TOKEN="e5ZZ3oETS4o0LfKceZqvX9JKwBThYBYdNbB9NnjLCAvUv5xgUDHQnXrqzrXc"
BASE="https://authentik.fichtlworks.com"
OUTPOST="c5d4f24c-741e-41e4-8387-0af5388e9b7f"

CURRENT=$(curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/v3/outposts/instances/$OUTPOST/")
NEW_PROVIDERS=$(echo $CURRENT | python3 -c "
import sys, json
d = json.load(sys.stdin)
providers = d.get('providers', [])
# Get all proxy provider PKs
import urllib.request
req = urllib.request.Request(
    'https://authentik.fichtlworks.com/api/v3/providers/proxy/',
    headers={'Authorization': 'Bearer $TOKEN'}
)
with urllib.request.urlopen(req) as r:
    all_proxy = json.loads(r.read())
for p in all_proxy['results']:
    if p['pk'] not in providers:
        providers.append(p['pk'])
print(json.dumps(providers))
")

curl -s -X PATCH \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$BASE/api/v3/outposts/instances/$OUTPOST/" \
  -d "{\"providers\": $NEW_PROVIDERS}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('Outpost providers:', sorted(d.get('providers',[])))"
```

Expected: list containing all provider PKs (at minimum 4, 5, 6, 7, 8, 9, 10, 11).

---

## Task 7: Update backend superadmin.py

**Files:** Modify `backend/app/routers/superadmin.py`

- [ ] **Step 1: Replace the COMPONENTS list**

In `backend/app/routers/superadmin.py`, replace the entire `COMPONENTS = [...]` block with:

```python
COMPONENTS = [
    {
        "name": "Authentik",
        "label": "Identity Provider",
        "internal_url": "http://assist2-authentik-server:9000",
        "health_path": "/-/health/ready/",
        "admin_url": "https://authentik.fichtlworks.com/if/admin/",
    },
    {
        "name": "n8n",
        "label": "Workflow Engine",
        "internal_url": "http://assist2-n8n:5678",
        "health_path": "/healthz",
        "admin_url": "https://admin.fichtlworks.com/n8n/",
    },
    {
        "name": "LiteLLM",
        "label": "AI Proxy",
        "internal_url": "http://assist2-litellm:4000",
        "health_path": "/health/liveliness",
        "admin_url": "https://admin.fichtlworks.com/litellm/ui",
    },
    {
        "name": "Nextcloud",
        "label": "Dateiverwaltung",
        "internal_url": "http://assist2-nextcloud",
        "health_path": "/status.php",
        "admin_url": "https://admin.fichtlworks.com/nextcloud",
    },
    {
        "name": "Stirling PDF",
        "label": "PDF-Tools",
        "internal_url": "http://assist2-stirling-pdf:8080",
        "health_path": "/",
        "admin_url": "https://admin.fichtlworks.com/pdf",
    },
    {
        "name": "Whisper",
        "label": "Transkription",
        "internal_url": "http://assist2-whisper:9000",
        "health_path": "/",
        "admin_url": "https://admin.fichtlworks.com/whisper",
    },
    {
        "name": "pgAdmin",
        "label": "PostgreSQL UI",
        "internal_url": "http://assist2-pgadmin:80",
        "health_path": "/pgadmin/misc/ping",
        "admin_url": "https://admin.fichtlworks.com/pgadmin",
    },
    {
        "name": "phpMyAdmin",
        "label": "MariaDB UI",
        "internal_url": "http://assist2-phpmyadmin:80",
        "health_path": "/phpmyadmin/",
        "admin_url": "https://admin.fichtlworks.com/phpmyadmin",
    },
    {
        "name": "Redis Commander",
        "label": "Redis UI",
        "internal_url": "http://assist2-redis-commander:8081",
        "health_path": "/redis/",
        "admin_url": "https://admin.fichtlworks.com/redis",
    },
]
```

- [ ] **Step 2: Commit**

```bash
cd /opt/assist2
git add backend/app/routers/superadmin.py
git commit -m "feat(admin): add DB UI components and update admin_urls to path routing"
```

---

## Task 8: Deploy new DB UI containers

**Files:** None (deployment)

- [ ] **Step 1: Start new containers**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d pgadmin phpmyadmin redis-commander 2>&1
```

Expected: three containers starting without errors.

- [ ] **Step 2: Verify containers are running**

```bash
docker ps --filter "name=assist2-pgadmin" --filter "name=assist2-phpmyadmin" --filter "name=assist2-redis-commander" --format "{{.Names}}\t{{.Status}}"
```

Expected: all three showing `Up`.

- [ ] **Step 3: Verify pgAdmin is reachable internally**

```bash
sleep 15 && docker exec assist2-backend curl -s -o /dev/null -w "%{http_code}" http://assist2-pgadmin:80/pgadmin/misc/ping
```

Expected: `200`

- [ ] **Step 4: Verify phpMyAdmin is reachable internally**

```bash
docker exec assist2-backend curl -s -o /dev/null -w "%{http_code}" http://assist2-phpmyadmin:80/phpmyadmin/
```

Expected: `200`

- [ ] **Step 5: Verify Redis Commander is reachable internally**

```bash
docker exec assist2-backend curl -s -o /dev/null -w "%{http_code}" http://assist2-redis-commander:8081/redis/
```

Expected: `200`

---

## Task 9: Redeploy changed services and apply Nextcloud config

**Files:** None (deployment)

- [ ] **Step 1: Rebuild and restart backend**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend 2>&1 | tail -5
```

Expected: `assist2-backend Started`

- [ ] **Step 2: Restart n8n with new host config**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d n8n 2>&1 | tail -3
```

Expected: `assist2-n8n Started` (or Recreated)

- [ ] **Step 3: Restart Nextcloud with new overwrite config**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d nextcloud 2>&1 | tail -3
```

Expected: `assist2-nextcloud Started`

- [ ] **Step 4: Apply Nextcloud overwrite settings via occ**

The Docker env vars only apply on initial install. Run occ commands to update the running config:

```bash
docker exec -u www-data assist2-nextcloud php occ config:system:set overwritehost --value="admin.fichtlworks.com"
docker exec -u www-data assist2-nextcloud php occ config:system:set overwriteprotocol --value="https"
docker exec -u www-data assist2-nextcloud php occ config:system:set overwritewebroot --value="/nextcloud"
docker exec -u www-data assist2-nextcloud php occ config:system:set overwritecliurl --value="https://admin.fichtlworks.com/nextcloud"
docker exec -u www-data assist2-nextcloud php occ config:system:set trusted_domains 2 --value="admin.fichtlworks.com"
```

Expected: each command prints `System config value ... set to string ...`

- [ ] **Step 5: Verify Nextcloud config**

```bash
docker exec -u www-data assist2-nextcloud php occ config:system:get overwritewebroot
docker exec -u www-data assist2-nextcloud php occ config:system:get overwritehost
```

Expected:
```
/nextcloud
admin.fichtlworks.com
```

---

## Task 10: End-to-end verification

- [ ] **Step 1: Check Traefik routes loaded**

```bash
docker logs assist-traefik --since 2m 2>&1 | grep -i "error" | grep -v "acme"
```

Expected: no errors.

- [ ] **Step 2: Test all new paths via HTTPS**

```bash
for path in pgadmin phpmyadmin redis n8n nextcloud litellm pdf whisper; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-redirs 3 \
    "https://admin.fichtlworks.com/$path" \
    -H "Host: admin.fichtlworks.com")
  echo "$path: $CODE"
done
```

Expected: all return `200` or `302` (Authentik login redirect). A `404` or `502` means the route or container is broken.

- [ ] **Step 3: Verify superadmin status endpoint**

```bash
docker exec assist2-backend curl -s http://localhost:8000/api/v1/superadmin/status \
  -H "Authorization: Bearer test" 2>&1 | head -5
```

Expected: `{"error":"Not authenticated"...}` — confirms endpoint is reachable (auth is expected to fail here).

- [ ] **Step 4: Verify old subdomains no longer route**

```bash
for sub in litellm pdf whisper nextcloud; do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" "https://$sub.fichtlworks.com" 2>/dev/null || echo "DNS_FAIL")
  echo "$sub.fichtlworks.com: $CODE"
done
```

Expected: `404`, `000` (no route), or DNS failure — confirms old routes are gone.

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
cd /opt/assist2
git status
# commit any remaining changes
```
