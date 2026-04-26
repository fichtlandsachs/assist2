# tests/unit/test_agile_services.py
"""
Unit tests for the HeyKarl Agile Workspace services.

Tests cover:
1. Knowledge Model: method access, entity lookup, HeyKarl mapping
2. Recommendation Engine: alle 5 Spec-Szenarien + Grenzfälle
3. Anti-Pattern Detector: signal-based + text-based detection
4. Config Service: default, preset, mandated method, org standards
5. Integration: full pipeline from context → recommendation → anti-patterns
"""
from __future__ import annotations

import pytest

from app.services.agile.agile_knowledge import (
    METHODS,
    get_all_methods,
    get_artifacts_for_method,
    get_events_for_method,
    get_method,
    get_roles_for_method,
)
from app.services.agile.agile_recommendation_service import (
    AgileRecommendationEngine,
    ProjectContext,
    ProjectSetupRecommendation,
)
from app.services.agile.agile_antipattern_service import (
    AgileAntiPatternDetector,
)
from app.services.agile.agile_config_service import (
    AgileConfigService,
    AgileOrgConfig,
    get_preset,
    PRESETS,
)


@pytest.fixture()
def engine() -> AgileRecommendationEngine:
    return AgileRecommendationEngine()


@pytest.fixture()
def detector() -> AgileAntiPatternDetector:
    return AgileAntiPatternDetector()


@pytest.fixture()
def config_svc() -> AgileConfigService:
    return AgileConfigService()


# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE MODEL
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeModel:
    def test_all_methods_available(self):
        methods = get_all_methods()
        method_ids = {m.id for m in methods}
        assert "scrum" in method_ids
        assert "kanban" in method_ids
        assert "scrumban" in method_ids
        assert "lean" in method_ids

    def test_scrum_has_required_roles(self):
        roles = get_roles_for_method("scrum")
        role_names = {r.name for r in roles}
        assert "Product Owner" in role_names
        assert "Scrum Master" in role_names
        assert "Developers (Scrum Team)" in role_names

    def test_scrum_has_required_events(self):
        events = get_events_for_method("scrum")
        event_names = {e.name for e in events}
        assert "Daily Scrum" in event_names
        assert "Sprint Planning" in event_names
        assert "Sprint Review" in event_names
        assert "Sprint Retrospective" in event_names

    def test_scrum_has_required_artifacts(self):
        artifacts = get_artifacts_for_method("scrum")
        artifact_names = {a.name for a in artifacts}
        assert "Product Backlog" in artifact_names
        assert "Sprint Backlog" in artifact_names
        assert "Definition of Done" in artifact_names
        assert "Increment" in artifact_names

    def test_kanban_has_wip_limit_flow_rule(self):
        method = get_method("kanban")
        assert method is not None
        assert "wip_limit" in method.flow_rules

    def test_all_entities_have_heykarl_type(self):
        for method_id in METHODS:
            for role in get_roles_for_method(method_id):
                assert role.heykarl_type, f"Role {role.id} missing heykarl_type"
            for event in get_events_for_method(method_id):
                assert event.heykarl_type, f"Event {event.id} missing heykarl_type"
            for artifact in get_artifacts_for_method(method_id):
                assert artifact.heykarl_type, f"Artifact {artifact.id} missing heykarl_type"

    def test_all_methods_have_anti_patterns(self):
        for method in get_all_methods():
            assert len(method.risk_patterns) > 0, f"{method.name} has no risk_patterns"

    def test_all_methods_have_ideal_contexts(self):
        for method in get_all_methods():
            assert len(method.ideal_contexts) > 0, f"{method.name} has no ideal_contexts"

    def test_scrum_event_cadence_defined(self):
        events = get_events_for_method("scrum")
        for ev in events:
            assert ev.cadence, f"Event {ev.name} has no cadence"

    def test_dod_maps_to_governance_element(self):
        artifacts = get_artifacts_for_method("scrum")
        dod = next((a for a in artifacts if a.id == "definition_of_done"), None)
        assert dod is not None
        assert dod.heykarl_type == "GovernanceElement"

    def test_kanban_board_maps_to_artifact(self):
        artifacts = get_artifacts_for_method("kanban")
        board = next((a for a in artifacts if a.id == "kanban_board"), None)
        assert board is not None
        assert board.heykarl_type == "Artifact"


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATION ENGINE — 5 SPEC SCENARIOS
# ══════════════════════════════════════════════════════════════════════════════

class TestRecommendationEngine:

    # Scenario 1: Produktentwicklungsprojekt mit 7-köpfigem cross-funktionalem Team
    def test_scenario_1_product_team_7_recommends_scrum(self, engine):
        ctx = ProjectContext(
            project_type="product",
            team_size=7,
            requirement_stability="low",
            unplanned_work_ratio="low",
            operations_proximity="none",
            innovation_degree="high",
            has_product_owner=True,
            has_clear_product_goal=True,
        )
        rec = engine.recommend(ctx)
        assert rec.recommended_method == "scrum", f"Expected scrum, got {rec.recommended_method}"
        assert len(rec.roles) > 0
        assert len(rec.events) > 0
        assert len(rec.artifacts) > 0

    # Scenario 2: Support-/Betriebsteam mit vielen ungeplanten Aufgaben
    def test_scenario_2_support_team_high_unplanned_recommends_kanban(self, engine):
        ctx = ProjectContext(
            project_type="service",
            team_size=5,
            requirement_stability="high",
            unplanned_work_ratio="high",
            operations_proximity="high",
            cadence_preference="continuous",
        )
        rec = engine.recommend(ctx)
        assert rec.recommended_method == "kanban", f"Expected kanban, got {rec.recommended_method}"

    # Scenario 3: Produktteam mit festen Releases und viel Supportanteil
    def test_scenario_3_product_plus_support_recommends_scrumban(self, engine):
        ctx = ProjectContext(
            project_type="mixed",
            team_size=6,
            unplanned_work_ratio="medium",
            operations_proximity="partial",
            cadence_preference="sprint",
        )
        rec = engine.recommend(ctx)
        assert rec.recommended_method == "scrumban", f"Expected scrumban, got {rec.recommended_method}"

    # Scenario 4: Internes Verbesserungsprojekt mit vielen Abhängigkeiten
    def test_scenario_4_internal_multi_team_initiative(self, engine):
        ctx = ProjectContext(
            project_type="initiative",
            team_size=12,
            num_teams=3,
            cross_team_dependencies="high",
            requirement_stability="medium",
            unplanned_work_ratio="medium",
        )
        rec = engine.recommend(ctx)
        # Any method is valid — but risks must mention multi-team coordination
        assert isinstance(rec, ProjectSetupRecommendation)
        risk_text = " ".join(rec.risks).lower()
        assert "team" in risk_text or "koordination" in risk_text or "koordinationsmodell" in risk_text

    # Scenario 5: Stark reguliertes Umfeld
    def test_scenario_5_regulated_environment_has_governance(self, engine):
        ctx = ProjectContext(
            project_type="product",
            team_size=6,
            regulatory_burden="high",
            requirement_stability="medium",
            has_product_owner=True,
        )
        rec = engine.recommend(ctx)
        gov_names = {g["name"] for g in rec.governance_elements}
        # Must include audit-specific governance
        assert any("audit" in n.lower() or "sign" in n.lower() or "change" in n.lower() for n in gov_names), \
            f"No audit governance found in: {gov_names}"

    def test_recommendation_always_has_reasoning(self, engine):
        ctx = ProjectContext(project_type="product", team_size=5)
        rec = engine.recommend(ctx)
        assert len(rec.reasoning) > 0

    def test_recommendation_always_has_alternatives(self, engine):
        ctx = ProjectContext(project_type="product", team_size=5)
        rec = engine.recommend(ctx)
        assert len(rec.alternatives) >= 2

    def test_low_context_yields_clarifying_questions(self, engine):
        ctx = ProjectContext()  # no context at all
        rec = engine.recommend(ctx)
        assert len(rec.clarifying_questions) >= 3

    def test_high_context_yields_high_confidence(self, engine):
        ctx = ProjectContext(
            project_type="product",
            team_size=6,
            requirement_stability="low",
            unplanned_work_ratio="low",
            operations_proximity="none",
        )
        rec = engine.recommend(ctx)
        assert rec.confidence == "high"

    def test_low_context_yields_medium_or_low_confidence(self, engine):
        ctx = ProjectContext(project_type="product")
        rec = engine.recommend(ctx)
        assert rec.confidence in ("medium", "low")

    def test_to_dict_schema(self, engine):
        ctx = ProjectContext(project_type="product", team_size=5)
        rec = engine.recommend(ctx)
        d = rec.to_dict()
        required = {
            "recommended_method", "recommended_operating_model", "reasoning",
            "roles", "artifacts", "events", "flow_rules", "governance_elements",
            "project_setup", "risks", "alternatives", "clarifying_questions", "confidence",
        }
        assert required.issubset(d.keys())

    def test_to_chat_summary_not_empty(self, engine):
        ctx = ProjectContext(project_type="product", team_size=5, has_product_owner=True)
        rec = engine.recommend(ctx)
        summary = rec.to_chat_summary()
        assert "Empfohlene Vorgehensweise" in summary
        assert "Begründung" in summary

    def test_scrum_recommendation_has_sprint_in_setup(self, engine):
        ctx = ProjectContext(
            project_type="product", team_size=5, unplanned_work_ratio="low",
            operations_proximity="none", has_product_owner=True,
        )
        rec = engine.recommend(ctx)
        if rec.recommended_method == "scrum":
            assert "Sprint" in rec.project_setup.get("delivery_cycle", "")

    def test_kanban_recommendation_has_wip_in_flow_rules(self, engine):
        ctx = ProjectContext(
            project_type="service", unplanned_work_ratio="high", operations_proximity="high",
        )
        rec = engine.recommend(ctx)
        if rec.recommended_method == "kanban":
            rule_names = [r["name"] for r in rec.flow_rules]
            assert any("WIP" in n for n in rule_names)

    def test_team_size_12_triggers_coordination_risk(self, engine):
        ctx = ProjectContext(project_type="product", team_size=12)
        rec = engine.recommend(ctx)
        risk_text = " ".join(rec.risks)
        assert "12" in risk_text or "Koordination" in risk_text or "Teams" in risk_text

    def test_scrumban_setup_has_buffer(self, engine):
        ctx = ProjectContext(project_type="mixed", unplanned_work_ratio="medium", operations_proximity="partial")
        rec = engine.recommend(ctx)
        if rec.recommended_method == "scrumban":
            model = rec.project_setup.get("planning_model", "")
            assert "ungeplant" in model.lower() or "buffer" in model.lower() or "pull" in model.lower()


# ══════════════════════════════════════════════════════════════════════════════
# ANTI-PATTERN DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestAntiPatternDetector:
    def test_detects_no_product_goal(self, detector):
        ctx = ProjectContext(has_clear_product_goal=False)
        result = detector.detect(ctx, active_method="scrum")
        ids = {ap.id for ap in result.detected}
        assert "scrum_no_product_goal" in ids

    def test_detects_oversize_team(self, detector):
        ctx = ProjectContext(team_size=12)
        result = detector.detect(ctx, active_method="scrum")
        ids = {ap.id for ap in result.detected}
        assert "scrum_oversize_team" in ids

    def test_detects_no_product_owner(self, detector):
        ctx = ProjectContext(has_product_owner=False)
        result = detector.detect(ctx, active_method="scrum")
        ids = {ap.id for ap in result.detected}
        assert "scrum_po_unavailable" in ids

    def test_detects_multiteam_no_coordination(self, detector):
        ctx = ProjectContext(num_teams=3, cross_team_dependencies="high")
        result = detector.detect(ctx)
        ids = {ap.id for ap in result.detected}
        assert "general_multiteam_no_coordination" in ids

    def test_detects_sprint_with_high_unplanned(self, detector):
        ctx = ProjectContext(cadence_preference="sprint", unplanned_work_ratio="high")
        result = detector.detect(ctx)
        ids = {ap.id for ap in result.detected}
        assert "general_sprints_with_high_unplanned" in ids

    def test_no_anti_patterns_for_clean_setup(self, detector):
        ctx = ProjectContext(
            project_type="product",
            team_size=6,
            has_product_owner=True,
            has_clear_product_goal=True,
            num_teams=1,
            cross_team_dependencies="low",
        )
        result = detector.detect(ctx, active_method="scrum")
        criticals = [ap for ap in result.detected if ap.severity == "critical"]
        assert len(criticals) == 0

    def test_critical_before_warning_in_output(self, detector):
        ctx = ProjectContext(
            has_clear_product_goal=False,  # critical
            team_size=8,                    # warning (borderline)
        )
        result = detector.detect(ctx, active_method="scrum")
        if len(result.detected) >= 2:
            # Criticals must come first
            severities = [ap.severity for ap in result.detected]
            first_warning = next((i for i, s in enumerate(severities) if s == "warning"), len(severities))
            last_critical = max((i for i, s in enumerate(severities) if s == "critical"), default=-1)
            assert last_critical < first_warning, "Criticals must appear before warnings"

    def test_text_detection_kanban_no_wip(self, detector):
        detected = detector.detect_from_text("Wir nutzen ein Board ohne wip limit für Übersicht")
        ids = {ap.id for ap in detected}
        assert "kanban_no_wip_limits" in ids

    def test_text_detection_no_role_clarity(self, detector):
        detected = detector.detect_from_text("Es ist unklar wer entscheidet im Team — niemand verantwortlich")
        ids = {ap.id for ap in detected}
        assert "general_no_role_clarity" in ids

    def test_detection_result_to_dict_schema(self, detector):
        ctx = ProjectContext(has_clear_product_goal=False)
        result = detector.detect(ctx, active_method="scrum")
        d = result.to_dict()
        assert "detected" in d
        assert "summary" in d
        for item in d["detected"]:
            assert "id" in item
            assert "severity" in item
            assert "fix" in item

    def test_chat_warning_format(self, detector):
        ctx = ProjectContext(has_clear_product_goal=False, has_product_owner=False)
        result = detector.detect(ctx, active_method="scrum")
        warning = result.to_chat_warning()
        assert "🔴" in warning or "⚠️" in warning
        assert "→" in warning

    def test_summary_not_empty_when_detected(self, detector):
        ctx = ProjectContext(team_size=15)
        result = detector.detect(ctx)
        assert len(result.summary) > 0


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class TestAgileConfigService:
    def test_default_config_enables_all_methods(self, config_svc):
        cfg = config_svc.get_config(None)
        assert "scrum" in cfg.enabled_methods
        assert "kanban" in cfg.enabled_methods
        assert "scrumban" in cfg.enabled_methods

    def test_empty_org_config_returns_default(self, config_svc):
        cfg = config_svc.get_config({})
        assert isinstance(cfg, AgileOrgConfig)
        assert cfg.recommendation_mode == "recommend"

    def test_loads_from_dict(self, config_svc):
        data = {
            "agile": {
                "enabled_methods": ["scrum"],
                "recommendation_mode": "explain_only",
                "team_choice_model": "mandated",
                "mandated_method": "scrum",
            }
        }
        cfg = config_svc.get_config(data)
        assert cfg.enabled_methods == ["scrum"]
        assert cfg.recommendation_mode == "explain_only"
        assert cfg.mandated_method == "scrum"

    def test_mandated_method_overrides_recommendation(self, config_svc):
        cfg = AgileOrgConfig(
            team_choice_model="mandated",
            mandated_method="kanban",
        )
        method, reason = config_svc.get_effective_method(cfg, "scrum")
        assert method == "kanban"
        assert reason is not None
        assert "kanban" in reason.lower()

    def test_free_choice_does_not_override(self, config_svc):
        cfg = AgileOrgConfig(team_choice_model="free")
        method, reason = config_svc.get_effective_method(cfg, "scrum")
        assert method == "scrum"
        assert reason is None

    def test_org_standards_context_formatted(self, config_svc):
        cfg = AgileOrgConfig(org_standards=["2-Wochen-Sprints", "Code Review verpflichtend"])
        ctx = config_svc.org_standards_context(cfg)
        assert "2-Wochen-Sprints" in ctx
        assert "Code Review verpflichtend" in ctx

    def test_org_standards_context_empty_when_no_standards(self, config_svc):
        cfg = AgileOrgConfig(org_standards=[])
        ctx = config_svc.org_standards_context(cfg)
        assert ctx == ""

    def test_preset_scrum_standard(self):
        preset = get_preset("scrum_standard")
        assert preset is not None
        assert preset.preferred_method == "scrum"
        assert len(preset.org_standards) > 0

    def test_preset_kanban_ops(self):
        preset = get_preset("kanban_ops")
        assert preset is not None
        assert preset.preferred_method == "kanban"

    def test_preset_regulated_enterprise_has_governance(self):
        preset = get_preset("regulated_enterprise")
        assert preset is not None
        assert preset.show_governance_hints is True
        assert any("audit" in s.lower() or "sign" in s.lower() for s in preset.org_standards)

    def test_all_presets_are_valid(self):
        for name, preset in PRESETS.items():
            assert isinstance(preset, AgileOrgConfig), f"Preset {name} invalid"
            assert len(preset.enabled_methods) > 0

    def test_default_for_new_org_has_agile_key(self, config_svc):
        default = config_svc.build_default_for_new_org()
        assert "agile" in default
        assert "enabled_methods" in default["agile"]


# ══════════════════════════════════════════════════════════════════════════════
# INTEGRATION: Full pipeline
# ══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_product_team_scrum_pipeline(self, engine, detector):
        ctx = ProjectContext(
            project_type="product",
            team_size=7,
            requirement_stability="low",
            unplanned_work_ratio="low",
            operations_proximity="none",
            has_product_owner=True,
            has_clear_product_goal=True,
        )
        rec = engine.recommend(ctx)
        anti = detector.detect(ctx, active_method=rec.recommended_method)

        assert rec.recommended_method == "scrum"
        # Clean context — no critical anti-patterns
        criticals = [ap for ap in anti.detected if ap.severity == "critical"]
        assert len(criticals) == 0

    def test_ops_team_kanban_pipeline(self, engine, detector):
        ctx = ProjectContext(
            project_type="service",
            team_size=4,
            unplanned_work_ratio="high",
            operations_proximity="high",
        )
        rec = engine.recommend(ctx)
        anti = detector.detect(ctx, active_method=rec.recommended_method)

        assert rec.recommended_method == "kanban"
        # Kanban without explicit WIP setup context may flag it
        summary = anti.summary
        assert isinstance(summary, str)

    def test_config_mandated_overrides_engine(self, engine, config_svc):
        ctx = ProjectContext(
            project_type="product",
            team_size=7,
            has_product_owner=True,
        )
        rec = engine.recommend(ctx)
        cfg = AgileOrgConfig(team_choice_model="mandated", mandated_method="kanban")
        effective, reason = config_svc.get_effective_method(cfg, rec.recommended_method)
        assert effective == "kanban"
        assert reason is not None

    def test_recommendation_output_is_json_serialisable(self, engine):
        import json
        ctx = ProjectContext(project_type="mixed", team_size=6, unplanned_work_ratio="medium")
        rec = engine.recommend(ctx)
        serialised = json.dumps(rec.to_dict())
        assert len(serialised) > 100
