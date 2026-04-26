# app/services/agile/agile_recommendation_service.py
"""
Agile Project Setup Recommendation Engine for HeyKarl.

Takes project context signals and derives a concrete, reasoned
recommendation for method, roles, artifacts, events and governance.

Deliberately pragmatic — no method is dogmatically preferred.
Output is structured for chat rendering and HeyKarl domain integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.services.agile.agile_knowledge import (
    METHODS,
    MethodId,
    get_artifacts_for_method,
    get_events_for_method,
    get_roles_for_method,
)


# ── Input model ───────────────────────────────────────────────────────────────

@dataclass
class ProjectContext:
    """
    Context signals provided by the user / collected via chat dialog.
    All fields optional — engine handles missing data gracefully.
    """
    project_type: Literal["product", "service", "initiative", "mixed"] | None = None

    team_size: int | None = None
    # 1-3: tiny, 4-7: ideal Scrum, 8-12: larger, 12+: multiple teams needed

    requirement_stability: Literal["low", "medium", "high"] | None = None
    # low = evolving/unknown, high = fully specified upfront

    unplanned_work_ratio: Literal["low", "medium", "high"] | None = None
    # low <20%, medium 20–50%, high >50% of team capacity

    operations_proximity: Literal["none", "partial", "high"] | None = None
    # none = pure product dev, high = mostly support/ops

    innovation_degree: Literal["low", "medium", "high"] | None = None
    # high = new territory, low = known domain

    num_teams: int | None = None
    # 1 = single team, 2+ = multi-team coordination needed

    cross_team_dependencies: Literal["low", "medium", "high"] | None = None

    regulatory_burden: Literal["low", "medium", "high"] | None = None
    # high = audit trails, formal documentation, sign-offs required

    cadence_preference: Literal["sprint", "continuous", "no_preference"] | None = None
    # explicit user preference

    has_product_owner: bool | None = None
    has_clear_product_goal: bool | None = None

    # Free-form description (used for context in prompt)
    description: str = ""


# ── Output model ──────────────────────────────────────────────────────────────

@dataclass
class ProjectSetupRecommendation:
    """
    Full project setup recommendation — structured for JSON output and chat rendering.
    Matches the spec-required schema with full reasoning.
    """
    recommended_method:         MethodId
    recommended_operating_model: str
    reasoning:                  list[str]
    roles:                      list[dict]
    artifacts:                  list[dict]
    events:                     list[dict]
    flow_rules:                 list[dict]
    governance_elements:        list[dict]
    project_setup: dict = field(default_factory=dict)
    risks:                      list[str] = field(default_factory=list)
    alternatives:               list[dict] = field(default_factory=list)
    clarifying_questions:       list[str] = field(default_factory=list)
    confidence:                 Literal["high", "medium", "low"] = "medium"

    def to_dict(self) -> dict:
        return {
            "recommended_method":          self.recommended_method,
            "recommended_operating_model": self.recommended_operating_model,
            "reasoning":                   self.reasoning,
            "roles":                       self.roles,
            "artifacts":                   self.artifacts,
            "events":                      self.events,
            "flow_rules":                  self.flow_rules,
            "governance_elements":         self.governance_elements,
            "project_setup":               self.project_setup,
            "risks":                       self.risks,
            "alternatives":                self.alternatives,
            "clarifying_questions":        self.clarifying_questions,
            "confidence":                  self.confidence,
        }

    def to_chat_summary(self) -> str:
        """Human-readable summary for chat rendering."""
        lines = [
            f"**Empfohlene Vorgehensweise: {METHODS[self.recommended_method].name}**",
            f"_{self.recommended_operating_model}_",
            "",
            "**Begründung:**",
        ]
        for r in self.reasoning:
            lines.append(f"- {r}")

        if self.roles:
            lines.append("")
            lines.append(f"**Empfohlene Rollen:** {', '.join(r['name'] for r in self.roles)}")

        if self.events:
            lines.append(f"**Empfohlene Meetings:** {', '.join(e['name'] for e in self.events)}")

        if self.artifacts:
            lines.append(f"**Empfohlene Artefakte:** {', '.join(a['name'] for a in self.artifacts)}")

        if self.risks:
            lines.append("")
            lines.append("**Risiken / auf die ihr achten solltet:**")
            for risk in self.risks[:3]:
                lines.append(f"- ⚠ {risk}")

        if self.alternatives:
            lines.append("")
            lines.append("**Alternativen:**")
            for alt in self.alternatives:
                lines.append(f"- **{alt['method']}**: {alt['when']}")

        if self.clarifying_questions:
            lines.append("")
            lines.append("**Noch offen — ich würde gerne verstehen:**")
            for q in self.clarifying_questions[:3]:
                lines.append(f"- {q}")

        return "\n".join(lines)


# ── Scoring logic ─────────────────────────────────────────────────────────────

@dataclass
class _MethodScore:
    method_id: MethodId
    score:     float
    reasons:   list[str] = field(default_factory=list)


def _score_scrum(ctx: ProjectContext) -> _MethodScore:
    score = 0.0
    reasons: list[str] = []

    if ctx.project_type == "product":
        score += 25
        reasons.append("Produktfokus ist ideal für Scrums inkrementelle Lieferlogik")
    if ctx.team_size is not None and 3 <= ctx.team_size <= 9:
        score += 20
        reasons.append(f"Teamgröße ({ctx.team_size} Personen) liegt im optimalen Scrum-Bereich (3–9)")
    if ctx.requirement_stability == "low":
        score += 15
        reasons.append("Unsichere Anforderungen profitieren von Scrums Inspect-&-Adapt-Zyklus")
    if ctx.innovation_degree == "high":
        score += 10
        reasons.append("Hohes Innovationsgrad passt zu iterativer Entdeckung im Sprint")
    if ctx.has_product_owner:
        score += 10
        reasons.append("Product Owner vorhanden — Scrum-Rolle besetzbar")
    if ctx.has_clear_product_goal:
        score += 10
        reasons.append("Klares Produktziel ermöglicht sinnvolle Sprint Goals")
    if ctx.cadence_preference == "sprint":
        score += 10
        reasons.append("Explizite Präferenz für Sprint-Taktung")
    if ctx.unplanned_work_ratio == "high":
        score -= 20
        reasons.append("Hoher Anteil ungeplanter Arbeit macht Sprint-Planung schwierig")
    if ctx.operations_proximity == "high":
        score -= 15
        reasons.append("Starke Betriebsnähe passt weniger zu Scrum als zu Kanban")
    if ctx.team_size is not None and ctx.team_size > 9:
        score -= 10
        reasons.append(f"Teamgröße ({ctx.team_size} Personen) überschreitet Scrum-Optimum (max. 9) — Koordinationsmodell prüfen")

    return _MethodScore("scrum", score, reasons)


def _score_kanban(ctx: ProjectContext) -> _MethodScore:
    score = 0.0
    reasons: list[str] = []

    if ctx.project_type == "service":
        score += 25
        reasons.append("Service-/Betriebsteam profitiert von Kanbans Continuous-Flow-Ansatz")
    if ctx.operations_proximity == "high":
        score += 25
        reasons.append("Hohe Betriebsnähe — Kanban optimal für kontinuierlichen Arbeitsfluss")
    if ctx.unplanned_work_ratio == "high":
        score += 20
        reasons.append("Viele ungeplante Aufgaben — Kanban-Pull statt Sprint-Planung geeigneter")
    if ctx.cadence_preference == "continuous":
        score += 15
        reasons.append("Explizite Präferenz für kontinuierlichen Fluss")
    if ctx.requirement_stability == "high":
        score += 10
        reasons.append("Stabile, bekannte Arbeit passt gut zu Kanban-Optimierung")
    if ctx.has_clear_product_goal is False:
        score += 10
        reasons.append("Kein klares Produktziel — Kanban ohne Produktziel-Zwang geeigneter")
    if ctx.project_type == "product" and ctx.innovation_degree == "high":
        score -= 10
        reasons.append("Innovative Produktentwicklung profitiert mehr von Scrum-Iteration")

    return _MethodScore("kanban", score, reasons)


def _score_scrumban(ctx: ProjectContext) -> _MethodScore:
    score = 0.0
    reasons: list[str] = []

    if ctx.unplanned_work_ratio == "medium":
        score += 20
        reasons.append("Mittlerer Anteil ungeplanter Arbeit — Scrumban kombiniert beide Welten")
    if ctx.operations_proximity == "partial":
        score += 20
        reasons.append("Teils Produkt, teils Betrieb — hybrides Modell sinnvoll")
    if ctx.project_type == "mixed":
        score += 25
        reasons.append("Gemischter Projekttyp spricht direkt für Scrumban")
    if ctx.cadence_preference == "sprint" and ctx.unplanned_work_ratio in ("medium", "high"):
        score += 10
        reasons.append("Sprint-Präferenz bei gleichzeitig hoher Unplanbarkeit → Scrumban als Kompromiss")

    return _MethodScore("scrumban", score, reasons)


def _determine_confidence(ctx: ProjectContext) -> Literal["high", "medium", "low"]:
    filled = sum([
        ctx.project_type is not None,
        ctx.team_size is not None,
        ctx.requirement_stability is not None,
        ctx.unplanned_work_ratio is not None,
        ctx.operations_proximity is not None,
    ])
    if filled >= 4:
        return "high"
    if filled >= 2:
        return "medium"
    return "low"


def _clarifying_questions(ctx: ProjectContext) -> list[str]:
    q: list[str] = []
    if ctx.project_type is None:
        q.append("Handelt es sich eher um ein Produkt, einen Service/Betrieb oder ein zeitlich begrenztes Vorhaben?")
    if ctx.team_size is None:
        q.append("Wie groß ist das Team, das damit arbeiten soll?")
    if ctx.unplanned_work_ratio is None:
        q.append("Wie hoch ist der Anteil ungeplanter Arbeit (Bugs, Supporttickets, Ad-hoc-Anfragen) im Vergleich zur geplanten Arbeit?")
    if ctx.has_product_owner is None:
        q.append("Gibt es eine klare Person, die Anforderungen priorisiert und als Product Owner agieren kann?")
    if ctx.regulatory_burden is None:
        q.append("Gibt es besondere Dokumentations- oder Audit-Anforderungen (z.B. reguliertes Umfeld)?")
    return q


def _governance_elements(method_id: MethodId, ctx: ProjectContext) -> list[dict]:
    elements = []
    if method_id in ("scrum", "scrumban"):
        elements.append({
            "name": "Definition of Done",
            "type": "GovernanceElement",
            "description": "Formales Qualitätsgate für jedes Inkrement — nicht verhandelbar",
            "required": True,
        })
    if method_id in ("kanban", "scrumban"):
        elements.append({
            "name": "WIP-Limit-Policy",
            "type": "FlowRule",
            "description": "Explizite WIP-Grenzen pro Workflow-Stage",
            "required": True,
        })
        elements.append({
            "name": "Service Level Expectation (SLE)",
            "type": "GovernanceElement",
            "description": "Wahrscheinlichkeitsbasierte Lieferzeit-Erwartung pro Work-Item-Typ",
            "required": False,
        })
    if ctx.regulatory_burden == "high":
        elements.append({
            "name": "Change Record / Audit Log",
            "type": "GovernanceElement",
            "description": "Formale Dokumentation von Änderungen für Audit-Zwecke",
            "required": True,
        })
        elements.append({
            "name": "Sprint Review Sign-Off",
            "type": "GovernanceElement",
            "description": "Formale Abnahme des Inkrements durch autorisierte Stakeholder",
            "required": True,
        })
    return elements


def _flow_rules(method_id: MethodId) -> list[dict]:
    if method_id == "scrum":
        return [
            {"name": "Sprint Goal Immutability", "rule": "Sprint-Scope schützen — keine Ad-hoc-Änderungen ohne Sprint-Goal-Renegotiation"},
            {"name": "Velocity Tracking", "rule": "Velocity als Planungsgrundlage verwenden, nicht als Leistungsindikator"},
        ]
    if method_id == "kanban":
        return [
            {"name": "WIP Limit", "rule": "Maximale Anzahl paralleler Work Items pro Stage explizit begrenzen"},
            {"name": "Pull Policy", "rule": "Arbeit wird gezogen, nicht gedrückt — explizite Pull-Regeln"},
            {"name": "Service Class", "rule": "Work Items nach Cost-of-Delay kategorisieren: Expedite / Fixed Date / Standard"},
        ]
    if method_id == "scrumban":
        return [
            {"name": "Sprint Buffer", "rule": "20–30% Kapazität pro Sprint für ungeplante Arbeit reservieren"},
            {"name": "WIP Limit", "rule": "Auch im Sprint WIP-Grenzen für parallele Arbeit setzen"},
        ]
    return []


def _risks(method_id: MethodId, ctx: ProjectContext) -> list[str]:
    method = METHODS[method_id]
    risks = list(method.risk_patterns[:4])

    # Context-specific additional risks
    if method_id == "scrum" and ctx.unplanned_work_ratio == "medium":
        risks.append("Ungeplante Aufgaben stören den Sprint — Sprint-Buffer oder separate Kanban-Lane einplanen")
    if method_id == "kanban" and not ctx.has_product_owner:
        risks.append("Ohne klare Priorisierungsverantwortung droht das Kanban-Board zur Aufgabenhalde zu werden")
    if ctx.team_size is not None and ctx.team_size > 9:
        risks.append(f"Teamgröße {ctx.team_size}: Koordinationsmodell erforderlich (z.B. Scrum of Scrums, Nexus, PI Planning)")
    if ctx.num_teams and ctx.num_teams > 1:
        risks.append(f"Mit {ctx.num_teams} Teams: Koordinationsmodell (z.B. PI Planning, Scrum of Scrums) erforderlich")
    if ctx.regulatory_burden == "high":
        risks.append("Hohes regulatorisches Umfeld: agile Vorgehensweise mit formaler Governance ergänzen")

    return risks


def _alternatives(method_id: MethodId, ctx: ProjectContext) -> list[dict]:
    alts = []
    all_methods: list[MethodId] = ["scrum", "kanban", "scrumban"]
    for m in all_methods:
        if m == method_id:
            continue
        method = METHODS[m]
        alts.append({
            "method": method.name,
            "when": method.ideal_contexts[0] if method.ideal_contexts else "",
            "tagline": method.tagline,
        })
    return alts


# ── Main engine ───────────────────────────────────────────────────────────────

class AgileRecommendationEngine:
    """
    Derives a ProjectSetupRecommendation from ProjectContext signals.
    Context-sensitive, not dogmatic. Always provides reasoning and alternatives.
    """

    def recommend(self, ctx: ProjectContext) -> ProjectSetupRecommendation:
        scores = [
            _score_scrum(ctx),
            _score_kanban(ctx),
            _score_scrumban(ctx),
        ]
        scores.sort(key=lambda s: -s.score)
        winner = scores[0]
        method_id: MethodId = winner.method_id
        method = METHODS[method_id]

        # Collect winning reasons (positive only)
        reasoning = [r for r in winner.reasons if not r.startswith("Hin") and "schwierig" not in r and "passt weniger" not in r]

        # Roles
        roles = [
            {"id": r.id, "name": r.name, "description": r.description, "heykarl_type": r.heykarl_type}
            for r in get_roles_for_method(method_id)
        ]

        # Artifacts
        artifacts = [
            {"id": a.id, "name": a.name, "description": a.description, "heykarl_type": a.heykarl_type}
            for a in get_artifacts_for_method(method_id)
        ]

        # Events
        events = [
            {
                "id": e.id, "name": e.name, "description": e.description,
                "cadence": e.cadence, "duration_hint": e.duration_hint,
                "heykarl_type": e.heykarl_type,
            }
            for e in get_events_for_method(method_id)
        ]

        # Project setup
        setup = self._build_setup(method_id, ctx)

        return ProjectSetupRecommendation(
            recommended_method=method_id,
            recommended_operating_model=method.planning_model,
            reasoning=reasoning if reasoning else winner.reasons[:3],
            roles=roles,
            artifacts=artifacts,
            events=events,
            flow_rules=_flow_rules(method_id),
            governance_elements=_governance_elements(method_id, ctx),
            project_setup=setup,
            risks=_risks(method_id, ctx),
            alternatives=_alternatives(method_id, ctx),
            clarifying_questions=_clarifying_questions(ctx),
            confidence=_determine_confidence(ctx),
        )

    def _build_setup(self, method_id: MethodId, ctx: ProjectContext) -> dict:
        if method_id == "scrum":
            sprint_length = "2 Wochen" if ctx.requirement_stability != "high" else "3–4 Wochen"
            return {
                "planning_model": f"Sprint Planning alle {sprint_length}",
                "delivery_cycle": f"Sprint-Takt: {sprint_length}",
                "coordination_model": (
                    "Scrum of Scrums (wöchentlich)" if (ctx.num_teams or 1) > 1
                    else "Intern: Daily Scrum + Weekly Refinement"
                ),
                "improvement_model": "Retrospektive am Ende jedes Sprints (timeboxed)",
            }
        if method_id == "kanban":
            return {
                "planning_model": "Wöchentliches Replenishment Meeting — Pull-basiert",
                "delivery_cycle": "Kontinuierlicher Fluss, keine festen Releases",
                "coordination_model": "Wöchentlicher Flow Review + Replenishment",
                "improvement_model": "Kaizen-Ansatz: kontinuierliche kleine Verbesserungen basierend auf Flow Metrics",
            }
        if method_id == "scrumban":
            return {
                "planning_model": "2-Wochen-Sprint für geplante Arbeit + täglicher Pull für ungeplante Aufgaben",
                "delivery_cycle": "Sprint-Takt mit 20–30% Kapazitätspuffer",
                "coordination_model": "Sprint Review + wöchentliches Replenishment für unplanned queue",
                "improvement_model": "Retrospektive + Flow-Metriken kombiniert",
            }
        return {}
