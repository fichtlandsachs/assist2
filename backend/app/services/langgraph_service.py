"""LangGraph Service - Placeholder (LangGraph not installed)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class LangGraphService:
    """Service for running conversation LangGraph workflows (disabled)."""

    @staticmethod
    async def process_message(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        input_message: str,
        observer_enabled: bool = False,
    ) -> dict[str, Any]:
        """Disabled - returns error."""
        return {
            "success": False,
            "error": "LangGraph not installed. Use OrchestratorService instead.",
            "response": "",
        }
