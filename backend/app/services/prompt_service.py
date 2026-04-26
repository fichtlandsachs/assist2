"""Prompt Service - Manages LLM prompt templates."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import PromptTemplate


class PromptService:
    """Service for managing LLM prompts."""

    @staticmethod
    async def get_prompt_template(
        db: AsyncSession,
        key: str,
        mode: str,
    ) -> Optional[PromptTemplate]:
        """Get a prompt template by key and mode."""
        result = await db.execute(
            select(PromptTemplate).where(
                PromptTemplate.key == key,
                PromptTemplate.mode == mode,
                PromptTemplate.is_active == True,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_templates(
        db: AsyncSession,
        mode: Optional[str] = None,
    ) -> list[PromptTemplate]:
        """Get all active prompt templates."""
        query = select(PromptTemplate).where(PromptTemplate.is_active == True)

        if mode:
            query = query.where(PromptTemplate.mode == mode)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def build_prompt(
        template: PromptTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Build a prompt by substituting variables."""
        prompt = template.prompt_text

        # Simple variable substitution
        for key, value in variables.items():
            placeholder = f"{{{key}}}"
            prompt = prompt.replace(placeholder, str(value))

        return prompt

    @staticmethod
    def prepare_system_prompt(
        mode: str,
        context: dict[str, Any],
    ) -> str:
        """Prepare system prompt for conversation mode."""
        base_prompts = {
            "exploration": """Du bist ein freundlicher Assistent für die Ideenfindung.

Aufgabe: Hilf dem Nutzer, sein Thema zu strukturieren.

Regeln:
- Stelle offene Fragen
- Sammle Informationen
- Vermeide Voreiligkeit
- Keine technischen Details erzwingen""",
            "story": """Du bist ein strukturierter Assistant für User Story Erstellung.

Aufgabe: Führe den Nutzer durch die Story-Erstellung.

Regeln:
- Ein Thema pro Frage
- Maximal 2-3 Fragen pro Antwort
- Fakten zusammenfassen
- Vorschläge machen, nicht erzwingen""",
            "review": """Du bist ein kritischer Reviewer für User Stories.

Aufgabe: Bewerte Stories auf Vollständigkeit und Qualität.

Regeln:
- Testbarkeit prüfen
- Unklarheiten aufzeigen
- Verbesserungen vorschlagen
- Konstruktiv bleiben""",
        }

        return base_prompts.get(mode, base_prompts["exploration"])
