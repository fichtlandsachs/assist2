"""Integration tests for membership endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User


@pytest.mark.asyncio
async def test_list_members(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    test_user: User,
):
    """Test that org members can be listed."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/members",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] >= 1

    # The creator (test_user) should be in the list
    user_ids = [item["user"]["id"] for item in data["items"]]
    assert str(test_user.id) in user_ids


@pytest.mark.asyncio
async def test_list_members_pagination(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """Test that pagination parameters work correctly."""
    response = await client.get(
        f"/api/v1/organizations/{test_org.id}/members",
        params={"page": 1, "page_size": 5},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert len(data["items"]) <= 5


@pytest.mark.asyncio
async def test_invite_member(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that an admin can invite a new member."""
    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/invite",
        json={"email": "newmember@example.com", "role_ids": []},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "invited"
    assert data["organization_id"] == str(test_org.id)


@pytest.mark.asyncio
async def test_invite_existing_user(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that inviting an existing user creates a membership."""
    # Create a user first
    from app.models.user import User as UserModel

    existing_user = UserModel(
        email="existing@example.com",
        authentik_id="existing-authentik-id",
        display_name="Existing User",
        is_active=True,
    )
    db.add(existing_user)
    await db.commit()

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/invite",
        json={"email": "existing@example.com", "role_ids": []},
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "invited"


@pytest.mark.asyncio
async def test_invite_duplicate_member(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    test_user: User,
):
    """Test that inviting an already-existing member returns 409."""
    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/invite",
        json={"email": "testuser@example.com", "role_ids": []},
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_invite_member_with_role(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that inviting a member with a role assigns it correctly."""
    # Get the org_member role ID
    result = await db.execute(
        select(Role).where(Role.name == "org_member", Role.is_system == True)
    )
    member_role = result.scalar_one_or_none()
    assert member_role is not None

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/invite",
        json={
            "email": "roledinvite@example.com",
            "role_ids": [str(member_role.id)],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "invited"


@pytest.mark.asyncio
async def test_remove_member(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that an admin can remove a member."""
    # First invite a member
    from app.models.user import User as UserModel
    from datetime import datetime, timezone

    new_user = UserModel(
        email="removeme@example.com",
        authentik_id="removeme-authentik-id",
        display_name="Remove Me",
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    membership = Membership(
        user_id=new_user.id,
        organization_id=test_org.id,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    # Remove the member
    response = await client.delete(
        f"/api/v1/organizations/{test_org.id}/members/{membership.id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Verify they're no longer in the list
    list_response = await client.get(
        f"/api/v1/organizations/{test_org.id}/members",
        headers=auth_headers,
    )
    assert list_response.status_code == 200
    member_ids = [item["user"]["id"] for item in list_response.json()["items"]]
    assert str(new_user.id) not in member_ids


@pytest.mark.asyncio
async def test_remove_nonexistent_member(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """Test that removing a non-existent membership returns 404."""
    import uuid
    fake_id = uuid.uuid4()

    response = await client.delete(
        f"/api/v1/organizations/{test_org.id}/members/{fake_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_membership_status(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that a membership status can be updated."""
    from app.models.user import User as UserModel
    from datetime import datetime, timezone

    new_user = UserModel(
        email="updatemember@example.com",
        authentik_id="updatemember-authentik-id",
        display_name="Update Member",
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    membership = Membership(
        user_id=new_user.id,
        organization_id=test_org.id,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)

    response = await client.patch(
        f"/api/v1/organizations/{test_org.id}/members/{membership.id}",
        json={"status": "suspended"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "suspended"


@pytest.mark.asyncio
async def test_assign_role(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    test_user: User,
    db: AsyncSession,
):
    """Test that a role can be assigned to a membership."""
    from app.models.user import User as UserModel
    from datetime import datetime, timezone

    # Create a member to assign role to
    new_user = UserModel(
        email="roleassign@example.com",
        authentik_id="roleassign-authentik-id",
        display_name="Role Assign User",
        is_active=True,
    )
    db.add(new_user)
    await db.flush()

    membership = Membership(
        user_id=new_user.id,
        organization_id=test_org.id,
        status="active",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(membership)
    await db.flush()

    # Get the org_member role
    result = await db.execute(
        select(Role).where(Role.name == "org_member", Role.is_system == True)
    )
    member_role = result.scalar_one_or_none()
    assert member_role is not None

    await db.commit()

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/{membership.id}/roles",
        json={"role_id": str(member_role.id)},
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    role_names = [r["name"] for r in data["roles"]]
    assert "org_member" in role_names


@pytest.mark.asyncio
async def test_assign_role_duplicate(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
    test_user: User,
    db: AsyncSession,
):
    """Test that assigning a role that's already assigned returns 409."""
    from sqlalchemy import select as sa_select

    # Get the creator's membership
    result = await db.execute(
        sa_select(Membership).where(
            Membership.user_id == test_user.id,
            Membership.organization_id == test_org.id,
        )
    )
    membership = result.scalar_one()

    # Get the org_owner role (already assigned)
    role_result = await db.execute(
        sa_select(Role).where(Role.name == "org_owner", Role.is_system == True)
    )
    owner_role = role_result.scalar_one_or_none()
    assert owner_role is not None

    response = await client.post(
        f"/api/v1/organizations/{test_org.id}/members/{membership.id}/roles",
        json={"role_id": str(owner_role.id)},
        headers=auth_headers,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_members_unauthorized(
    client: AsyncClient,
    test_org: Organization,
    db: AsyncSession,
):
    """Test that a non-member cannot list members."""
    from app.main import app
    from app.deps import get_current_user
    from app.models.user import User as UserModel

    outsider = UserModel(
        email="outsider2@example.com",
        authentik_id="outsider2-authentik-id",
        display_name="Outsider",
        is_active=True,
    )
    db.add(outsider)
    await db.commit()
    await db.refresh(outsider)

    app.dependency_overrides[get_current_user] = lambda: outsider
    try:
        response = await client.get(
            f"/api/v1/organizations/{test_org.id}/members",
            headers={"Authorization": "Bearer outsider-token"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_generate_invite_link(
    client: AsyncClient,
    auth_headers: dict,
    test_org,
):
    r = await client.post(
        f"/api/v1/organizations/{test_org.id}/invite-link",
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert "url" in data
    assert "token" in data
