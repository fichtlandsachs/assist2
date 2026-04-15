from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str

    # Security
    SECRET_KEY: str
    JWT_SECRET: str
    ENCRYPTION_KEY: str

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Application
    ENVIRONMENT: str = "production"
    CORS_ORIGINS: list[str] = []

    # n8n Integration
    N8N_WEBHOOK_URL: str = "http://n8n:5678"
    N8N_API_KEY: str = ""

    # LangGraph Service
    LANGGRAPH_BASE_URL: str = "http://heykarl-langgraph:8100"
    LANGGRAPH_API_KEY: str = "dev-langgraph-secret"
    LANGGRAPH_TIMEOUT: int = 90

    # AI (all model calls go through LiteLLM — no direct API keys needed here)

    # ── IONOS AI ──────────────────────────────────────────────────────────────
    # OpenAI-compatible base URL. Swap for a different region without code change.
    IONOS_API_BASE: str = "https://openai.ionos.com/openai"
    IONOS_API_KEY: str = ""
    # How long (seconds) to cache the /v1/models response. 0 = no cache.
    IONOS_MODEL_CACHE_TTL: int = 300

    # ── Provider Routing Policy ───────────────────────────────────────────────
    # Maps task category to the LiteLLM model alias that should handle it.
    # Allowed values: ionos-fast | ionos-quality | ionos-reasoning |
    #                 claude-sonnet-4-6 | claude-haiku-4-5 | auto
    PROVIDER_ROUTING_SUGGEST: str = "auto"
    PROVIDER_ROUTING_DOCS: str = "claude-sonnet-4-6"
    PROVIDER_ROUTING_FALLBACK: str = "ionos-fast"

    # ── Feature Flags ─────────────────────────────────────────────────────────
    # Comma-separated list of enabled optional features.
    # Known flags: embeddings, images, rag_ionos, streaming
    AI_FEATURE_FLAGS: str = "streaming,embeddings"

    # Confluence
    CONFLUENCE_BASE_URL: str = ""   # e.g. https://your-org.atlassian.net/wiki
    CONFLUENCE_USER: str = ""       # Atlassian account email
    CONFLUENCE_API_TOKEN: str = ""  # Atlassian API token

    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""
    GITHUB_REDIRECT_URI: str = "https://heykarl.app/api/v1/auth/github/callback"
    GITHUB_SCOPES: str = "read:user user:email"

    # Authentik IdP
    AUTHENTIK_URL: str = "http://heykarl-authentik-server:9000"
    AUTHENTIK_API_TOKEN: str = ""
    AUTHENTIK_BACKEND_CLIENT_ID: str = ""
    AUTHENTIK_BACKEND_CLIENT_SECRET: str = ""
    AUTHENTIK_JWKS_URL: str = ""
    AUTHENTIK_APP_SLUG: str = "backend"  # Slug of the OAuth2 Application created in Authentik UI
    AUTHENTIK_ADMIN_CLIENT_ID: str = ""
    AUTHENTIK_ADMIN_CLIENT_SECRET: str = ""

    # Atlassian OAuth 2.0
    ATLASSIAN_CLIENT_ID: str = ""
    ATLASSIAN_CLIENT_SECRET: str = ""
    ATLASSIAN_REDIRECT_URI: str = ""
    ATLASSIAN_SCOPES: str = "read:me read:jira-work write:jira-work read:jira-user offline_access"

    # Stirling PDF
    STIRLING_PDF_URL: str = "http://heykarl-stirling-pdf:8080"
    STIRLING_PDF_USERNAME: str = "admin"
    STIRLING_PDF_PASSWORD: str = "stirling"
    PDF_TEMPLATES_PATH: str = "/app/pdf_templates"
    PDF_CACHE_PATH: str = "/app/pdf_cache"

    # OAuth redirect base (used for calendar/inbox OAuth callbacks)
    APP_BASE_URL: str = "https://heykarl.app"

    # Nextcloud
    NEXTCLOUD_URL: str = "https://nextcloud.heykarl.app"  # Public URL (for frontend links)
    NEXTCLOUD_INTERNAL_URL: str = "http://heykarl-nextcloud"  # Internal URL (for backend WebDAV/OCS)
    NEXTCLOUD_ADMIN_USER: str = "admin"
    NEXTCLOUD_ADMIN_APP_PASSWORD: str = ""  # Nextcloud App Password für WebDAV + OCS

    # Whisper ASR
    WHISPER_URL: str = "http://heykarl-whisper:9000"

    # LiteLLM (internal AI gateway)
    LITELLM_URL: str = "http://heykarl-litellm:4000"
    LITELLM_API_KEY: str = ""

    # ── Grounded Chat Policy ──────────────────────────────────────────────────
    # Hard rule: web search only when [Web] signal present in user message
    CHAT_WEB_SIGNAL: str = "[Web]"
    CHAT_WEB_REQUIRES_SIGNAL: bool = True
    # Minimum number of usable evidence items required before generating an answer
    CHAT_MIN_EVIDENCE_COUNT: int = 1
    # Minimum cosine similarity score for a chunk to be considered usable evidence
    CHAT_MIN_RELEVANCE_SCORE: float = 0.50
    # Policy mode for /ai/chat/grounded: strict_grounded | grounded_with_explicit_uncertainty
    #   | draft_mode | block_on_insufficient_evidence
    CHAT_POLICY_MODE: str = "strict_grounded"
    # Fallback message when no internal evidence is found (must not be changed lightly)
    CHAT_FALLBACK_MESSAGE: str = "Ich konnte in den Tickets und Confluence Artikeln nichts finden."

    # ── Stripe ─────────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""             # sk_live_... or sk_test_...
    STRIPE_PUBLISHABLE_KEY: str = ""        # pk_live_... or pk_test_...
    STRIPE_WEBHOOK_SECRET: str = ""         # whsec_...

    # ── PayPal ─────────────────────────────────────────────────────────────────
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_LIVE_MODE: bool = False          # False = sandbox

    # ── Billing defaults ───────────────────────────────────────────────────────
    # Set BILLING_ENABLED=false to disable the paywall (dev/self-hosted)
    BILLING_ENABLED: bool = True
    # Free trial duration in days (0 = no trial)
    BILLING_TRIAL_DAYS: int = 14

    # Contact form / outbound SMTP
    SMTP_HOST: str = "smtp.hostinger.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""   # leave empty for direct MX delivery
    SMTP_PASS: str = ""
    SMTP_FROM: str = "noreply@heykarl.app"
    CONTACT_EMAIL_TO: str = "info@heykarl.app"

    # Sync defaults (used as initial value when creating connections)
    MAIL_SYNC_INTERVAL_MINUTES: int = 15
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 30

    def ai_feature_enabled(self, flag: str) -> bool:
        """Check whether an optional AI feature flag is active."""
        flags = {f.strip() for f in self.AI_FEATURE_FLAGS.split(",") if f.strip()}
        return flag in flags

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
