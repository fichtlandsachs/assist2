"""Billing & payment models: Subscription, Payment, UsageLog, PricingConfig."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


# ── Enums ─────────────────────────────────────────────────────────────────────

class BillingPlan(str, enum.Enum):
    free = "free"
    starter = "starter"
    pro = "pro"
    enterprise = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"
    unpaid = "unpaid"
    incomplete = "incomplete"


class PaymentProvider(str, enum.Enum):
    stripe = "stripe"
    paypal = "paypal"
    manual = "manual"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    succeeded = "succeeded"
    failed = "failed"
    refunded = "refunded"


# ── Models ────────────────────────────────────────────────────────────────────

class Subscription(UUIDMixin, TimestampMixin, Base):
    """One active subscription per organization. Tracks plan + billing cycle."""
    __tablename__ = "subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # one subscription per org
    )
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default=BillingPlan.starter)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=SubscriptionStatus.incomplete)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default=PaymentProvider.stripe)

    # Provider-specific IDs (never expose raw keys to frontend)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    paypal_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Billing period
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Limits (copied from pricing config at subscription time, so they don't change mid-cycle)
    included_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_members: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", foreign_keys=[organization_id])
    payments: Mapped[List["Payment"]] = relationship(
        "Payment", back_populates="subscription", cascade="all, delete-orphan"
    )

    @property
    def is_access_granted(self) -> bool:
        """Return True if this subscription grants full workspace access."""
        return self.status in (
            SubscriptionStatus.active,
            SubscriptionStatus.trialing,
        )


class Payment(UUIDMixin, TimestampMixin, Base):
    """Record of each individual payment or invoice item."""
    __tablename__ = "payments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # EUR cents
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default=PaymentStatus.pending)
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    invoice_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    invoice_pdf_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)

    subscription: Mapped[Optional["Subscription"]] = relationship("Subscription", back_populates="payments")


class UsageLog(UUIDMixin, TimestampMixin, Base):
    """Per-request AI usage record for pay-per-use billing."""
    __tablename__ = "usage_logs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="anthropic")
    feature: Mapped[str] = mapped_column(String(100), nullable=False, default="chat")  # chat|story|suggest|...
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False, default=0)
    request_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)


class PricingConfig(UUIDMixin, TimestampMixin, Base):
    """Configurable pricing per plan. Only one active entry per plan."""
    __tablename__ = "pricing_configs"

    plan: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_price_eur_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # monthly base, EUR cents
    included_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # tokens per cycle
    price_per_1k_tokens_eur_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # EUR cents per 1K tokens
    max_members: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    stripe_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # recurring price in Stripe
    paypal_plan_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    features: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # feature flags per plan
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
