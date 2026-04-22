"""Unit tests for capability service logic (no DB needed)."""
from app.schemas.capability import CapabilityNodeRead, CapabilityTreeNode, ImportValidationResult
from app.services.capability_service import _build_tree, _apply_counts


def _make_node(id: str, node_type: str, parent_id: str | None = None, title: str = "N") -> dict:
    return {
        "id": id,
        "org_id": "org1",
        "parent_id": parent_id,
        "node_type": node_type,
        "title": title,
        "description": None,
        "sort_order": 0,
        "is_active": True,
        "external_import_key": None,
        "source_type": None,
        "children": [],
        "story_count": 0,
    }


def test_build_tree_single_root():
    nodes = [_make_node("cap1", "capability")]
    tree = _build_tree(nodes)
    assert len(tree) == 1
    assert tree[0]["id"] == "cap1"
    assert tree[0]["children"] == []


def test_build_tree_hierarchy():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l3a", "level_3", parent_id="l2a"),
    ]
    tree = _build_tree(nodes)
    assert len(tree) == 1
    l1_children = tree[0]["children"]
    assert len(l1_children) == 1
    assert l1_children[0]["id"] == "l1a"
    l2_children = l1_children[0]["children"]
    assert l2_children[0]["id"] == "l2a"


def test_apply_counts_aggregates_bottom_up():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l3a", "level_3", parent_id="l2a"),
    ]
    tree = _build_tree(nodes)
    counts = {"l3a": 3}
    _apply_counts(tree, counts)
    l3 = tree[0]["children"][0]["children"][0]["children"][0]
    assert l3["story_count"] == 3
    l2 = tree[0]["children"][0]["children"][0]
    assert l2["story_count"] == 3
    l1 = tree[0]["children"][0]
    assert l1["story_count"] == 3
    cap = tree[0]
    assert cap["story_count"] == 3


def test_apply_counts_multi_branch():
    nodes = [
        _make_node("cap1", "capability"),
        _make_node("l1a", "level_1", parent_id="cap1"),
        _make_node("l1b", "level_1", parent_id="cap1"),
        _make_node("l2a", "level_2", parent_id="l1a"),
        _make_node("l2b", "level_2", parent_id="l1b"),
    ]
    tree = _build_tree(nodes)
    counts = {"l2a": 2, "l2b": 5}
    _apply_counts(tree, counts)
    assert tree[0]["story_count"] == 7
