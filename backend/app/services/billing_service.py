"""Core billing engine: subscription management, usage tracking, invoicing."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.billing import (
    BillingPlan,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PricingConfig,
    Subscription,
    SubscriptionStatus,
    UsageLog,
)
from app.models.organization import Organization
from app.schemas.billing import (
    BillingStatus,
    InvoiceLineItem,
    InvoiceSimulation,
    UsageSummary,
)

logger = logging.getLogger(__name__)

# Redis key TTLs
_SUBSCRIPTION_CACHE_TTL = 60  # seconds — hot path, short TTL
_PRICING_CACHE_TTL = 3600     # 1 hour — rarely changes


class BillingService:

    # ── Redis helpers ──────────────────────────────────────────────────────────

    async def _redis(self) -> aioredis.Redis:
        return aioredis.from_url(get_settings().REDIS_URL, decode_responses=True)

    async def _invalidate_subscription_cache(self, org_id: uuid.UUID) -> None:
        r = await self._redis()
        await r.delete(f"billing:sub:{org_id}")

    # ── Pricing config ─────────────────────────────────────────────────────────

    async def get_pricing_configs(self, db: AsyncSession) -> List[PricingConfig]:
        result = await db.execute(
            select(PricingConfig)
            .where(PricingConfig.is_active == True)
            .order_by(PricingConfig.sort_order)
        )
        return list(result.scalars().all())

    async def get_pricing_config(self, plan: str, db: AsyncSession) -> Optional[PricingConfig]:
        result = await db.execute(
            select(PricingConfig).where(PricingConfig.plan == plan, PricingConfig.is_active == True)
        )
        return result.scalar_one_or_none()

    async def seed_default_pricing(self, db: AsyncSession) -> None:
        """Create default pricing tiers if none exist."""
        existing = await db.execute(select(func.count(PricingConfig.id)))
        count = existing.scalar_one()
        if count > 0:
            return

        configs = [
            PricingConfig(
                plan=BillingPlan.free,
                display_name="Free",
                base_price_eur_cents=0,
                included_tokens=0,
                price_per_1k_tokens_eur_cents=0,
                max_members=3,
                features={"ai_chat": False, "story_create": False, "feature_create": False},
                sort_order=0,
            ),
            PricingConfig(
                plan=BillingPlan.starter,
                display_name="Starter",
                base_price_eur_cents=2900,   # €29/mo
                included_tokens=100_000,
                price_per_1k_tokens_eur_cents=2,  # €0.02 per 1K tokens
                max_members=10,
                features={"ai_chat": True, "story_create": True, "feature_create": True},
                sort_order=1,
            ),
            PricingConfig(
                plan=BillingPlan.pro,
                display_name="Pro",
                base_price_eur_cents=9900,   # €99/mo
                included_tokens=500_000,
                price_per_1k_tokens_eur_cents=1,  # €0.01 per 1K tokens
                max_members=None,  # unlimited
                features={"ai_chat": True, "story_create": True, "feature_create": True, "advanced_analytics": True},
                sort_order=2,
            ),
            PricingConfig(
                plan=BillingPlan.enterprise,
                display_name="Enterprise",
                base_price_eur_cents=0,  # custom
                included_tokens=0,
                price_per_1k_tokens_eur_cents=0,
                max_members=None,
                features={"ai_chat": True, "story_create": True, "feature_create": True, "advanced_analytics": True, "sso": True},
                sort_order=3,
            ),
        ]
        db.add_all(configs)
        await db.commit()
        logger.info("Default pricing configs seeded")

    # ── Subscription queries ───────────────────────────────────────────────────

    async def get_subscription(self, org_id: uuid.UUID, db: AsyncSession) -> Optional[Subscription]:
        result = await db.execute(
            select(Subscription).where(Subscription.organization_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_billing_status(self, org_id: uuid.UUID, db: AsyncSession) -> BillingStatus:
        """Returns compact billing status — used by frontend guard and middleware."""
        sub = await self.get_subscription(org_id, db)
        if not sub:
            return BillingStatus(
                has_access=False,
                plan=BillingPlan.free,
                status=None,
                trial_end=None,
                cancel_at_period_end=False,
                current_period_end=None,
            )
        return BillingStatus(
            has_access=sub.is_access_granted,
            plan=sub.plan,
            status=sub.status,
            trial_end=sub.trial_end,
            cancel_at_period_end=sub.cancel_at_period_end,
            current_period_end=sub.current_period_end,
        )

    async def check_access_cached(self, org_id: uuid.UUID, db: AsyncSession) -> bool:
        """
        Hot-path access check. Reads from Redis cache (60s TTL) before DB.
        Returns True if org has an active/trialing subscription.
        """
        r = await self._redis()
        cache_key = f"billing:sub:{org_id}"
        cached = await r.get(cache_key)
        if cached is not None:
            return cached == "1"

        sub = await self.get_subscription(org_id, db)
        has_access = sub is not None and sub.is_access_granted
        await r.setex(cache_key, _SUBSCRIPTION_CACHE_TTL, "1" if has_access else "0")
        return has_access

    # ── Subscription creation ──────────────────────────────────────────────────

    async def create_subscription_manual(
        self,
        org_id: uuid.UUID,
        plan: str,
        provider: str,
        status: str,
        stripe_subscription_id: Optional[str],
        stripe_customer_id: Optional[str],
        paypal_subscription_id: Optional[str],
        period_start: Optional[datetime],
        period_end: Optional[datetime],
        trial_end: Optional[datetime],
        db: AsyncSession,
    ) -> Subscription:
        """Create or update the subscription for an org (called from webhook handlers)."""
        pricing = await self.get_pricing_config(plan, db)

        existing = await self.get_subscription(org_id, db)
        if existing:
            sub = existing
        else:
            sub = Subscription(organization_id=org_id)
            db.add(sub)

        sub.plan = plan
        sub.status = status
        sub.provider = provider
        if stripe_subscription_id:
            sub.stripe_subscription_id = stripe_subscription_id
        if stripe_customer_id:
            sub.stripe_customer_id = stripe_customer_id
        if paypal_subscription_id:
            sub.paypal_subscription_id = paypal_subscription_id
        if period_start:
            sub.current_period_start = period_start
        if period_end:
            sub.current_period_end = period_end
        if trial_end:
            sub.trial_end = trial_end
        sub.included_tokens = pricing.included_tokens if pricing else 0
        sub.max_members = pricing.max_members if pricing else None

        # Sync org.plan field
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        if org:
            org.plan = plan

        await db.commit()
        await self._invalidate_subscription_cache(org_id)
        logger.info("Subscription created/updated for org %s: plan=%s status=%s", org_id, plan, status)
        return sub

    async def activate_subscription(
        self,
        org_id: uuid.UUID,
        db: AsyncSession,
    ) -> None:
        """Set subscription status to active (after successful payment webhook)."""
        sub = await self.get_subscription(org_id, db)
        if sub:
            sub.status = SubscriptionStatus.active
            await db.commit()
            await self._invalidate_subscription_cache(org_id)

    async def cancel_subscription_db(
        self,
        org_id: uuid.UUID,
        at_period_end: bool,
        db: AsyncSession,
    ) -> Optional[Subscription]:
        sub = await self.get_subscription(org_id, db)
        if not sub:
            return None
        if at_period_end:
            sub.cancel_at_period_end = True
        else:
            sub.status = SubscriptionStatus.canceled
            sub.canceled_at = datetime.now(timezone.utc)
        await db.commit()
        await self._invalidate_subscription_cache(org_id)
        return sub

    # ── Usage tracking ─────────────────────────────────────────────────────────

    async def record_usage(
        self,
        org_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        model: str,
        provider: str,
        feature: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        request_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record a single AI usage event.
        Can be called without db (creates its own session via Celery task).
        """
        if db is None:
            # Dispatch to Celery so the endpoint doesn't block
            from app.tasks.billing_tasks import record_usage_task
            record_usage_task.delay(
                str(org_id), str(user_id) if user_id else None,
                model, provider, feature,
                input_tokens, output_tokens, cost_usd,
                request_id, extra,
            )
            return

        log = UsageLog(
            organization_id=org_id,
            user_id=user_id,
            model=model,
            provider=provider,
            feature=feature,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            cost_usd=Decimal(str(cost_usd)),
            request_id=request_id,
            metadata_=extra,
        )
        db.add(log)
        await db.commit()

    # ── Usage aggregation ──────────────────────────────────────────────────────

    async def get_usage_summary(
        self,
        org_id: uuid.UUID,
        db: AsyncSession,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> UsageSummary:
        sub = await self.get_subscription(org_id, db)
        pricing = await self.get_pricing_config(sub.plan if sub else BillingPlan.free, db)

        # Default period = current subscription period
        ps = period_start or (sub.current_period_start if sub else None)
        pe = period_end or (sub.current_period_end if sub else None)

        query = select(UsageLog).where(UsageLog.organization_id == org_id)
        if ps:
            query = query.where(UsageLog.created_at >= ps)
        if pe:
            query = query.where(UsageLog.created_at <= pe)

        result = await db.execute(query)
        logs = result.scalars().all()

        total_input = sum(l.input_tokens for l in logs)
        total_output = sum(l.output_tokens for l in logs)
        total_tokens = sum(l.total_tokens for l in logs)
        total_cost_usd = float(sum(l.cost_usd for l in logs))

        included = sub.included_tokens if sub else 0
        overage = max(0, total_tokens - included)
        rate = (pricing.price_per_1k_tokens_eur_cents / 100.0 / 1000.0) if pricing else 0.0
        overage_cost_eur = overage * rate

        # Group by model
        model_map: Dict[str, Dict] = {}
        for l in logs:
            if l.model not in model_map:
                model_map[l.model] = {"model": l.model, "total_tokens": 0, "cost_usd": 0.0, "requests": 0}
            model_map[l.model]["total_tokens"] += l.total_tokens
            model_map[l.model]["cost_usd"] += float(l.cost_usd)
            model_map[l.model]["requests"] += 1

        # Group by feature
        feature_map: Dict[str, Dict] = {}
        for l in logs:
            if l.feature not in feature_map:
                feature_map[l.feature] = {"feature": l.feature, "total_tokens": 0, "requests": 0}
            feature_map[l.feature]["total_tokens"] += l.total_tokens
            feature_map[l.feature]["requests"] += 1

        return UsageSummary(
            organization_id=org_id,
            period_start=ps,
            period_end=pe,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_tokens,
            included_tokens=included,
            overage_tokens=overage,
            total_cost_usd=total_cost_usd,
            overage_cost_eur=overage_cost_eur,
            request_count=len(logs),
            by_model=list(model_map.values()),
            by_feature=list(feature_map.values()),
        )

    # ── Invoice simulation ────────────────────────────────────────────────────

    async def simulate_invoice(
        self,
        org_id: uuid.UUID,
        db: AsyncSession,
    ) -> Optional[InvoiceSimulation]:
        sub = await self.get_subscription(org_id, db)
        if not sub:
            return None
        pricing = await self.get_pricing_config(sub.plan, db)
        if not pricing:
            return None

        usage = await self.get_usage_summary(org_id, db)

        items: List[InvoiceLineItem] = [
            InvoiceLineItem(
                description=f"{pricing.display_name} Plan (monatliche Grundgebühr)",
                quantity=1,
                unit_price_eur=pricing.base_price_eur_cents / 100.0,
                total_eur=pricing.base_price_eur_cents / 100.0,
            )
        ]

        if usage.overage_tokens > 0:
            rate = pricing.price_per_1k_tokens_eur_cents / 100.0
            overage_cost = (usage.overage_tokens / 1000.0) * rate
            items.append(InvoiceLineItem(
                description=f"Token-Mehrverbrauch ({usage.overage_tokens:,} Tokens über Inklusivkontingent)",
                quantity=usage.overage_tokens,
                unit_price_eur=rate / 1000,
                total_eur=overage_cost,
            ))

        subtotal = sum(i.total_eur for i in items)
        tax = round(subtotal * 0.19, 2)  # 19% VAT
        total = subtotal + tax

        return InvoiceSimulation(
            organization_id=org_id,
            period_start=sub.current_period_start or datetime.now(timezone.utc),
            period_end=sub.current_period_end or datetime.now(timezone.utc),
            plan=sub.plan,
            line_items=items,
            subtotal_eur=round(subtotal, 2),
            tax_eur=tax,
            total_eur=round(total, 2),
        )

    # ── Payment history ────────────────────────────────────────────────────────

    async def get_payments(
        self,
        org_id: uuid.UUID,
        db: AsyncSession,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[int, List[Payment]]:
        count_q = select(func.count(Payment.id)).where(Payment.organization_id == org_id)
        items_q = (
            select(Payment)
            .where(Payment.organization_id == org_id)
            .order_by(Payment.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        total = (await db.execute(count_q)).scalar_one()
        items = list((await db.execute(items_q)).scalars().all())
        return total, items

    async def record_payment(
        self,
        org_id: uuid.UUID,
        subscription_id: Optional[uuid.UUID],
        provider: str,
        provider_payment_id: str,
        amount_cents: int,
        currency: str,
        status: str,
        description: Optional[str],
        invoice_url: Optional[str],
        invoice_pdf_url: Optional[str],
        paid_at: Optional[datetime],
        db: AsyncSession,
    ) -> Payment:
        p = Payment(
            organization_id=org_id,
            subscription_id=subscription_id,
            provider=provider,
            provider_payment_id=provider_payment_id,
            amount_cents=amount_cents,
            currency=currency,
            status=status,
            description=description,
            invoice_url=invoice_url,
            invoice_pdf_url=invoice_pdf_url,
            paid_at=paid_at,
        )
        db.add(p)
        await db.commit()
        return p


billing_service = BillingService()
