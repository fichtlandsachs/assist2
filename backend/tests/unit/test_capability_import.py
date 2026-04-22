def test_capability_node_import():
    from app.models.capability_node import CapabilityNode, NodeType
    assert NodeType.capability == "capability"
    assert NodeType.level_1 == "level_1"
    assert NodeType.level_2 == "level_2"
    assert NodeType.level_3 == "level_3"
    assert CapabilityNode.__tablename__ == "capability_nodes"
