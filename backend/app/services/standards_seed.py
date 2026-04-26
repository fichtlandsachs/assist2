# app/services/standards_seed.py
"""
Seed Standards, Control-Families, and Standard-Mappings.

Idempotent — safe to run multiple times.
"""
from __future__ import annotations

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.control_standards import StandardDefinition, ControlStandardMapping
from app.models.product_governance import ControlDefinition

logger = logging.getLogger(__name__)

# ── Standards ─────────────────────────────────────────────────────────────────

STANDARDS = [
    {
        "slug": "iso_9001",
        "name": "ISO 9001 – Qualitätsmanagementsystem",
        "short_name": "ISO 9001",
        "description": "Internationaler Standard für Qualitätsmanagementsysteme.",
        "standard_type": "external",
        "color": "blue",
        "display_order": 10,
    },
    {
        "slug": "iso_27001",
        "name": "ISO/IEC 27001 – Informationssicherheit",
        "short_name": "ISO 27001",
        "description": "Standard für Informationssicherheits-Managementsysteme.",
        "standard_type": "external",
        "color": "violet",
        "display_order": 20,
    },
    {
        "slug": "nis2",
        "name": "NIS2 – Netz- und Informationssicherheit",
        "short_name": "NIS2",
        "description": "EU-Richtlinie zur Cybersicherheit kritischer Infrastrukturen.",
        "standard_type": "regulatory",
        "color": "red",
        "display_order": 30,
    },
    {
        "slug": "internal_governance",
        "name": "Interne Governance",
        "short_name": "Intern",
        "description": "Organisationsinterne Governance- und Kontrollvorgaben.",
        "standard_type": "internal",
        "color": "slate",
        "display_order": 40,
    },
    {
        "slug": "product_norms",
        "name": "Produktspezifische Normen",
        "short_name": "Produktnorm",
        "description": "CE, UKCA, WEEE, RoHS, EMV und weitere produktbezogene Normen.",
        "standard_type": "product_specific",
        "color": "amber",
        "display_order": 50,
    },
    {
        "slug": "customer_requirements",
        "name": "Kundenspezifische Anforderungen",
        "short_name": "Kundenvorgabe",
        "description": "Anforderungen aus Rahmenverträgen oder Kundenaudits.",
        "standard_type": "customer_specific",
        "color": "emerald",
        "display_order": 60,
    },
]

# ── Control-Family + Standard-Mapping table ───────────────────────────────────
# Format: {slug_pattern: (family_name, [(standard_slug, section_ref, is_primary)])}

CONTROL_MAPPINGS: list[dict] = [
    # Market & Regulatory
    {
        "slug_contains": "market",
        "family": "Markt & Kundengruppe",
        "standards": [
            ("iso_9001", "4.2", True),
            ("product_norms", None, False),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "regulat",
        "family": "Markt & Kundengruppe",
        "standards": [
            ("iso_9001", "4.2", True),
            ("nis2", "Art. 21", False),
            ("product_norms", None, False),
        ],
    },
    # Quality & Reliability
    {
        "slug_contains": "qualit",
        "family": "Qualität & Zuverlässigkeit",
        "standards": [
            ("iso_9001", "8.1", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "zuverl",
        "family": "Qualität & Zuverlässigkeit",
        "standards": [
            ("iso_9001", "8.5.1", True),
            ("product_norms", None, False),
        ],
    },
    # Product Development
    {
        "slug_contains": "entwick",
        "family": "Produktentwicklung & Änderung",
        "standards": [
            ("iso_9001", "8.3", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "aender",
        "family": "Produktentwicklung & Änderung",
        "standards": [
            ("iso_9001", "8.3.6", True),
            ("internal_governance", None, False),
        ],
    },
    # Security & Cyber
    {
        "slug_contains": "cyber",
        "family": "Sicherheit & Compliance",
        "standards": [
            ("iso_27001", "A.12", True),
            ("nis2", "Art. 21", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "datens",
        "family": "Sicherheit & Compliance",
        "standards": [
            ("iso_27001", "A.18", True),
            ("nis2", "Art. 21", False),
        ],
    },
    # Procurement
    {
        "slug_contains": "beschaff",
        "family": "Beschaffung & Lieferanten",
        "standards": [
            ("iso_9001", "8.4", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "liefer",
        "family": "Beschaffung & Lieferanten",
        "standards": [
            ("iso_9001", "8.4.2", True),
            ("customer_requirements", None, False),
        ],
    },
    # Risk & Economics
    {
        "slug_contains": "risiko",
        "family": "Wirtschaftlichkeit & Risiko",
        "standards": [
            ("iso_9001", "6.1", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "wirtsch",
        "family": "Wirtschaftlichkeit & Risiko",
        "standards": [
            ("internal_governance", None, True),
            ("customer_requirements", None, False),
        ],
    },
    # Service & Support
    {
        "slug_contains": "service",
        "family": "Service & Support",
        "standards": [
            ("iso_9001", "8.5.5", True),
            ("customer_requirements", None, False),
        ],
    },
    {
        "slug_contains": "support",
        "family": "Service & Support",
        "standards": [
            ("iso_9001", "8.5.5", True),
            ("internal_governance", None, False),
        ],
    },
    # Gate & Release
    {
        "slug_contains": "gate",
        "family": "Freigabe & Gate-Steuerung",
        "standards": [
            ("internal_governance", None, True),
            ("iso_9001", "8.3.4", False),
        ],
    },
    {
        "slug_contains": "freigabe",
        "family": "Freigabe & Gate-Steuerung",
        "standards": [
            ("internal_governance", None, True),
        ],
    },
    # CAPA & Improvement
    {
        "slug_contains": "capa",
        "family": "Reklamation, CAPA & Verbesserung",
        "standards": [
            ("iso_9001", "10.2", True),
            ("internal_governance", None, False),
        ],
    },
    {
        "slug_contains": "rekla",
        "family": "Reklamation, CAPA & Verbesserung",
        "standards": [
            ("iso_9001", "8.7", True),
            ("customer_requirements", None, False),
        ],
    },
    # Evidence & Documentation
    {
        "slug_contains": "nachweis",
        "family": "Freigabe & Gate-Steuerung",
        "standards": [
            ("iso_9001", "7.5", True),
            ("internal_governance", None, False),
        ],
    },
    # Environment
    {
        "slug_contains": "umwelt",
        "family": "Sicherheit & Compliance",
        "standards": [
            ("product_norms", None, True),
            ("internal_governance", None, False),
        ],
    },
    # Software
    {
        "slug_contains": "software",
        "family": "Produktentwicklung & Änderung",
        "standards": [
            ("iso_27001", "A.14", True),
            ("product_norms", None, False),
            ("nis2", "Art. 21", False),
        ],
    },
]

# Default family + standard for controls that match none of the above
DEFAULT_FAMILY = "Allgemeine Governance"
DEFAULT_STANDARD = "internal_governance"


async def seed_standards(db: AsyncSession) -> dict:
    """Create StandardDefinition entries if they don't exist yet."""
    created = 0
    std_map: dict[str, StandardDefinition] = {}

    for s in STANDARDS:
        existing = await db.scalar(
            select(StandardDefinition).where(StandardDefinition.slug == s["slug"])
        )
        if not existing:
            obj = StandardDefinition(**s)
            db.add(obj)
            await db.flush()
            std_map[s["slug"]] = obj
            created += 1
        else:
            std_map[s["slug"]] = existing

    logger.info("Standards seeded: %d created", created)
    return std_map


async def seed_control_mappings(db: AsyncSession) -> int:
    """
    For every ControlDefinition:
    1. Set control_family based on slug matching.
    2. Create ControlStandardMapping rows.
    Skips already-mapped controls.
    """
    std_map: dict[str, StandardDefinition] = {}
    for s in STANDARDS:
        obj = await db.scalar(
            select(StandardDefinition).where(StandardDefinition.slug == s["slug"])
        )
        if obj:
            std_map[s["slug"]] = obj

    result = await db.execute(select(ControlDefinition))
    controls = result.scalars().all()

    mapped = 0
    for ctrl in controls:
        slug_lower = ctrl.slug.lower()
        name_lower = ctrl.name.lower()

        # Find matching mapping rule
        matched_rule = None
        for rule in CONTROL_MAPPINGS:
            if rule["slug_contains"] in slug_lower or rule["slug_contains"] in name_lower:
                matched_rule = rule
                break

        # Set family
        family = matched_rule["family"] if matched_rule else DEFAULT_FAMILY
        if ctrl.control_family != family:
            ctrl.control_family = family

        # Determine which standards to map to
        standards_to_map = matched_rule["standards"] if matched_rule else [
            (DEFAULT_STANDARD, None, True)
        ]

        for std_slug, section_ref, is_primary in standards_to_map:
            std = std_map.get(std_slug)
            if not std:
                continue
            existing = await db.scalar(
                select(ControlStandardMapping).where(
                    ControlStandardMapping.control_id == ctrl.id,
                    ControlStandardMapping.standard_id == std.id,
                )
            )
            if not existing:
                db.add(ControlStandardMapping(
                    control_id=ctrl.id,
                    standard_id=std.id,
                    section_ref=section_ref,
                    is_primary=is_primary,
                ))
                mapped += 1

    await db.flush()
    logger.info("Control-Standard mappings created: %d", mapped)
    return mapped
