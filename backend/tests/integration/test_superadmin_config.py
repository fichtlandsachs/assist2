"""Integration tests for GET/PATCH /api/v1/superadmin/config/."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.global_config import GlobalConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def superuser(test_user: User) -> User:
    test_user.is_superuser = True
    return test_user


@pytest.fixture
def superuser_headers(client: AsyncClient, superuser: User):
    from app.routers.superadmin import get_admin_user
    app.dependency_overrides[get_admin_user] = lambda: superuser
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_admin_user, None)


# ---------------------------------------------------------------------------
# GET /api/v1/superadmin/config/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_config_returns_all_keys(
    client: AsyncClient, superuser_headers: dict
) -> None:
    r = await client.get("/api/v1/superadmin/config/", headers=superuser_headers)
    assert r.status_code == 200
    data = r.json()
    assert "litellm.url" in data
    assert "litellm.api_key" in data
    assert "atlassian.sso_enabled" in data
    assert "ai.anthropic_api_key" in data


@pytest.mark.asyncio
async def test_get_config_secret_key_has_no_value(
    client: AsyncClient, superuser_headers: dict
) -> None:
    r = await client.get("/api/v1/superadmin/config/", headers=superuser_headers)
    assert r.status_code == 200
    data = r.json()
    key = data["litellm.api_key"]
    assert key["value"] is None
    assert key["is_secret"] is True
    assert "is_set" in key


@pytest.mark.asyncio
async def test_get_config_plaintext_key_returns_value(
    client: AsyncClient, superuser_headers: dict, db: AsyncSession
) -> None:
    db.add(GlobalConfig(key="litellm.url", value="http://litellm:4000", is_secret=False))
    await db.commit()

    r = await client.get("/api/v1/superadmin/config/", headers=superuser_headers)
    assert r.status_code == 200
    assert r.json()["litellm.url"]["value"] == "http://litellm:4000"


# ---------------------------------------------------------------------------
# PATCH /api/v1/superadmin/config/
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_config_sets_plaintext_value(
    client: AsyncClient, superuser_headers: dict, db: AsyncSession
) -> None:
    r = await client.patch(
        "/api/v1/superadmin/config/",
        json={"key": "litellm.url", "value": "http://assist2-litellm:4000"},
        headers=superuser_headers,
    )
    assert r.status_code == 204

    await db.refresh(await db.get(GlobalConfig, "litellm.url") or GlobalConfig())
    row = await db.get(GlobalConfig, "litellm.url")
    assert row is not None
    assert row.value == "http://assist2-litellm:4000"
    assert row.is_secret is False


@pytest.mark.asyncio
async def test_patch_config_encrypts_secret_value(
    client: AsyncClient, superuser_headers: dict, db: AsyncSession
) -> None:
    r = await client.patch(
        "/api/v1/superadmin/config/",
        json={"key": "litellm.api_key", "value": "sk-test-123"},
        headers=superuser_headers,
    )
    assert r.status_code == 204

    row = await db.get(GlobalConfig, "litellm.api_key")
    assert row is not None
    assert row.is_secret is True
    assert row.value != "sk-test-123"  # must be encrypted


@pytest.mark.asyncio
async def test_patch_config_clears_value_with_null(
    client: AsyncClient, superuser_headers: dict, db: AsyncSession
) -> None:
    db.add(GlobalConfig(key="n8n.url", value="http://n8n:5678", is_secret=False))
    await db.commit()

    r = await client.patch(
        "/api/v1/superadmin/config/",
        json={"key": "n8n.url", "value": None},
        headers=superuser_headers,
    )
    assert r.status_code == 204

    row = await db.get(GlobalConfig, "n8n.url")
    assert row is not None
    assert row.value is None


@pytest.mark.asyncio
async def test_patch_config_unknown_key_returns_400(
    client: AsyncClient, superuser_headers: dict
) -> None:
    r = await client.patch(
        "/api/v1/superadmin/config/",
        json={"key": "evil.injection", "value": "x"},
        headers=superuser_headers,
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_patch_config_requires_superuser(
    client: AsyncClient, auth_headers: dict
) -> None:
    r = await client.patch(
        "/api/v1/superadmin/config/",
        json={"key": "litellm.url", "value": "x"},
        headers=auth_headers,
    )
    assert r.status_code in (401, 403)
