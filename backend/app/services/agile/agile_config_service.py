# app/services/agile/agile_config_service.py
"""
Agile Configuration Service for HeyKarl.

Manages organisation-level agile method configuration:
- Which methods are enabled in the Workspace
- Whether recommendations are active or explanation-only
- Preferred method (if organisation has a standard)
- Whether teams can freely choose or must use a standard
- Organisation-specific agile standards and policies

Stored in org config JSON — no DB migration needed (uses existing SystemConfig pattern).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.services.agile.agile_knowledge import MethodId


# ── Configuration schema ──────────────────────────────────────────────────────

@dataclass
class AgileMethodConfig:
    """Per-method activation settings."""
    method_id:   MethodId
    enabled:     bool = True
    description: str = ""


@dataclass
class AgileOrgConfig:
    """
    Organisation-level agile configuration.
    Stored as JSON in org settings.
    """
    # Which methods are available in the Workspace
    enabled_methods: list[MethodId] = field(
        default_factory=lambda: ["scrum", "kanban", "scrumban", "lean"]
    )

    # Whether the system should make recommendations or only explain methods
    recommendation_mode: Literal["recommend", "explain_only"] = "recommend"

    # Optional: organisation prefers one method (not enforced, just weighted in scoring)
    preferred_method: MethodId | None = None

    # Whether teams can freely choose or must follow organisation standard
    team_choice_model: Literal["free", "guided", "mandated"] = "guided"
    # free     = teams choose any enabled method
    # guided   = system recommends, team can override
    # mandated = organisation sets the method, teams use it

    # Mandatory method when team_choice_model = "mandated"
    mandated_method: MethodId | None = None

    # Organisation-specific standards (free text, shown in prompts)
    org_standards: list[str] = field(default_factory=list)
    # Examples:
    # "Alle Teams verwenden 2-Wochen-Sprints"
    # "Definition of Done muss Code Review und automatisierte Tests enthalten"
    # "Sprint Reviews erfordern formale Abnahme durch den Product Owner"

    # Whether anti-pattern detection is active
    antipattern_detection: bool = True

    # Whether HeyKarl should show governance hints alongside recommendations
    show_governance_hints: bool = True

    def to_dict(self) -> dict:
        return {
            "enabled_methods":        self.enabled_methods,
            "recommendation_mode":    self.recommendation_mode,
            "preferred_method":       self.preferred_method,
            "team_choice_model":      self.team_choice_model,
            "mandated_method":        self.mandated_method,
            "org_standards":          self.org_standards,
            "antipattern_detection":  self.antipattern_detection,
            "show_governance_hints":  self.show_governance_hints,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgileOrgConfig":
        return cls(
            enabled_methods=data.get("enabled_methods", ["scrum", "kanban", "scrumban", "lean"]),
            recommendation_mode=data.get("recommendation_mode", "recommend"),
            preferred_method=data.get("preferred_method"),
            team_choice_model=data.get("team_choice_model", "guided"),
            mandated_method=data.get("mandated_method"),
            org_standards=data.get("org_standards", []),
            antipattern_detection=data.get("antipattern_detection", True),
            show_governance_hints=data.get("show_governance_hints", True),
        )

    @classmethod
    def default(cls) -> "AgileOrgConfig":
        return cls()


# ── Config service ────────────────────────────────────────────────────────────

class AgileConfigService:
    """
    Resolves effective agile configuration for an organisation.
    Uses safe defaults when no configuration exists.
    """

    def get_config(self, org_config_json: dict | None) -> AgileOrgConfig:
        """
        Returns effective config from org_config_json.
        Falls back to sensible defaults if not configured.
        """
        if not org_config_json:
            return AgileOrgConfig.default()
        agile_section = org_config_json.get("agile", {})
        if not agile_section:
            return AgileOrgConfig.default()
        return AgileOrgConfig.from_dict(agile_section)

    def is_method_enabled(self, config: AgileOrgConfig, method_id: MethodId) -> bool:
        return method_id in config.enabled_methods

    def get_effective_method(
        self, config: AgileOrgConfig, recommended_method: MethodId
    ) -> tuple[MethodId, str | None]:
        """
        Returns (effective_method, override_reason).
        If mandated, returns mandated method with explanation.
        """
        if config.team_choice_model == "mandated" and config.mandated_method:
            if config.mandated_method != recommended_method:
                return config.mandated_method, (
                    f"Eure Organisation hat **{config.mandated_method.title()}** als Standard festgelegt. "
                    f"Die Empfehlung wäre {recommended_method.title()}, aber organisationsseitig ist {config.mandated_method.title()} verpflichtend."
                )
        return recommended_method, None

    def org_standards_context(self, config: AgileOrgConfig) -> str:
        """Return org standards as formatted context for prompt injection."""
        if not config.org_standards:
            return ""
        lines = ["**Organisationsstandards:**"]
        for std in config.org_standards:
            lines.append(f"- {std}")
        return "\n".join(lines)

    def build_default_for_new_org(self) -> dict:
        """Returns default config JSON for a new organisation."""
        return {"agile": AgileOrgConfig.default().to_dict()}


# ── Preset configurations ─────────────────────────────────────────────────────

PRESETS: dict[str, AgileOrgConfig] = {
    "scrum_standard": AgileOrgConfig(
        enabled_methods=["scrum", "scrumban"],
        recommendation_mode="recommend",
        preferred_method="scrum",
        team_choice_model="guided",
        org_standards=[
            "Alle Teams verwenden 2-Wochen-Sprints",
            "Sprint Reviews erfordern formale Abnahme durch den Product Owner",
            "Definition of Done enthält: Code Review, automatisierte Tests, PO-Abnahme",
        ],
    ),
    "kanban_ops": AgileOrgConfig(
        enabled_methods=["kanban", "scrumban"],
        recommendation_mode="recommend",
        preferred_method="kanban",
        team_choice_model="guided",
        org_standards=[
            "Alle Teams setzen WIP-Limits",
            "Wöchentlicher Flow Review ist Pflicht",
            "Cycle Time wird für alle Work Items gemessen",
        ],
    ),
    "regulated_enterprise": AgileOrgConfig(
        enabled_methods=["scrum", "kanban", "scrumban"],
        recommendation_mode="recommend",
        team_choice_model="guided",
        show_governance_hints=True,
        org_standards=[
            "Sprint Reviews erfordern formalen Sign-Off durch autorisierten Reviewer",
            "Definition of Done enthält Audit-Dokumentation",
            "Change Records für alle Releases verpflichtend",
            "Jeder Sprint muss einen messbaren Sprint Goal haben",
        ],
    ),
    "free_agile": AgileOrgConfig(
        enabled_methods=["scrum", "kanban", "scrumban", "lean"],
        recommendation_mode="recommend",
        team_choice_model="free",
        org_standards=[],
    ),
}


def get_preset(preset_name: str) -> AgileOrgConfig | None:
    return PRESETS.get(preset_name)
