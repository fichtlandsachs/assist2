"""Integration tests for the Admin Configuration Layer.

Covers:
  - Config reads (defaults when no row exists)
  - Config updates (version increment, audit history)
  - Permission checks (superuser vs regular user vs non-member)
  - Feature toggles (retrieval_only gate on AI endpoints)
"""
from __future__ import annotations

import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.organization import Organization
from app.models.system_config import SystemConfig, ConfigHistory
from app.services.admin_config_service import admin_config_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org_id(test_org: Organization) -> uuid.UUID:
    return test_org.id


@pytest.fixture
def org_id_str(test_org: Organization) -> str:
    return str(test_org.id)


# ---------------------------------------------------------------------------
# 1. Config reads — defaults
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_config_returns_all_six_sections(
    client: AsyncClient, auth_headers: dict, org_id_str: str
) -> None:
    """GET /admin/{org_id}/config returns all 6 sections with defaults."""
    r = await client.get(f"/api/v1/admin/{org_id_str}/config", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["organization_id"] == org_id_str
    sections = data["sections"]
    for ct in ("retrieval", "prompt_learning", "workflow_learning", "governance", "learning_sensitivity", "llm_trigger"):
        assert ct in sections, f"missing section: {ct}"
        s = sections[ct]
        assert s["config_type"] == ct
        assert isinstance(s["config_payload"], dict)
        assert s["version"] == 0  # default (no DB row yet)


@pytest.mark.asyncio
async def test_get_config_retrieval_defaults(
    client: AsyncClient, auth_headers: dict, org_id_str: str
) -> None:
    """Retrieval defaults match schema defaults."""
    r = await client.get(f"/api/v1/admin/{org_id_str}/config", headers=auth_headers)
    p = r.json()["sections"]["retrieval"]["config_payload"]
    assert p["top_k"] == 5
    assert p["similarity_weight"] == pytest.approx(0.7)
    assert p["learning_based_ranking"] is False


@pytest.mark.asyncio
async def test_get_config_llm_trigger_defaults(
    client: AsyncClient, auth_headers: dict, org_id_str: str
) -> None:
    """LLM trigger defaults: retrieval_only is False by default."""
    r = await client.get(f"/api/v1/admin/{org_id_str}/config", headers=auth_headers)
    p = r.json()["sections"]["llm_trigger"]["config_payload"]
    assert p["retrieval_only"] is False
    assert p["min_input_length"] == 50


# ---------------------------------------------------------------------------
# 2. Config updates — version increment + audit trail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_config_as_superuser(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str, org_id: uuid.UUID,
) -> None:
    """Superuser can update config; version increments; payload persisted."""
    # Make test_user a superuser
    test_user.is_superuser = True
    await db.commit()

    r = await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "retrieval", "config_payload": {"top_k": 10, "similarity_weight": 0.8}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["config_type"] == "retrieval"
    assert data["version"] == 1
    assert data["config_payload"]["top_k"] == 10
    assert data["config_payload"]["similarity_weight"] == pytest.approx(0.8)

    # Second save → version 2
    r2 = await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "retrieval", "config_payload": {"top_k": 15}},
        headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["version"] == 2


@pytest.mark.asyncio
async def test_post_config_merges_with_defaults(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str,
) -> None:
    """Saved payload is merged with defaults — missing keys get default values."""
    test_user.is_superuser = True
    await db.commit()

    r = await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "retrieval", "config_payload": {"top_k": 20}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    p = r.json()["config_payload"]
    assert p["top_k"] == 20
    # Default values still present
    assert p["similarity_weight"] == pytest.approx(0.7)
    assert p["learning_based_ranking"] is False


@pytest.mark.asyncio
async def test_config_history_written_on_update(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str, org_id: uuid.UUID,
) -> None:
    """Each POST to config writes a ConfigHistory entry."""
    test_user.is_superuser = True
    await db.commit()

    # First write
    await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "learning_sensitivity", "config_payload": {"mode": "balanced"}},
        headers=auth_headers,
    )
    # Second write
    await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "learning_sensitivity", "config_payload": {"mode": "aggressive"}},
        headers=auth_headers,
    )

    history = await admin_config_service.get_history(org_id, "learning_sensitivity", db)
    assert len(history) == 2
    # Most recent entry first
    assert history[0].new_value["mode"] == "aggressive"
    assert history[0].previous_value["mode"] == "balanced"
    assert history[1].new_value["mode"] == "balanced"
    assert history[1].previous_value is None  # first write has no previous


@pytest.mark.asyncio
async def test_get_history_endpoint(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str,
) -> None:
    """GET /admin/{org_id}/config/{type}/history returns history entries."""
    test_user.is_superuser = True
    await db.commit()

    await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "governance", "config_payload": {"approval_required": {"prompt_updates": False}}},
        headers=auth_headers,
    )

    r = await client.get(
        f"/api/v1/admin/{org_id_str}/config/governance/history",
        headers=auth_headers,
    )
    assert r.status_code == 200
    entries = r.json()
    assert len(entries) >= 1
    assert entries[0]["new_value"]["approval_required"]["prompt_updates"] is False


@pytest.mark.asyncio
async def test_post_invalid_config_type(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str,
) -> None:
    """Unknown config_type is rejected with 422 (Pydantic) or 400."""
    test_user.is_superuser = True
    await db.commit()

    r = await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "nonexistent", "config_payload": {}},
        headers=auth_headers,
    )
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# 3. Permission checks
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_config_regular_user_forbidden(
    client: AsyncClient, db: AsyncSession,
    test_user_2: User, test_org: Organization,
    org_id_str: str,
) -> None:
    """A regular org_member (not owner, not superuser) gets 403 on config write."""
    from app.models.membership import Membership, MembershipRole
    from app.models.role import Role
    from sqlalchemy import select

    # Add test_user_2 as org_member (no admin:config permission, no wildcard)
    role_q = await db.execute(select(Role).where(Role.name == "org_member", Role.is_system == True))
    member_role = role_q.scalar_one()
    membership = Membership(
        user_id=test_user_2.id,
        organization_id=test_org.id,
        status="active",
    )
    db.add(membership)
    await db.flush()
    db.add(MembershipRole(membership_id=membership.id, role_id=member_role.id))
    await db.commit()

    # Override get_current_user to return test_user_2 directly (no Authentik needed)
    from app.main import app
    from app.deps import get_current_user

    app.dependency_overrides[get_current_user] = lambda: test_user_2
    try:
        r = await client.post(
            f"/api/v1/admin/{org_id_str}/config",
            json={"config_type": "retrieval", "config_payload": {"top_k": 99}},
            headers={"Authorization": "Bearer test-token"},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_get_config_unauthenticated(
    client: AsyncClient, org_id_str: str,
) -> None:
    """Unauthenticated requests to admin config are rejected."""
    r = await client.get(f"/api/v1/admin/{org_id_str}/config")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_config_superuser_success(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, org_id_str: str,
) -> None:
    """Superuser flag grants write access regardless of role assignments."""
    test_user.is_superuser = True
    await db.commit()

    r = await client.post(
        f"/api/v1/admin/{org_id_str}/config",
        json={"config_type": "workflow_learning", "config_payload": {"enabled": True, "auto_suggestions": True}},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["config_payload"]["enabled"] is True


# ---------------------------------------------------------------------------
# 4. Feature toggles — retrieval_only gates AI endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieval_only_blocks_ai_test_cases(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, test_org: Organization,
) -> None:
    """When retrieval_only=True, AI test case generation returns 503."""
    from app.models.user_story import UserStory

    # Enable retrieval_only for the org
    test_user.is_superuser = True
    await db.commit()
    await admin_config_service.upsert_config(
        org_id=test_org.id,
        config_type="llm_trigger",
        payload={"retrieval_only": True, "min_input_length": 50, "idle_time_threshold": 300},
        changed_by_id=test_user.id,
        db=db,
    )

    # Create a story
    story = UserStory(
        organization_id=test_org.id,
        created_by_id=test_user.id,
        title="Test Story",
        description="As a user I want something",
        acceptance_criteria="Given X When Y Then Z",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    r = await client.post(
        f"/api/v1/user-stories/{story.id}/ai-test-cases",
        headers=auth_headers,
    )
    assert r.status_code == 503
    assert "Retrieval-only" in r.json()["error"]


@pytest.mark.asyncio
async def test_retrieval_only_blocks_ai_dod(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, test_org: Organization,
) -> None:
    """When retrieval_only=True, AI DoD generation returns 503."""
    from app.models.user_story import UserStory

    test_user.is_superuser = True
    await db.commit()
    await admin_config_service.upsert_config(
        org_id=test_org.id,
        config_type="llm_trigger",
        payload={"retrieval_only": True, "min_input_length": 50, "idle_time_threshold": 300},
        changed_by_id=test_user.id,
        db=db,
    )

    story = UserStory(
        organization_id=test_org.id,
        created_by_id=test_user.id,
        title="DoD Story",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    r = await client.post(f"/api/v1/user-stories/{story.id}/ai-dod", headers=auth_headers)
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_retrieval_only_blocks_ai_features(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, test_org: Organization,
) -> None:
    """When retrieval_only=True, AI feature suggestions return 503."""
    from app.models.user_story import UserStory

    test_user.is_superuser = True
    await db.commit()
    await admin_config_service.upsert_config(
        org_id=test_org.id,
        config_type="llm_trigger",
        payload={"retrieval_only": True, "min_input_length": 50, "idle_time_threshold": 300},
        changed_by_id=test_user.id,
        db=db,
    )

    story = UserStory(
        organization_id=test_org.id,
        created_by_id=test_user.id,
        title="Feature Story",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    r = await client.post(f"/api/v1/user-stories/{story.id}/ai-features", headers=auth_headers)
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_llm_allowed_when_retrieval_only_false(
    client: AsyncClient, db: AsyncSession, test_user: User,
    auth_headers: dict, test_org: Organization,
) -> None:
    """When retrieval_only=False (default), AI endpoints are not blocked by config."""
    from app.models.user_story import UserStory

    test_user.is_superuser = True
    await db.commit()
    # Explicitly set retrieval_only=False
    await admin_config_service.upsert_config(
        org_id=test_org.id,
        config_type="llm_trigger",
        payload={"retrieval_only": False, "min_input_length": 50, "idle_time_threshold": 300},
        changed_by_id=test_user.id,
        db=db,
    )

    story = UserStory(
        organization_id=test_org.id,
        created_by_id=test_user.id,
        title="Allowed Story",
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)

    # Should NOT be 503 (might be 500/other if AI key is missing in test env, but not 503)
    r = await client.post(f"/api/v1/user-stories/{story.id}/ai-dod", headers=auth_headers)
    assert r.status_code != 503


# ---------------------------------------------------------------------------
# 5. Service layer unit tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_service_get_merged_config_defaults(
    db: AsyncSession, org_id: uuid.UUID,
) -> None:
    """Service returns all 6 sections with defaults for fresh org."""
    merged = await admin_config_service.get_merged_config(org_id, db)
    assert len(merged.sections) == 6
    assert merged.sections["retrieval"].version == 0
    assert merged.sections["retrieval"].config_payload["top_k"] == 5


@pytest.mark.asyncio
async def test_service_upsert_increments_version(
    db: AsyncSession, org_id: uuid.UUID, test_user: User,
) -> None:
    """Service upsert increments version on each call."""
    s1 = await admin_config_service.upsert_config(
        org_id, "retrieval", {"top_k": 8}, test_user.id, db
    )
    assert s1.version == 1

    s2 = await admin_config_service.upsert_config(
        org_id, "retrieval", {"top_k": 12}, test_user.id, db
    )
    assert s2.version == 2


@pytest.mark.asyncio
async def test_service_is_retrieval_only_default_false(
    db: AsyncSession, org_id: uuid.UUID,
) -> None:
    """is_retrieval_only returns False when no config row exists."""
    result = await admin_config_service.is_retrieval_only(org_id, db)
    assert result is False


@pytest.mark.asyncio
async def test_service_is_retrieval_only_reflects_config(
    db: AsyncSession, org_id: uuid.UUID, test_user: User,
) -> None:
    """is_retrieval_only returns True after setting retrieval_only=True."""
    await admin_config_service.upsert_config(
        org_id, "llm_trigger",
        {"retrieval_only": True, "min_input_length": 50, "idle_time_threshold": 300},
        test_user.id, db,
    )
    result = await admin_config_service.is_retrieval_only(org_id, db)
    assert result is True


@pytest.mark.asyncio
async def test_service_sensitivity_mode_default(
    db: AsyncSession, org_id: uuid.UUID,
) -> None:
    """get_sensitivity_mode defaults to 'conservative'."""
    mode = await admin_config_service.get_sensitivity_mode(org_id, db)
    assert mode == "conservative"


@pytest.mark.asyncio
async def test_service_sensitivity_mode_persisted(
    db: AsyncSession, org_id: uuid.UUID, test_user: User,
) -> None:
    """get_sensitivity_mode returns saved value."""
    await admin_config_service.upsert_config(
        org_id, "learning_sensitivity", {"mode": "aggressive"}, test_user.id, db
    )
    mode = await admin_config_service.get_sensitivity_mode(org_id, db)
    assert mode == "aggressive"
