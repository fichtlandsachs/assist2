"""Pydantic schemas for billing API."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.billing import BillingPlan, PaymentProvider, PaymentStatus, SubscriptionStatus


# ── Pricing ────────────────────────────────────────────────────────────────────

class PricingConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plan: str
    display_name: str
    base_price_eur_cents: int
    included_tokens: int
    price_per_1k_tokens_eur_cents: int
    max_members: Optional[int]
    features: Optional[Dict[str, Any]]
    sort_order: int

    @property
    def base_price_eur(self) -> float:
        return self.base_price_eur_cents / 100

    @property
    def price_per_1k_tokens_eur(self) -> float:
        return self.price_per_1k_tokens_eur_cents / 100


# ── Subscription ──────────────────────────────────────────────────────────────

class SubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    plan: str
    status: str
    provider: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    trial_end: Optional[datetime]
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]
    included_tokens: int
    max_members: Optional[int]
    is_access_granted: bool
    created_at: datetime
    updated_at: datetime


class SubscriptionCreateRequest(BaseModel):
    plan: BillingPlan
    provider: PaymentProvider = PaymentProvider.stripe
    # Stripe: optionally provide payment_method_id (from Stripe.js)
    payment_method_id: Optional[str] = None
    # For trial starts without payment method
    start_trial: bool = False


class SubscriptionCancelRequest(BaseModel):
    cancel_at_period_end: bool = True  # False = immediate


# ── Payment ────────────────────────────────────────────────────────────────────

class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    subscription_id: Optional[uuid.UUID]
    provider: str
    amount_cents: int
    currency: str
    status: str
    description: Optional[str]
    invoice_url: Optional[str]
    invoice_pdf_url: Optional[str]
    paid_at: Optional[datetime]
    created_at: datetime

    @property
    def amount_eur(self) -> float:
        return self.amount_cents / 100


class PaymentListResponse(BaseModel):
    total: int
    items: List[PaymentRead]


# ── Usage ─────────────────────────────────────────────────────────────────────

class UsageSummary(BaseModel):
    """Aggregated usage for the current billing period."""
    organization_id: uuid.UUID
    period_start: Optional[datetime]
    period_end: Optional[datetime]
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    included_tokens: int
    overage_tokens: int
    total_cost_usd: float
    overage_cost_eur: float  # calculated from pricing config
    request_count: int
    by_model: List[Dict[str, Any]]
    by_feature: List[Dict[str, Any]]


class UsageLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: Optional[uuid.UUID]
    model: str
    provider: str
    feature: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    created_at: datetime


# ── Stripe webhooks ───────────────────────────────────────────────────────────

class StripeWebhookEvent(BaseModel):
    """Raw Stripe webhook event (we verify signature, then parse this)."""
    id: str
    type: str
    data: Dict[str, Any]


# ── Checkout / Portal ─────────────────────────────────────────────────────────

class CheckoutSessionResponse(BaseModel):
    """Returned after creating a Stripe Checkout session."""
    session_id: str
    url: str


class BillingPortalResponse(BaseModel):
    """Stripe Customer Portal redirect URL."""
    url: str


# ── Invoice simulation ────────────────────────────────────────────────────────

class InvoiceLineItem(BaseModel):
    description: str
    quantity: int
    unit_price_eur: float
    total_eur: float


class InvoiceSimulation(BaseModel):
    organization_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    plan: str
    line_items: List[InvoiceLineItem]
    subtotal_eur: float
    tax_eur: float
    total_eur: float
    currency: str = "EUR"


# ── Billing status (used by frontend guard) ───────────────────────────────────

class BillingStatus(BaseModel):
    """Compact billing status for the frontend paywall check."""
    has_access: bool
    plan: str
    status: Optional[str]
    trial_end: Optional[datetime]
    cancel_at_period_end: bool
    current_period_end: Optional[datetime]
