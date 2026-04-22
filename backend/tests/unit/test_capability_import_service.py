"""Unit tests for capability import validation logic."""
from app.services.capability_import_service import validate_rows, build_nodes_from_rows


def _row(cap="Cap A", l1="Proc 1", l2="Sub 1", l3=None, key=None) -> dict:
    return {
        "capability": cap,
        "level_1": l1,
        "level_2": l2,
        "level_3": l3,
        "description": None,
        "external_key": key,
        "is_active": True,
    }


def test_valid_rows_produce_no_errors():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 1", "Sub 2")]
    result = validate_rows(rows)
    assert result.is_valid
    assert result.error_count == 0


def test_missing_capability_is_error():
    rows = [_row("", "Proc 1", "Sub 1")]
    result = validate_rows(rows)
    assert not result.is_valid
    assert result.error_count >= 1
    assert any("capability" in i.message.lower() for i in result.issues if i.level == "error")


def test_level_2_without_level_1_is_error():
    rows = [{"capability": "Cap A", "level_1": "", "level_2": "Orphaned", "level_3": None,
             "description": None, "external_key": None, "is_active": True}]
    result = validate_rows(rows)
    assert not result.is_valid


def test_duplicate_level_2_is_warning():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 1", "Sub 1")]
    result = validate_rows(rows)
    assert result.warning_count >= 1


def test_build_nodes_creates_correct_hierarchy():
    rows = [_row("Cap A", "Proc 1", "Sub 1", "Task 1")]
    nodes = build_nodes_from_rows(rows, source_type="excel")
    types = {n["node_type"] for n in nodes}
    assert "capability" in types
    assert "level_1" in types
    assert "level_2" in types
    assert "level_3" in types
    assert len(nodes) == 4


def test_build_nodes_deduplicates_repeated_capabilities():
    rows = [_row("Cap A", "Proc 1", "Sub 1"), _row("Cap A", "Proc 2", "Sub 2")]
    nodes = build_nodes_from_rows(rows, source_type="excel")
    caps = [n for n in nodes if n["node_type"] == "capability"]
    assert len(caps) == 1


def test_counts_are_correct():
    rows = [
        _row("Cap A", "Proc 1", "Sub 1"),
        _row("Cap A", "Proc 1", "Sub 2"),
        _row("Cap B", "Proc 3", "Sub 3"),
    ]
    result = validate_rows(rows)
    assert result.capability_count == 2
    assert result.level_1_count == 2
    assert result.level_2_count == 3
