"""Stripe payment integration. All Stripe SDK calls are isolated here."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_STRIPE_BASE = "https://api.stripe.com/v1"
_TIMEOUT = httpx.Timeout(30.0)


def _headers(secret_key: str) -> dict:
    return {
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def _encode(data: dict, prefix: str = "") -> str:
    """Encode nested dict as Stripe's form-encoded format."""
    parts = []
    for key, value in data.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            parts.append(_encode(value, full_key))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    parts.append(_encode(item, f"{full_key}[]"))
                else:
                    parts.append(f"{full_key}[]={item}")
        elif value is not None:
            parts.append(f"{full_key}={value}")
    return "&".join(parts)


class StripeService:
    """Thin async wrapper around the Stripe REST API using httpx."""

    def _key(self) -> str:
        return get_settings().STRIPE_SECRET_KEY

    # ── Customers ──────────────────────────────────────────────────────────────

    async def create_customer(
        self,
        email: str,
        name: str,
        org_id: str,
        org_slug: str,
    ) -> Dict[str, Any]:
        payload = _encode({
            "email": email,
            "name": name,
            "metadata": {"org_id": str(org_id), "org_slug": org_slug},
        })
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_STRIPE_BASE}/customers",
                headers=_headers(self._key()),
                content=payload,
            )
        resp.raise_for_status()
        return resp.json()

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_STRIPE_BASE}/customers/{customer_id}",
                headers=_headers(self._key()),
            )
        resp.raise_for_status()
        return resp.json()

    # ── Subscriptions ──────────────────────────────────────────────────────────

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        trial_period_days: Optional[int] = None,
        payment_method_id: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "payment_behavior": "default_incomplete",
            "expand[]": "latest_invoice.payment_intent",
        }
        if trial_period_days:
            data["trial_period_days"] = trial_period_days
        if payment_method_id:
            data["default_payment_method"] = payment_method_id
        if metadata:
            data["metadata"] = metadata

        payload = _encode(data)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_STRIPE_BASE}/subscriptions",
                headers=_headers(self._key()),
                content=payload,
            )
        resp.raise_for_status()
        return resp.json()

    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True,
    ) -> Dict[str, Any]:
        if at_period_end:
            payload = _encode({"cancel_at_period_end": "true"})
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    f"{_STRIPE_BASE}/subscriptions/{subscription_id}",
                    headers=_headers(self._key()),
                    content=payload,
                )
        else:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.delete(
                    f"{_STRIPE_BASE}/subscriptions/{subscription_id}",
                    headers=_headers(self._key()),
                )
        resp.raise_for_status()
        return resp.json()

    async def update_subscription_payment_method(
        self,
        subscription_id: str,
        payment_method_id: str,
    ) -> Dict[str, Any]:
        payload = _encode({"default_payment_method": payment_method_id})
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_STRIPE_BASE}/subscriptions/{subscription_id}",
                headers=_headers(self._key()),
                content=payload,
            )
        resp.raise_for_status()
        return resp.json()

    # ── Checkout sessions ──────────────────────────────────────────────────────

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        trial_period_days: Optional[int] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "customer": customer_id,
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        if trial_period_days:
            data["subscription_data"] = {"trial_period_days": trial_period_days}
        if metadata:
            data["metadata"] = metadata

        payload = _encode(data)
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_STRIPE_BASE}/checkout/sessions",
                headers=_headers(self._key()),
                content=payload,
            )
        resp.raise_for_status()
        return resp.json()

    # ── Customer portal ────────────────────────────────────────────────────────

    async def create_billing_portal_session(
        self,
        customer_id: str,
        return_url: str,
    ) -> Dict[str, Any]:
        payload = _encode({
            "customer": customer_id,
            "return_url": return_url,
        })
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{_STRIPE_BASE}/billing_portal/sessions",
                headers=_headers(self._key()),
                content=payload,
            )
        resp.raise_for_status()
        return resp.json()

    # ── Payment methods ────────────────────────────────────────────────────────

    async def list_payment_methods(self, customer_id: str) -> list:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{_STRIPE_BASE}/payment_methods",
                headers=_headers(self._key()),
                params={"customer": customer_id, "type": "card"},
            )
        resp.raise_for_status()
        return resp.json().get("data", [])

    # ── Webhook signature verification ────────────────────────────────────────

    def construct_event(self, payload: bytes, sig_header: str) -> Dict[str, Any]:
        """
        Verify Stripe webhook signature and return the parsed event dict.
        Uses HMAC-SHA256 (no SDK needed).
        """
        import hashlib
        import hmac
        import time

        secret = get_settings().STRIPE_WEBHOOK_SECRET
        if not secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET not configured")

        # Parse Stripe-Signature header: t=...,v1=...
        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")

        if not timestamp or not v1_sig:
            raise ValueError("Invalid Stripe-Signature header")

        # Tolerance: 5 minutes
        if abs(int(time.time()) - int(timestamp)) > 300:
            raise ValueError("Stripe webhook timestamp too old")

        signed_payload = f"{timestamp}.{payload.decode()}"
        expected = hmac.new(
            secret.encode(), signed_payload.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected, v1_sig):
            raise ValueError("Stripe signature verification failed")

        import json
        return json.loads(payload)


stripe_service = StripeService()
