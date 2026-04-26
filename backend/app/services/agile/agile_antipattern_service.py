# app/services/agile/agile_antipattern_service.py
"""
Agile Anti-Pattern Detector for HeyKarl.

Analyses project signals and identifies known failure modes
across Scrum, Kanban and hybrid delivery models.

Designed to surface problems early — as proactive warnings in the
workspace, not post-mortems.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.services.agile.agile_recommendation_service import ProjectContext


@dataclass
class AntiPattern:
    id:          str
    name:        str
    method:      str            # "scrum" | "kanban" | "scrumban" | "general"
    severity:    Literal["warning", "critical"]
    description: str
    signal:      str            # what triggers detection
    fix:         str            # concrete corrective action
    heykarl_link: str = ""      # which HeyKarl element is affected


# ── Anti-pattern catalogue ────────────────────────────────────────────────────

ANTI_PATTERNS: list[AntiPattern] = [
    # ── SCRUM ────────────────────────────────────────────────────────────────
    AntiPattern(
        id="scrum_no_product_goal",
        name="Scrum ohne Produktziel",
        method="scrum",
        severity="critical",
        description=(
            "Das Team arbeitet in Sprints, aber es gibt kein übergeordnetes Produktziel. "
            "Sprints werden zur Aufgabenliste ohne strategischen Bezug."
        ),
        signal="has_clear_product_goal is False or project_type != 'product'",
        fix=(
            "Definiere ein konkretes Produktziel (Product Goal) bevor Sprints beginnen. "
            "Sprint Goals müssen sich darauf beziehen. "
            "Ohne Produktziel fehlt dem Product Owner die Grundlage für Backlog-Priorisierung."
        ),
        heykarl_link="Capability / Epic level",
    ),
    AntiPattern(
        id="scrum_daily_status_meeting",
        name="Daily als Statusmeeting",
        method="scrum",
        severity="warning",
        description=(
            "Das Daily Scrum wird als Statusbericht für Management genutzt. "
            "Teammitglieder berichten 'an' jemanden statt miteinander zu koordinieren."
        ),
        signal="management_in_daily signal OR daily>15min signal",
        fix=(
            "Daily ist ein Team-Event für Entwickler. "
            "Management darf beobachten aber nicht teilnehmen oder Fragen stellen. "
            "Fokus: Was hindert uns am Sprint Goal? Nicht: Was habe ich gestern gemacht?"
        ),
        heykarl_link="ProcessStep: Daily Scrum",
    ),
    AntiPattern(
        id="scrum_no_dod",
        name="Keine Definition of Done",
        method="scrum",
        severity="critical",
        description=(
            "Es gibt keine formale DoD. 'Fertig' bedeutet für jeden etwas anderes. "
            "Qualität ist subjektiv und nicht reproduzierbar."
        ),
        signal="no governance elements with 'definition of done'",
        fix=(
            "Erstelle eine schriftliche, für alle verbindliche Definition of Done "
            "BEVOR das erste Sprint Review stattfindet. "
            "Mindestinhalt: Code reviewed, Tests passed, deployed to staging, PO accepted."
        ),
        heykarl_link="GovernanceElement: Definition of Done",
    ),
    AntiPattern(
        id="scrum_retro_no_actions",
        name="Retrospektive ohne Umsetzungsfolgen",
        method="scrum",
        severity="warning",
        description=(
            "Die Retrospektive findet statt, aber keine Verbesserungsmaßnahmen werden umgesetzt. "
            "Gleiche Probleme werden Sprint für Sprint genannt."
        ),
        signal="recurring issues in retrospective OR no improvement items in next Sprint Backlog",
        fix=(
            "Jede Retrospektive muss mit mindestens einem konkreten, messbaren Verbesserungsitem enden, "
            "das im nächsten Sprint Backlog landet. "
            "Scrum Master ist verantwortlich für Follow-through."
        ),
        heykarl_link="ProcessStep: Sprint Retrospective",
    ),
    AntiPattern(
        id="scrum_oversize_team",
        name="Team zu groß für Scrum",
        method="scrum",
        severity="warning",
        description=(
            "Das Scrum-Team hat mehr als 9 Mitglieder. "
            "Daily wird unhandlich, Sprint Planning dauert Stunden, Koordinationsaufwand wächst exponentiell."
        ),
        signal="team_size > 9",
        fix=(
            "Teile das Team in 2 oder mehr Scrum-Teams auf (3–9 Personen je Team). "
            "Führe ein Koordinationsmodell ein: Scrum of Scrums oder Nexus-Framework. "
            "Shared Backlog oder separate Backlogs mit klarer Abstimmungslogik definieren."
        ),
        heykarl_link="TeamPattern: Multi-Team Coordination",
    ),
    AntiPattern(
        id="scrum_po_unavailable",
        name="Product Owner nicht verfügbar",
        method="scrum",
        severity="critical",
        description=(
            "Der Product Owner ist im Sprint kaum erreichbar. "
            "Team trifft Priorisierungsentscheidungen selbst oder wartet auf Feedback."
        ),
        signal="has_product_owner is False OR PO availability < 50%",
        fix=(
            "Der Product Owner muss dem Team mindestens 50% seiner Zeit widmen können. "
            "Ohne verfügbaren PO ist Scrum nicht funktionsfähig — "
            "prüfe Kanban als Alternative oder weise die PO-Verantwortung eindeutig zu."
        ),
        heykarl_link="Role: Product Owner",
    ),
    AntiPattern(
        id="scrum_backlog_no_priority",
        name="Backlog ohne Priorisierungslogik",
        method="scrum",
        severity="warning",
        description=(
            "Das Product Backlog hat Hunderte von Items ohne klare Reihenfolge. "
            "Sprint Planning wird zum Diskussionsmarathon ohne Ergebnis."
        ),
        signal="backlog size >> team velocity without clear ordering",
        fix=(
            "Der Product Owner muss das Backlog nach Wert priorisieren. "
            "Maximal die obersten 2–3 Sprints müssen detailliert und refiniert sein. "
            "Darunter: Epics und grobe Ideen reichen. "
            "Priorisierungskriterien explizit definieren (z.B. WSJF, MoSCoW, Business Value)."
        ),
        heykarl_link="Artifact: Product Backlog",
    ),

    # ── KANBAN ────────────────────────────────────────────────────────────────
    AntiPattern(
        id="kanban_no_wip_limits",
        name="Kanban-Board ohne WIP-Limits",
        method="kanban",
        severity="critical",
        description=(
            "Ein Kanban-Board wird genutzt, aber es gibt keine WIP-Limits. "
            "Das ist kein Kanban — das ist ein digitales Post-It-Board. "
            "Multitasking bleibt unkontrolliert, Bottlenecks werden nicht sichtbar."
        ),
        signal="using kanban board BUT no wip_limit flow_rule defined",
        fix=(
            "Definiere WIP-Limits für jede Spalte SOFORT. "
            "Startpunkt: WIP-Limit = Anzahl Teammitglieder (oder weniger). "
            "Wenn eine Spalte voll ist, zieht niemand neue Arbeit — finish before start."
        ),
        heykarl_link="FlowRule: WIP Limit",
    ),
    AntiPattern(
        id="kanban_no_flow_metrics",
        name="Kein Flow-Monitoring",
        method="kanban",
        severity="warning",
        description=(
            "Das Team nutzt ein Kanban-Board, misst aber keine Flow-Metriken. "
            "Verbesserungen basieren auf Bauchgefühl statt auf Daten."
        ),
        signal="no cycle time OR throughput tracked",
        fix=(
            "Beginne mit Cycle Time und Throughput als Mindestmetriken. "
            "Wöchentlicher Flow Review mit Cumulative Flow Diagram. "
            "Aging Work Items aufzeigen: Items älter als 2× durchschnittliche Cycle Time eskalieren."
        ),
        heykarl_link="Artifact: Flow Metrics",
    ),
    AntiPattern(
        id="kanban_push_not_pull",
        name="Push statt Pull — keine Pull-Kultur",
        method="kanban",
        severity="warning",
        description=(
            "Arbeit wird dem Team zugeteilt (push) statt vom Team gezogen (pull). "
            "WIP-Limits werden ignoriert, wenn jemand Arbeit 'dringend' zuweist."
        ),
        signal="work assigned by external party without replenishment meeting",
        fix=(
            "Führe ein wöchentliches Replenishment Meeting ein. "
            "Nur dort wird neue Arbeit authorisiert. "
            "Expedite-Klasse für echte Notfälle definieren — aber konservativ einsetzen."
        ),
        heykarl_link="Event: Replenishment Meeting",
    ),

    # ── GENERAL ───────────────────────────────────────────────────────────────
    AntiPattern(
        id="general_no_retrospective",
        name="Kein kontinuierlicher Verbesserungsprozess",
        method="general",
        severity="warning",
        description=(
            "Das Team hat keine regelmäßige Retrospektive oder Review-Routine. "
            "Probleme akkumulieren ohne Reflexions- und Verbesserungsschleife."
        ),
        signal="no retrospective in method events",
        fix=(
            "Etabliere mindestens alle 2–4 Wochen eine Retrospektive oder Teamreview. "
            "Auch Kanban-Teams brauchen einen Kaizen-Rhythmus — z.B. wöchentlicher Flow Review mit Verbesserungsblock."
        ),
        heykarl_link="ProcessStep: Retrospective / Kaizen",
    ),
    AntiPattern(
        id="general_no_role_clarity",
        name="Fehlende Rollenklarheit",
        method="general",
        severity="critical",
        description=(
            "Priorisierungsverantwortung, Teamleitung und Delivery-Verantwortung sind nicht klar verteilt. "
            "Niemand fühlt sich verantwortlich, alle fühlen sich zuständig."
        ),
        signal="has_product_owner is None OR roles not defined",
        fix=(
            "Kläre vor Projektstart: Wer entscheidet über Priorität? "
            "Wer ist verantwortlich für die Qualität des Lieferergebnisses? "
            "Wer hilft dem Team, Hindernisse zu überwinden? "
            "Diese drei Fragen müssen beantwortet sein — unabhängig vom gewählten Framework."
        ),
        heykarl_link="Role: Product Owner / Scrum Master",
    ),
    AntiPattern(
        id="general_multiteam_no_coordination",
        name="Mehrere Teams ohne Koordinationsmodell",
        method="general",
        severity="critical",
        description=(
            "Mehr als ein Team arbeitet an denselben Produkten oder teilt Abhängigkeiten, "
            "aber es gibt keine formale Koordinationslogik. "
            "Abhängigkeiten werden ad-hoc in Chats koordiniert."
        ),
        signal="num_teams > 1 AND cross_team_dependencies in ('medium', 'high')",
        fix=(
            "Führe ein explizites Koordinationsmodell ein: "
            "Scrum of Scrums (wöchentlich), gemeinsames Backlog-Review, oder PI Planning für größere Strukturen. "
            "Abhängigkeiten im Backlog explizit markieren und priorisieren."
        ),
        heykarl_link="TeamPattern: Multi-Team Coordination",
    ),
    AntiPattern(
        id="general_sprints_with_high_unplanned",
        name="Sprints mit dauerhaft hohem Unplanned-Anteil",
        method="general",
        severity="warning",
        description=(
            "Das Team arbeitet in Sprints, hat aber dauerhaft >30% ungeplante Aufgaben, "
            "die den Sprint stören. Sprint Goals werden systematisch verfehlt."
        ),
        signal="cadence_preference='sprint' AND unplanned_work_ratio='high'",
        fix=(
            "Drei Optionen: "
            "1. Sprint-Buffer: 30% Kapazität explizit für Unplanned reservieren. "
            "2. Separate Kanban-Lane für Bugs/Support neben dem Sprint. "
            "3. Wechsel zu Scrumban oder Kanban, wenn Sprints strukturell nicht funktionieren."
        ),
        heykarl_link="FlowRule: Sprint Buffer",
    ),
]


# ── Detector ──────────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    detected:   list[AntiPattern]
    summary:    str

    def to_dict(self) -> dict:
        return {
            "detected": [
                {
                    "id": ap.id,
                    "name": ap.name,
                    "severity": ap.severity,
                    "description": ap.description,
                    "fix": ap.fix,
                    "heykarl_link": ap.heykarl_link,
                }
                for ap in self.detected
            ],
            "summary": self.summary,
        }

    def to_chat_warning(self) -> str:
        if not self.detected:
            return ""
        criticals = [ap for ap in self.detected if ap.severity == "critical"]
        warnings   = [ap for ap in self.detected if ap.severity == "warning"]
        lines = ["**Erkannte Risiken für eure Vorgehensweise:**", ""]
        for ap in criticals:
            lines.append(f"🔴 **{ap.name}**")
            lines.append(f"   {ap.description}")
            lines.append(f"   → *{ap.fix}*")
            lines.append("")
        for ap in warnings:
            lines.append(f"⚠️ **{ap.name}**")
            lines.append(f"   → *{ap.fix}*")
            lines.append("")
        return "\n".join(lines)


class AgileAntiPatternDetector:
    """
    Detects anti-patterns from ProjectContext and free-text signals.
    Returns prioritised list of detected anti-patterns with fixes.
    """

    def detect(
        self,
        ctx: ProjectContext,
        active_method: str = "",
        free_text: str = "",
    ) -> DetectionResult:
        detected: list[AntiPattern] = []

        for ap in ANTI_PATTERNS:
            if self._matches(ap, ctx, active_method, free_text):
                detected.append(ap)

        # Sort: critical first
        detected.sort(key=lambda x: (0 if x.severity == "critical" else 1, x.id))

        summary = self._summarise(detected)
        return DetectionResult(detected=detected, summary=summary)

    def detect_from_text(self, text: str) -> list[AntiPattern]:
        """Quick text-based detection for chat input analysis."""
        detected: list[AntiPattern] = []
        text_lower = text.lower()

        text_signals = {
            "scrum_no_product_goal": ["kein ziel", "keine vision", "einfach anfangen", "wir wissen noch nicht was"],
            "scrum_daily_status_meeting": ["tagesupdate", "status meeting", "was habe ich gestern", "daily report"],
            "scrum_no_dod": ["done bedeutet", "irgendwie fertig", "das entscheiden wir dann", "kein kriterium"],
            "scrum_retro_no_actions": ["retro ohne ergebnis", "immer die gleichen probleme", "retro ist sinnlos"],
            "kanban_no_wip_limits": ["kein wip limit", "ohne wip limit", "wip ohne limit", "einfach board", "übersicht haben", "board ohne wip"],
            "kanban_no_flow_metrics": ["kein tracking", "wir sehen es schon", "keine messung", "bauchgefühl"],
            "kanban_push_not_pull": ["wird zugewiesen", "bekomme ich zugeteilt", "andere geben mir", "push"],
            "general_no_role_clarity": ["wer entscheidet", "unklar wer", "niemand verantwortlich", "alle zuständig"],
        }

        for ap_id, keywords in text_signals.items():
            if any(kw in text_lower for kw in keywords):
                ap = next((a for a in ANTI_PATTERNS if a.id == ap_id), None)
                if ap and ap not in detected:
                    detected.append(ap)

        return detected

    def _matches(
        self, ap: AntiPattern, ctx: ProjectContext, active_method: str, free_text: str
    ) -> bool:
        if ap.id == "scrum_no_product_goal":
            return (ctx.has_clear_product_goal is False or
                    (ctx.project_type not in ("product", None) and active_method == "scrum"))
        if ap.id == "scrum_oversize_team":
            return ctx.team_size is not None and ctx.team_size > 9
        if ap.id == "scrum_po_unavailable":
            return ctx.has_product_owner is False
        if ap.id == "kanban_no_wip_limits":
            return active_method == "kanban" and "wip" not in free_text.lower()
        if ap.id == "general_no_role_clarity":
            return ctx.has_product_owner is None and not free_text
        if ap.id == "general_multiteam_no_coordination":
            return (ctx.num_teams or 1) > 1 and ctx.cross_team_dependencies in ("medium", "high")
        if ap.id == "general_sprints_with_high_unplanned":
            return (ctx.cadence_preference == "sprint" and
                    ctx.unplanned_work_ratio == "high")
        if ap.id == "general_no_retrospective":
            return active_method == "kanban" and "retro" not in free_text.lower()

        # Text-based signals from description
        if free_text:
            return any(kw in free_text.lower() for kw in ap.signal.split(" OR "))
        return False

    def _summarise(self, detected: list[AntiPattern]) -> str:
        if not detected:
            return "Keine Risiken erkannt — Setup sieht strukturell solide aus."
        critical = sum(1 for ap in detected if ap.severity == "critical")
        warnings = sum(1 for ap in detected if ap.severity == "warning")
        parts = []
        if critical:
            parts.append(f"{critical} kritische{'s' if critical == 1 else ''} Risiko{'' if critical == 1 else 's'}")
        if warnings:
            parts.append(f"{warnings} Hinweis{'' if warnings == 1 else 'e'}")
        return f"Erkannte Risiken: {', '.join(parts)}. Bitte vor Projektstart adressieren."
