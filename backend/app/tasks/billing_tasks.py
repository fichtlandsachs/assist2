"""Celery tasks for billing: async usage recording + monthly aggregation."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="billing.record_usage", bind=True, max_retries=3)
def record_usage_task(
    self,
    org_id: str,
    user_id: Optional[str],
    model: str,
    provider: str,
    feature: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    request_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a single AI usage event to the database (fire-and-forget from API)."""
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models.billing import UsageLog

    async def _run():
        async with AsyncSessionLocal() as db:
            log = UsageLog(
                organization_id=uuid.UUID(org_id),
                user_id=uuid.UUID(user_id) if user_id else None,
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

    try:
        asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())
    except Exception as exc:
        logger.error("Failed to record usage: %s", exc)
        raise self.retry(exc=exc, countdown=5)


@shared_task(name="billing.monthly_aggregation")
def monthly_usage_aggregation() -> None:
    """
    Run at the start of each billing cycle (triggered by Stripe webhook or cron).
    Aggregates usage per org, calculates overage charges.
    Could trigger invoice creation or add line items via Stripe Usage API.
    """
    import asyncio
    from app.database import AsyncSessionLocal
    from app.services.billing_service import billing_service

    async def _run():
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, distinct
            from app.models.billing import Subscription, SubscriptionStatus
            result = await db.execute(
                select(Subscription).where(
                    Subscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.past_due])
                )
            )
            subscriptions = result.scalars().all()
            logger.info("Running monthly aggregation for %d subscriptions", len(subscriptions))

            for sub in subscriptions:
                try:
                    usage = await billing_service.get_usage_summary(sub.organization_id, db)
                    if usage.overage_tokens > 0:
                        logger.info(
                            "Org %s: %d overage tokens → €%.2f",
                            sub.organization_id, usage.overage_tokens, usage.overage_cost_eur,
                        )
                        # TODO: Report to Stripe metered billing or create invoice item
                except Exception as e:
                    logger.error("Aggregation failed for org %s: %s", sub.organization_id, e)

    try:
        asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())


@shared_task(name="billing.seed_pricing")
def seed_pricing_task() -> None:
    """One-time task to seed default pricing configs into the DB."""
    import asyncio
    from app.database import AsyncSessionLocal
    from app.services.billing_service import billing_service

    async def _run():
        async with AsyncSessionLocal() as db:
            await billing_service.seed_default_pricing(db)

    try:
        asyncio.get_event_loop().run_until_complete(_run())
    except RuntimeError:
        asyncio.run(_run())
