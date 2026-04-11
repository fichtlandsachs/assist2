import pytest
import pytest_asyncio
from httpx import AsyncClient
from app.main import app
from app.models.user import User
from app.deps import get_current_user


@pytest.fixture
def auth_headers_v(test_user: User):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def test_story(client: AsyncClient, auth_headers_v, test_org):
    r = await client.post(
        "/api/v1/user-stories",
        json={"title": "Versioned Story", "description": "as a user"},
        params={"org_id": str(test_org.id)},
        headers=auth_headers_v,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()


@pytest.mark.asyncio
async def test_create_version_returns_version_number(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    r = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={
            "title": "Versioned Story",
            "description": "As a user I want to login",
            "acceptance_criteria": [{"text": "Can log in with email"}],
        },
        headers=auth_headers_v,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["version_number"] == 1
    assert data["story_id"] == story_id


@pytest.mark.asyncio
async def test_duplicate_content_returns_409(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    payload = {"title": "Same Content", "description": "same description"}
    r1 = await client.post(
        f"/api/v1/stories/{story_id}/versions", json=payload, headers=auth_headers_v
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/api/v1/stories/{story_id}/versions", json=payload, headers=auth_headers_v
    )
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_version_number_increments(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    v1 = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={"title": "V1", "description": "first"},
        headers=auth_headers_v,
    )
    v2 = await client.post(
        f"/api/v1/stories/{story_id}/versions",
        json={"title": "V2", "description": "second, different content"},
        headers=auth_headers_v,
    )
    assert v1.json()["version_number"] == 1
    assert v2.json()["version_number"] == 2


@pytest.mark.asyncio
async def test_list_versions_for_story(
    client: AsyncClient, auth_headers_v, test_org, test_story
):
    story_id = test_story["id"]
    for i in range(3):
        await client.post(
            f"/api/v1/stories/{story_id}/versions",
            json={"title": f"Version {i}", "description": f"desc {i}"},
            headers=auth_headers_v,
        )
    r = await client.get(f"/api/v1/stories/{story_id}/versions", headers=auth_headers_v)
    assert r.status_code == 200
    assert len(r.json()) >= 3
