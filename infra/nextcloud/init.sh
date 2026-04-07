#!/bin/bash
# Nextcloud one-time initialization script.
# Run AFTER first container start when Nextcloud is fully installed:
#
#   source infra/.env
#   bash infra/nextcloud/init.sh
#
# Requires: NEXTCLOUD_OIDC_CLIENT_ID and NEXTCLOUD_OIDC_CLIENT_SECRET set in environment.

set -euo pipefail

NC_EXEC="docker exec --user www-data assist2-nextcloud php /var/www/html/occ"

echo "=== Warte bis Nextcloud bereit ist ==="
until docker exec assist2-nextcloud curl -sf http://localhost/status.php | grep -q '"installed":true'; do
  echo "Nextcloud nicht bereit, warte 5s..."
  sleep 5
done
echo "Nextcloud ist bereit."

echo "=== Social Login App installieren ==="
$NC_EXEC app:install sociallogin 2>/dev/null || $NC_EXEC app:enable sociallogin

echo "=== Group Folders App installieren ==="
$NC_EXEC app:install groupfolders 2>/dev/null || $NC_EXEC app:enable groupfolders

echo "=== Social Login: OIDC Provider zu Authentik konfigurieren ==="
$NC_EXEC config:app:set sociallogin custom_providers --value='{
  "custom_oidc": [{
    "name": "authentik",
    "title": "Login with Workplace",
    "authorizeUrl": "https://authentik.heykarl.app/application/o/nextcloud/authorize/",
    "tokenUrl": "https://authentik.heykarl.app/application/o/nextcloud/token/",
    "userInfoUrl": "https://authentik.heykarl.app/application/o/nextcloud/userinfo/",
    "clientId": "'"${NEXTCLOUD_OIDC_CLIENT_ID}"'",
    "clientSecret": "'"${NEXTCLOUD_OIDC_CLIENT_SECRET}"'",
    "scope": "openid email profile",
    "uidClaim": "preferred_username",
    "displayNameClaim": "name",
    "emailClaim": "email",
    "autoCreate": true,
    "defaultGroup": "nextcloud-users"
  }]
}'

echo "=== Trusted Proxies konfigurieren (Traefik) ==="
$NC_EXEC config:system:set trusted_proxies 0 --value="172.0.0.0/8"
$NC_EXEC config:system:set overwriteprotocol --value="https"

echo "=== Fertig! Nächste Schritte: ==="
echo "1. App Password für admin-User erstellen:"
echo "   Nextcloud UI → oben rechts Profilbild → Settings → Security → App passwords"
echo "2. NEXTCLOUD_ADMIN_APP_PASSWORD in infra/.env eintragen"
echo "3. Backend-Container neu starten: make up-dev"
