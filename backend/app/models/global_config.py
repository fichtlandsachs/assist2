"""Global (system-level) admin configuration key-value store."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


ALLOWED_KEYS: frozenset[str] = frozenset({
    # LiteLLM
    "litellm.url",
    "litellm.api_key",
    # Nextcloud
    "nextcloud.url",
    "nextcloud.admin_user",
    "nextcloud.admin_password",
    # n8n
    "n8n.url",
    "n8n.api_key",
    # OAuth SSO
    "atlassian.sso_enabled",
    "atlassian.client_id",
    "atlassian.client_secret",
    "github.sso_enabled",
    "github.client_id",
    "github.client_secret",
    # AI providers
    "ai.anthropic_api_key",
    "ai.openai_api_key",
    "ai.ionos_api_key",
    "ai.ionos_api_base",
    "ai.provider_routing_suggest",
    "ai.provider_routing_docs",
    "ai.provider_routing_fallback",
    "ai.feature_flags",
    # SMTP / Contact
    "smtp.host",
    "smtp.port",
    "smtp.user",
    "smtp.pass",
    "smtp.from",
    "smtp.contact_to",
    # Chat / Grounded policy
    "chat.policy_mode",
    "chat.min_evidence_count",
    "chat.min_relevance_score",
    "chat.fallback_message",
    "chat.web_signal",
    "chat.web_requires_signal",
})

SECRET_KEYS: frozenset[str] = frozenset({
    "litellm.api_key",
    "nextcloud.admin_password",
    "n8n.api_key",
    "atlassian.client_secret",
    "github.client_secret",
    "ai.anthropic_api_key",
    "ai.openai_api_key",
    "ai.ionos_api_key",
    "smtp.pass",
})


class GlobalConfig(Base):
    __tablename__ = "global_config"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
