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

    # AI
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    AI_MODEL_OVERRIDE: str = ""   # if set, bypasses routing (e.g. "claude-sonnet-4-6")

    # Confluence
    CONFLUENCE_BASE_URL: str = ""   # e.g. https://your-org.atlassian.net/wiki
    CONFLUENCE_USER: str = ""       # Atlassian account email
    CONFLUENCE_API_TOKEN: str = ""  # Atlassian API token

    # OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GITHUB_CLIENT_ID: str = ""
    GITHUB_CLIENT_SECRET: str = ""

    # Authentik IdP
    AUTHENTIK_URL: str = "http://assist2-authentik-server:9000"
    AUTHENTIK_API_TOKEN: str = ""
    AUTHENTIK_BACKEND_CLIENT_ID: str = ""
    AUTHENTIK_BACKEND_CLIENT_SECRET: str = ""
    AUTHENTIK_JWKS_URL: str = ""
    AUTHENTIK_APP_SLUG: str = "backend"  # Slug of the OAuth2 Application created in Authentik UI

    # Stirling PDF
    STIRLING_PDF_URL: str = "http://assist2-stirling-pdf:8080"
    PDF_TEMPLATES_PATH: str = "/app/pdf_templates"
    PDF_CACHE_PATH: str = "/app/pdf_cache"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
