"""
Per-organization integration settings stored in org.metadata_["integrations"].

Sensitive values (API tokens) are Fernet-encrypted before storage.
All get_* functions return masked placeholders instead of raw tokens.
"""
from __future__ import annotations

from typing import Any

from app.core.security import encrypt_value, decrypt_value
from app.models.organization import Organization


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
        "default_space_key": cfg.get("default_space_key", ""),
        "default_parent_page_id": cfg.get("default_parent_page_id", ""),
    }


def set_confluence_settings(
    org: Organization,
    base_url: str,
    user: str,
    api_token: str | None = None,
    default_space_key: str | None = None,
    default_parent_page_id: str | None = None,
) -> None:
    cfg = _get_section(org, "confluence")
    cfg["base_url"] = base_url
    cfg["user"] = user
    cfg["api_token_enc"] = _maybe_encrypt(cfg.get("api_token_enc"), api_token)
    if default_space_key is not None:
        cfg["default_space_key"] = default_space_key.strip()
    if default_parent_page_id is not None:
        cfg["default_parent_page_id"] = default_parent_page_id.strip()
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

DEFAULT_DOR_RULES: list[str] = [
    "Hat die Story einen klaren Titel?",
    'Ist die Beschreibung im Format "Als [Rolle] möchte ich [Funktion], damit [Nutzen]"?',
    "Sind die Akzeptanzkriterien konkret, testbar und vollständig?",
    "Ist die Story klein genug für einen Sprint?",
    "Sind Abhängigkeiten bekannt?",
]

DEFAULT_MIN_QUALITY_SCORE: int = 50


def get_ai_settings(org: Organization) -> dict:
    cfg = _get_section(org, "ai")
    return {
        "dor_rules": cfg.get("dor_rules", DEFAULT_DOR_RULES),
        "min_quality_score": cfg.get("min_quality_score", DEFAULT_MIN_QUALITY_SCORE),
    }


def set_ai_settings(
    org: Organization,
    dor_rules: list[str] | None = None,
    min_quality_score: int | None = None,
) -> None:
    cfg = _get_section(org, "ai")
    if dor_rules is not None:
        cfg["dor_rules"] = [r.strip() for r in dor_rules if r.strip()]
    if min_quality_score is not None:
        cfg["min_quality_score"] = max(0, min(100, min_quality_score))
    _set_section(org, "ai", cfg)


def get_ai_client_settings(org: Organization) -> dict:
    """Return AI ruleset for the service layer (all model calls go through LiteLLM)."""
    cfg = _get_section(org, "ai")
    return {
        "dor_rules": cfg.get("dor_rules", DEFAULT_DOR_RULES),
        "min_quality_score": cfg.get("min_quality_score", DEFAULT_MIN_QUALITY_SCORE),
    }


# ── GitHub (per-org) ──────────────────────────────────────────────────────────

def get_github_settings(org: Organization) -> dict:
    cfg = _get_section(org, "github")
    return {
        "enabled": cfg.get("enabled", False),
        "client_id": cfg.get("client_id", ""),
        "client_secret_set": bool(cfg.get("client_secret_enc")),
    }


def set_github_settings(
    org: Organization,
    enabled: bool,
    client_id: str,
    client_secret: str | None = None,
) -> None:
    cfg = _get_section(org, "github")
    cfg["enabled"] = enabled
    cfg["client_id"] = client_id
    cfg["client_secret_enc"] = _maybe_encrypt(cfg.get("client_secret_enc"), client_secret)
    _set_section(org, "github", cfg)


# ── Atlassian (per-org) ───────────────────────────────────────────────────────

def get_atlassian_settings(org: Organization) -> dict:
    cfg = _get_section(org, "atlassian")
    return {
        "enabled": cfg.get("enabled", False),
        "client_id": cfg.get("client_id", ""),
        "client_secret_set": bool(cfg.get("client_secret_enc")),
    }


def set_atlassian_settings(
    org: Organization,
    enabled: bool,
    client_id: str,
    client_secret: str | None = None,
) -> None:
    cfg = _get_section(org, "atlassian")
    cfg["enabled"] = enabled
    cfg["client_id"] = client_id
    cfg["client_secret_enc"] = _maybe_encrypt(cfg.get("client_secret_enc"), client_secret)
    _set_section(org, "atlassian", cfg)


def get_all_settings(org: Organization) -> dict[str, Any]:
    return {
        "jira": get_jira_settings(org),
        "confluence": get_confluence_settings(org),
        "github": get_github_settings(org),
        "atlassian": get_atlassian_settings(org),
        "ai": get_ai_settings(org),
    }
