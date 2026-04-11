import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def auth_headers_fixture(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def test_rule_set(client: AsyncClient, auth_headers_fixture, test_org):
    r = await client.post(
        "/api/v1/rule-sets",
        json={"name": "Profile Test RS"},
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    return r.json()


@pytest.mark.asyncio
async def test_create_scoring_profile(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    r = await client.post(
        "/api/v1/scoring-profiles",
        json={
            "rule_set_id": test_rule_set["id"],
            "name": "Strict",
            "pass_threshold": 0.80,
            "warn_threshold": 0.60,
            "auto_approve_threshold": 0.95,
            "require_review_below": 0.70,
        },
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 201
    assert r.json()["name"] == "Strict"
    assert float(r.json()["pass_threshold"]) == 0.80


@pytest.mark.asyncio
async def test_invalid_thresholds_rejected(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    r = await client.post(
        "/api/v1/scoring-profiles",
        json={
            "rule_set_id": test_rule_set["id"],
            "name": "Invalid",
            "pass_threshold": 0.40,   # lower than warn_threshold
            "warn_threshold": 0.60,
            "auto_approve_threshold": 0.95,
            "require_review_below": 0.50,
        },
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_profiles_for_rule_set(
    client: AsyncClient, auth_headers_fixture, test_org, test_rule_set
):
    await client.post(
        "/api/v1/scoring-profiles",
        json={"rule_set_id": test_rule_set["id"], "name": "P1",
              "pass_threshold": 0.7, "warn_threshold": 0.5,
              "auto_approve_threshold": 0.9, "require_review_below": 0.6},
        params={"org_id": str(test_org.id)},
        headers=auth_headers_fixture,
    )
    r = await client.get(
        "/api/v1/scoring-profiles",
        params={"org_id": str(test_org.id), "rule_set_id": test_rule_set["id"]},
        headers=auth_headers_fixture,
    )
    assert r.status_code == 200
    assert len(r.json()) >= 1
