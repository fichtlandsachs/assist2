"""Integration tests for superadmin user management endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.routers.superadmin import require_superuser


@pytest.fixture
def superuser(test_user: User) -> User:
    test_user.is_superuser = True
    return test_user


@pytest.fixture
def superuser_headers(superuser: User):
    app.dependency_overrides[require_superuser] = lambda: superuser
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(require_superuser, None)


@pytest.mark.asyncio
async def test_list_users_returns_paginated(
    client: AsyncClient, superuser_headers: dict, test_user: User
):
    r = await client.get("/api/v1/superadmin/users", headers=superuser_headers)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_list_users_search_filter(
    client: AsyncClient, superuser_headers: dict, test_user: User
):
    r = await client.get(
        "/api/v1/superadmin/users",
        params={"search": "testuser"},
        headers=superuser_headers,
    )
    assert r.status_code == 200
    data = r.json()
    emails = [u["email"] for u in data["items"]]
    assert "testuser@example.com" in emails


@pytest.mark.asyncio
async def test_patch_user_deactivate(
    client: AsyncClient, superuser_headers: dict, test_user_2: User
):
    r = await client.patch(
        f"/api/v1/superadmin/users/{test_user_2.id}",
        json={"is_active": False},
        headers=superuser_headers,
    )
    assert r.status_code == 200
    assert r.json()["is_active"] is False


@pytest.mark.asyncio
async def test_delete_user_soft(
    client: AsyncClient, superuser_headers: dict, test_user_2: User, db: AsyncSession
):
    r = await client.delete(
        f"/api/v1/superadmin/users/{test_user_2.id}",
        headers=superuser_headers,
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_superuser_cannot_delete_self(
    client: AsyncClient, superuser_headers: dict, superuser: User
):
    r = await client.delete(
        f"/api/v1/superadmin/users/{superuser.id}",
        headers=superuser_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_list_users_requires_superuser(
    client: AsyncClient, auth_headers: dict
):
    r = await client.get("/api/v1/superadmin/users", headers=auth_headers)
    assert r.status_code == 403


# ── Org endpoints ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_org(
    client: AsyncClient, superuser_headers: dict
):
    r = await client.post(
        "/api/v1/superadmin/organizations",
        json={"name": "New Org", "slug": "new-org-test", "plan": "free"},
        headers=superuser_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["slug"] == "new-org-test"
    assert data["plan"] == "free"


@pytest.mark.asyncio
async def test_patch_org(
    client: AsyncClient, superuser_headers: dict, test_org
):
    r = await client.patch(
        f"/api/v1/superadmin/organizations/{test_org.id}",
        json={"plan": "pro"},
        headers=superuser_headers,
    )
    assert r.status_code == 200
    assert r.json()["plan"] == "pro"


@pytest.mark.asyncio
async def test_delete_org(
    client: AsyncClient, superuser_headers: dict, test_org
):
    r = await client.delete(
        f"/api/v1/superadmin/organizations/{test_org.id}",
        headers=superuser_headers,
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_get_org_members(
    client: AsyncClient, superuser_headers: dict, test_org, test_user: User
):
    r = await client.get(
        f"/api/v1/superadmin/organizations/{test_org.id}/members",
        headers=superuser_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    user_ids = [item["user"]["id"] for item in data["items"]]
    assert str(test_user.id) in user_ids
