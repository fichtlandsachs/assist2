"""PayPal REST API integration (Subscriptions v1 API)."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(30.0)


class PayPalService:
    """Async PayPal billing integration via REST API."""

    def _base(self) -> str:
        settings = get_settings()
        return "https://api-m.paypal.com" if settings.PAYPAL_LIVE_MODE else "https://api-m.sandbox.paypal.com"

    async def _get_access_token(self) -> str:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base()}/v1/oauth2/token",
                auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
                data={"grant_type": "client_credentials"},
            )
        resp.raise_for_status()
        return resp.json()["access_token"]

    def _headers(self, token: str) -> dict:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Subscriptions ──────────────────────────────────────────────────────────

    async def create_subscription(
        self,
        plan_id: str,
        subscriber_email: str,
        subscriber_name: str,
        return_url: str,
        cancel_url: str,
        custom_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        token = await self._get_access_token()
        payload: Dict[str, Any] = {
            "plan_id": plan_id,
            "subscriber": {
                "name": {"given_name": subscriber_name},
                "email_address": subscriber_email,
            },
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        if custom_id:
            payload["custom_id"] = custom_id

        import json
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base()}/v1/billing/subscriptions",
                headers=self._headers(token),
                content=json.dumps(payload),
            )
        resp.raise_for_status()
        return resp.json()

    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{self._base()}/v1/billing/subscriptions/{subscription_id}",
                headers=self._headers(token),
            )
        resp.raise_for_status()
        return resp.json()

    async def cancel_subscription(self, subscription_id: str, reason: str = "Customer cancelled") -> None:
        import json
        token = await self._get_access_token()
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base()}/v1/billing/subscriptions/{subscription_id}/cancel",
                headers=self._headers(token),
                content=json.dumps({"reason": reason}),
            )
        if resp.status_code not in (200, 204):
            logger.error("PayPal cancel failed: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()

    # ── Webhook verification ───────────────────────────────────────────────────

    async def verify_webhook_signature(
        self,
        headers: Dict[str, str],
        body: bytes,
    ) -> bool:
        """
        Verify PayPal webhook signature via PayPal's own verification API.
        Required headers: PAYPAL-TRANSMISSION-ID, PAYPAL-TRANSMISSION-TIME,
                          PAYPAL-CERT-URL, PAYPAL-TRANSMISSION-SIG
        """
        import json
        settings = get_settings()
        token = await self._get_access_token()
        payload = {
            "auth_algo": headers.get("PAYPAL-AUTH-ALGO", "SHA256withRSA"),
            "cert_url": headers.get("PAYPAL-CERT-URL", ""),
            "transmission_id": headers.get("PAYPAL-TRANSMISSION-ID", ""),
            "transmission_sig": headers.get("PAYPAL-TRANSMISSION-SIG", ""),
            "transmission_time": headers.get("PAYPAL-TRANSMISSION-TIME", ""),
            "webhook_id": settings.PAYPAL_WEBHOOK_ID,
            "webhook_event": json.loads(body),
        }
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self._base()}/v1/notifications/verify-webhook-signature",
                headers=self._headers(token),
                content=json.dumps(payload),
            )
        if not resp.is_success:
            return False
        return resp.json().get("verification_status") == "SUCCESS"


paypal_service = PayPalService()
