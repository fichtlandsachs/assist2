import pytest
from httpx import AsyncClient

from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def admin_headers(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_rule_set(client: AsyncClient, admin_headers: dict, test_org):
    r = await client.post(
        f"/api/v1/rule-sets",
        json={"name": "Default Rules", "description": "Base rule set"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Default Rules"
    assert data["status"] == "draft"
    assert data["version"] == 1
    assert data["frozen_at"] is None


@pytest.mark.asyncio
async def test_create_rule_set_duplicate_name_rejected(
    client: AsyncClient, admin_headers: dict, test_org
):
    payload = {"name": "Unique Rules"}
    params = {"org_id": str(test_org.id)}
    await client.post("/api/v1/rule-sets", json=payload, params=params, headers=admin_headers)
    r = await client.post("/api/v1/rule-sets", json=payload, params=params, headers=admin_headers)
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_add_rule_to_rule_set(client: AsyncClient, admin_headers: dict, test_org):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Rules With Defs"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/rule-sets/{rs_id}/rules",
        json={
            "name": "min_criteria",
            "rule_type": "completeness",
            "dimension": "completeness",
            "weight": 0.8,
            "parameters": {"min_criteria": 3},
            "prompt_template": "Check that the story has at least {{min_criteria}} criteria.",
        },
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    assert r.status_code == 201
    assert r.json()["dimension"] == "completeness"


@pytest.mark.asyncio
async def test_activate_rule_set_freezes_it(client: AsyncClient, admin_headers: dict, test_org):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Rules To Activate"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]

    r = await client.post(
        f"/api/v1/rule-sets/{rs_id}/activate",
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "active"
    assert data["frozen_at"] is not None


@pytest.mark.asyncio
async def test_cannot_add_rule_to_frozen_rule_set(
    client: AsyncClient, admin_headers: dict, test_org
):
    create_r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Frozen Rules"},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    rs_id = create_r.json()["id"]
    await client.post(
        f"/api/v1/rule-sets/{rs_id}/activate",
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )

    r = await client.post(
        f"/api/v1/rule-sets/{rs_id}/rules",
        json={"name": "new rule", "rule_type": "quality", "dimension": "clarity", "weight": 0.5},
        params={"org_id": str(test_org.id)},
        headers=admin_headers,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_list_rule_sets_for_org(client: AsyncClient, admin_headers: dict, test_org):
    for name in ["RS A", "RS B"]:
        await client.post(
            "/api/v1/rule-sets",
            json={"name": name},
            params={"org_id": str(test_org.id)},
            headers=admin_headers,
        )
    r = await client.get(
        "/api/v1/rule-sets", params={"org_id": str(test_org.id)}, headers=admin_headers
    )
    assert r.status_code == 200
    assert len(r.json()) >= 2
