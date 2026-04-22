# app/services/capability_import_service.py
"""Capability map import: Excel parsing, validation, and node assembly."""
from __future__ import annotations

import io
import uuid
from typing import Any, Optional

from app.schemas.capability import ImportValidationResult, ImportIssue


def validate_rows(rows: list[dict[str, Any]]) -> ImportValidationResult:
    """Validate a list of flat import rows. Returns errors, warnings, and counts."""
    errors: list[ImportIssue] = []
    warnings: list[ImportIssue] = []

    seen_l2: set[str] = set()
    caps: set[str] = set()
    l1s: set[str] = set()
    l2s: set[str] = set()
    l3s: set[str] = set()

    for i, row in enumerate(rows):
        row_num = i + 2
        cap = (row.get("capability") or "").strip()
        l1 = (row.get("level_1") or "").strip()
        l2 = (row.get("level_2") or "").strip()
        l3 = (row.get("level_3") or "").strip() or None

        if not cap:
            errors.append(ImportIssue(level="error", message="Missing Capability title", row=row_num, field="capability"))
            continue

        if l2 and not l1:
            errors.append(ImportIssue(level="error", message=f"Level 2 '{l2}' has no Level 1 parent", row=row_num, field="level_1"))

        if l3 and not l2:
            errors.append(ImportIssue(level="error", message=f"Level 3 '{l3}' has no Level 2 parent", row=row_num, field="level_2"))

        caps.add(cap)
        if l1:
            l1s.add(f"{cap}||{l1}")
        if l2:
            key = f"{cap}||{l1}||{l2}"
            if key in seen_l2:
                warnings.append(ImportIssue(level="warning", message=f"Duplicate Level 2 '{l2}' under '{l1}'", row=row_num, field="level_2"))
            seen_l2.add(key)
            l2s.add(key)
        if l3:
            l3s.add(f"{cap}||{l1}||{l2}||{l3}")

    is_valid = len(errors) == 0
    nodes = build_nodes_from_rows(rows, source_type="import") if is_valid else []
    return ImportValidationResult(
        is_valid=is_valid,
        error_count=len(errors),
        warning_count=len(warnings),
        capability_count=len(caps),
        level_1_count=len(l1s),
        level_2_count=len(l2s),
        level_3_count=len(l3s),
        node_count=len(nodes),
        issues=errors + warnings,
        nodes=nodes,
        preview=_build_preview_tree(nodes),
    )


def build_nodes_from_rows(
    rows: list[dict[str, Any]], source_type: str = "excel"
) -> list[dict[str, Any]]:
    """Build a flat list of node dicts from import rows. Deduplicates by title path."""
    caps: dict[str, str] = {}
    l1s: dict[str, str] = {}
    l2s: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []

    for i, row in enumerate(rows):
        cap = (row.get("capability") or "").strip()
        l1 = (row.get("level_1") or "").strip()
        l2 = (row.get("level_2") or "").strip()
        l3 = (row.get("level_3") or "").strip() or None
        desc = (row.get("description") or "").strip() or None
        ext_key = row.get("external_key")
        is_active = bool(row.get("is_active", True))

        if not cap:
            continue

        if cap not in caps:
            tid = str(uuid.uuid4())
            caps[cap] = tid
            nodes.append({
                "id": tid,
                "node_type": "capability",
                "title": cap,
                "description": None,
                "parent_id": None,
                "sort_order": len(caps) - 1,
                "external_import_key": ext_key if not l1 else None,
                "source_type": source_type,
                "is_active": is_active,
            })

        if l1:
            l1_key = f"{cap}||{l1}"
            if l1_key not in l1s:
                tid = str(uuid.uuid4())
                l1s[l1_key] = tid
                nodes.append({
                    "id": tid,
                    "node_type": "level_1",
                    "title": l1,
                    "description": None,
                    "parent_id": caps[cap],
                    "sort_order": len(l1s) - 1,
                    "external_import_key": ext_key if not l2 else None,
                    "source_type": source_type,
                    "is_active": is_active,
                })

            if l2:
                l2_key = f"{cap}||{l1}||{l2}"
                if l2_key not in l2s:
                    tid = str(uuid.uuid4())
                    l2s[l2_key] = tid
                    nodes.append({
                        "id": tid,
                        "node_type": "level_2",
                        "title": l2,
                        "description": desc,
                        "parent_id": l1s[l1_key],
                        "sort_order": len(l2s) - 1,
                        "external_import_key": ext_key if not l3 else None,
                        "source_type": source_type,
                        "is_active": is_active,
                    })

                if l3:
                    tid = str(uuid.uuid4())
                    nodes.append({
                        "id": tid,
                        "node_type": "level_3",
                        "title": l3,
                        "description": desc,
                        "parent_id": l2s[l2_key],
                        "sort_order": i,
                        "external_import_key": ext_key,
                        "source_type": source_type,
                        "is_active": is_active,
                    })

    return nodes


def _build_preview_tree(flat_nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert flat node list (with id, parent_id) into nested tree dicts."""
    by_id: dict[str, dict[str, Any]] = {}
    for n in flat_nodes:
        node_id = n.get("id")
        if node_id:
            by_id[node_id] = {
                "id": node_id,
                "node_type": n["node_type"],
                "title": n["title"],
                "description": n.get("description"),
                "sort_order": n.get("sort_order", 0),
                "is_active": n.get("is_active", True),
                "children": [],
            }
    roots: list[dict[str, Any]] = []
    for n in flat_nodes:
        node_id = n.get("id")
        if not node_id or node_id not in by_id:
            continue
        parent_id = n.get("parent_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(by_id[node_id])
        else:
            roots.append(by_id[node_id])
    return roots


def parse_excel(file_bytes: bytes) -> ImportValidationResult:
    """Parse XLSX bytes and return validation result."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel import: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)
    try:
        header = [str(c).strip().lower() if c else "" for c in next(rows_iter)]
    except StopIteration:
        return ImportValidationResult(
            is_valid=False, error_count=1, warning_count=0,
            capability_count=0, level_1_count=0, level_2_count=0, level_3_count=0,
            issues=[ImportIssue(level="error", message="Excel file is empty or has no header row")],
        )

    col_aliases = {
        "capability": ["capability", "cap", "fähigkeit", "kompetenz"],
        "level_1": ["level1", "level 1", "l1", "prozess 1", "level_1", "lvl1"],
        "level_2": ["level2", "level 2", "l2", "prozess 2", "level_2", "lvl2"],
        "level_3": ["level3", "level 3", "l3", "prozess 3", "level_3", "lvl3"],
        "description": ["description", "beschreibung", "desc"],
        "external_key": ["external_key", "key", "import_key", "external key"],
        "is_active": ["is_active", "aktiv", "active"],
    }

    col_idx: dict[str, Optional[int]] = {}
    for field, aliases in col_aliases.items():
        idx = None
        for alias in aliases:
            try:
                idx = header.index(alias)
                break
            except ValueError:
                pass
        col_idx[field] = idx

    def _cell(row: tuple, field: str) -> Optional[str]:
        idx = col_idx.get(field)
        if idx is None or idx >= len(row):
            return None
        val = row[idx]
        return str(val).strip() if val is not None else None

    parsed_rows: list[dict[str, Any]] = []
    for row in rows_iter:
        if all(c is None for c in row):
            continue
        parsed_rows.append({
            "capability": _cell(row, "capability") or "",
            "level_1": _cell(row, "level_1"),
            "level_2": _cell(row, "level_2"),
            "level_3": _cell(row, "level_3"),
            "description": _cell(row, "description"),
            "external_key": _cell(row, "external_key"),
            "is_active": True,
        })

    wb.close()
    return validate_rows(parsed_rows)


# ── Demo / Template seeds ─────────────────────────────────────────────────────

DEMO_ROWS: list[dict[str, Any]] = [
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Cloud-Migration", "level_3": "Assessment", "description": "Bewertung der Cloud-Readiness", "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Cloud-Migration", "level_3": "Planung", "description": None, "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "IT-Strategie", "level_2": "Architektur", "level_3": None, "description": "Enterprise-Architektur", "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "Datenstrategie", "level_2": "Data Governance", "level_3": "Richtlinien", "description": None, "external_key": None, "is_active": True},
    {"capability": "Digitale Transformation", "level_1": "Datenstrategie", "level_2": "Analytics", "level_3": None, "description": "Business Intelligence & Reporting", "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Produktmanagement", "level_2": "Roadmap-Planung", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Produktmanagement", "level_2": "Anforderungsmanagement", "level_3": "User Stories", "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "Frontend", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "Backend", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Produkt & Entwicklung", "level_1": "Software-Entwicklung", "level_2": "QA & Testing", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "IT-Betrieb", "level_2": "Monitoring", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "IT-Betrieb", "level_2": "Deployment", "level_3": "CI/CD", "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "Sicherheit", "level_2": "Identity & Access", "level_3": None, "description": None, "external_key": None, "is_active": True},
    {"capability": "Betrieb & Infrastruktur", "level_1": "Sicherheit", "level_2": "Compliance", "level_3": "Audit", "description": None, "external_key": None, "is_active": True},
]

TEMPLATE_ROWS: dict[str, list[dict[str, Any]]] = {
    "software_product": [
        {"capability": "Strategie", "level_1": "Produktvision", "level_2": "Roadmap", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Strategie", "level_1": "Markt & Wettbewerb", "level_2": "Marktanalyse", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Frontend", "level_2": "UI/UX", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Backend", "level_2": "API", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Entwicklung", "level_1": "Backend", "level_2": "Datenbank", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Betrieb", "level_1": "DevOps", "level_2": "CI/CD", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Betrieb", "level_1": "Support", "level_2": "Kundensupport", "level_3": None, "description": None, "external_key": None, "is_active": True},
    ],
    "it_operations": [
        {"capability": "Infrastruktur", "level_1": "Server & Netzwerk", "level_2": "Netzwerk", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Infrastruktur", "level_1": "Cloud", "level_2": "AWS", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Sicherheit", "level_1": "Identity & Access", "level_2": "SSO", "level_3": None, "description": None, "external_key": None, "is_active": True},
        {"capability": "Sicherheit", "level_1": "Compliance", "level_2": "Audit", "level_3": None, "description": None, "external_key": None, "is_active": True},
    ],
    "energy_utility": [
        # ── Erzeugung & Beschaffung ──────────────────────────────────────────────
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Konventionelle Erzeugung", "level_3": "Gas & Dampf (GuD)", "description": "Kombinierte Gas- und Dampfturbinenkraftwerke", "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Konventionelle Erzeugung", "level_3": "Pumpspeicher", "description": "Kurzzeitige Flexibilität und Regelenergie", "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Konventionelle Erzeugung", "level_3": "Biomasse / KWK", "description": "Kraft-Wärme-Kopplung mit biogenen Brennstoffen", "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Erneuerbare Energien", "level_3": "Wind Onshore", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Erneuerbare Energien", "level_3": "Wind Offshore", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Erneuerbare Energien", "level_3": "Solar / PV", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Stromerzeugung", "level_2": "Erneuerbare Energien", "level_3": "Wasserkraft", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Wärmeerzeugung", "level_2": "Fernwärme", "level_3": "Wärmenetz", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Wärmeerzeugung", "level_2": "Fernwärme", "level_3": "Wärmespeicher", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Energiebeschaffung", "level_2": "Portfoliomanagement", "level_3": "Optimierung Erzeugungsmix", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Energiebeschaffung", "level_2": "Brennstoffbeschaffung", "level_3": "Gasversorgung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Erzeugung & Beschaffung", "level_1": "Energiebeschaffung", "level_2": "Brennstoffbeschaffung", "level_3": "Biomasse-Logistik", "description": None, "external_key": None, "is_active": True},
        # ── Handel & Märkte ───────────────────────────────────────────────────────
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Spotmarkt", "level_3": "Day-Ahead (EPEX)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Spotmarkt", "level_3": "Intraday (kontinuierlich)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Regelenergiemarkt", "level_3": "Primärregelleistung (FCR)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Regelenergiemarkt", "level_3": "Sekundärregelleistung (aFRR)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Terminmarkt", "level_3": "Forwards & Futures", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Energiehandel", "level_2": "Terminmarkt", "level_3": "Optionen & Strukturierte Produkte", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Risikomanagement", "level_2": "Marktpreisrisiko", "level_3": "Value-at-Risk (VaR)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Risikomanagement", "level_2": "Mengenrisiko", "level_3": "Prognoseabweichung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Risikomanagement", "level_2": "Gegenparteirisiko", "level_3": "Kreditlimitmanagement", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Bilanzkreismanagement", "level_2": "Fahrplanmanagement", "level_3": "Einspeise- & Abnahmefahrpläne", "description": None, "external_key": None, "is_active": True},
        {"capability": "Handel & Märkte", "level_1": "Bilanzkreismanagement", "level_2": "Ausgleichsenergie", "level_3": "Bilanzkreisabrechnung (BKA)", "description": None, "external_key": None, "is_active": True},
        # ── Netz & Infrastruktur ──────────────────────────────────────────────────
        {"capability": "Netz & Infrastruktur", "level_1": "Netzbetrieb", "level_2": "Übertragungsnetz", "level_3": "Systemführung & Dispatch", "description": "Hochspannungs-Leitstelle", "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzbetrieb", "level_2": "Übertragungsnetz", "level_3": "Engpassmanagement", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzbetrieb", "level_2": "Verteilnetz", "level_3": "Mittelspannung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzbetrieb", "level_2": "Verteilnetz", "level_3": "Niederspannung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzplanung", "level_2": "Investitionsplanung", "level_3": "Netzentwicklungsplan", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzplanung", "level_2": "Kapazitätsplanung", "level_3": "Lastprognose", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Netzplanung", "level_2": "Anschlussmanagement", "level_3": "Einspeiseanschlüsse (EE)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Smart Grid", "level_2": "Smart Metering", "level_3": "Intelligente Messsysteme (iMSys)", "description": "MsbG-konformer Rollout", "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Smart Grid", "level_2": "Smart Metering", "level_3": "Datenvalidierung & Plausibilisierung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Smart Grid", "level_2": "Netzautomatisierung", "level_3": "SCADA / EMS", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Smart Grid", "level_2": "Netzautomatisierung", "level_3": "Fernwirktechnik & IEC 61850", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Instandhaltung", "level_2": "Wartungsmanagement", "level_3": "Präventive Wartung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Netz & Infrastruktur", "level_1": "Instandhaltung", "level_2": "Störungsmanagement", "level_3": "Entstörung & Wiederversorgung", "description": None, "external_key": None, "is_active": True},
        # ── Vertrieb & Kundenservice ──────────────────────────────────────────────
        {"capability": "Vertrieb & Kundenservice", "level_1": "Kundenverwaltung", "level_2": "Vertragsmanagement", "level_3": "Neukundengewinnung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Kundenverwaltung", "level_2": "Vertragsmanagement", "level_3": "Vertragsverlängerung & Kündigung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Kundenverwaltung", "level_2": "Kundenkommunikation", "level_3": "Beschwerdemanagement", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Kundenverwaltung", "level_2": "Kundenkommunikation", "level_3": "Self-Service-Portal", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Abrechnung", "level_2": "Messstellenbetrieb", "level_3": "Zählerablesung & -wechsel", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Abrechnung", "level_2": "Messstellenbetrieb", "level_3": "EDIFACT-Marktkommunikation", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Abrechnung", "level_2": "Rechnungsstellung", "level_3": "Jahresabrechnung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Abrechnung", "level_2": "Rechnungsstellung", "level_3": "Abschlags- & Vorauszahlungsplanung", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Produktmanagement", "level_2": "Tarifgestaltung", "level_3": "Privat- & Gewerbekunden", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Produktmanagement", "level_2": "Ökostromprodukte", "level_3": "Herkunftsnachweise (HKN)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Produktmanagement", "level_2": "Neue Energiedienstleistungen", "level_3": "Wärme-Contracting", "description": None, "external_key": None, "is_active": True},
        {"capability": "Vertrieb & Kundenservice", "level_1": "Produktmanagement", "level_2": "Neue Energiedienstleistungen", "level_3": "Ladelösungen Elektromobilität", "description": None, "external_key": None, "is_active": True},
        # ── Regulierung & Compliance ──────────────────────────────────────────────
        {"capability": "Regulierung & Compliance", "level_1": "Regulatorisches Management", "level_2": "Behördenkommunikation", "level_3": "Bundesnetzagentur (BNetzA)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Regulatorisches Management", "level_2": "Behördenkommunikation", "level_3": "Landesregulierungsbehörden", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Regulatorisches Management", "level_2": "Netzentgelte", "level_3": "Anreizregulierung (ARegV)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Regulatorisches Management", "level_2": "Netzentgelte", "level_3": "Genehmigungsverfahren", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Compliance", "level_2": "Energierecht", "level_3": "EnWG & Netzzugangsverordnungen", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Compliance", "level_2": "Energierecht", "level_3": "EEG / KWKG / WindSeeG", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Compliance", "level_2": "IT-Sicherheit & KRITIS", "level_3": "KRITIS-Schutz (IT-SiG 2.0)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Compliance", "level_2": "IT-Sicherheit & KRITIS", "level_3": "ISMS (ISO 27001 / IEC 62443)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Reporting", "level_2": "Markttransparenz", "level_3": "REMIT-Meldepflichten", "description": None, "external_key": None, "is_active": True},
        {"capability": "Regulierung & Compliance", "level_1": "Reporting", "level_2": "Nachhaltigkeitsreporting", "level_3": "ESG & CSRD-Berichterstattung", "description": None, "external_key": None, "is_active": True},
        # ── Nachhaltigkeit & Energiewende ─────────────────────────────────────────
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Dekarbonisierung", "level_2": "CO₂-Management", "level_3": "EU-Emissionshandel (ETS)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Dekarbonisierung", "level_2": "CO₂-Management", "level_3": "Corporate Carbon Footprint", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Dekarbonisierung", "level_2": "Power-to-X", "level_3": "Grüner Wasserstoff", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Dekarbonisierung", "level_2": "Power-to-X", "level_3": "Elektromobilität & Ladeinfrastruktur", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "EE-Projektentwicklung", "level_2": "Genehmigungsmanagement", "level_3": "Standortentwicklung & BImSchV", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "EE-Projektentwicklung", "level_2": "Projektfinanzierung", "level_3": "PPA (Power Purchase Agreement)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "EE-Projektentwicklung", "level_2": "Projektfinanzierung", "level_3": "Fördermittel & Zuschüsse", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Asset Management", "level_2": "Bestandsanlagen", "level_3": "Repowering Wind & Solar", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Asset Management", "level_2": "Speichertechnologien", "level_3": "Batteriespeicher (BESS)", "description": None, "external_key": None, "is_active": True},
        {"capability": "Nachhaltigkeit & Energiewende", "level_1": "Asset Management", "level_2": "Speichertechnologien", "level_3": "Sektorenkopplung", "description": "Wärme, Mobilität, Industrie", "external_key": None, "is_active": True},
    ],
}


def get_demo_nodes(source_type: str = "demo") -> list[dict[str, Any]]:
    return build_nodes_from_rows(DEMO_ROWS, source_type=source_type)


def get_template_nodes(template_key: str) -> list[dict[str, Any]]:
    rows = TEMPLATE_ROWS.get(template_key, [])
    if not rows:
        raise ValueError(f"Unknown template: {template_key}. Available: {list(TEMPLATE_ROWS.keys())}")
    return build_nodes_from_rows(rows, source_type="template")


def list_templates() -> list[dict]:
    meta: dict[str, dict] = {
        "software_product": {"label": "Software-Produkt", "description": "Strategie, Entwicklung, Betrieb"},
        "it_operations":    {"label": "IT-Betrieb",       "description": "Infrastruktur, Sicherheit"},
        "energy_utility":   {"label": "Energiewirtschaft", "description": "Erzeugung, Handel, Netz, Vertrieb, Regulierung"},
    }
    return [
        {
            "key": key,
            "label": meta[key]["label"],
            "description": meta[key]["description"],
            "node_count": len(rows),
        }
        for key, rows in TEMPLATE_ROWS.items()
    ]
