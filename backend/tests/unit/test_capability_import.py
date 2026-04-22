def test_capability_node_import():
    from app.models.capability_node import CapabilityNode, NodeType
    assert NodeType.capability == "capability"
    assert NodeType.level_1 == "level_1"
    assert NodeType.level_2 == "level_2"
    assert NodeType.level_3 == "level_3"
    assert CapabilityNode.__tablename__ == "capability_nodes"


def test_artifact_assignment_import():
    from app.models.artifact_assignment import ArtifactAssignment, ArtifactType, RelationType
    assert ArtifactType.project == "project"
    assert ArtifactType.epic == "epic"
    assert ArtifactType.user_story == "user_story"
    assert RelationType.primary == "primary"
    assert RelationType.secondary == "secondary"
    assert ArtifactAssignment.__tablename__ == "artifact_assignments"


def test_org_has_init_fields():
    from app.models.organization import Organization, OrgInitializationStatus
    assert OrgInitializationStatus.not_initialized == "not_initialized"
    assert OrgInitializationStatus.initialized == "initialized"
    cols = {c.name for c in Organization.__table__.c}
    assert "initialization_status" in cols
    assert "initialization_completed_at" in cols
    assert "capability_map_version" in cols
    assert "initial_setup_source" in cols


def test_project_has_extended_fields():
    from app.models.project import Project
    cols = {c.name for c in Project.__table__.c}
    assert "project_brief" in cols
    assert "planned_start_date" in cols
    assert "planned_end_date" in cols
    assert "jira_project_key" in cols
    assert "jira_source_metadata" in cols
