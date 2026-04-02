"""Integration tests for /api/v1/projects endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient, auth_headers: dict, test_org: Organization):
    response = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Alpha Release", "status": "planning"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Alpha Release"
    assert data["status"] == "planning"
    assert data["color"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, auth_headers: dict, test_org: Organization):
    await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Project One", "status": "active"},
        headers=auth_headers,
    )
    response = await client.get(
        f"/api/v1/projects?org_id={test_org.id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(p["name"] == "Project One" for p in data)


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, auth_headers: dict, test_org: Organization):
    create = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "Beta", "status": "planning"},
        headers=auth_headers,
    )
    project_id = create.json()["id"]
    response = await client.patch(
        f"/api/v1/projects/{project_id}",
        json={"status": "active", "color": "#E11D48"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["color"] == "#E11D48"


@pytest.mark.asyncio
async def test_delete_project_unlinks_items(client: AsyncClient, auth_headers: dict, test_org: Organization):
    """Deleting a project must not delete epics — it must unlink them."""
    proj = await client.post(
        f"/api/v1/projects?org_id={test_org.id}",
        json={"name": "To Delete"},
        headers=auth_headers,
    )
    project_id = proj.json()["id"]
    epic = await client.post(
        f"/api/v1/epics?org_id={test_org.id}",
        json={"title": "Orphan Epic", "project_id": project_id},
        headers=auth_headers,
    )
    assert epic.status_code == 201

    del_resp = await client.delete(f"/api/v1/projects/{project_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # Epic still exists
    list_resp = await client.get(f"/api/v1/epics?org_id={test_org.id}", headers=auth_headers)
    assert any(e["title"] == "Orphan Epic" for e in list_resp.json())
    # Epic is now unlinked
    orphan = next(e for e in list_resp.json() if e["title"] == "Orphan Epic")
    assert orphan["project_id"] is None
