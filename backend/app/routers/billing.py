"""
Billing & subscription API.

Endpoints:
  GET    /orgs/{org_id}/billing/status          — compact paywall status
  GET    /orgs/{org_id}/billing/subscription    — full subscription details
  POST   /orgs/{org_id}/billing/checkout        — create Stripe Checkout session
  POST   /orgs/{org_id}/billing/portal          — open Stripe Customer Portal
  POST   /orgs/{org_id}/billing/cancel          — cancel subscription
  GET    /orgs/{org_id}/billing/payments        — payment history
  GET    /orgs/{org_id}/billing/usage           — usage summary
  GET    /orgs/{org_id}/billing/invoice/preview — current invoice simulation
  GET    /billing/pricing                       — public pricing plans

  POST   /webhooks/stripe                       — Stripe webhook receiver
  POST   /webhooks/paypal                       — PayPal webhook receiver
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_permission
from app.models.billing import PaymentProvider, PaymentStatus, SubscriptionStatus
from app.models.user import User
from app.schemas.billing import (
    BillingPortalResponse,
    BillingStatus,
    CheckoutSessionResponse,
    InvoiceSimulation,
    PaymentListResponse,
    PricingConfigRead,
    SubscriptionCancelRequest,
    SubscriptionRead,
    UsageSummary,
)
from app.services.billing_service import billing_service
from app.services.stripe_service import stripe_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Public: Pricing plans ─────────────────────────────────────────────────────

@router.get("/billing/pricing", response_model=list[PricingConfigRead], tags=["Billing"])
async def list_pricing(db: AsyncSession = Depends(get_db)):
    """Return all active pricing plans (public — no auth required)."""
    configs = await billing_service.get_pricing_configs(db)
    return configs


# ── Billing status (compact, used by frontend paywall) ────────────────────────

@router.get("/orgs/{org_id}/billing/status", response_model=BillingStatus, tags=["Billing"])
async def get_billing_status(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Returns has_access + plan info — called by the frontend on every page load."""
    return await billing_service.get_billing_status(org_id, db)


# ── Subscription details ──────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/billing/subscription", response_model=Optional[SubscriptionRead], tags=["Billing"])
async def get_subscription(
    org_id: uuid.UUID,
    current_user: User = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_subscription(org_id, db)


# ── Stripe Checkout session ───────────────────────────────────────────────────

@router.post("/orgs/{org_id}/billing/checkout", response_model=CheckoutSessionResponse, tags=["Billing"])
async def create_checkout_session(
    org_id: uuid.UUID,
    plan: str = Query(..., description="Plan slug: starter|pro|enterprise"),
    current_user: User = Depends(require_permission("billing:manage")),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Stripe Checkout session. The frontend redirects to session.url.
    On success, Stripe calls our webhook which activates the subscription.
    """
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    pricing = await billing_service.get_pricing_config(plan, db)
    if not pricing or not pricing.stripe_price_id:
        raise HTTPException(400, f"Plan '{plan}' not available or not configured in Stripe")

    # Get or create Stripe customer
    sub = await billing_service.get_subscription(org_id, db)
    from sqlalchemy import select
    from app.models.organization import Organization
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()
    if not org:
        raise HTTPException(404, "Organization not found")

    # Resolve Stripe customer ID
    stripe_customer_id = sub.stripe_customer_id if sub else None
    if not stripe_customer_id:
        # Find org owner email
        from app.models.membership import Membership
        membership_result = await db.execute(
            select(Membership).where(Membership.organization_id == org_id)
            .order_by(Membership.joined_at)
            .limit(1)
        )
        membership = membership_result.scalar_one_or_none()
        owner_email = current_user.email
        customer = await stripe_service.create_customer(
            email=owner_email,
            name=org.name,
            org_id=str(org_id),
            org_slug=org.slug,
        )
        stripe_customer_id = customer["id"]

    base_url = settings.APP_BASE_URL
    session = await stripe_service.create_checkout_session(
        customer_id=stripe_customer_id,
        price_id=pricing.stripe_price_id,
        success_url=f"{base_url}/{org.slug}/settings?tab=billing&checkout=success",
        cancel_url=f"{base_url}/{org.slug}/settings?tab=billing&checkout=cancel",
        trial_period_days=14 if plan == "starter" else None,
        metadata={"org_id": str(org_id), "plan": plan},
    )

    return CheckoutSessionResponse(session_id=session["id"], url=session["url"])


# ── Stripe Customer Portal ────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/billing/portal", response_model=BillingPortalResponse, tags=["Billing"])
async def create_billing_portal(
    org_id: uuid.UUID,
    current_user: User = Depends(require_permission("billing:manage")),
    db: AsyncSession = Depends(get_db),
):
    """Redirect user to Stripe's self-service billing portal."""
    settings = get_settings()
    sub = await billing_service.get_subscription(org_id, db)
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(400, "Kein Stripe-Konto verknüpft")

    from app.models.organization import Organization
    from sqlalchemy import select
    org_result = await db.execute(select(Organization).where(Organization.id == org_id))
    org = org_result.scalar_one_or_none()

    portal = await stripe_service.create_billing_portal_session(
        customer_id=sub.stripe_customer_id,
        return_url=f"{settings.APP_BASE_URL}/{org.slug}/settings?tab=billing",
    )
    return BillingPortalResponse(url=portal["url"])


# ── Cancel subscription ────────────────────────────────────────────────────────

@router.post("/orgs/{org_id}/billing/cancel", response_model=SubscriptionRead, tags=["Billing"])
async def cancel_subscription(
    org_id: uuid.UUID,
    body: SubscriptionCancelRequest,
    current_user: User = Depends(require_permission("billing:manage")),
    db: AsyncSession = Depends(get_db),
):
    sub = await billing_service.get_subscription(org_id, db)
    if not sub:
        raise HTTPException(404, "Kein aktives Abonnement")

    # Cancel in Stripe
    if sub.stripe_subscription_id:
        try:
            await stripe_service.cancel_subscription(
                sub.stripe_subscription_id,
                at_period_end=body.cancel_at_period_end,
            )
        except Exception as e:
            logger.error("Stripe cancel failed: %s", e)
            raise HTTPException(502, "Fehler beim Stornieren bei Stripe")

    # Cancel in PayPal
    if sub.paypal_subscription_id:
        from app.services.paypal_service import paypal_service
        try:
            await paypal_service.cancel_subscription(sub.paypal_subscription_id)
        except Exception as e:
            logger.warning("PayPal cancel failed: %s", e)

    updated = await billing_service.cancel_subscription_db(org_id, body.cancel_at_period_end, db)
    return updated


# ── Payment history ────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/billing/payments", response_model=PaymentListResponse, tags=["Billing"])
async def list_payments(
    org_id: uuid.UUID,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_db),
):
    total, items = await billing_service.get_payments(org_id, db, limit=limit, offset=offset)
    return PaymentListResponse(total=total, items=items)


# ── Usage summary ─────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/billing/usage", response_model=UsageSummary, tags=["Billing"])
async def get_usage(
    org_id: uuid.UUID,
    current_user: User = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.get_usage_summary(org_id, db)


# ── Invoice preview ────────────────────────────────────────────────────────────

@router.get("/orgs/{org_id}/billing/invoice/preview", response_model=Optional[InvoiceSimulation], tags=["Billing"])
async def invoice_preview(
    org_id: uuid.UUID,
    current_user: User = Depends(require_permission("billing:read")),
    db: AsyncSession = Depends(get_db),
):
    return await billing_service.simulate_invoice(org_id, db)


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOK HANDLERS
# These endpoints must NOT require auth — Stripe/PayPal call them directly.
# Signature verification replaces auth.
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/webhooks/stripe", tags=["Billing Webhooks"], include_in_schema=False)
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Stripe webhook endpoint.
    Handles: checkout.session.completed, invoice.paid, invoice.payment_failed,
             customer.subscription.updated, customer.subscription.deleted
    """
    body = await request.body()

    try:
        event = stripe_service.construct_event(body, stripe_signature or "")
    except ValueError as e:
        logger.warning("Stripe webhook signature invalid: %s", e)
        raise HTTPException(400, "Invalid signature")

    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    logger.info("Stripe webhook: %s", event_type)

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)

    elif event_type in ("invoice.paid", "invoice.payment_succeeded"):
        await _handle_invoice_paid(data, db)

    elif event_type in ("invoice.payment_failed", "invoice.payment_action_required"):
        await _handle_invoice_failed(data, db)

    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)

    return {"received": True}


async def _handle_checkout_completed(data: dict, db: AsyncSession) -> None:
    """checkout.session.completed — subscription created via Checkout."""
    meta = data.get("metadata", {})
    org_id_str = meta.get("org_id")
    plan = meta.get("plan", "starter")
    if not org_id_str:
        logger.warning("checkout.session.completed: missing org_id in metadata")
        return

    org_id = uuid.UUID(org_id_str)
    stripe_sub_id = data.get("subscription")
    stripe_customer_id = data.get("customer")

    # Fetch subscription details from Stripe for period info
    period_start = period_end = trial_end = None
    if stripe_sub_id:
        try:
            stripe_sub = await _fetch_stripe_subscription(stripe_sub_id)
            period_start = _ts(stripe_sub.get("current_period_start"))
            period_end = _ts(stripe_sub.get("current_period_end"))
            trial_end = _ts(stripe_sub.get("trial_end"))
            plan = _plan_from_stripe_sub(stripe_sub) or plan
        except Exception as e:
            logger.error("Could not fetch Stripe subscription %s: %s", stripe_sub_id, e)

    await billing_service.create_subscription_manual(
        org_id=org_id,
        plan=plan,
        provider=PaymentProvider.stripe,
        status=SubscriptionStatus.active,
        stripe_subscription_id=stripe_sub_id,
        stripe_customer_id=stripe_customer_id,
        paypal_subscription_id=None,
        period_start=period_start,
        period_end=period_end,
        trial_end=trial_end,
        db=db,
    )


async def _handle_invoice_paid(data: dict, db: AsyncSession) -> None:
    """invoice.paid — record payment + ensure subscription is active."""
    stripe_customer_id = data.get("customer")
    stripe_sub_id = data.get("subscription")
    amount = data.get("amount_paid", 0)
    currency = (data.get("currency") or "eur").upper()
    invoice_url = data.get("hosted_invoice_url")
    invoice_pdf = data.get("invoice_pdf")
    provider_payment_id = data.get("id", "")
    paid_at_ts = data.get("status_transitions", {}).get("paid_at")

    # Find org by stripe_customer_id
    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        logger.warning("invoice.paid: no subscription for customer %s", stripe_customer_id)
        return

    # Update subscription period from Stripe
    if stripe_sub_id:
        try:
            stripe_sub = await _fetch_stripe_subscription(stripe_sub_id)
            sub.current_period_start = _ts(stripe_sub.get("current_period_start"))
            sub.current_period_end = _ts(stripe_sub.get("current_period_end"))
            sub.status = SubscriptionStatus.active
            await db.commit()
        except Exception as e:
            logger.error("Failed to update subscription period: %s", e)

    await billing_service.record_payment(
        org_id=sub.organization_id,
        subscription_id=sub.id,
        provider=PaymentProvider.stripe,
        provider_payment_id=provider_payment_id,
        amount_cents=amount,
        currency=currency,
        status=PaymentStatus.succeeded,
        description=f"Abonnement-Zahlung {sub.plan.capitalize()}",
        invoice_url=invoice_url,
        invoice_pdf_url=invoice_pdf,
        paid_at=_ts(paid_at_ts),
        db=db,
    )
    await billing_service._invalidate_subscription_cache(sub.organization_id)


async def _handle_invoice_failed(data: dict, db: AsyncSession) -> None:
    """invoice.payment_failed — mark subscription as past_due."""
    stripe_customer_id = data.get("customer")
    provider_payment_id = data.get("id", "")

    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == stripe_customer_id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        return

    sub.status = SubscriptionStatus.past_due
    await db.commit()
    await billing_service._invalidate_subscription_cache(sub.organization_id)

    await billing_service.record_payment(
        org_id=sub.organization_id,
        subscription_id=sub.id,
        provider=PaymentProvider.stripe,
        provider_payment_id=provider_payment_id,
        amount_cents=data.get("amount_due", 0),
        currency=(data.get("currency") or "eur").upper(),
        status=PaymentStatus.failed,
        description="Zahlung fehlgeschlagen",
        invoice_url=data.get("hosted_invoice_url"),
        invoice_pdf_url=None,
        paid_at=None,
        db=db,
    )


async def _handle_subscription_updated(data: dict, db: AsyncSession) -> None:
    """customer.subscription.updated — sync status + period."""
    stripe_sub_id = data.get("id")
    stripe_customer_id = data.get("customer")

    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        return

    status_map = {
        "active": SubscriptionStatus.active,
        "trialing": SubscriptionStatus.trialing,
        "past_due": SubscriptionStatus.past_due,
        "canceled": SubscriptionStatus.canceled,
        "unpaid": SubscriptionStatus.unpaid,
        "incomplete": SubscriptionStatus.incomplete,
    }
    stripe_status = data.get("status", "")
    sub.status = status_map.get(stripe_status, sub.status)
    sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
    sub.current_period_start = _ts(data.get("current_period_start"))
    sub.current_period_end = _ts(data.get("current_period_end"))
    if data.get("trial_end"):
        sub.trial_end = _ts(data["trial_end"])

    plan = _plan_from_stripe_sub(data)
    if plan:
        sub.plan = plan
        # Sync org.plan
        from app.models.organization import Organization
        org_result = await db.execute(select(Organization).where(Organization.id == sub.organization_id))
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = plan

    await db.commit()
    await billing_service._invalidate_subscription_cache(sub.organization_id)


async def _handle_subscription_deleted(data: dict, db: AsyncSession) -> None:
    """customer.subscription.deleted — mark as canceled."""
    stripe_sub_id = data.get("id")

    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        return

    sub.status = SubscriptionStatus.canceled
    sub.canceled_at = datetime.now(timezone.utc)
    await db.commit()
    await billing_service._invalidate_subscription_cache(sub.organization_id)
    logger.info("Subscription %s canceled for org %s", stripe_sub_id, sub.organization_id)


# ── PayPal Webhook ─────────────────────────────────────────────────────────────

@router.post("/webhooks/paypal", tags=["Billing Webhooks"], include_in_schema=False)
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    PayPal webhook endpoint.
    Handles: BILLING.SUBSCRIPTION.ACTIVATED, BILLING.SUBSCRIPTION.CANCELLED,
             PAYMENT.SALE.COMPLETED
    """
    body = await request.body()
    headers = dict(request.headers)

    from app.services.paypal_service import paypal_service
    try:
        valid = await paypal_service.verify_webhook_signature(headers, body)
        if not valid:
            raise HTTPException(400, "Invalid PayPal webhook signature")
    except Exception as e:
        logger.warning("PayPal webhook verification failed: %s", e)
        raise HTTPException(400, "Webhook verification failed")

    import json
    event = json.loads(body)
    event_type = event.get("event_type", "")
    resource = event.get("resource", {})

    logger.info("PayPal webhook: %s", event_type)

    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        await _handle_paypal_subscription_activated(resource, db)
    elif event_type == "BILLING.SUBSCRIPTION.CANCELLED":
        await _handle_paypal_subscription_cancelled(resource, db)
    elif event_type == "PAYMENT.SALE.COMPLETED":
        await _handle_paypal_payment_completed(resource, db)

    return {"received": True}


async def _handle_paypal_subscription_activated(resource: dict, db: AsyncSession) -> None:
    custom_id = resource.get("custom_id", "")
    paypal_sub_id = resource.get("id")
    plan_id = resource.get("plan_id", "")

    org_id_str = custom_id
    if not org_id_str:
        return

    # Determine plan from plan_id via pricing config
    from sqlalchemy import select
    from app.models.billing import PricingConfig
    cfg_result = await db.execute(select(PricingConfig).where(PricingConfig.paypal_plan_id == plan_id))
    cfg = cfg_result.scalar_one_or_none()
    plan = cfg.plan if cfg else "starter"

    await billing_service.create_subscription_manual(
        org_id=uuid.UUID(org_id_str),
        plan=plan,
        provider=PaymentProvider.paypal,
        status=SubscriptionStatus.active,
        stripe_subscription_id=None,
        stripe_customer_id=None,
        paypal_subscription_id=paypal_sub_id,
        period_start=None,
        period_end=None,
        trial_end=None,
        db=db,
    )


async def _handle_paypal_subscription_cancelled(resource: dict, db: AsyncSession) -> None:
    paypal_sub_id = resource.get("id")
    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.paypal_subscription_id == paypal_sub_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.canceled
        sub.canceled_at = datetime.now(timezone.utc)
        await db.commit()
        await billing_service._invalidate_subscription_cache(sub.organization_id)


async def _handle_paypal_payment_completed(resource: dict, db: AsyncSession) -> None:
    billing_agreement_id = resource.get("billing_agreement_id")
    from sqlalchemy import select
    from app.models.billing import Subscription
    sub_result = await db.execute(
        select(Subscription).where(Subscription.paypal_subscription_id == billing_agreement_id)
    )
    sub = sub_result.scalar_one_or_none()
    if not sub:
        return

    amount_str = resource.get("amount", {}).get("total", "0")
    currency = resource.get("amount", {}).get("currency", "EUR")
    amount_cents = int(float(amount_str) * 100)

    await billing_service.record_payment(
        org_id=sub.organization_id,
        subscription_id=sub.id,
        provider=PaymentProvider.paypal,
        provider_payment_id=resource.get("id", ""),
        amount_cents=amount_cents,
        currency=currency,
        status=PaymentStatus.succeeded,
        description=f"PayPal-Zahlung {sub.plan.capitalize()}",
        invoice_url=None,
        invoice_pdf_url=None,
        paid_at=datetime.now(timezone.utc),
        db=db,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ts(epoch: int | None) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), tz=timezone.utc)


def _plan_from_stripe_sub(stripe_sub: dict) -> str | None:
    """Extract plan slug from Stripe subscription object via metadata or price ID lookup."""
    meta = stripe_sub.get("metadata", {})
    if meta.get("plan"):
        return meta["plan"]
    # Fallback: look at items
    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        # Will be resolved via PricingConfig.stripe_price_id by the caller if needed
        return None
    return None


@router.post("/billing/litellm-usage", tags=["Billing Webhooks"], include_in_schema=False)
async def litellm_usage_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    LiteLLM spend_logs_url webhook — receives token usage after each AI call.
    Provides accurate per-request token counts and cost for billing.
    """
    import json
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        return {"ok": True}

    # LiteLLM posts a list of spend log entries
    entries = data if isinstance(data, list) else [data]
    for entry in entries:
        metadata = entry.get("metadata", {}) or {}
        org_id_str = metadata.get("org_id") or entry.get("org_id")
        user_id_str = metadata.get("user_id") or entry.get("user_id")
        if not org_id_str:
            continue
        try:
            await billing_service.record_usage(
                org_id=uuid.UUID(org_id_str),
                user_id=uuid.UUID(user_id_str) if user_id_str else None,
                model=entry.get("model", "unknown"),
                provider=entry.get("provider", "litellm"),
                feature=metadata.get("feature", "chat"),
                input_tokens=int(entry.get("prompt_tokens", 0)),
                output_tokens=int(entry.get("completion_tokens", 0)),
                cost_usd=float(entry.get("spend", 0)),
                request_id=entry.get("request_id"),
                db=db,
            )
        except Exception as e:
            logger.warning("LiteLLM usage webhook: failed to record entry: %s", e)

    return {"ok": True}


async def _fetch_stripe_subscription(stripe_sub_id: str) -> dict:
    import httpx
    settings = get_settings()
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        resp = await client.get(
            f"https://api.stripe.com/v1/subscriptions/{stripe_sub_id}",
            headers={"Authorization": f"Bearer {settings.STRIPE_SECRET_KEY}"},
        )
    resp.raise_for_status()
    return resp.json()
