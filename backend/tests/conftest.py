import pytest
import pytest_asyncio
from typing import AsyncGenerator

from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import get_db
from app.deps import get_current_user
from app.models.base import Base
from app.models.user import User
from app.models.organization import Organization
from app.models.membership import Membership, MembershipRole
from app.models.role import Role, Permission, RolePermission

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncTestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with AsyncTestSession() as session:
        await _seed_system_data(session)
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_system_data(session: AsyncSession) -> None:
    """Seed minimal system roles and permissions for tests."""
    import uuid
    permissions_data = [
        ("org", "read"), ("org", "update"), ("org", "delete"),
        ("membership", "read"), ("membership", "invite"), ("membership", "update"), ("membership", "delete"),
        ("role", "read"), ("role", "create"), ("role", "update"), ("role", "delete"), ("role", "assign"),
        ("group", "read"), ("group", "create"), ("group", "update"), ("group", "delete"), ("group", "manage"),
        ("plugin", "read"), ("plugin", "activate"), ("plugin", "configure"), ("plugin", "deactivate"),
        ("workflow", "read"), ("workflow", "create"), ("workflow", "update"), ("workflow", "delete"), ("workflow", "execute"),
        ("agent", "read"), ("agent", "create"), ("agent", "update"), ("agent", "delete"), ("agent", "invoke"),
        ("story", "read"), ("story", "create"), ("story", "update"), ("story", "delete"),
        ("inbox", "read"), ("inbox", "manage"), ("inbox", "update"),
        ("calendar", "read"), ("calendar", "manage"), ("calendar", "create"),
    ]
    perm_map = {}
    for resource, action in permissions_data:
        perm = Permission(resource=resource, action=action)
        session.add(perm)
        perm_map[f"{resource}:{action}"] = perm
    await session.flush()

    roles_data = {
        "org_owner": list(perm_map.keys()),
        "org_admin": [p for p in perm_map.keys() if p != "org:delete"],
        "org_member": ["org:read", "membership:read", "group:read", "plugin:read", "workflow:read",
                       "agent:read", "story:read", "story:create", "story:update",
                       "inbox:read", "inbox:update", "calendar:read", "calendar:create"],
        "org_guest": ["org:read", "membership:read"],
    }
    for role_name, perm_keys in roles_data.items():
        role = Role(name=role_name, is_system=True, description=f"System role: {role_name}")
        session.add(role)
        await session.flush()
        for perm_key in perm_keys:
            if perm_key in perm_map:
                session.add(RolePermission(role_id=role.id, permission_id=perm_map[perm_key].id))
    await session.commit()


@pytest_asyncio.fixture(scope="function")
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def test_user(db: AsyncSession) -> User:
    """Test user with authentik_id set (no password_hash needed)."""
    user = User(
        email="testuser@example.com",
        authentik_id="test-authentik-id-1",
        display_name="Test User",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def test_user_2(db: AsyncSession) -> User:
    user = User(
        email="testuser2@example.com",
        authentik_id="test-authentik-id-2",
        display_name="Test User 2",
        is_active=True,
        email_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture(scope="function")
async def auth_headers(client: AsyncClient, test_user: User):
    """
    Auth headers for integration tests.
    Overrides get_current_user to return test_user directly —
    auth is unit-tested separately in test_auth_service.py and test_deps.py.
    Yields headers and cleans up its own override to avoid test pollution.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield {"Authorization": "Bearer test-token"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture(scope="function")
async def test_org(db: AsyncSession, test_user: User) -> Organization:
    from app.services.org_service import org_service
    from app.schemas.organization import OrgCreate
    org = await org_service.create(db, OrgCreate(name="Test Organization", slug="test-org"), test_user.id)
    return org
