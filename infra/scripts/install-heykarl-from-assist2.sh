#!/usr/bin/env bash
# =============================================================================
# HeyKarl-Instanz aus assist2 (Neuinstallation / Migration)
#
# Zweck:
#   - Beliebige Zielpfade (z. B. /opt/heykarl-<unternehmen>) für eine neue Instanz
#   - Standard: Konfiguration 1:1 aus assist2 (inkl. infra/.env, Traefik, Compose)
#   - assist2 kann danach gestoppt werden; Löschen nur mit expliziter Freigabe
#
# Umgebungsvariablen (optional):
#   ASSIST2_ROOT      Quelle (Default: /opt/assist2)
#   HEYKARL_ROOT      Zielbaum (Default: /opt/heykarl)
#   HEYKARL_INSTANCE  Freie Bezeichnung für Meta/Logs (z. B. Firmenname)
#
# Nutzung:
#   sudo HEYKARL_INSTANCE="Muster GmbH" bash /opt/assist2/infra/scripts/install-heykarl-from-assist2.sh
#   sudo HEYKARL_ROOT=/opt/heykarl-kunde1 ASSIST2_ROOT=/opt/assist2 bash .../install-heykarl-from-assist2.sh
#
# Optionen:
#   --dry-run              Nur anzeigen (benötigt rsync)
#   --delete               Ziel an Quelle spiegeln (rsync --delete; tar: eingeschränkt)
#   --no-infra-env         infra/.env NICHT kopieren (grüne Instanz ohne Secrets)
#   --with-node-modules    node_modules mitkopieren
#   --with-next            .next mitkopieren
#   --no-git               .git weglassen
#   --stop-source-stack       Nach erfolgreicher Kopie: docker compose down in assist2/infra
#   --delete-source-dir       Nach Kopie: assist2 Quellbaum löschen (nur mit I_UNDERSTAND_DELETE_ASSIST2=1)
#   --delete-assist2-only     Nur Quellbaum löschen, keine Kopie (nach Migration; Ziel muss existieren)
#   -h, --help                Hilfe
#
# Hinweis Mehrfach-Instanz auf einem Host:
#   docker-compose.yml nutzt feste container_name (heykarl-*). Zwei laufende Stacks
#   kollidieren. Ablauf: Quelle stoppen (--stop-source-stack), dann Ziel starten.
# =============================================================================
set -euo pipefail

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${BLUE}[install-heykarl]${NC} $*"; }
ok()   { echo -e "${GREEN}[install-heykarl]${NC} $*"; }
warn() { echo -e "${YELLOW}[install-heykarl]${NC} $*"; }
die()  { echo -e "${RED}[install-heykarl]${NC} $*" >&2; exit 1; }

ASSIST2_ROOT="${ASSIST2_ROOT:-/opt/assist2}"
HEYKARL_ROOT="${HEYKARL_ROOT:-/opt/heykarl}"
HEYKARL_INSTANCE="${HEYKARL_INSTANCE:-}"

DRY_RUN=0
DELETE=0
WITH_NODE=0
WITH_NEXT=0
WITH_GIT=1
INCLUDE_INFRA_ENV=1
STOP_SOURCE_STACK=0
DELETE_SOURCE_DIR=0
ASSIST2_DELETE_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --dry-run)              DRY_RUN=1 ;;
    --delete)               DELETE=1 ;;
    --with-node-modules)    WITH_NODE=1 ;;
    --with-next)            WITH_NEXT=1 ;;
    --no-git)               WITH_GIT=0 ;;
    --with-git)             WITH_GIT=1 ;;
    --no-infra-env)         INCLUDE_INFRA_ENV=0 ;;
    --stop-source-stack)    STOP_SOURCE_STACK=1 ;;
    --delete-source-dir)    DELETE_SOURCE_DIR=1 ;;
    --delete-assist2-only)  ASSIST2_DELETE_ONLY=1 ;;
    --instance=*)           HEYKARL_INSTANCE="${arg#*=}" ;;
    -h|--help)
      sed -n '2,34p' "$0"
      exit 0
      ;;
    *)
      die "Unbekannte Option: $arg (siehe --help)"
      ;;
  esac
done

[[ "$(id -u)" -eq 0 ]] || die "Bitte als root ausführen (sudo)."

[[ -d "$ASSIST2_ROOT" ]] || die "Quellverzeichnis fehlt: $ASSIST2_ROOT"
[[ -f "$ASSIST2_ROOT/infra/docker-compose.yml" ]] || die "Ungültige Quelle (docker-compose.yml fehlt): $ASSIST2_ROOT/infra/"
[[ "$HEYKARL_ROOT" != "$ASSIST2_ROOT" ]] || die "HEYKARL_ROOT und ASSIST2_ROOT dürfen nicht identisch sein."

if [[ "$DELETE_SOURCE_DIR" -eq 1 || "$ASSIST2_DELETE_ONLY" -eq 1 ]]; then
  [[ "${I_UNDERSTAND_DELETE_ASSIST2:-}" == "1" ]] || die "Löschen der Quelle verweigert. Zum Bestätigen: I_UNDERSTAND_DELETE_ASSIST2=1 …"
fi

if [[ "$ASSIST2_DELETE_ONLY" -eq 1 ]]; then
  [[ -f "$HEYKARL_ROOT/infra/docker-compose.yml" ]] || die "--delete-assist2-only: Ziel-Instanz fehlt oder unvollständig (erwartet $HEYKARL_ROOT/infra/docker-compose.yml)."
  [[ -d "$ASSIST2_ROOT" ]] || die "Quelle existiert nicht (schon gelöscht?): $ASSIST2_ROOT"
  warn "Entferne nur Quellbaum: $ASSIST2_ROOT"
  rm -rf "$ASSIST2_ROOT"
  ok "assist2-Verzeichnis gelöscht."
  exit 0
fi

EXCLUDES=(
  --exclude '.worktrees/'
  --exclude '__pycache__/'
  --exclude '*.py[cod]'
  --exclude '.pytest_cache/'
  --exclude '.venv/'
  --exclude 'venv/'
  --exclude '.mypy_cache/'
  --exclude '.coverage'
  --exclude 'htmlcov/'
  --exclude 'frontend/out/'
  --exclude 'admin-frontend/.turbo/'
)

[[ "$WITH_NODE" -eq 0 ]] && EXCLUDES+=(--exclude 'node_modules' --exclude '**/node_modules')
[[ "$WITH_NEXT" -eq 0 ]] && EXCLUDES+=(--exclude '.next' --exclude 'frontend/.next' --exclude 'admin-frontend/.next')
[[ "$WITH_GIT" -eq 0 ]] && EXCLUDES+=(--exclude '.git')
[[ "$INCLUDE_INFRA_ENV" -eq 0 ]] && EXCLUDES+=(--exclude './infra/.env' --exclude 'infra/.env')

info "Instanz:    ${HEYKARL_INSTANCE:-"(nicht gesetzt)"}"
info "Quelle:     $ASSIST2_ROOT"
info "Ziel:       $HEYKARL_ROOT"
info "infra/.env: $([[ "$INCLUDE_INFRA_ENV" -eq 1 ]] && echo "einbeziehen (1:1)" || echo "weglassen (--no-infra-env)")"
[[ "$DELETE" -eq 1 ]] && warn "Modus: --delete"
[[ "$DRY_RUN" -eq 1 ]] && warn "Modus: --dry-run"

mkdir -p "$HEYKARL_ROOT"

sync_tree() {
  if command -v rsync >/dev/null 2>&1; then
    local RSYNC=(rsync -aH --numeric-ids)
    [[ "$DRY_RUN" -eq 1 ]] && RSYNC+=(--dry-run --itemize-changes)
    [[ "$DELETE" -eq 1 ]] && RSYNC+=(--delete)
    info "rsync …"
    "${RSYNC[@]}" "${EXCLUDES[@]}" "$ASSIST2_ROOT/" "$HEYKARL_ROOT/"
    return
  fi
  [[ "$DRY_RUN" -eq 1 ]] && die "Ohne rsync ist --dry-run nicht unterstützt."
  [[ "$DELETE" -eq 1 ]] && warn "Ohne rsync wird --delete ignoriert (kein vollständiger Spiegel)."
  info "rsync nicht gefunden — nutze tar-Pipeline …"
  ( cd "$ASSIST2_ROOT" && tar -c "${EXCLUDES[@]}" -f - . ) | ( cd "$HEYKARL_ROOT" && tar -xf - )
}

sync_tree

# Sichere Rechte für produktive Secrets
if [[ -f "$HEYKARL_ROOT/infra/.env" ]]; then
  chmod 0600 "$HEYKARL_ROOT/infra/.env" || true
  ok "infra/.env vorhanden (Rechte 0600)."
elif [[ "$INCLUDE_INFRA_ENV" -eq 1 ]]; then
  warn "Kein infra/.env im Ziel — in der Quelle fehlt die Datei oder sie wurde ausgeschlossen."
fi

META="$HEYKARL_ROOT/.install-from-assist2.meta"
{
  echo "HEYKARL_ROOT=$HEYKARL_ROOT"
  echo "SOURCE_ASSIST2_ROOT=$ASSIST2_ROOT"
  echo "HEYKARL_INSTANCE=${HEYKARL_INSTANCE:-}"
  echo "INSTALLED_AT=$(date -Iseconds)"
  echo "INCLUDE_INFRA_ENV=$INCLUDE_INFRA_ENV"
  echo "RSYNC_DELETE=$DELETE"
  echo "STOP_SOURCE_STACK_REQUESTED=$STOP_SOURCE_STACK"
} > "$META"
chmod 0644 "$META" || true
ok "Meta geschrieben: $META"

compose_down() {
  local root="$1"
  [[ -f "$root/infra/docker-compose.yml" ]] || return 0
  if command -v docker >/dev/null 2>&1; then
    info "docker compose down in $root/infra …"
    docker compose --project-directory "$root/infra" -f "$root/infra/docker-compose.yml" down --remove-orphans || warn "compose down meldete einen Fehler (Container schon weg?)"
  else
    warn "docker nicht im PATH — überspringe compose down."
  fi
}

if [[ "$STOP_SOURCE_STACK" -eq 1 ]]; then
  compose_down "$ASSIST2_ROOT"
  ok "Quell-Stack assist2 gestoppt (down)."
fi

if [[ "$DELETE_SOURCE_DIR" -eq 1 ]]; then
  warn "Lösche Quellbaum: $ASSIST2_ROOT"
  rm -rf "$ASSIST2_ROOT"
  ok "Quellbaum entfernt."
fi

ok "Kopie fertig."
echo ""
echo "Nächste Schritte (Zielinstanz):"
echo "  cd $HEYKARL_ROOT/infra && docker compose build backend worker beat frontend admin-frontend langgraph-service  # bei Bedarf eingrenzen"
echo "  cd $HEYKARL_ROOT/infra && docker compose up -d"
echo ""
echo "Falls node_modules/.next fehlen:"
echo "  cd $HEYKARL_ROOT/infra && npm ci --prefix ../frontend && npm ci --prefix ../admin-frontend && npm run build --prefix ../frontend && npm run build --prefix ../admin-frontend"
echo ""
if [[ "$STOP_SOURCE_STACK" -eq 0 ]]; then
  echo "assist2 noch aktiv? Vor dem Start von heykarl auf demselben Host:"
  echo "  cd $ASSIST2_ROOT/infra && docker compose down"
  echo "  oder erneut mit Option: --stop-source-stack (Quelle muss noch existieren)"
fi
if [[ "$DELETE_SOURCE_DIR" -eq 0 ]]; then
  echo ""
  echo "assist2-Verzeichnis später löschen (nur nach erfolgreicher Migration, irreversibel):"
  echo "  sudo I_UNDERSTAND_DELETE_ASSIST2=1 HEYKARL_ROOT=$HEYKARL_ROOT ASSIST2_ROOT=$ASSIST2_ROOT \\"
  echo "    bash $HEYKARL_ROOT/infra/scripts/install-heykarl-from-assist2.sh --delete-assist2-only"
fi
