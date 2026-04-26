# app/services/bcm_dialog_guard.py
"""
BCM Dialog Guard — controls when BCM setup questions are asked in chat.

Core rule (spec §2):
  BCM questions are asked EXACTLY ONCE — only if no active BCM exists.

States:
  not_defined → BCM questions allowed
  draft       → BCM questions allowed (in progress)
  active      → NO BCM questions — use existing BCM, check new processes

This service is the single source of truth for the setup dialog flow.
It is called at the START of every chat session to produce a DialogContext
that the AI prompt builder uses to decide what to ask.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization, OrgInitializationStatus
from app.models.process_suggestion import ProcessMappingSuggestion, SuggestionStatus

logger = logging.getLogger(__name__)

BcmState = Literal["not_defined", "draft", "active"]
DialogMode = Literal["setup_mode", "operational_mode"]


@dataclass
class BcmDialogContext:
    """
    Consumed by the AI prompt builder.
    All decisions about what to ask are derived from this context.
    """
    org_id:             uuid.UUID
    bcm_state:          BcmState
    dialog_mode:        DialogMode

    # Only populated when bcm_state == "active"
    capability_count:   int = 0
    bcm_last_updated:   Optional[datetime] = None

    # Pending admin items
    pending_suggestions: int = 0   # how many process suggestions await admin review

    # Flags for the AI system prompt
    skip_industry_question:   bool = False   # True if BCM active → skip "welche Branche"
    skip_bcm_selection:       bool = False   # True if BCM active → skip BCM choice
    offer_process_clustering: bool = False   # True if starting without BCM
    hint_admin_suggestions:   bool = False   # True if pending suggestions exist


def _map_status_to_state(status: str) -> BcmState:
    """Map OrgInitializationStatus string to BCM state."""
    if status == OrgInitializationStatus.initialized.value:
        return "active"
    if status == OrgInitializationStatus.pending.value:
        return "draft"
    return "not_defined"


async def load_bcm_dialog_context(
    org_id: uuid.UUID,
    db: AsyncSession,
) -> BcmDialogContext:
    """
    Load BCM dialog context from DB.
    Always reads current state — never caches across requests.
    """
    org = await db.scalar(
        select(Organization).where(Organization.id == org_id)
    )
    if org is None:
        logger.warning("BCM dialog guard: org %s not found, defaulting to not_defined", org_id)
        return BcmDialogContext(
            org_id=org_id,
            bcm_state="not_defined",
            dialog_mode="setup_mode",
            skip_industry_question=False,
            skip_bcm_selection=False,
            offer_process_clustering=False,
        )

    bcm_state = _map_status_to_state(
        (org.initialization_status or "pending")
        if hasattr(org, "initialization_status") else "pending"
    )

    # Count capability nodes
    from app.models.capability_node import CapabilityNode
    cap_count_result = await db.scalar(
        select(func.count()).select_from(CapabilityNode).where(
            CapabilityNode.org_id == org_id
        )
    )
    capability_count = int(cap_count_result or 0)

    # Count pending process suggestions
    pending_sugg = await db.scalar(
        select(func.count()).select_from(ProcessMappingSuggestion).where(
            ProcessMappingSuggestion.org_id == org_id,
            ProcessMappingSuggestion.status == SuggestionStatus.pending.value,
        )
    )
    pending_suggestions = int(pending_sugg or 0)

    if bcm_state == "active":
        return BcmDialogContext(
            org_id=org_id,
            bcm_state="active",
            dialog_mode="operational_mode",
            capability_count=capability_count,
            pending_suggestions=pending_suggestions,
            # Core guard: skip ALL BCM setup questions
            skip_industry_question=True,
            skip_bcm_selection=True,
            offer_process_clustering=False,
            hint_admin_suggestions=pending_suggestions > 0,
        )

    return BcmDialogContext(
        org_id=org_id,
        bcm_state=bcm_state,
        dialog_mode="setup_mode",
        capability_count=capability_count,
        pending_suggestions=pending_suggestions,
        skip_industry_question=False,
        skip_bcm_selection=False,
        offer_process_clustering=(bcm_state == "not_defined"),
        hint_admin_suggestions=pending_suggestions > 0,
    )


def build_system_prompt_extension(ctx: BcmDialogContext) -> str:
    """
    Generate the BCM-awareness section of the AI system prompt.

    This is APPENDED to the base chat prompt — not replacing it.
    The AI router must include this in every chat session.
    """
    if ctx.bcm_state == "active":
        lines = [
            "## BCM-Kontext (PFLICHT — STRIKT EINHALTEN)",
            "",
            f"Die Organisation hat eine aktive Business Capability Map mit "
            f"{ctx.capability_count} Capabilities.",
            "",
            "REGELN:",
            "- Du fragst NIEMALS nach der Branche oder Industrie.",
            "- Du fragst NIEMALS nach einer BCM-Auswahl oder BCM-Vorschlägen.",
            "- Du nutzt die bestehende BCM automatisch als Strukturrahmen.",
            "- Wenn neue Prozesse genannt werden, ordnest du sie den bestehenden "
            "Capabilities zu oder erzeugst einen Vorschlag für den Admin.",
        ]
        if ctx.hint_admin_suggestions:
            lines += [
                "",
                f"HINWEIS: Es liegen {ctx.pending_suggestions} offene Prozesszuordnung(en) "
                "zur Admin-Prüfung vor. Erwähne dies kurz, falls relevant.",
            ]
    else:
        lines = [
            "## BCM-Kontext",
            "",
            "Die Organisation hat noch keine aktive Business Capability Map.",
            "",
            "Du kannst anbieten:",
            "1. Eine Beispiel-BCM zu verwenden (nach Branche)",
            "2. Eine eigene BCM zu definieren",
            "3. Ohne BCM zu starten (Fokus auf Prozesse und thematische Clusterbildung)",
            "",
            "Stelle dazu EINE klare Frage — nicht mehrere auf einmal.",
        ]
        if ctx.bcm_state == "draft":
            lines += [
                "",
                "Die BCM ist noch im Entwurfsstatus. Biete an, den Einrichtungsdialog fortzusetzen.",
            ]

    return "\n".join(lines)


def validate_process_assignment(
    process_name: str,
    capability_keywords: list[str],
    threshold_auto: float = 0.85,
    threshold_suggest: float = 0.50,
) -> dict:
    """
    Pure-logic process classification for BCM assignment.

    Returns:
        {
            "action": "auto_assign" | "suggest" | "admin_case",
            "confidence": float,
            "matched_capability": str | None,
        }

    This is intentionally simple (keyword overlap) — for production,
    replace with embedding similarity against capability nodes.
    """
    if not capability_keywords:
        return {"action": "admin_case", "confidence": 0.0, "matched_capability": None}

    proc_lower = process_name.lower()
    best_score = 0.0
    best_cap = None

    for cap in capability_keywords:
        # Overlap score: shared words / max words
        cap_words = set(cap.lower().split())
        proc_words = set(proc_lower.split())
        if not cap_words:
            continue
        overlap = len(cap_words & proc_words) / max(len(cap_words), len(proc_words))
        if overlap > best_score:
            best_score = overlap
            best_cap = cap

    if best_score >= threshold_auto:
        action = "auto_assign"
    elif best_score >= threshold_suggest:
        action = "suggest"
    else:
        action = "admin_case"

    return {
        "action": action,
        "confidence": round(best_score, 3),
        "matched_capability": best_cap if action != "admin_case" else None,
    }
