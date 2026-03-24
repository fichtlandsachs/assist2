"""Integration tests for organization endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User


@pytest.mark.asyncio
async def test_create_org(client: AsyncClient, auth_headers: dict):
    """Test that an authenticated user can create an organization."""
    response = await client.post(
        "/api/v1/organizations",
        json={
            "name": "My New Organization",
            "slug": "my-new-org",
            "description": "A test organization",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My New Organization"
    assert data["slug"] == "my-new-org"
    assert data["description"] == "A test organization"
    assert data["plan"] == "free"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_org_creator_is_owner(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
):
    """Test that the org creator is assigned the org_owner role."""
    response = await client.post(
        "/api/v1/organizations",
        json={"name": "Owner Test Org", "slug": "owner-test-org"},
        headers=auth_headers,
    )

    assert response.status_code == 201
    org_id = response.json()["id"]

    # Verify the creator can access the org (which requires org:read permission via org_owner)
    get_response = await client.get(
        f"/api/v1/organizations/{org_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 200


@pytest.mark.asyncio
async def test_create_org_duplicate_slug(
    client: AsyncClient, auth_headers: dict, test_org: Organization
):
    """Test that creating an org with a duplicate slug returns 409."""
    response = await client.post(
        "/api/v1/organizations",
        json={"name": "Another Org", "slug": "test-org"},
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_org_invalid_slug(client: AsyncClient, auth_headers: dict):
    """Test that creating an org with an invalid slug returns 422."""
    response = await client.post(
        "/api/v1/organizations",
        json={"name": "Test Org", "slug": "INVALID SLUG!"},
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_orgs(
    client: AsyncClient, auth_headers: dict, test_org: Organization
):
    """Test that only the user's own organizations are returned."""
    response = await client.get("/api/v1/organizations", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    org_slugs = [org["slug"] for org in data]
    assert "test-org" in org_slugs


@pytest.mark.asyncio
async def test_list_orgs_unauthenticated(client: AsyncClient):
    """Test that listing orgs without authentication returns 403."""
    response = await client.get("/api/v1/organizations")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_org(
    client: AsyncClient, auth_headers: dict, test_org: Organization
):
    """Test that an org member can retrieve organization details."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(test_org.id)
    assert data["slug"] == "test-org"
    assert data["name"] == "Test Organization"


@pytest.mark.asyncio
async def test_get_org_unauthorized(
    client: AsyncClient,
    test_user: User,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that a user without membership gets 403 when accessing an org."""
    # Create a second user who is not a member
    from app.main import app
    from app.deps import get_current_user
    from app.models.user import User as UserModel

    other_user = UserModel(
        email="outsider@example.com",
        authentik_id="outsider-authentik-id",
        display_name="Outsider",
        is_active=True,
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    app.dependency_overrides[get_current_user] = lambda: other_user
    try:
        response = await client.get(
            f"/api/v1/organizations/{test_org.id}",
            headers={"Authorization": "Bearer outsider-token"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_org(
    client: AsyncClient, auth_headers: dict, test_org: Organization
):
    """Test that an org admin can update organization details."""
    response = await client.patch(
        f"/api/v1/organizations/{test_org.id}",
        json={"name": "Updated Organization Name", "description": "New description"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Organization Name"
    assert data["description"] == "New description"
    assert data["slug"] == "test-org"  # slug should not change


@pytest.mark.asyncio
async def test_update_org_partial(
    client: AsyncClient, auth_headers: dict, test_org: Organization
):
    """Test that partial updates work correctly."""
    response = await client.patch(
        f"/api/v1/organizations/{test_org.id}",
        json={"description": "Only updating description"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "Only updating description"
    assert data["name"] == "Test Organization"  # name should remain unchanged


@pytest.mark.asyncio
async def test_delete_org(
    client: AsyncClient, auth_headers: dict, db: AsyncSession
):
    """Test that an org owner can delete (soft-delete) an organization."""
    # Create a new org to delete
    create_response = await client.post(
        "/api/v1/organizations",
        json={"name": "Delete Me Org", "slug": "delete-me-org"},
        headers=auth_headers,
    )
    assert create_response.status_code == 201
    org_id = create_response.json()["id"]

    # Delete it
    delete_response = await client.delete(
        f"/api/v1/organizations/{org_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204

    # Verify it's no longer accessible
    get_response = await client.get(
        f"/api/v1/organizations/{org_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_tenant_isolation(
    client: AsyncClient,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that User A cannot see the organization of User B."""
    from app.main import app
    from app.deps import get_current_user
    from app.models.user import User as UserModel
    from app.models.organization import Organization as OrgModel
    from app.models.membership import Membership
    from datetime import datetime, timezone

    # Create User B
    user_b = UserModel(
        email="userb@example.com",
        authentik_id="userb-authentik-id",
        display_name="User B",
        is_active=True,
    )
    db.add(user_b)
    await db.flush()

    # Create Org B (owned by User B)
    org_b = OrgModel(
        name="User B Organization",
        slug="user-b-org",
    )
    db.add(org_b)
    await db.flush()

    membership_b = Membership(
        user_id=user_b.id,
        organization_id=org_b.id,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership_b)
    await db.commit()

    # Make requests as User B via dependency override
    app.dependency_overrides[get_current_user] = lambda: user_b
    try:
        # User B lists their orgs - should only see org_b
        list_response = await client.get(
            "/api/v1/organizations",
            headers={"Authorization": "Bearer userb-token"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert list_response.status_code == 200
    orgs = list_response.json()
    org_ids = [org["id"] for org in orgs]

    assert str(org_b.id) in org_ids
    assert str(test_org.id) not in org_ids


@pytest.mark.asyncio
async def test_org_not_found(client: AsyncClient, auth_headers: dict):
    """Test that accessing a non-existent org returns 404 or 403."""
    import uuid
    fake_id = uuid.uuid4()

    response = await client.get(
        f"/api/v1/organizations/{fake_id}",
        headers=auth_headers,
    )

    # Either 403 (no permission) or 404 (not found) are acceptable
    assert response.status_code in (403, 404)
