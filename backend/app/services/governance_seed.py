# app/services/governance_seed.py
"""
Seed data for the Product Governance system.

Idempotent — safe to run multiple times (checks existence before insert).

Includes:
  - 12 control categories (energy product matrix)
  - Product scopes (Wallbox, Battery, Inverter, ...)
  - Market scopes (EU, DE, AT, ...)
  - Customer segments (B2B, B2C, B2B2C)
  - Risk dimensions
  - Evidence types (18 types)
  - Default scoring scheme (0–3)
  - Gate definitions (G1–G4)
  - 24 fixed baseline controls
  - 8 example trigger rules
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_governance import (
    ControlCategory, ProductScope, MarketScope, CustomerSegment,
    RiskDimension, EvidenceType, ScoringScheme, GateDefinition,
    ControlDefinition, DynamicTriggerRule,
    ControlKind, ControlStatus,
)

logger = logging.getLogger(__name__)


async def seed_all(db: AsyncSession) -> None:
    """Run all seed operations idempotently."""
    logger.info("Running Product Governance seed...")
    await seed_categories(db)
    await seed_product_scopes(db)
    await seed_market_scopes(db)
    await seed_customer_segments(db)
    await seed_risk_dimensions(db)
    await seed_evidence_types(db)
    await seed_scoring_scheme(db)
    await seed_gates(db)
    await seed_fixed_controls(db)
    await seed_triggers(db)
    await db.commit()
    logger.info("Product Governance seed complete.")


async def _get_or_none(db: AsyncSession, model, slug: str):
    return await db.scalar(select(model).where(model.slug == slug))


# ── Categories ─────────────────────────────────────────────────────────────────

CATEGORIES = [
    ("produkt-kunden-fit",      "Produkt-/Kundensegment-Fit",                1),
    ("regulatorik-marktzugang", "Regulatorik & Marktzugang",                 2),
    ("sicherheit-compliance",   "Sicherheits- und Compliance-Architektur",   3),
    ("anforderungen-entwicklung","Anforderungen & Entwicklungslenkung",      4),
    ("energieperformance",      "Energieperformance & Produktclaims",        5),
    ("beschaffung-lieferanten", "Beschaffung & Lieferantenrobustheit",       6),
    ("kosten-marge-garantie",   "Kosten-, Margen- und Garantie-Risiko",      7),
    ("qualitaet-zuverlaessigkeit","Qualität & Zuverlässigkeit",              8),
    ("servicefaehigkeit",       "Servicefähigkeit & Anrufvolumen",           9),
    ("rueckverfolgbarkeit",     "Rückverfolgbarkeit & Konfigurationsmanagement", 10),
    ("umsatz-kredit-risiko",    "Umsatz-, Kredit- und Konzentrationsrisiko", 11),
    ("capa-beschwerde",         "Beschwerdebild, CAPA & Lernschleife",       12),
]


async def seed_categories(db: AsyncSession) -> None:
    for slug, name, order in CATEGORIES:
        if not await _get_or_none(db, ControlCategory, slug):
            db.add(ControlCategory(slug=slug, name=name, sort_order=order))
    await db.flush()


# ── Product Scopes ─────────────────────────────────────────────────────────────

PRODUCT_SCOPES = [
    ("wallbox",         "Wallbox / Ladestation",      {"has_grid_connection": True}),
    ("battery-storage", "Batteriespeicher",           {"has_battery": True, "has_grid_connection": True}),
    ("inverter",        "Wechselrichter / Inverter",  {"has_grid_connection": True}),
    ("power-supply",    "Netzteil / Stromversorgung", {}),
    ("smart-energy",    "Smarte Energietechnik",      {"has_software": True, "has_cloud": True}),
    ("ev-charger",      "EV-Ladeinfrastruktur",       {"has_grid_connection": True}),
    ("heat-pump",       "Wärmepumpe",                 {}),
    ("solar-system",    "Solaranlage / PV-System",    {"has_grid_connection": True}),
]


async def seed_product_scopes(db: AsyncSession) -> None:
    for slug, name, attrs in PRODUCT_SCOPES:
        if not await _get_or_none(db, ProductScope, slug):
            db.add(ProductScope(slug=slug, name=name, attributes=attrs))
    await db.flush()


# ── Market Scopes ──────────────────────────────────────────────────────────────

MARKET_SCOPES = [
    ("eu",   "EU / Europa",     "EU",   ["DE","AT","CH","FR","NL","IT","ES","PL"], "CE / RED / LVD"),
    ("de",   "Deutschland",     "DACH", ["DE"],                                   "VDE / BNetzA"),
    ("at",   "Österreich",      "DACH", ["AT"],                                   "CE / ÖVE"),
    ("us",   "USA",             "NA",   ["US"],                                   "UL / NEC / FCC"),
    ("uk",   "Großbritannien",  "UK",   ["GB"],                                   "UKCA / BS"),
    ("apac", "Asia Pacific",    "APAC", ["JP","AU","SG","KR"],                    "PSE / SAA / various"),
    ("global","Global",         "GLOBAL", [],                                     "various"),
]


async def seed_market_scopes(db: AsyncSession) -> None:
    for slug, name, region, countries, framework in MARKET_SCOPES:
        if not await _get_or_none(db, MarketScope, slug):
            db.add(MarketScope(slug=slug, name=name, region=region,
                               countries=countries, regulatory_framework=framework))
    await db.flush()


# ── Customer Segments ──────────────────────────────────────────────────────────

SEGMENTS = [
    ("b2b-enterprise", "B2B Enterprise",      "B2B",   {"scale": "large", "support_expectation": "high"}),
    ("b2b-smb",        "B2B SMB",             "B2B",   {"scale": "medium"}),
    ("b2c-mass",       "B2C Massenmarkt",     "B2C",   {"volume": "high", "support_expectation": "high"}),
    ("b2c-premium",    "B2C Premium",         "B2C",   {"volume": "low", "margin": "high"}),
    ("b2b2c",          "B2B2C (Reseller)",    "B2B2C", {}),
    ("installer",      "Fachhandwerker",      "B2B",   {"technical_competence": "high"}),
    ("utility",        "Energieversorger",    "B2B",   {"regulatory_expectation": "high"}),
]


async def seed_customer_segments(db: AsyncSession) -> None:
    for slug, name, seg_type, attrs in SEGMENTS:
        if not await _get_or_none(db, CustomerSegment, slug):
            db.add(CustomerSegment(slug=slug, name=name, segment_type=seg_type, attributes=attrs))
    await db.flush()


# ── Risk Dimensions ────────────────────────────────────────────────────────────

RISKS = [
    ("umsatzrisiko",       "Umsatzrisiko",             "financial"),
    ("kostenrisiko",       "Kostenrisiko",             "financial"),
    ("kreditrisiko",       "Kreditrisiko",             "financial"),
    ("beschaffungsrisiko", "Beschaffungsrisiko",       "supply_chain"),
    ("qualitaetsrisiko",   "Qualitätsrisiko",          "quality"),
    ("sicherheitsrisiko",  "Sicherheitsrisiko",        "safety"),
    ("regulatorik",        "Regulatorisches Risiko",   "compliance"),
    ("supportrisiko",      "Supportlast-Risiko",       "operations"),
    ("ausfallrisiko",      "Ausfallkritikalität",      "reliability"),
    ("konzentration",      "Konzentrationsrisiko",     "strategic"),
]


async def seed_risk_dimensions(db: AsyncSession) -> None:
    for slug, name, risk_type in RISKS:
        if not await _get_or_none(db, RiskDimension, slug):
            db.add(RiskDimension(slug=slug, name=name, risk_type=risk_type))
    await db.flush()


# ── Evidence Types ─────────────────────────────────────────────────────────────

EVIDENCE_TYPES = [
    ("pruefbericht",        "Prüfbericht",              True,  "PDF, mit Datum und Prüfer-Signatur"),
    ("lastenheft",          "Lastenheft",               True,  "Word/PDF, versioniert"),
    ("pflichtenheft",       "Pflichtenheft",            True,  "Word/PDF, versioniert"),
    ("fmea",                "FMEA",                     True,  "Excel/PDF, aktuelles Datum"),
    ("lieferantenbewertung","Lieferantenbewertung",     True,  "Scorecard + Bericht"),
    ("business-case",       "Business Case",            True,  "Finanzmodell + Annahmen"),
    ("bonitaetspruefung",   "Bonitätsprüfung",          False, "Auszug aus Creditreform o.ä."),
    ("testprotokoll",       "Testprotokoll",            True,  "Systemtest-Dokumentation"),
    ("serienfreigabe",      "Serienfreigabe",           True,  "Freigebener Bericht mit Unterschriften"),
    ("installationsanleitung","Installationsanleitung", False, "Gedruckt + PDF"),
    ("supportkonzept",      "Supportkonzept",           False, "Beschreibung Eskalationswege"),
    ("risikoanalyse",       "Risikoanalyse",            True,  "Berichtsformat mit Risk-Matrix"),
    ("capa",                "CAPA-Dokumentation",       False, "Corrective & Preventive Action"),
    ("auditnachweis",       "Auditnachweis",            False, "Auditbericht oder Zertifikat"),
    ("ce-konformitaet",     "CE-Konformitätserklärung", True,  "Offizielle DoC mit Normenreferenz"),
    ("iso-zertifikat",      "ISO-Zertifikat",           False, "Zertifikat mit Gültigkeitsdatum"),
    ("testergebnis-labor",  "Laborprüfergebnis",        True,  "Akkreditiertes Prüflabor-Bericht"),
    ("markteintrittsstrategie","Markteintrittsstrategie", False,"Strategiepapier + Market-Research"),
]


async def seed_evidence_types(db: AsyncSession) -> None:
    for slug, name, is_system, fmt in EVIDENCE_TYPES:
        if not await _get_or_none(db, EvidenceType, slug):
            db.add(EvidenceType(slug=slug, name=name, is_system=is_system,
                                format_guidance=fmt, is_active=True))
    await db.flush()


# ── Scoring Scheme ─────────────────────────────────────────────────────────────

async def seed_scoring_scheme(db: AsyncSession) -> None:
    if await _get_or_none(db, ScoringScheme, "standard-0-3"):
        return
    db.add(ScoringScheme(
        slug="standard-0-3",
        name="Standard 0–3 Skala",
        is_default=True,
        scale_min=0,
        scale_max=3,
        scale_labels=[
            {"value": 0, "label": "Nicht bewertet", "color": "gray",   "description": "Kein Nachweis vorhanden oder nicht bewertet"},
            {"value": 1, "label": "Kritisch unzureichend", "color": "red",  "description": "Nachweis fehlt oder grundlegende Anforderung nicht erfüllt"},
            {"value": 2, "label": "Teilweise beherrscht",  "color": "amber","description": "Anforderung teilweise erfüllt, Maßnahmen definiert"},
            {"value": 3, "label": "Beherrscht",            "color": "green","description": "Anforderung vollständig erfüllt, Nachweis vorliegend"},
        ],
        traffic_light={
            "green":  {"min_score": 2.5},
            "yellow": {"min_score": 1.5},
            "red":    {"max_score": 1.5},
        },
        formula="weighted_average(scores, weights)",
        is_active=True,
    ))
    await db.flush()


# ── Gates ──────────────────────────────────────────────────────────────────────

GATES = [
    {
        "phase": "G1", "name": "Gate 1: Opportunity / Business Case", "sort": 0,
        "desc": "Freigabe zur weiteren Investition in Produktidee und Business Case.",
        "min_score": 1.5,
        "required_cats": ["produkt-kunden-fit", "regulatorik-marktzugang", "umsatz-kredit-risiko"],
        "approvers": ["Product Owner", "CFO"],
        "hs_threshold": 1,
    },
    {
        "phase": "G2", "name": "Gate 2: Entwicklungsfreigabe", "sort": 1,
        "desc": "Freigabe zur Produktentwicklung nach abgeschlossener Konzeptphase.",
        "min_score": 2.0,
        "required_cats": ["anforderungen-entwicklung", "sicherheit-compliance", "beschaffung-lieferanten"],
        "approvers": ["Head of Product", "Quality Manager", "Engineering Lead"],
        "hs_threshold": 1,
    },
    {
        "phase": "G3", "name": "Gate 3: Markt- / Serienfreigabe", "sort": 2,
        "desc": "Freigabe zur Serienproduktion und Markteinführung.",
        "min_score": 2.5,
        "required_cats": ["qualitaet-zuverlaessigkeit", "regulatorik-marktzugang", "energieperformance",
                          "servicefaehigkeit", "rueckverfolgbarkeit"],
        "approvers": ["CPO", "Quality Director", "Legal", "Regulatory Affairs"],
        "hs_threshold": 1,
    },
    {
        "phase": "G4", "name": "Gate 4: Scale-up / Portfolio-Fortführung", "sort": 3,
        "desc": "Freigabe zur Skalierung oder Bestandteil des aktiven Portfolios.",
        "min_score": 2.0,
        "required_cats": ["capa-beschwerde", "servicefaehigkeit", "umsatz-kredit-risiko"],
        "approvers": ["CPO", "CFO", "Head of After Sales"],
        "hs_threshold": 1,
    },
]


async def seed_gates(db: AsyncSession) -> None:
    for g in GATES:
        phase = g["phase"]
        name = g["name"]
        sort = g["sort"]
        desc = g["desc"]
        min_score = g["min_score"]
        required_cats = g["required_cats"]
        approvers = g["approvers"]
        hs_threshold = g["hs_threshold"]
        existing = await db.scalar(
            select(GateDefinition).where(GateDefinition.phase == phase)
        )
        if existing:
            continue
        db.add(GateDefinition(
            phase=phase,
            name=name,
            sort_order=sort,
            description=desc,
            min_total_score=min_score,
            required_fixed_control_slugs=required_cats,
            hard_stop_threshold=hs_threshold,
            approver_roles=approvers,
            outcomes_config={
                "go": {"min_score": min_score, "no_hard_stops": True},
                "conditional_go": {"min_score": min_score * 0.75, "open_actions_allowed": True},
                "no_go": {"max_score": min_score * 0.75},
            },
            is_active=True,
            status=ControlStatus.approved.value,
        ))
    await db.flush()


# ── Fixed Controls ─────────────────────────────────────────────────────────────

FIXED_CONTROLS = [
    # ── Kategorie 1: Produkt-/Kundensegment-Fit
    ("FC-001", "produkt-kunden-fit-klarheit",     "Produkt-/Kundensegment-Fit",
     "Klärung ob Produkt auf definiertes Kundensegment und Markt passt.",
     ["G1"], True, 1.5, "produkt-kunden-fit"),
    ("FC-002", "nutzenversprechen-validierung",   "Nutzenversprechen-Validierung",
     "Nachweis, dass Nutzenversprechen im Zielsegment validiert wurde.",
     ["G1","G2"], False, 1.0, "produkt-kunden-fit"),

    # ── Kategorie 2: Regulatorik & Marktzugang
    ("FC-003", "ce-konformitaet-check",           "CE-Konformitätscheck",
     "Prüfung aller anwendbaren EU-Richtlinien und Normen (RED, LVD, EMV, …).",
     ["G2","G3"], True, 2.0, "regulatorik-marktzugang"),
    ("FC-004", "marktzulassung-status",           "Marktzulassungs-Status",
     "Nachweis aller erforderlichen Zulassungen je Zielmarkt.",
     ["G3"], True, 2.0, "regulatorik-marktzugang"),
    ("FC-005", "exportkontrolle",                 "Exportkontrolle",
     "Prüfung auf Exportkontrollbeschränkungen und ECCN-Klassifizierung.",
     ["G2","G3"], False, 1.5, "regulatorik-marktzugang"),

    # ── Kategorie 3: Sicherheit & Compliance
    ("FC-006", "sicherheitsarchitektur",          "Sicherheitsarchitektur-Review",
     "Strukturelle Überprüfung der Produkt- und Systemsicherheit.",
     ["G2"], True, 2.0, "sicherheit-compliance"),
    ("FC-007", "datenschutz-privacy",             "Datenschutz & Privacy",
     "DSGVO-Compliance bei Produkten mit Software/Cloud-Anteil.",
     ["G2","G3"], False, 1.5, "sicherheit-compliance"),

    # ── Kategorie 4: Anforderungen & Entwicklung
    ("FC-008", "lastenheft-pflichtenheft",        "Lastenheft/Pflichtenheft vorliegend",
     "Vollständiges Lasten- und Pflichtenheft als Entwicklungsgrundlage.",
     ["G2"], True, 2.0, "anforderungen-entwicklung"),
    ("FC-009", "design-review",                   "Formaler Design Review",
     "Abnahme des technischen Designs durch relevante Stakeholder.",
     ["G2","G3"], False, 1.5, "anforderungen-entwicklung"),

    # ── Kategorie 5: Energieperformance
    ("FC-010", "energieleistung-claims",          "Energieleistungs-Claims validiert",
     "Alle beworbenen Energie-Kennwerte durch Messung oder Simulation belegt.",
     ["G3"], True, 2.0, "energieperformance"),
    ("FC-011", "effizienzklasse-konformitaet",   "Effizienzklassen-Konformität",
     "Produkt entspricht deklarierten Energieeffizienzklassen (EEI, ErP, …).",
     ["G3"], True, 2.0, "energieperformance"),

    # ── Kategorie 6: Beschaffung & Lieferanten
    ("FC-012", "lieferantenbewertung",            "Lieferantenbewertung",
     "Qualifizierung aller kritischen Zulieferer (Qualität, Finanzen, Geo-Risiko).",
     ["G2","G3"], True, 1.5, "beschaffung-lieferanten"),
    ("FC-013", "single-source-pruefung",          "Single-Source-Prüfung",
     "Identifikation und Bewertung von Single-Source-Abhängigkeiten.",
     ["G2"], False, 1.5, "beschaffung-lieferanten"),

    # ── Kategorie 7: Kosten, Marge & Garantie
    ("FC-014", "kostenstruktur-analyse",          "Kostenstruktur-Analyse",
     "Vollständige COGS-Analyse inkl. Beschaffung, Logistik, Garantie.",
     ["G1","G2"], True, 1.5, "kosten-marge-garantie"),
    ("FC-015", "garantiereserve-kalkulation",     "Garantiereserven-Kalkulation",
     "Nachweis ausreichender Rückstellungen für Garantiefälle.",
     ["G2","G3"], True, 1.5, "kosten-marge-garantie"),

    # ── Kategorie 8: Qualität & Zuverlässigkeit
    ("FC-016", "fmea-durchgefuehrt",              "FMEA durchgeführt",
     "Failure Mode & Effects Analysis für kritische Komponenten.",
     ["G2","G3"], True, 2.0, "qualitaet-zuverlaessigkeit"),
    ("FC-017", "testprotokoll-serie",             "Serienprüfung abgeschlossen",
     "Vollständige Prüfprotokolle der Serienfertigung.",
     ["G3"], True, 2.0, "qualitaet-zuverlaessigkeit"),

    # ── Kategorie 9: Servicefähigkeit
    ("FC-018", "service-konzept",                 "Servicekonzept vorliegend",
     "Beschreibung Servicemodell, Eskalationswege, SLA-Konzept.",
     ["G3"], False, 1.0, "servicefaehigkeit"),
    ("FC-019", "support-kapazitaet",              "Supportkapazität gesichert",
     "Ausreichende Support-Ressourcen für erwartetes Anrufvolumen.",
     ["G3"], False, 1.0, "servicefaehigkeit"),

    # ── Kategorie 10: Rückverfolgbarkeit
    ("FC-020", "seriennummern-system",            "Seriennummernsystem",
     "Vollständige Rückverfolgbarkeit jeder Einheit über Seriennummer.",
     ["G3"], True, 1.5, "rueckverfolgbarkeit"),
    ("FC-021", "softwareversion-management",      "Softwareversion-Management",
     "Klarer Prozess für Firmware/SW-Versionsmanagement und Updates.",
     ["G2","G3"], False, 1.5, "rueckverfolgbarkeit"),

    # ── Kategorie 11: Umsatz-/Kredit-/Konzentrationsrisiko
    ("FC-022", "umsatzprognose-validitaet",       "Umsatzprognose Validität",
     "Business Case mit nachvollziehbaren Umsatzannahmen und Sensitivitätsanalyse.",
     ["G1"], True, 1.5, "umsatz-kredit-risiko"),
    ("FC-023", "kundenkonzentration",             "Kundenkonzentrations-Risiko",
     "Bewertung des Risikos bei Abhängigkeit von wenigen Großkunden.",
     ["G1","G2"], False, 1.0, "umsatz-kredit-risiko"),

    # ── Kategorie 12: Beschwerde & CAPA
    ("FC-024", "capa-prozess",                   "CAPA-Prozess etabliert",
     "Corrective & Preventive Action Prozess dokumentiert und operativ.",
     ["G3","G4"], True, 1.5, "capa-beschwerde"),
]


async def seed_fixed_controls(db: AsyncSession) -> None:
    # Build category slug → id map
    cat_result = await db.execute(select(ControlCategory))
    cat_map = {c.slug: c.id for c in cat_result.scalars().all()}

    for sys_id, slug, name, desc, gates, hard_stop, weight, cat_slug in FIXED_CONTROLS:
        existing = await db.scalar(
            select(ControlDefinition).where(ControlDefinition.slug == slug)
        )
        if existing:
            continue
        db.add(ControlDefinition(
            system_id=sys_id,
            slug=slug,
            kind=ControlKind.fixed.value,
            name=name,
            short_description=desc,
            control_objective=f"Sicherstellung: {name}",
            gate_phases=gates,
            default_weight=weight,
            hard_stop=hard_stop,
            hard_stop_threshold=1,
            category_id=cat_map.get(cat_slug),
            status=ControlStatus.approved.value,
            version=1,
            published_at=datetime.now(timezone.utc),
            evidence_requirements=[],
            guiding_questions=[
                f"Liegt ein vollständiger Nachweis für '{name}' vor?",
                "Ist der Nachweis aktuell und gültig?",
                "Sind alle Verantwortlichkeiten geklärt?",
            ],
            why_relevant=f"Dieses Control ist Pflichtbestandteil der Produktprüfung im Bereich {cat_slug.replace('-', ' ').title()}.",
        ))
    await db.flush()


# ── Trigger Rules ──────────────────────────────────────────────────────────────

async def seed_triggers(db: AsyncSession) -> None:
    # Get some dynamic control IDs to activate (if they exist)
    # Triggers reference controls by ID but we'll use empty lists for seed

    triggers = [
        {
            "slug": "trigger-battery-eu-b2b-critical",
            "name": "Batteriespeicher + EU + B2B + Hohe Ausfallkritikalität",
            "description": "Aktiviert verschärfte Controls bei kritischen Batterie-Produkten im EU B2B-Segment.",
            "condition_tree": {
                "operator": "AND",
                "conditions": [
                    {"field": "product_type", "op": "eq", "value": "battery-storage"},
                    {"field": "market", "op": "in", "value": ["eu", "de"]},
                    {"field": "customer_segment", "op": "in", "value": ["b2b-enterprise", "utility"]},
                    {"field": "failure_criticality", "op": "gte", "value": "high"},
                ]
            },
            "activates_control_ids": [],
            "priority": 10,
        },
        {
            "slug": "trigger-single-source",
            "name": "Single Source Lieferant",
            "description": "Aktiviert vertiefte Lieferantenbewertung bei Single-Source-Abhängigkeit.",
            "condition_tree": {"field": "has_single_source", "op": "is_true", "value": True},
            "activates_control_ids": [],
            "priority": 20,
        },
        {
            "slug": "trigger-software-firmware",
            "name": "Produkt mit Software/Firmware-Anteil",
            "description": "Aktiviert Software-Qualitäts- und Cybersecurity-Controls.",
            "condition_tree": {
                "operator": "OR",
                "conditions": [
                    {"field": "has_software", "op": "is_true", "value": True},
                    {"field": "has_cloud", "op": "is_true", "value": True},
                ]
            },
            "activates_control_ids": [],
            "priority": 30,
        },
        {
            "slug": "trigger-high-support-load",
            "name": "Hohe Supportlast erwartet",
            "description": "Aktiviert Service-Readiness und Kapazitätsplanung-Controls.",
            "condition_tree": {"field": "support_load", "op": "gte", "value": "high"},
            "activates_control_ids": [],
            "priority": 40,
        },
        {
            "slug": "trigger-b2c-mass-market",
            "name": "B2C Massenmarkt",
            "description": "Aktiviert verschärfte Sicherheits- und Compliance-Controls für Endverbraucher.",
            "condition_tree": {
                "operator": "AND",
                "conditions": [
                    {"field": "customer_segment", "op": "eq", "value": "b2c-mass"},
                    {"field": "market", "op": "in", "value": ["eu", "de", "uk"]},
                ]
            },
            "activates_control_ids": [],
            "priority": 50,
        },
        {
            "slug": "trigger-eu-battery-regulation",
            "name": "EU Battery Regulation (2023)",
            "description": "Aktiviert Batteriepass und erweiterte Traceability bei EU-Batteriespeichern.",
            "condition_tree": {
                "operator": "AND",
                "conditions": [
                    {"field": "has_battery", "op": "is_true", "value": True},
                    {"field": "market", "op": "in", "value": ["eu", "de", "at", "fr"]},
                ]
            },
            "activates_control_ids": [],
            "priority": 15,
        },
        {
            "slug": "trigger-new-supplier",
            "name": "Neue Lieferanten involviert",
            "description": "Aktiviert vollständige Lieferantenqualifizierung bei neuen Zulieferern.",
            "condition_tree": {"field": "new_suppliers", "op": "is_true", "value": True},
            "activates_control_ids": [],
            "priority": 25,
        },
        {
            "slug": "trigger-high-credit-risk",
            "name": "Hohes Kredit- oder Umsatzrisiko",
            "description": "Aktiviert Bonitäts- und Finanzrisiko-Controls.",
            "condition_tree": {
                "operator": "OR",
                "conditions": [
                    {"field": "credit_risk", "op": "gte", "value": "high"},
                    {"field": "revenue_risk", "op": "gte", "value": "high"},
                ]
            },
            "activates_control_ids": [],
            "priority": 35,
        },
    ]

    for t in triggers:
        if not await _get_or_none(db, DynamicTriggerRule, t["slug"]):
            db.add(DynamicTriggerRule(
                slug=t["slug"],
                name=t["name"],
                description=t.get("description"),
                condition_tree=t["condition_tree"],
                activates_control_ids=t["activates_control_ids"],
                priority=t.get("priority", 100),
                is_active=True,
                status=ControlStatus.approved.value,
            ))
    await db.flush()
