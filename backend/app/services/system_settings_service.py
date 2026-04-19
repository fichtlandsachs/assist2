"""Runtime settings overlay — merges DB GlobalConfig values on top of env-based Settings.

Usage (anywhere in the app):
    from app.services.system_settings_service import get_runtime_settings
    s = await get_runtime_settings(db)
    # s.SMTP_PASS, s.SMTP_HOST, etc. — DB value wins, env is fallback

The result is a plain dataclass (not the pydantic Settings) so it stays lightweight.
Cache TTL: 60 seconds per DB session — avoids a DB round-trip on every request.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import decrypt_value
from app.models.global_config import GlobalConfig, SECRET_KEYS

logger = logging.getLogger(__name__)

# ── In-process TTL cache ──────────────────────────────────────────────────────
_CACHE_TTL = 60  # seconds
_cache: dict[str, Any] = {}
_cache_ts: float = 0.0
_cache_lock = asyncio.Lock()


# ── Key → Settings attribute mapping ─────────────────────────────────────────
# Maps every GlobalConfig key to the Settings field it overrides.
_KEY_MAP: dict[str, str] = {
    "litellm.url":                   "LITELLM_URL",
    "litellm.api_key":               "LITELLM_API_KEY",
    "nextcloud.url":                 "NEXTCLOUD_URL",
    "nextcloud.admin_user":          "NEXTCLOUD_ADMIN_USER",
    "nextcloud.admin_password":      "NEXTCLOUD_ADMIN_APP_PASSWORD",
    "n8n.url":                       "N8N_WEBHOOK_URL",
    "n8n.api_key":                   "N8N_API_KEY",
    "atlassian.client_id":           "ATLASSIAN_CLIENT_ID",
    "atlassian.client_secret":       "ATLASSIAN_CLIENT_SECRET",
    "github.client_id":              "GITHUB_CLIENT_ID",
    "github.client_secret":          "GITHUB_CLIENT_SECRET",
    "ai.ionos_api_key":              "IONOS_API_KEY",
    "ai.ionos_api_base":             "IONOS_API_BASE",
    "ai.provider_routing_suggest":   "PROVIDER_ROUTING_SUGGEST",
    "ai.provider_routing_docs":      "PROVIDER_ROUTING_DOCS",
    "ai.provider_routing_fallback":  "PROVIDER_ROUTING_FALLBACK",
    "ai.feature_flags":              "AI_FEATURE_FLAGS",
    "smtp.host":                     "SMTP_HOST",
    "smtp.port":                     "SMTP_PORT",
    "smtp.user":                     "SMTP_USER",
    "smtp.pass":                     "SMTP_PASS",
    "smtp.from":                     "SMTP_FROM",
    "smtp.contact_to":               "CONTACT_EMAIL_TO",
    "chat.policy_mode":              "CHAT_POLICY_MODE",
    "chat.min_evidence_count":       "CHAT_MIN_EVIDENCE_COUNT",
    "chat.min_relevance_score":      "CHAT_MIN_RELEVANCE_SCORE",
    "chat.fallback_message":         "CHAT_FALLBACK_MESSAGE",
    "chat.web_signal":               "CHAT_WEB_SIGNAL",
    "chat.web_requires_signal":      "CHAT_WEB_REQUIRES_SIGNAL",
    "web_search.enabled":            "WEB_SEARCH_ENABLED",
    "web_search.provider":           "WEB_SEARCH_PROVIDER",
    "web_search.api_key":            "WEB_SEARCH_API_KEY",
    "web_search.google_cx":          "WEB_SEARCH_GOOGLE_CX",
    "web_search.monthly_budget_usd": "WEB_SEARCH_MONTHLY_BUDGET_USD",
}


@dataclass
class RuntimeSettings:
    """Flat bag of effective settings values (env defaults + DB overrides)."""
    # Bootstrap (never overridden from DB)
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
    JWT_SECRET: str
    ENCRYPTION_KEY: str
    ENVIRONMENT: str
    CORS_ORIGINS: list[str]
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int

    # Overrideable via DB
    LITELLM_URL: str = "http://heykarl-litellm:4000"
    LITELLM_API_KEY: str = ""
    NEXTCLOUD_URL: str = ""
    NEXTCLOUD_ADMIN_USER: str = ""
    NEXTCLOUD_ADMIN_APP_PASSWORD: str = ""
    N8N_WEBHOOK_URL: str = "http://n8n:5678"
    N8N_API_KEY: str = ""
    ATLASSIAN_CLIENT_ID: str = ""
    ATLASSIAN_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    IONOS_API_KEY: str = ""
    IONOS_API_BASE: str = "https://openai.ionos.com/openai"
    PROVIDER_ROUTING_SUGGEST: str = "auto"
    PROVIDER_ROUTING_DOCS: str = "claude-sonnet-4-6"
    PROVIDER_ROUTING_FALLBACK: str = "ionos-fast"
    AI_FEATURE_FLAGS: str = "streaming,embeddings"
    SMTP_HOST: str = "smtp.hostinger.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "noreply@heykarl.app"
    CONTACT_EMAIL_TO: str = "info@heykarl.app"
    CHAT_POLICY_MODE: str = "strict_grounded"
    CHAT_MIN_EVIDENCE_COUNT: int = 1
    CHAT_MIN_RELEVANCE_SCORE: float = 0.50
    CHAT_FALLBACK_MESSAGE: str = "Ich konnte in den Tickets und Confluence Artikeln nichts finden."
    CHAT_WEB_SIGNAL: str = "/WEB"
    CHAT_WEB_REQUIRES_SIGNAL: bool = True
    WEB_SEARCH_ENABLED: bool = False
    WEB_SEARCH_PROVIDER: str = "brave"
    WEB_SEARCH_API_KEY: str = ""
    WEB_SEARCH_GOOGLE_CX: str = ""
    WEB_SEARCH_MONTHLY_BUDGET_USD: float = 10.0

    def ai_feature_enabled(self, flag: str) -> bool:
        flags = {f.strip() for f in self.AI_FEATURE_FLAGS.split(",") if f.strip()}
        return flag in flags


def _coerce(attr: str, raw: str) -> Any:
    """Coerce a raw DB string to the expected Python type based on the field name."""
    int_fields = {"SMTP_PORT", "CHAT_MIN_EVIDENCE_COUNT", "ACCESS_TOKEN_EXPIRE_MINUTES", "REFRESH_TOKEN_EXPIRE_DAYS"}
    float_fields = {"CHAT_MIN_RELEVANCE_SCORE", "WEB_SEARCH_MONTHLY_BUDGET_USD"}
    bool_fields = {"CHAT_WEB_REQUIRES_SIGNAL", "WEB_SEARCH_ENABLED"}
    if attr in int_fields:
        return int(raw)
    if attr in float_fields:
        return float(raw)
    if attr in bool_fields:
        return raw.lower() in ("1", "true", "yes")
    return raw


async def get_runtime_settings(db: AsyncSession) -> RuntimeSettings:
    """Return effective settings: env base + DB overrides. Cached for 60 s."""
    global _cache, _cache_ts

    now = time.monotonic()
    async with _cache_lock:
        if _cache and (now - _cache_ts) < _CACHE_TTL:
            return RuntimeSettings(**_cache)

        env = get_settings()

        # Seed from env
        overrides: dict[str, Any] = {
            "DATABASE_URL": env.DATABASE_URL,
            "REDIS_URL": env.REDIS_URL,
            "SECRET_KEY": env.SECRET_KEY,
            "JWT_SECRET": env.JWT_SECRET,
            "ENCRYPTION_KEY": env.ENCRYPTION_KEY,
            "ENVIRONMENT": env.ENVIRONMENT,
            "CORS_ORIGINS": env.CORS_ORIGINS,
            "ACCESS_TOKEN_EXPIRE_MINUTES": env.ACCESS_TOKEN_EXPIRE_MINUTES,
            "REFRESH_TOKEN_EXPIRE_DAYS": env.REFRESH_TOKEN_EXPIRE_DAYS,
            # Overrideable defaults from env
            "LITELLM_URL": env.LITELLM_URL,
            "LITELLM_API_KEY": env.LITELLM_API_KEY,
            "NEXTCLOUD_URL": env.NEXTCLOUD_URL,
            "NEXTCLOUD_ADMIN_USER": env.NEXTCLOUD_ADMIN_USER,
            "NEXTCLOUD_ADMIN_APP_PASSWORD": env.NEXTCLOUD_ADMIN_APP_PASSWORD,
            "N8N_WEBHOOK_URL": env.N8N_WEBHOOK_URL,
            "N8N_API_KEY": env.N8N_API_KEY,
            "ATLASSIAN_CLIENT_ID": env.ATLASSIAN_CLIENT_ID,
            "ATLASSIAN_CLIENT_SECRET": env.ATLASSIAN_CLIENT_SECRET,
            "GITHUB_CLIENT_ID": env.GITHUB_CLIENT_ID,
            "GITHUB_CLIENT_SECRET": env.GITHUB_CLIENT_SECRET,
            "IONOS_API_KEY": env.IONOS_API_KEY,
            "IONOS_API_BASE": env.IONOS_API_BASE,
            "PROVIDER_ROUTING_SUGGEST": env.PROVIDER_ROUTING_SUGGEST,
            "PROVIDER_ROUTING_DOCS": env.PROVIDER_ROUTING_DOCS,
            "PROVIDER_ROUTING_FALLBACK": env.PROVIDER_ROUTING_FALLBACK,
            "AI_FEATURE_FLAGS": env.AI_FEATURE_FLAGS,
            "SMTP_HOST": env.SMTP_HOST,
            "SMTP_PORT": env.SMTP_PORT,
            "SMTP_USER": env.SMTP_USER,
            "SMTP_PASS": env.SMTP_PASS,
            "SMTP_FROM": env.SMTP_FROM,
            "CONTACT_EMAIL_TO": env.CONTACT_EMAIL_TO,
            "CHAT_POLICY_MODE": env.CHAT_POLICY_MODE,
            "CHAT_MIN_EVIDENCE_COUNT": env.CHAT_MIN_EVIDENCE_COUNT,
            "CHAT_MIN_RELEVANCE_SCORE": env.CHAT_MIN_RELEVANCE_SCORE,
            "CHAT_FALLBACK_MESSAGE": env.CHAT_FALLBACK_MESSAGE,
            "CHAT_WEB_SIGNAL": env.CHAT_WEB_SIGNAL,
            "CHAT_WEB_REQUIRES_SIGNAL": env.CHAT_WEB_REQUIRES_SIGNAL,
            "WEB_SEARCH_ENABLED": False,
            "WEB_SEARCH_PROVIDER": "brave",
            "WEB_SEARCH_API_KEY": "",
            "WEB_SEARCH_GOOGLE_CX": "",
            "WEB_SEARCH_MONTHLY_BUDGET_USD": 10.0,
        }

        # Apply DB overrides
        try:
            result = await db.execute(select(GlobalConfig))
            rows = result.scalars().all()
            for row in rows:
                attr = _KEY_MAP.get(row.key)
                if not attr or row.value is None:
                    continue
                try:
                    raw = decrypt_value(row.value) if row.is_secret else row.value
                    overrides[attr] = _coerce(attr, raw)
                except Exception as exc:
                    logger.warning("system_settings: failed to apply %s: %s", row.key, exc)
        except Exception as exc:
            logger.warning("system_settings: DB read failed, using env only: %s", exc)

        _cache = overrides
        _cache_ts = now
        return RuntimeSettings(**overrides)


def invalidate_settings_cache() -> None:
    """Call after any PATCH /superadmin/config to flush the in-process cache."""
    global _cache, _cache_ts
    _cache = {}
    _cache_ts = 0.0
