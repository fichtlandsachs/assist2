"""
Idempotent OIDC setup for a fresh Authentik (HeyKarl standalone install).
Run inside Authentik server container, e.g.:

  docker cp infra/scripts/authentik_provision_oidc.py heykarl-authentik-server:/tmp/
  docker exec -e DOMAIN=example.com heykarl-authentik-server ak shell -c "exec(open('/tmp/authentik_provision_oidc.py').read())"

Set DOMAIN to the primary hostname (same as install.sh DOMAIN).

Prints a single JSON line with client credentials for backend + admin applications.
"""
from __future__ import annotations

import json
import os
import secrets

from authentik.core.models import Application
from authentik.flows.models import Flow
from authentik.providers.oauth2.models import OAuth2Provider


def _flow(slug: str) -> Flow:
    return Flow.objects.get(slug=slug)


def ensure_oauth_app(
    *,
    app_slug: str,
    app_name: str,
    provider_name: str,
    client_id: str,
    redirect_uris: str,
) -> tuple[str, str]:
    """Return (client_id, client_secret). Creates or reuses provider + application."""
    existing = Application.objects.filter(slug=app_slug).first()
    if existing and isinstance(existing.provider, OAuth2Provider):
        prov = existing.provider
        # Plain client_secret is not readable after first save; keep .env values on re-provision
        return prov.client_id, "__PRESERVE__"

    authz = _flow("default-provider-authorization-implicit-consent")
    authn = _flow("ropc-authentication-flow")
    invalid = _flow("default-provider-invalidation-flow")
    client_secret = secrets.token_urlsafe(48)

    prov = OAuth2Provider(
        name=provider_name,
        authorization_flow=authz,
        authentication_flow=authn,
        invalidation_flow=invalid,
        client_type="confidential",
        client_id=client_id,
        client_secret=client_secret,
        redirect_uris=redirect_uris,
    )
    prov.save()
    app = Application(name=app_name, slug=app_slug, provider=prov)
    app.save()
    return client_id, client_secret


def main() -> None:
    domain = os.environ.get("DOMAIN", "").strip()
    if not domain:
        raise SystemExit("DOMAIN environment variable is required for admin redirect URI")

    admin_redirect = f"https://admin.{domain}/callback"

    # Must match backend AUTHENTIK_JWKS_URL path …/application/o/backend/jwks/
    backend_client_id = "heykarl-backend"
    admin_client_id = "heykarl-admin"

    b_id, b_secret = ensure_oauth_app(
        app_slug="backend",
        app_name="HeyKarl Backend API",
        provider_name="HeyKarl Backend API",
        client_id=backend_client_id,
        redirect_uris="",
    )
    # Admin UI: authorization code + PKCE (see admin-frontend/lib/auth.ts)
    a_id, a_secret = ensure_oauth_app(
        app_slug="heykarl-admin",
        app_name="HeyKarl Admin",
        provider_name="HeyKarl Admin",
        client_id=admin_client_id,
        redirect_uris=admin_redirect,
    )

    out = {
        "AUTHENTIK_BACKEND_CLIENT_ID": b_id,
        "AUTHENTIK_BACKEND_CLIENT_SECRET": b_secret,
        "AUTHENTIK_ADMIN_CLIENT_ID": a_id,
        "AUTHENTIK_ADMIN_CLIENT_SECRET": a_secret,
    }
    print(json.dumps(out, separators=(",", ":")))


main()
