"""
Billing access guard — FastAPI dependency.

Routes that require an active subscription add:
    _ = Depends(require_billing_access)

The check is cached in Redis for 60 seconds so it doesn't add meaningful
latency to the hot path.
"""
from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.billing_service import billing_service


def require_billing_access(org_id_param: str = "org_id"):
    """
    Factory that returns a FastAPI dependency checking billing access.

    Usage:
        @router.post("/{org_id}/stories")
        async def create_story(
            ...,
            _billing = Depends(require_billing_access()),
        ):

    Superusers always bypass the check (for admin operations).
    """
    async def _check(
        org_id: uuid.UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> None:
        # Superusers bypass billing checks
        if current_user.is_superuser:
            return

        has_access = await billing_service.check_access_cached(org_id, db)
        if not has_access:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Kein aktives Abonnement",
                    "code": "BILLING_REQUIRED",
                    "message": (
                        "Diese Funktion erfordert ein aktives Abonnement. "
                        "Bitte upgraden Sie Ihren Plan unter Einstellungen → Abrechnung."
                    ),
                    "upgrade_url": f"/{org_id}/settings?tab=billing",
                },
            )

    return _check


# Pre-built dependency instance for direct use
require_active_subscription = require_billing_access()
