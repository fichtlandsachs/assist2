"""
Per-organization integration settings stored in org.metadata_["integrations"].

Sensitive values (API tokens) are Fernet-encrypted before storage.
All get_* functions return masked placeholders instead of raw tokens.
"""
from __future__ import annotations

from typing import Any

from app.core.security import encrypt_value, decrypt_value
from app.models.organization import Organization
from app.config import get_settings


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_section(org: Organization, key: str) -> dict:
    meta: dict = org.metadata_ or {}
    return dict(meta.get("integrations", {}).get(key, {}))


def _set_section(org: Organization, key: str, data: dict) -> None:
    meta: dict = dict(org.metadata_ or {})
    integrations: dict = dict(meta.get("integrations", {}))
    integrations[key] = data
    meta["integrations"] = integrations
    org.metadata_ = meta


def _maybe_encrypt(existing_enc: str | None, new_val: str | None) -> str | None:
    """Return encrypted new value if provided, otherwise keep existing."""
    if new_val:
        return encrypt_value(new_val)
    return existing_enc


# ── Jira ─────────────────────────────────────────────────────────────────────

def get_jira_settings(org: Organization) -> dict:
    cfg = _get_section(org, "jira")
    return {
        "base_url": cfg.get("base_url", ""),
        "user": cfg.get("user", ""),
        "api_token_set": bool(cfg.get("api_token_enc")),
    }


def set_jira_settings(
    org: Organization,
    base_url: str,
    user: str,
    api_token: str | None = None,
) -> None:
    cfg = _get_section(org, "jira")
    cfg["base_url"] = base_url
    cfg["user"] = user
    cfg["api_token_enc"] = _maybe_encrypt(cfg.get("api_token_enc"), api_token)
    _set_section(org, "jira", cfg)


def get_jira_token(org: Organization) -> str | None:
    cfg = _get_section(org, "jira")
    enc = cfg.get("api_token_enc")
    return decrypt_value(enc) if enc else None


# ── Confluence ────────────────────────────────────────────────────────────────

def get_confluence_settings(org: Organization) -> dict:
    cfg = _get_section(org, "confluence")
    return {
        "base_url": cfg.get("base_url", ""),
        "user": cfg.get("user", ""),
        "api_token_set": bool(cfg.get("api_token_enc")),
    }


def set_confluence_settings(
    org: Organization,
    base_url: str,
    user: str,
    api_token: str | None = None,
) -> None:
    cfg = _get_section(org, "confluence")
    cfg["base_url"] = base_url
    cfg["user"] = user
    cfg["api_token_enc"] = _maybe_encrypt(cfg.get("api_token_enc"), api_token)
    _set_section(org, "confluence", cfg)


def get_confluence_credentials(org: Organization) -> tuple[str, str, str] | None:
    """Returns (base_url, user, api_token) or None if not configured."""
    cfg = _get_section(org, "confluence")
    base_url = cfg.get("base_url", "")
    user = cfg.get("user", "")
    enc = cfg.get("api_token_enc")
    if not (base_url and user and enc):
        return None
    return base_url, user, decrypt_value(enc)


# ── AI ────────────────────────────────────────────────────────────────────────

def get_ai_settings(org: Organization) -> dict:
    cfg = _get_section(org, "ai")
    return {
        "ai_provider": cfg.get("ai_provider", "anthropic"),
        "anthropic_api_key_set": bool(cfg.get("anthropic_api_key_enc")),
        "openai_api_key_set": bool(cfg.get("openai_api_key_enc")),
        "model_override": cfg.get("model_override", ""),
    }


def set_ai_settings(
    org: Organization,
    model_override: str = "",
    anthropic_api_key: str | None = None,
    ai_provider: str = "anthropic",
    openai_api_key: str | None = None,
) -> None:
    cfg = _get_section(org, "ai")
    cfg["model_override"] = model_override
    cfg["ai_provider"] = ai_provider
    cfg["anthropic_api_key_enc"] = _maybe_encrypt(cfg.get("anthropic_api_key_enc"), anthropic_api_key)
    cfg["openai_api_key_enc"] = _maybe_encrypt(cfg.get("openai_api_key_enc"), openai_api_key)
    _set_section(org, "ai", cfg)


def get_ai_client_settings(org: Organization) -> dict:
    """Return decrypted AI credentials for the service layer.

    Returns both keys so the service layer can pick the right one per task:
      {"anthropic_api_key", "openai_api_key", "model_override"}
    Falls back to global env vars if no org-level key is stored.
    """
    cfg = _get_section(org, "ai")
    settings = get_settings()
    model_override = cfg.get("model_override", "")

    enc_anthropic = cfg.get("anthropic_api_key_enc")
    anthropic_api_key = decrypt_value(enc_anthropic) if enc_anthropic else settings.ANTHROPIC_API_KEY

    enc_openai = cfg.get("openai_api_key_enc")
    openai_api_key = decrypt_value(enc_openai) if enc_openai else settings.OPENAI_API_KEY

    return {
        "anthropic_api_key": anthropic_api_key,
        "openai_api_key": openai_api_key,
        "model_override": model_override,
    }


def get_all_settings(org: Organization) -> dict[str, Any]:
    return {
        "jira": get_jira_settings(org),
        "confluence": get_confluence_settings(org),
        "ai": get_ai_settings(org),
    }
