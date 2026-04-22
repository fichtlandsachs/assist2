"""Integration tests for capability map API endpoints."""
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.deps import get_current_user


@pytest_asyncio.fixture
async def auth_client(db):
    """Client with seeded org + owner user injected via dependency override."""
    from app.models.user import User
    from app.models.organization import Organization
    from app.models.membership import Membership, MembershipRole

    org = Organization(id=uuid.uuid4(), slug="test-cap-org", name="Test Cap Org", plan="free")
    user = User(
        id=uuid.uuid4(),
        email="cap-admin@test.org",
        display_name="Cap Admin",
        hashed_password="x",
        is_active=True,
    )
    db.add_all([org, user])
    await db.flush()

    membership = Membership(
        organization_id=org.id, user_id=user.id, role=MembershipRole.owner
    )
    db.add(membership)
    await db.commit()

    async def override_db():
        yield db

    async def override_user():
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    yield client, org, user

    app.dependency_overrides.clear()
    await client.aclose()


@pytest.mark.asyncio
async def test_get_init_status_default_is_not_initialized(auth_client):
    client, org, _ = auth_client
    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/init-status")
    assert resp.status_code == 200
    assert resp.json()["initialization_status"] == "not_initialized"


@pytest.mark.asyncio
async def test_advance_init_status(auth_client):
    client, org, _ = auth_client
    resp = await client.patch(
        f"/api/v1/capabilities/orgs/{org.id}/init-status",
        json={"status": "capability_setup_in_progress"},
    )
    assert resp.status_code == 200
    assert resp.json()["initialization_status"] == "capability_setup_in_progress"


@pytest.mark.asyncio
async def test_get_empty_tree(auth_client):
    client, org, _ = auth_client
    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_apply_demo_dry_run_does_not_persist(auth_client):
    client, org, _ = auth_client
    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/import/demo?dry_run=true"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["capability_count"] >= 3
    # dry run: nothing persisted
    tree_resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    assert tree_resp.json() == []


@pytest.mark.asyncio
async def test_apply_demo_persist(auth_client):
    client, org, _ = auth_client
    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/import/demo?dry_run=false"
    )
    assert resp.status_code == 200
    assert resp.json()["is_valid"] is True
    tree_resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/tree")
    tree = tree_resp.json()
    assert len(tree) >= 3  # demo has 3 root capabilities


@pytest.mark.asyncio
async def test_assignment_user_story_on_capability_node_rejected(auth_client, db):
    client, org, _ = auth_client
    from app.models.capability_node import CapabilityNode
    node = CapabilityNode(org_id=org.id, node_type="capability", title="Cap A")
    db.add(node)
    await db.commit()

    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/assignments",
        json={
            "artifact_type": "user_story",
            "artifact_id": str(uuid.uuid4()),
            "node_id": str(node.id),
            "relation_type": "primary",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_assignment_user_story_on_level_3_accepted(auth_client, db):
    client, org, _ = auth_client
    from app.models.capability_node import CapabilityNode

    cap = CapabilityNode(org_id=org.id, node_type="capability", title="Cap")
    db.add(cap)
    await db.flush()
    l1 = CapabilityNode(org_id=org.id, node_type="level_1", title="L1", parent_id=cap.id)
    db.add(l1)
    await db.flush()
    l2 = CapabilityNode(org_id=org.id, node_type="level_2", title="L2", parent_id=l1.id)
    db.add(l2)
    await db.flush()
    l3 = CapabilityNode(org_id=org.id, node_type="level_3", title="L3", parent_id=l2.id)
    db.add(l3)
    await db.commit()

    resp = await client.post(
        f"/api/v1/capabilities/orgs/{org.id}/assignments",
        json={
            "artifact_type": "user_story",
            "artifact_id": str(uuid.uuid4()),
            "node_id": str(l3.id),
            "relation_type": "primary",
        },
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_tree_with_story_counts_aggregates_bottom_up(auth_client, db):
    client, org, _ = auth_client
    from app.models.capability_node import CapabilityNode
    from app.models.artifact_assignment import ArtifactAssignment

    cap = CapabilityNode(org_id=org.id, node_type="capability", title="Cap")
    db.add(cap)
    await db.flush()
    l1 = CapabilityNode(org_id=org.id, node_type="level_1", title="L1", parent_id=cap.id)
    db.add(l1)
    await db.flush()
    l2 = CapabilityNode(org_id=org.id, node_type="level_2", title="L2", parent_id=l1.id)
    db.add(l2)
    await db.flush()
    l3 = CapabilityNode(org_id=org.id, node_type="level_3", title="L3", parent_id=l2.id)
    db.add(l3)
    await db.commit()

    for _ in range(2):
        db.add(ArtifactAssignment(
            org_id=org.id,
            artifact_type="user_story",
            artifact_id=uuid.uuid4(),
            node_id=l3.id,
            relation_type="primary",
        ))
    await db.commit()

    resp = await client.get(
        f"/api/v1/capabilities/orgs/{org.id}/tree?with_counts=true"
    )
    assert resp.status_code == 200
    tree = resp.json()
    # root capability should have count=2 (aggregated from l3)
    assert tree[0]["story_count"] == 2


@pytest.mark.asyncio
async def test_list_templates(auth_client):
    client, org, _ = auth_client
    resp = await client.get(f"/api/v1/capabilities/orgs/{org.id}/import/templates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    keys = {t["key"] for t in data}
    assert "software_product" in keys
    assert "it_operations" in keys
