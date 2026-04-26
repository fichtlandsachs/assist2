#!/usr/bin/env bash
# =============================================================================
# heykarl + Ghost + Traefik — Full-Stack Installer (eigenständig inkl. Authentik IDP)
# Reproduced from production layout on a fresh Debian VM.
#
# Usage:
#   curl -fsSL https://<repo>/infra/scripts/install.sh | bash
#   -- or --
#   HEYKARL_ROOT=/opt/heykarl bash infra/scripts/install.sh
#
# Requirements:
#   - Debian 11/12 (root or sudo)
#   - DNS records for your domain already pointing to this VM
#   - A Cloudflare API token with Zone:DNS:Edit for ACME (or use --no-tls for
#     self-signed certs when setting up a local test environment)
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fatal()   { echo -e "${RED}[FATAL]${NC} $*" >&2; exit 1; }
section() { echo -e "\n${BOLD}━━━ $* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }

# ── Argument parsing ─────────────────────────────────────────────────────────
NO_TLS=false
SKIP_BUILD=false
REPO_URL=""
GIT_BRANCH="main"
HEYKARL_ROOT="${HEYKARL_ROOT:-/opt/heykarl}"
# Festes Authentik-Bootstrap-Passwort (z. B. admin123) nur zusammen mit --new-install / HEYKARL_NEW_INSTALL=1
NEW_INSTALL=false
[[ "${HEYKARL_NEW_INSTALL:-}" == "1" || "${HEYKARL_NEW_INSTALL:-}" =~ ^(true|yes)$ ]] && NEW_INSTALL=true
INITIAL_ADMIN_PASSWORD="${INITIAL_ADMIN_PASSWORD:-}"

for arg in "$@"; do
  case $arg in
    --no-tls)      NO_TLS=true ;;
    --skip-build)  SKIP_BUILD=true ;;
    --repo=*)      REPO_URL="${arg#*=}" ;;
    --branch=*)    GIT_BRANCH="${arg#*=}" ;;
    --heykarl-root=*) HEYKARL_ROOT="${arg#*=}" ;;
    --new-install) NEW_INSTALL=true ;;
    --initial-admin-password=*) INITIAL_ADMIN_PASSWORD="${arg#*=}" ;;
    --help|-h)
      echo "Usage: $0 [--no-tls] [--skip-build] [--repo=<url>] [--branch=<name>] [--heykarl-root=<path>] [--new-install] [--initial-admin-password=<pw>]"
      echo "  --no-tls           Use self-signed certs (no Let's Encrypt, no Cloudflare token needed)"
      echo "  --skip-build       Skip Docker image builds (use cached images)"
      echo "  --repo=URL         Git repository URL (defaults to interactive prompt)"
      echo "  --branch=NAME      Git branch to check out (default: main)"
      echo "  --heykarl-root=DIR          Install application tree here (default: /opt/heykarl)"
      echo "  --new-install               Neuinstallation: Authentik-Bootstrap-Passwort wählbar (Default: admin123)"
      echo "  --initial-admin-password=PW Nur mit --new-install: Passwort für Authentik akadmin (env: INITIAL_ADMIN_PASSWORD)"
      echo "  Env HEYKARL_NEW_INSTALL=1   Wie --new-install"
      exit 0
      ;;
  esac
done

if [[ -n "$INITIAL_ADMIN_PASSWORD" && "$NEW_INSTALL" != "true" ]]; then
  fatal "--initial-admin-password bzw. INITIAL_ADMIN_PASSWORD ist nur bei Neuinstallation erlaubt (zusätzlich --new-install oder HEYKARL_NEW_INSTALL=1)."
fi

export HEYKARL_ROOT
export NEW_INSTALL

# ── Root check ───────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
  fatal "This script must be run as root (or with sudo)."
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Welcome to the heykarl installer"
# ─────────────────────────────────────────────────────────────────────────────
echo -e "This script will:"
echo -e "  1. Install Docker + dependencies"
echo -e "  2. Check out the heykarl and Ghost repositories under ${HEYKARL_ROOT}"
echo -e "  3. Generate secrets and write .env files"
echo -e "  4. Start Traefik → Authentik (IDP) + HeyKarl Stack → Ghost"
echo -e "  5. Provision OIDC clients in Authentik (Backend + Admin) and merge into .env"
echo -e "  6. Run database migrations and seed data"
echo -e "  7. Optionally run the Nextcloud post-install wizard"
echo ""
if [[ "$NEW_INSTALL" == "true" ]]; then
  echo -e "${YELLOW}Modus: Neuinstallation — Authentik-Bootstrap-Passwort wie gewählt (Default admin123).${NC}"
else
  echo -e "${YELLOW}Kein --new-install: Authentik-Bootstrap-Passwort wird zufällig gesetzt (kein admin123).${NC}"
fi
echo -e "${YELLOW}Estimated time: 15-30 min (depending on image pull speed)${NC}"
echo ""

# ── Helpers ──────────────────────────────────────────────────────────────────
gen_secret() {
  openssl rand -base64 "${1:-32}" | tr -d '=+/' | cut -c1-"${1:-32}"
}

prompt() {
  # prompt VAR_NAME "text" ["default"]
  # If default is empty string "", the field is optional (Enter = empty).
  # If default is non-empty, Enter accepts the default.
  # Only loops when no default is provided AND the variable name does not end in _OPT.
  local var_name="$1" prompt_text="$2" default="${3-__REQUIRED__}"
  local value
  if [[ "$default" != "__REQUIRED__" ]]; then
    # Optional or has default — never loop
    local hint=""
    [[ -n "$default" ]] && hint=" [${default}]"
    read -rp "$(echo -e "${BOLD}${prompt_text}${NC}${hint}: ")" value </dev/tty
    echo "${value:-$default}"
  else
    # Required — loop until non-empty
    while true; do
      read -rp "$(echo -e "${BOLD}${prompt_text}${NC}: ")" value </dev/tty
      [[ -n "$value" ]] && break
      warn "This field is required."
    done
    echo "$value"
  fi
}

prompt_optional() {
  local prompt_text="$1"
  local value
  read -rp "$(echo -e "${BOLD}${prompt_text}${NC} [Enter to skip]: ")" value </dev/tty
  echo "$value"
}

prompt_secret() {
  local prompt_text="$1" default="${2:-}"
  local value
  if [[ -n "$default" ]]; then
    read -rsp "$(echo -e "${BOLD}${prompt_text}${NC} [leave empty to auto-generate]: ")" value </dev/tty
    echo ""
    echo "${value:-$default}"
  else
    read -rsp "$(echo -e "${BOLD}${prompt_text}${NC} [leave empty to auto-generate]: ")" value </dev/tty
    echo ""
    if [[ -z "$value" ]]; then
      value="$(gen_secret 32)"
      echo -e "${BLUE}[INFO]${NC}  Auto-generated secret." >/dev/tty
    fi
    echo "$value"
  fi
}

wait_healthy() {
  local name="$1" max="${2:-120}" i=0
  info "Waiting for ${name} to become healthy…"
  while [[ $i -lt $max ]]; do
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "missing")
    if [[ "$status" == "healthy" ]]; then
      ok "${name} is healthy."
      return 0
    fi
    sleep 3
    (( i+=3 ))
  done
  warn "${name} did not become healthy within ${max}s — check: docker logs ${name}"
  return 1
}

merge_oidc_credentials_into_env() {
  local env_file="${HEYKARL_ROOT}/infra/.env"
  local py="${HEYKARL_ROOT}/infra/scripts/authentik_provision_oidc.py"
  [[ -f "$py" ]] || fatal "Missing Authentik provisioning script: $py"
  info "Provisioning Authentik OAuth applications (HeyKarl Backend + Admin)…"
  docker cp "$py" heykarl-authentik-server:/tmp/authentik_provision_oidc.py
  local json
  json="$(docker exec -e DOMAIN="$DOMAIN" heykarl-authentik-server \
    ak shell -c "exec(open('/tmp/authentik_provision_oidc.py').read())" 2>/dev/null | grep '^{' | tail -1 || true)"
  [[ -n "$json" ]] || fatal "Authentik OIDC provision did not return JSON (see: docker logs heykarl-authentik-server)"
  local k v
  for k in AUTHENTIK_BACKEND_CLIENT_ID AUTHENTIK_BACKEND_CLIENT_SECRET AUTHENTIK_ADMIN_CLIENT_ID AUTHENTIK_ADMIN_CLIENT_SECRET; do
    v="$(echo "$json" | jq -r --arg k "$k" '.[$k] // empty')"
    [[ -n "$v" ]] || fatal "Missing key $k in provisioner output"
    if [[ "$v" == "__PRESERVE__" ]]; then
      warn "Authentik application already exists for $k — leaving existing .env value untouched."
      continue
    fi
    grep -q "^${k}=" "$env_file" && sed -i "/^${k}=/d" "$env_file"
    printf '%s=%s\n' "$k" "$v" >> "$env_file"
  done
  chmod 0600 "$env_file" || true
  ok "Authentik OIDC credentials merged into ${env_file}"
}

# ─────────────────────────────────────────────────────────────────────────────
section "Step 1 — System prerequisites"
# ─────────────────────────────────────────────────────────────────────────────
apt-get update -qq
apt-get install -y -qq \
  ca-certificates curl gnupg lsb-release git make jq \
  python3-pip 2>/dev/null || true

# Docker
if ! command -v docker &>/dev/null; then
  info "Installing Docker…"
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
    https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
    | tee /etc/apt/sources.list.d/docker.list > /dev/null
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable --now docker
  ok "Docker installed."
else
  ok "Docker already installed: $(docker --version)"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Step 2 — Configuration"
# ─────────────────────────────────────────────────────────────────────────────
echo ""
DOMAIN=$(prompt DOMAIN "Primary domain (e.g. example.com)" "")
ADMIN_EMAIL=$(prompt ADMIN_EMAIL "Admin email address" "admin@${DOMAIN}")
ACME_EMAIL=$(prompt ACME_EMAIL "Let's Encrypt / ACME email" "$ADMIN_EMAIL")

if [[ "$NO_TLS" == false ]]; then
  CF_DNS_API_TOKEN=$(prompt_secret "Cloudflare DNS API token (for Let's Encrypt DNS challenge)" "")
  CERT_RESOLVER="letsencrypt"
else
  CF_DNS_API_TOKEN="none"
  CERT_RESOLVER="localdev"
  warn "Running with self-signed TLS. Not suitable for production."
fi

echo ""
echo -e "${BOLD}Optional AI providers${NC} (press Enter to skip):"
ANTHROPIC_API_KEY=$(prompt_secret "Anthropic API key" "")
IONOS_API_KEY=$(prompt_secret "IONOS AI API key" "")
IONOS_API_BASE=$(prompt IONOS_API_BASE "IONOS API base URL" "https://openai.ionos.com/openai")

echo ""
echo -e "${BOLD}Optional OAuth (press Enter to skip — can be configured later)${NC}:"
GITHUB_CLIENT_ID=$(prompt_optional "GitHub OAuth Client ID")
GITHUB_CLIENT_SECRET=$(prompt_optional "GitHub OAuth Client Secret")
ATLASSIAN_CLIENT_ID=$(prompt_optional "Atlassian OAuth Client ID")
ATLASSIAN_CLIENT_SECRET=$(prompt_optional "Atlassian OAuth Client Secret")

echo ""
info "Generating secrets…"
if [[ "$NEW_INSTALL" == "true" ]]; then
  INITIAL_ADMIN_PASSWORD="${INITIAL_ADMIN_PASSWORD:-admin123}"
  if [[ "$INITIAL_ADMIN_PASSWORD" == "admin123" ]]; then
    warn "Authentik-Bootstrap nutzt das Default-Passwort „admin123“ — nach erstem Login ändern."
  fi
  AUTHENTIK_BOOTSTRAP_PASSWORD="${INITIAL_ADMIN_PASSWORD}"
else
  AUTHENTIK_BOOTSTRAP_PASSWORD=$(gen_secret 20)
fi

# Core secrets
SECRET_KEY=$(gen_secret 48)
JWT_SECRET=$(gen_secret 48)
ENCRYPTION_KEY=$(gen_secret 32)

# Database passwords
POSTGRES_PASSWORD=$(gen_secret 32)
REDIS_PASSWORD=$(gen_secret 32)
AUTHENTIK_DB_PASSWORD=$(gen_secret 32)
AUTHENTIK_SECRET_KEY=$(gen_secret 50)
AUTHENTIK_BOOTSTRAP_TOKEN=$(gen_secret 48)
LITELLM_MASTER_KEY="sk-$(gen_secret 32)"
LITELLM_DB_PASSWORD=$(gen_secret 32)
N8N_ENCRYPTION_KEY=$(gen_secret 32)
NEXTCLOUD_DB_PASSWORD=$(gen_secret 32)
NEXTCLOUD_DB_ROOT_PASSWORD=$(gen_secret 32)
GHOST_DB_PASSWORD=$(gen_secret 32)
GHOST_DB_ROOT_PASSWORD=$(gen_secret 32)

# Traefik basic auth (admin:<random>)
TRAEFIK_ADMIN_PASS=$(gen_secret 16)
# openssl passwd is always available; htpasswd is not installed on minimal Debian
TRAEFIK_BASIC_AUTH="admin:$(openssl passwd -apr1 "$TRAEFIK_ADMIN_PASS" | sed 's/\$/\$\$/g')"

ok "Secrets generated."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 3 — Repository checkout"
# ─────────────────────────────────────────────────────────────────────────────

if [[ -z "$REPO_URL" ]]; then
  REPO_URL=$(prompt REPO_URL "Git repository URL for heykarl" "")
fi

if [[ ! -d "${HEYKARL_ROOT}/.git" ]]; then
  info "Cloning heykarl into ${HEYKARL_ROOT}…"
  git clone --branch "$GIT_BRANCH" "$REPO_URL" "${HEYKARL_ROOT}"
  ok "Cloned."
else
  info "${HEYKARL_ROOT} already exists — pulling latest…"
  git -C "${HEYKARL_ROOT}" pull --ff-only
  ok "Up to date."
fi

# Traefik stack — stored separately from the app repo
mkdir -p /opt/traefik
if [[ ! -f /opt/traefik/docker-compose.yml ]]; then
  info "Creating Traefik stack at /opt/traefik…"

  # docker-api-proxy.conf (nginx socket proxy for Docker API version compat)
  cat > /opt/traefik/docker-api-proxy.conf << 'NGINX_EOF'
user root;
worker_processes 1;
events { worker_connections 256; }
http {
  upstream docker_upstream {
    server unix:/var/run/docker.sock;
  }
  server {
    listen 2375;
    location ~ ^/v[0-9]+\.[0-9]+(/.*)? {
      set $rest $1;
      proxy_pass http://docker_upstream/v1.47$rest$is_args$args;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_buffering off;
      proxy_read_timeout 36000s;
    }
    location / {
      proxy_pass http://docker_upstream;
      proxy_http_version 1.1;
      proxy_buffering off;
      proxy_read_timeout 36000s;
    }
  }
}
NGINX_EOF

  cat > /opt/traefik/docker-compose.yml << TRAEFIK_EOF
services:
  socket-proxy:
    image: nginx:alpine
    container_name: traefik-socket-proxy
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./docker-api-proxy.conf:/etc/nginx/nginx.conf:ro
    networks:
      - socket

  traefik:
    image: traefik:v3.3
    container_name: assist-traefik
    restart: unless-stopped
    depends_on:
      - socket-proxy
    environment:
      ACME_EMAIL: \${ACME_EMAIL}
      CF_DNS_API_TOKEN: \${CF_DNS_API_TOKEN}
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080"
    volumes:
      - ${HEYKARL_ROOT}/infra/traefik/traefik.yml:/etc/traefik/traefik.yml:ro
      - ${HEYKARL_ROOT}/infra/traefik/dynamic:/etc/traefik/dynamic:ro
      - traefik-certs:/certs
    networks:
      - proxy
      - socket
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.traefik-dashboard.rule=Host(\`traefik.${DOMAIN}\`)"
      - "traefik.http.routers.traefik-dashboard.entrypoints=websecure"
      - "traefik.http.routers.traefik-dashboard.service=api@internal"
      - "traefik.http.routers.traefik-dashboard.middlewares=authentik@file"
      - "traefik.http.routers.traefik-dashboard.tls.certresolver=${CERT_RESOLVER}"

networks:
  proxy:
    name: assist-proxy
    external: true
  socket:
    name: traefik-socket
    internal: true

volumes:
  traefik-certs:
    name: assist_traefik-certs
    external: true
TRAEFIK_EOF

  ok "Traefik stack created."
fi

# Keep Traefik volume paths in sync when HEYKARL_ROOT changes between installs
if [[ -f /opt/traefik/docker-compose.yml ]]; then
  sed -i "s#/opt/assist2/infra/traefik#${HEYKARL_ROOT}/infra/traefik#g" /opt/traefik/docker-compose.yml 2>/dev/null || true
  sed -i "s#/opt/heykarl_cloud/infra/traefik#${HEYKARL_ROOT}/infra/traefik#g" /opt/traefik/docker-compose.yml 2>/dev/null || true
  sed -i "s#/opt/heykarl/infra/traefik#${HEYKARL_ROOT}/infra/traefik#g" /opt/traefik/docker-compose.yml 2>/dev/null || true
fi

# Ghost stack
mkdir -p /opt/ghost
if [[ ! -f /opt/ghost/docker-compose.yml ]]; then
  info "Creating Ghost stack at /opt/ghost…"
  cat > /opt/ghost/docker-compose.yml << GHOST_EOF
name: ghost

services:
  db:
    image: mysql:8.0
    container_name: ghost-db
    restart: unless-stopped
    environment:
      MYSQL_ROOT_PASSWORD: \${MYSQL_ROOT_PASSWORD:?required}
      MYSQL_DATABASE: ghost
      MYSQL_USER: ghost
      MYSQL_PASSWORD: \${MYSQL_PASSWORD:?required}
    volumes:
      - ghost-db:/var/lib/mysql
    networks:
      - internal
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "ghost", "-p\${MYSQL_PASSWORD}"]
      interval: 10s
      timeout: 5s
      retries: 5

  ghost:
    image: ghost:5-alpine
    container_name: ghost
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      url: https://${DOMAIN}
      database__client: mysql
      database__connection__host: db
      database__connection__user: ghost
      database__connection__password: \${MYSQL_PASSWORD:?required}
      database__connection__database: ghost
      mail__transport: SMTP
      mail__options__host: \${SMTP_HOST:-}
      mail__options__port: \${SMTP_PORT:-587}
      mail__options__auth__user: \${SMTP_USER:-}
      mail__options__auth__pass: \${SMTP_PASS:-}
      mail__options__secure: "false"
      mail__from: \${MAIL_FROM:-noreply@${DOMAIN}}
      server__trustProxy: "true"
      privacy__useUpdateCheck: "false"
      privacy__useGhostPublicAPI: "false"
    volumes:
      - ghost-content:/var/lib/ghost/content
    networks:
      - proxy
      - internal
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ghost.rule=Host(\`${DOMAIN}\`)"
      - "traefik.http.routers.ghost.entrypoints=websecure"
      - "traefik.http.routers.ghost.tls.certresolver=${CERT_RESOLVER}"
      - "traefik.http.services.ghost.loadbalancer.server.port=2368"
      - "traefik.http.routers.ghost-www.rule=Host(\`www.${DOMAIN}\`)"
      - "traefik.http.routers.ghost-www.entrypoints=websecure"
      - "traefik.http.routers.ghost-www.tls.certresolver=${CERT_RESOLVER}"
      - "traefik.http.routers.ghost-www.middlewares=ghost-www-redirect"
      - "traefik.http.middlewares.ghost-www-redirect.redirectregex.regex=^https://www\\.${DOMAIN}/(.*)"
      - "traefik.http.middlewares.ghost-www-redirect.redirectregex.replacement=https://${DOMAIN}/\$\${1}"
      - "traefik.http.middlewares.ghost-www-redirect.redirectregex.permanent=true"

networks:
  proxy:
    name: assist-proxy
    external: true
  internal:
    name: ghost-internal

volumes:
  ghost-db:
    name: ghost-db
  ghost-content:
    name: ghost-content
GHOST_EOF
  ok "Ghost stack created."
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Step 4 — Write .env files"
# ─────────────────────────────────────────────────────────────────────────────

# Traefik .env
cat > /opt/traefik/.env << EOF
ACME_EMAIL=${ACME_EMAIL}
CF_DNS_API_TOKEN=${CF_DNS_API_TOKEN}
EOF

# Ghost .env
cat > /opt/ghost/.env << EOF
MYSQL_ROOT_PASSWORD=${GHOST_DB_ROOT_PASSWORD}
MYSQL_PASSWORD=${GHOST_DB_PASSWORD}
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
MAIL_FROM=noreply@${DOMAIN}
EOF

# Update Traefik static config with correct email and cert resolver
sed -i "s/email: .*/email: ${ACME_EMAIL}/" "${HEYKARL_ROOT}/infra/traefik/traefik.yml" || true

# Update Traefik dynamic config domain references
find "${HEYKARL_ROOT}/infra/traefik/dynamic" -name "*.yml" \
  -exec sed -i "s/heykarl\.app/${DOMAIN}/g" {} \; \
  -exec sed -i "s/certresolver: letsencrypt/certresolver: ${CERT_RESOLVER}/g" {} \;

# heykarl .env
cat > "${HEYKARL_ROOT}/infra/.env" << EOF
# ── Core ──────────────────────────────────────────────────────────────────────
DOMAIN=${DOMAIN}
ENVIRONMENT=production
SECRET_KEY=${SECRET_KEY}
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
CORS_ORIGINS=["https://${DOMAIN}","https://admin.${DOMAIN}"]
APP_BASE_URL=https://${DOMAIN}

# ── PostgreSQL ────────────────────────────────────────────────────────────────
POSTGRES_USER=platform
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=platform_db

# ── Redis ─────────────────────────────────────────────────────────────────────
REDIS_PASSWORD=${REDIS_PASSWORD}

# ── AI Providers ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
IONOS_API_KEY=${IONOS_API_KEY}
IONOS_API_BASE=${IONOS_API_BASE}
IONOS_MODEL_CACHE_TTL=300
OPENAI_API_KEY=

# ── LiteLLM ───────────────────────────────────────────────────────────────────
LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY}
LITELLM_DB_PASSWORD=${LITELLM_DB_PASSWORD}
LITELLM_UI_AUTH=admin:${LITELLM_MASTER_KEY}
PROVIDER_ROUTING_SUGGEST=auto
PROVIDER_ROUTING_DOCS=claude-sonnet-4-6
PROVIDER_ROUTING_FALLBACK=ionos-fast
AI_FEATURE_FLAGS=streaming,embeddings

# ── n8n ───────────────────────────────────────────────────────────────────────
N8N_API_KEY=$(gen_secret 40)
N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}

# ── Authentik (IDP) ───────────────────────────────────────────────────────────
AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
AUTHENTIK_DB_PASSWORD=${AUTHENTIK_DB_PASSWORD}
AUTHENTIK_BOOTSTRAP_EMAIL=${ADMIN_EMAIL}
AUTHENTIK_BOOTSTRAP_PASSWORD=${AUTHENTIK_BOOTSTRAP_PASSWORD}
AUTHENTIK_BOOTSTRAP_TOKEN=${AUTHENTIK_BOOTSTRAP_TOKEN}
# Bootstrap token doubles as API token until you create a dedicated token in Authentik
AUTHENTIK_API_TOKEN=${AUTHENTIK_BOOTSTRAP_TOKEN}
# OIDC clients (filled by install.sh after Authentik is up — see authentik_provision_oidc.py)
AUTHENTIK_BACKEND_CLIENT_ID=
AUTHENTIK_BACKEND_CLIENT_SECRET=
AUTHENTIK_JWKS_URL=https://authentik.${DOMAIN}/application/o/backend/jwks/
AUTHENTIK_APP_SLUG=backend
AUTHENTIK_ADMIN_CLIENT_ID=
AUTHENTIK_ADMIN_CLIENT_SECRET=

# ── OAuth ─────────────────────────────────────────────────────────────────────
GITHUB_CLIENT_ID=${GITHUB_CLIENT_ID}
GITHUB_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
GITHUB_REDIRECT_URI=https://${DOMAIN}/api/v1/auth/github/callback
ATLASSIAN_CLIENT_ID=${ATLASSIAN_CLIENT_ID}
ATLASSIAN_CLIENT_SECRET=${ATLASSIAN_CLIENT_SECRET}
ATLASSIAN_REDIRECT_URI=https://${DOMAIN}/api/v1/auth/atlassian/callback
ATLASSIAN_SCOPES=read:me read:jira-work write:jira-work read:jira-user offline_access
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# ── Nextcloud ─────────────────────────────────────────────────────────────────
NEXTCLOUD_URL=https://nextcloud.${DOMAIN}
NEXTCLOUD_ADMIN_USER=admin
NEXTCLOUD_ADMIN_PASSWORD=$(gen_secret 20)
NEXTCLOUD_ADMIN_APP_PASSWORD=
NEXTCLOUD_DB_PASSWORD=${NEXTCLOUD_DB_PASSWORD}
NEXTCLOUD_DB_ROOT_PASSWORD=${NEXTCLOUD_DB_ROOT_PASSWORD}
NEXTCLOUD_OIDC_CLIENT_ID=
NEXTCLOUD_OIDC_CLIENT_SECRET=

# ── SMTP (Contact Form) ───────────────────────────────────────────────────────
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SMTP_FROM=noreply@${DOMAIN}
CONTACT_EMAIL_TO=${ADMIN_EMAIL}

# ── Traefik ───────────────────────────────────────────────────────────────────
ACME_EMAIL=${ACME_EMAIL}
TRAEFIK_BASIC_AUTH=${TRAEFIK_BASIC_AUTH}

# ── Tools ────────────────────────────────────────────────────────────────────
PGADMIN_EMAIL=${ADMIN_EMAIL}
PGADMIN_PASSWORD=$(gen_secret 16)
OPENWEBUI_SECRET_KEY=$(gen_secret 32)
EOF

ok ".env files written."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 5 — Docker networks and volumes"
# ─────────────────────────────────────────────────────────────────────────────
docker network create assist-proxy 2>/dev/null && ok "Created network: assist-proxy" \
  || ok "Network assist-proxy already exists."
docker volume create assist_traefik-certs 2>/dev/null && ok "Created volume: assist_traefik-certs" \
  || ok "Volume assist_traefik-certs already exists."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 6 — Start Traefik"
# ─────────────────────────────────────────────────────────────────────────────
info "Starting Traefik reverse proxy…"
docker compose -f /opt/traefik/docker-compose.yml --env-file /opt/traefik/.env up -d
ok "Traefik started."
sleep 3

# ─────────────────────────────────────────────────────────────────────────────
section "Step 7 — Authentik (IDP) + Datenbasis"
# ─────────────────────────────────────────────────────────────────────────────
info "Starting PostgreSQL, Redis, Authentik (Server + Worker)…"
docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" \
  --env-file "${HEYKARL_ROOT}/infra/.env" \
  up -d postgres redis authentik-db authentik-server authentik-worker

wait_healthy heykarl-postgres 120
wait_healthy heykarl-redis 60
wait_healthy heykarl-authentik-server 180
info "Waiting for Authentik worker bootstrap…"
sleep 15

merge_oidc_credentials_into_env

# ─────────────────────────────────────────────────────────────────────────────
section "Step 8 — Build Docker images (nach OIDC-Provision)"
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$SKIP_BUILD" == false ]]; then
  info "Clearing BuildKit cache to avoid stale layer errors…"
  docker builder prune -f --filter type=exec.cachemount 2>/dev/null || docker builder prune -f 2>/dev/null || true
  info "Building backend image…"
  docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" --env-file "${HEYKARL_ROOT}/infra/.env" build --no-cache backend 2>&1 | tail -5
  info "Building frontend image…"
  docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" --env-file "${HEYKARL_ROOT}/infra/.env" build --no-cache frontend 2>&1 | tail -5
  info "Building admin-frontend image…"
  docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" --env-file "${HEYKARL_ROOT}/infra/.env" build --no-cache admin-frontend 2>&1 | tail -5
  ok "All images built."
else
  info "Skipping build (--skip-build)."
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Step 9 — HeyKarl Anwendungs-Stack"
# ─────────────────────────────────────────────────────────────────────────────
info "Starting LiteLLM…"
docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" \
  --env-file "${HEYKARL_ROOT}/infra/.env" \
  up -d litellm-postgres litellm

info "Starting Backend, Worker, Frontends…"
docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" \
  --env-file "${HEYKARL_ROOT}/infra/.env" \
  up -d backend worker frontend admin-frontend

wait_healthy heykarl-backend 180

info "Starting remaining services (n8n, Nextcloud, Whisper, Stirling-PDF, …)…"
docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" \
  --env-file "${HEYKARL_ROOT}/infra/.env" \
  up -d

ok "All heykarl services started."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 10 — Database migrations and seed"
# ─────────────────────────────────────────────────────────────────────────────
info "Running Alembic migrations…"
docker exec heykarl-backend \
  sh -c "cd /app && alembic upgrade head"
ok "Migrations complete."

info "Seeding system roles and permissions…"
docker exec heykarl-backend \
  sh -c "cd /app && python -m app.scripts.seed" 2>/dev/null \
  || warn "Seed script not found or failed — run manually if needed."
ok "Seed complete."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 11 — Start Ghost CMS"
# ─────────────────────────────────────────────────────────────────────────────
info "Starting Ghost CMS…"
docker compose -f /opt/ghost/docker-compose.yml \
  --env-file /opt/ghost/.env \
  up -d
ok "Ghost started."

# ─────────────────────────────────────────────────────────────────────────────
section "Step 12 — Optional: Nextcloud post-install"
# ─────────────────────────────────────────────────────────────────────────────
echo ""
read -rp "$(echo -e "${BOLD}Run Nextcloud post-install wizard now? [y/N]:${NC} ")" run_nc </dev/tty
if [[ "${run_nc,,}" == "y" ]]; then
  wait_healthy heykarl-nextcloud 180
  info "Running Nextcloud init script…"
  source "${HEYKARL_ROOT}/infra/.env"
  bash "${HEYKARL_ROOT}/infra/nextcloud/init.sh"
  ok "Nextcloud configured."
else
  info "Skipped. Run later: source ${HEYKARL_ROOT}/infra/.env && bash ${HEYKARL_ROOT}/infra/nextcloud/init.sh"
fi

# ─────────────────────────────────────────────────────────────────────────────
section "Step 13 — Health check"
# ─────────────────────────────────────────────────────────────────────────────
info "Checking service health…"
docker compose -f "${HEYKARL_ROOT}/infra/docker-compose.yml" \
  --env-file "${HEYKARL_ROOT}/infra/.env" ps \
  --format "table {{.Name}}\t{{.Status}}"

# ─────────────────────────────────────────────────────────────────────────────
section "Installation complete!"
# ─────────────────────────────────────────────────────────────────────────────
cat << SUMMARY

${BOLD}━━━ Access URLs ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
  App:        https://${DOMAIN}
  Admin:      https://admin.${DOMAIN}
  Authentik:  https://authentik.${DOMAIN}
  Traefik:    https://traefik.${DOMAIN}

${BOLD}━━━ Credentials ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
  Authentik (akadmin / Bootstrap, https://authentik.${DOMAIN}):
    E-Mail:    ${ADMIN_EMAIL}
    Passwort:  ${AUTHENTIK_BOOTSTRAP_PASSWORD}
    Hinweis:   Passwort aus .env nur bei neuem Authentik-DB-Volume wirksam; bei Neuinstallation mit --new-install ggf. bekanntes Initialpasswort (Default admin123).

  Traefik dashboard:
    User:     admin
    Password: ${TRAEFIK_ADMIN_PASS}

  All secrets saved to:  ${HEYKARL_ROOT}/infra/.env
                         /opt/ghost/.env
                         /opt/traefik/.env

${BOLD}━━━ Authentik (IDP) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
  OAuth2-Anwendungen „backend“ (API/ROPC) und „heykarl-admin“ (Admin-UI) wurden angelegt.
  AUTHENTIK_API_TOKEN ist zunächst identisch mit AUTHENTIK_BOOTSTRAP_TOKEN (API-Zugriff).
  Optional: In Authentik einen dedizierten API-Token anlegen, in .env eintragen, Backend neu starten.

${BOLD}━━━ Manual steps still needed ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}
  1. Ghost admin setup:  https://${DOMAIN}/ghost  (first-run wizard)

  2. Nextcloud (optional): NEXTCLOUD_OIDC_* in .env setzen, dann init.sh ausführen

SUMMARY
