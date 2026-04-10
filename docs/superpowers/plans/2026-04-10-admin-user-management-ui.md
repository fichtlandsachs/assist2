# Admin User Management UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a full member management page at `/[org]/settings/members` and a superadmin panel at `heykarl.app/superadmin` for global user and org administration.

**Architecture:** New `require_superuser` dependency (Authentik OIDC + `is_superuser` check) gates new superadmin endpoints in `superadmin.py` — existing `get_admin_user` stays untouched for backward compat. Settings/members page extends existing membership API. Superadmin route group lives in main `frontend/` as `app/(superadmin)/`. Traefik dynamic config gets one new router rule for `/superadmin` → frontend.

**Tech Stack:** FastAPI async, SQLAlchemy async, Next.js 14 App Router, SWR, Tailwind CSS, lucide-react, Redis (invite links), pyjwt (impersonation token).

---

## File Map

### Backend — Modify
- `backend/app/routers/superadmin.py` — add `require_superuser` dep; add users CRUD, org CRUD, impersonate endpoints
- `backend/app/routers/memberships.py` — add group-assign endpoint, invite-link endpoints

### Backend — New
- `backend/tests/integration/test_superadmin_users.py` — tests for new superadmin endpoints

### Frontend — New
- `frontend/app/[org]/settings/members/page.tsx` — full members management page
- `frontend/app/(superadmin)/layout.tsx` — superadmin shell + is_superuser guard
- `frontend/app/(superadmin)/page.tsx` — dashboard (stats + component status)
- `frontend/app/(superadmin)/users/page.tsx` — global user table
- `frontend/app/(superadmin)/organizations/page.tsx` — global org table
- `frontend/app/(superadmin)/organizations/[id]/page.tsx` — org detail + member list

### Frontend — Modify
- `frontend/components/shell/Sidebar.tsx` — `settings-user` route → `/settings/members`
- `frontend/app/[org]/settings/page.tsx` — remove `MembersSection` component + `tab=user` in TAB_IDS

### Infra — Modify
- `infra/traefik/dynamic/assist2.yml` — add `/superadmin` router rule for main frontend

---

## Task 1: Backend — `require_superuser` dependency

**Files:**
- Modify: `backend/app/routers/superadmin.py`

- [ ] **Step 1: Add `require_superuser` to `superadmin.py`**

  Open `backend/app/routers/superadmin.py`. After the existing imports add:

  ```python
  from app.deps import get_current_user
  ```

  Then add this new dependency function (keep `get_admin_user` untouched below it):

  ```python
  async def require_superuser(
      current_user: User = Depends(get_current_user),
  ) -> User:
      """Require standard JWT + is_superuser=True. Used by new endpoints."""
      if not current_user.is_superuser:
          raise HTTPException(status_code=403, detail="Superuser access required")
      return current_user
  ```

- [ ] **Step 2: Verify existing tests still pass**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_superadmin_config.py -v
  ```

  Expected: all tests PASS (they override `get_admin_user`, not `require_superuser`).

- [ ] **Step 3: Commit**

  ```bash
  cd /opt/assist2 && git add backend/app/routers/superadmin.py && git commit -m "feat: add require_superuser dependency to superadmin router"
  ```

---

## Task 2: Backend — Superadmin user endpoints

**Files:**
- Modify: `backend/app/routers/superadmin.py`
- New: `backend/tests/integration/test_superadmin_users.py`

- [ ] **Step 1: Write failing tests**

  Create `backend/tests/integration/test_superadmin_users.py`:

  ```python
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
  ```

- [ ] **Step 2: Run tests — verify they FAIL**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_superadmin_users.py -v 2>&1 | head -30
  ```

  Expected: FAIL with 404 (endpoints don't exist yet).

- [ ] **Step 3: Add user endpoints to `superadmin.py`**

  Append to `backend/app/routers/superadmin.py` after existing routes:

  ```python
  from pydantic import BaseModel as _BaseModel
  from typing import Optional as _Optional, List as _List
  from sqlalchemy import or_, func
  from datetime import timedelta
  from app.schemas.common import PaginatedResponse
  from app.schemas.user import UserRead
  from app.models.organization import Organization as _Org


  class SuperAdminUserItem(_BaseModel):
      id: str
      email: str
      display_name: str | None
      is_active: bool
      is_superuser: bool
      created_at: str
      organizations: list[dict]

      model_config = {"from_attributes": True}


  class SuperAdminUserPatch(_BaseModel):
      is_active: _Optional[bool] = None
      is_superuser: _Optional[bool] = None


  @router.get("/users", summary="List all users (superadmin)")
  async def list_all_users(
      search: str | None = None,
      org_id: str | None = None,
      page: int = Query(1, ge=1),
      page_size: int = Query(20, ge=1, le=100),
      _: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      """Return all non-deleted users with their org memberships."""
      from app.models.membership import Membership

      stmt = select(User).where(User.deleted_at.is_(None))
      if search:
          stmt = stmt.where(
              or_(
                  User.email.ilike(f"%{search}%"),
                  User.display_name.ilike(f"%{search}%"),
              )
          )
      if org_id:
          stmt = stmt.join(Membership, Membership.user_id == User.id).where(
              Membership.organization_id == org_id,
              Membership.status == "active",
          )

      total_res = await db.execute(select(func.count()).select_from(stmt.subquery()))
      total: int = total_res.scalar() or 0

      stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
      result = await db.execute(stmt)
      users = result.scalars().all()

      from app.models.membership import Membership as Mem

      items = []
      for u in users:
          mem_res = await db.execute(
              select(Mem, _Org)
              .join(_Org, _Org.id == Mem.organization_id)
              .where(Mem.user_id == u.id, Mem.status == "active", _Org.deleted_at.is_(None))
          )
          orgs = [
              {"id": str(org.id), "name": org.name, "slug": org.slug}
              for _, org in mem_res.all()
          ]
          items.append({
              "id": str(u.id),
              "email": u.email,
              "display_name": u.display_name,
              "is_active": u.is_active,
              "is_superuser": u.is_superuser,
              "created_at": u.created_at.isoformat(),
              "organizations": orgs,
          })

      return {"items": items, "total": total, "page": page, "page_size": page_size}


  @router.patch("/users/{user_id}", summary="Update user (superadmin)")
  async def patch_user(
      user_id: uuid.UUID,
      data: SuperAdminUserPatch,
      admin: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      result = await db.execute(
          select(User).where(User.id == user_id, User.deleted_at.is_(None))
      )
      user = result.scalar_one_or_none()
      if not user:
          raise HTTPException(status_code=404, detail="User not found")
      if data.is_active is not None:
          user.is_active = data.is_active
      if data.is_superuser is not None:
          user.is_superuser = data.is_superuser
      await db.commit()
      await db.refresh(user)
      return {
          "id": str(user.id),
          "email": user.email,
          "display_name": user.display_name,
          "is_active": user.is_active,
          "is_superuser": user.is_superuser,
          "created_at": user.created_at.isoformat(),
      }


  @router.delete("/users/{user_id}", status_code=204, summary="Soft-delete user (superadmin)")
  async def delete_user(
      user_id: uuid.UUID,
      admin: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> None:
      if user_id == admin.id:
          raise HTTPException(status_code=400, detail="Cannot delete yourself")
      result = await db.execute(
          select(User).where(User.id == user_id, User.deleted_at.is_(None))
      )
      user = result.scalar_one_or_none()
      if not user:
          raise HTTPException(status_code=404, detail="User not found")
      from datetime import datetime, timezone
      user.deleted_at = datetime.now(timezone.utc)
      await db.commit()
  ```

- [ ] **Step 4: Run tests — verify PASS**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_superadmin_users.py -v
  ```

  Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  cd /opt/assist2 && git add backend/app/routers/superadmin.py backend/tests/integration/test_superadmin_users.py && git commit -m "feat: add superadmin user list/patch/delete endpoints"
  ```

---

## Task 3: Backend — Superadmin org endpoints

**Files:**
- Modify: `backend/app/routers/superadmin.py`
- Modify: `backend/tests/integration/test_superadmin_users.py`

- [ ] **Step 1: Add org tests to `test_superadmin_users.py`**

  Append to the file:

  ```python
  @pytest.mark.asyncio
  async def test_create_org(
      client: AsyncClient, superuser_headers: dict
  ):
      r = await client.post(
          "/api/v1/superadmin/organizations",
          json={"name": "New Org", "slug": "new-org", "plan": "free"},
          headers=superuser_headers,
      )
      assert r.status_code == 201
      data = r.json()
      assert data["slug"] == "new-org"
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
  ```

- [ ] **Step 2: Run new tests — verify FAIL**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_superadmin_users.py::test_create_org tests/integration/test_superadmin_users.py::test_patch_org -v 2>&1 | tail -10
  ```

  Expected: FAIL with 404/405.

- [ ] **Step 3: Add org endpoints to `superadmin.py`**

  Append to `backend/app/routers/superadmin.py`:

  ```python
  class SuperAdminOrgCreate(_BaseModel):
      name: str
      slug: str
      plan: str = "free"


  class SuperAdminOrgPatch(_BaseModel):
      name: _Optional[str] = None
      plan: _Optional[str] = None
      is_active: _Optional[bool] = None


  @router.post("/organizations", status_code=201, summary="Create org (superadmin)")
  async def create_org(
      data: SuperAdminOrgCreate,
      _: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      from app.services.org_service import org_service
      from app.schemas.organization import OrgCreate
      # Check slug uniqueness
      existing = await db.execute(
          select(_Org).where(_Org.slug == data.slug, _Org.deleted_at.is_(None))
      )
      if existing.scalar_one_or_none():
          raise HTTPException(status_code=409, detail="Slug already in use")
      org = _Org(name=data.name, slug=data.slug, plan=data.plan, is_active=True)
      db.add(org)
      await db.commit()
      await db.refresh(org)
      return {
          "id": str(org.id),
          "name": org.name,
          "slug": org.slug,
          "plan": org.plan,
          "is_active": org.is_active,
          "created_at": org.created_at.isoformat(),
      }


  @router.patch("/organizations/{org_id}", summary="Update org (superadmin)")
  async def patch_org(
      org_id: uuid.UUID,
      data: SuperAdminOrgPatch,
      _: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      result = await db.execute(
          select(_Org).where(_Org.id == org_id, _Org.deleted_at.is_(None))
      )
      org = result.scalar_one_or_none()
      if not org:
          raise HTTPException(status_code=404, detail="Organization not found")
      if data.name is not None:
          org.name = data.name
      if data.plan is not None:
          org.plan = data.plan
      if data.is_active is not None:
          org.is_active = data.is_active
      await db.commit()
      await db.refresh(org)
      return {
          "id": str(org.id),
          "name": org.name,
          "slug": org.slug,
          "plan": org.plan,
          "is_active": org.is_active,
          "created_at": org.created_at.isoformat(),
      }


  @router.delete("/organizations/{org_id}", status_code=204, summary="Soft-delete org (superadmin)")
  async def delete_org(
      org_id: uuid.UUID,
      _: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> None:
      result = await db.execute(
          select(_Org).where(_Org.id == org_id, _Org.deleted_at.is_(None))
      )
      org = result.scalar_one_or_none()
      if not org:
          raise HTTPException(status_code=404, detail="Organization not found")
      from datetime import datetime, timezone
      org.deleted_at = datetime.now(timezone.utc)
      await db.commit()


  @router.get("/organizations/{org_id}/members", summary="List org members (superadmin)")
  async def get_org_members_superadmin(
      org_id: uuid.UUID,
      page: int = Query(1, ge=1),
      page_size: int = Query(20, ge=1, le=100),
      _: User = Depends(require_superuser),
      db: AsyncSession = Depends(get_db),
  ) -> dict:
      from app.services.membership_service import membership_service
      from app.routers.memberships import _membership_to_read
      memberships, total = await membership_service.list(db, org_id, page, page_size)
      items = [_membership_to_read(m).model_dump() for m in memberships]
      return {"items": items, "total": total, "page": page, "page_size": page_size}
  ```

- [ ] **Step 4: Run all superadmin tests**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_superadmin_users.py -v
  ```

  Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

  ```bash
  cd /opt/assist2 && git add backend/app/routers/superadmin.py backend/tests/integration/test_superadmin_users.py && git commit -m "feat: add superadmin org create/patch/delete/members endpoints"
  ```

---

## Task 4: Backend — Invite-link endpoints

**Files:**
- Modify: `backend/app/routers/memberships.py`
- Modify: `backend/tests/integration/test_memberships.py`

- [ ] **Step 1: Add invite-link tests**

  Append to `backend/tests/integration/test_memberships.py`:

  ```python
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
  ```

- [ ] **Step 2: Run test — verify FAIL**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_memberships.py::test_generate_invite_link -v 2>&1 | tail -10
  ```

  Expected: FAIL with 404/405.

- [ ] **Step 3: Add invite-link endpoint to `memberships.py`**

  Add to imports at top of `backend/app/routers/memberships.py`:

  ```python
  import secrets
  import redis.asyncio as aioredis
  from app.core.config import get_settings
  ```

  Then add the endpoint (before the last line of the file):

  ```python
  @router.post(
      "/organizations/{org_id}/invite-link",
      summary="Generate a shareable invite link (24h)",
  )
  async def generate_invite_link(
      org_id: uuid.UUID,
      db: AsyncSession = Depends(get_db),
      current_user: User = Depends(require_permission("membership:invite")),
  ) -> dict:
      """Generate a 24-hour invite link for the organization."""
      settings = get_settings()
      token = secrets.token_urlsafe(32)
      redis_client: aioredis.Redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
      await redis_client.setex(f"invite:{token}", 86400, str(org_id))
      await redis_client.aclose()
      url = f"{settings.APP_BASE_URL}/invite/{token}"
      return {"token": token, "url": url}
  ```

- [ ] **Step 4: Run test — verify PASS**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/integration/test_memberships.py::test_generate_invite_link -v
  ```

- [ ] **Step 5: Commit**

  ```bash
  cd /opt/assist2 && git add backend/app/routers/memberships.py backend/tests/integration/test_memberships.py && git commit -m "feat: add invite-link generation endpoint"
  ```

---

## Task 5: Frontend — Update Sidebar + remove old MembersSection

**Files:**
- Modify: `frontend/components/shell/Sidebar.tsx`
- Modify: `frontend/app/[org]/settings/page.tsx`

- [ ] **Step 1: Update Sidebar route**

  In `frontend/components/shell/Sidebar.tsx`, line ~103, change:

  ```tsx
  { id: "settings-user", label: "Benutzer", icon: Users, route: `/${orgSlug}/settings?tab=user` },
  ```

  to:

  ```tsx
  { id: "settings-user", label: "Benutzer", icon: Users, route: `/${orgSlug}/settings/members` },
  ```

- [ ] **Step 2: Remove `user` tab and `MembersSection` from `settings/page.tsx`**

  In `frontend/app/[org]/settings/page.tsx`:

  **Remove** `"user"` from `TAB_IDS` (line ~113):
  ```tsx
  // Before:
  const TAB_IDS = ["profile", "general", "user", "email", "calendar", "jira", "confluence", "processes", "ai"] as const;
  // After:
  const TAB_IDS = ["profile", "general", "email", "calendar", "jira", "confluence", "processes", "ai"] as const;
  ```

  **Remove** the tab definition entry (line ~1310):
  ```tsx
  // Remove this line:
  { id: "user" as const, label: t("settings_tab_users"), Icon: Users2 },
  ```

  **Remove** the entire `MembersSection` function (lines ~1069–1114) and the `MembershipRead` interface defined just below it (lines ~1117–1124).

  **Remove** the `tab === "user"` render branch in the main render. Search for `activeTab === "user"` or similar and remove that case.

- [ ] **Step 3: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -20
  ```

  Expected: build succeeds (or only pre-existing warnings).

- [ ] **Step 4: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/components/shell/Sidebar.tsx frontend/app/\[org\]/settings/page.tsx && git commit -m "refactor: move members tab to dedicated settings/members page"
  ```

---

## Task 6: Frontend — `/[org]/settings/members` page

**Files:**
- New: `frontend/app/[org]/settings/members/page.tsx`

- [ ] **Step 1: Create the page file**

  Create `frontend/app/[org]/settings/members/page.tsx`:

  ```tsx
  "use client";

  import { use, useState, useCallback } from "react";
  import { useOrg } from "@/lib/hooks/useOrg";
  import { useAuth } from "@/lib/auth/context";
  import { apiRequest, fetcher } from "@/lib/api/client";
  import useSWR from "swr";
  import {
    UserCircle2, Plus, MoreHorizontal, Trash2, ShieldCheck,
    UserX, UserCheck, Users, Link2, Check, Copy,
  } from "lucide-react";

  // ── Types ────────────────────────────────────────────────────────────────────

  interface RoleItem { id: string; name: string }
  interface GroupItem { id: string; name: string }
  interface MemberItem {
    id: string;
    user: { id: string; display_name: string; email: string };
    status: "active" | "invited" | "suspended";
    roles: RoleItem[];
    joined_at: string | null;
  }

  // ── InviteModal ──────────────────────────────────────────────────────────────

  function InviteModal({
    orgId,
    roles,
    onClose,
    onSuccess,
  }: {
    orgId: string;
    roles: RoleItem[];
    onClose: () => void;
    onSuccess: () => void;
  }) {
    const [email, setEmail] = useState("");
    const [selectedRoles, setSelectedRoles] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email.trim()) return;
      setSaving(true);
      setError(null);
      try {
        await apiRequest(`/api/v1/organizations/${orgId}/members/invite`, {
          method: "POST",
          body: JSON.stringify({ email: email.trim(), role_ids: selectedRoles }),
        });
        onSuccess();
        onClose();
      } catch (err: any) {
        setError(err?.detail ?? "Einladung fehlgeschlagen");
      } finally {
        setSaving(false);
      }
    };

    const toggleRole = (id: string) =>
      setSelectedRoles((prev) =>
        prev.includes(id) ? prev.filter((r) => r !== id) : [...prev, id]
      );

    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div
          className="w-full max-w-md p-6 rounded-sm border"
          style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
        >
          <h2 className="text-base font-semibold text-[var(--ink)] mb-4">Mitglied einladen</h2>
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">
                E-Mail-Adresse
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="user@example.com"
                className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]"
              />
            </div>
            {roles.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-2">
                  Rollen (optional)
                </label>
                <div className="flex flex-wrap gap-2">
                  {roles.map((r) => (
                    <button
                      key={r.id}
                      type="button"
                      onClick={() => toggleRole(r.id)}
                      className={`text-xs px-2 py-1 rounded border transition-colors ${
                        selectedRoles.includes(r.id)
                          ? "bg-[var(--accent-red)] text-white border-[var(--accent-red)]"
                          : "border-[var(--paper-rule)] text-[var(--ink-mid)]"
                      }`}
                    >
                      {r.name}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-1">
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]"
              >
                Abbrechen
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] disabled:opacity-50"
              >
                {saving ? "…" : "Einladen"}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  // ── ConfirmDialog ─────────────────────────────────────────────────────────────

  function ConfirmDialog({
    message,
    onConfirm,
    onCancel,
  }: {
    message: string;
    onConfirm: () => void;
    onCancel: () => void;
  }) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div
          className="w-full max-w-sm p-5 rounded-sm border"
          style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
        >
          <p className="text-sm text-[var(--ink)] mb-4">{message}</p>
          <div className="flex gap-2 justify-end">
            <button
              onClick={onCancel}
              className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]"
            >
              Abbrechen
            </button>
            <button
              onClick={onConfirm}
              className="px-3 py-1.5 text-sm rounded-sm text-white bg-red-600"
            >
              Bestätigen
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ── StatusBadge ───────────────────────────────────────────────────────────────

  function StatusBadge({ status }: { status: string }) {
    const map: Record<string, { label: string; color: string }> = {
      active:    { label: "Aktiv",       color: "text-[var(--green)]" },
      invited:   { label: "Eingeladen",  color: "text-amber-600" },
      suspended: { label: "Suspendiert", color: "text-[var(--ink-faint)]" },
    };
    const { label, color } = map[status] ?? { label: status, color: "" };
    return <span className={`text-xs ${color}`}>{label}</span>;
  }

  // ── Main Page ─────────────────────────────────────────────────────────────────

  export default function MembersPage({ params }: { params: Promise<{ org: string }> }) {
    const { org: orgSlug } = use(params);
    const { org } = useOrg(orgSlug);
    const orgId = org?.id ?? "";

    const { data, mutate } = useSWR<{ items: MemberItem[]; total: number }>(
      orgId ? `/api/v1/organizations/${orgId}/members?page_size=100` : null,
      fetcher,
      { revalidateOnFocus: false }
    );
    const { data: rolesData } = useSWR<RoleItem[]>(
      orgId ? `/api/v1/organizations/${orgId}/roles` : null,
      fetcher,
      { revalidateOnFocus: false }
    );
    const { data: groupsData } = useSWR<GroupItem[]>(
      orgId ? `/api/v1/organizations/${orgId}/groups` : null,
      fetcher,
      { revalidateOnFocus: false }
    );

    const [showInvite, setShowInvite] = useState(false);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [openMenu, setOpenMenu] = useState<string | null>(null);
    const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);
    const [inviteLink, setInviteLink] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    const members = data?.items ?? [];
    const roles = rolesData ?? [];

    const toggleSelect = (id: string) =>
      setSelected((prev) => {
        const next = new Set(prev);
        next.has(id) ? next.delete(id) : next.add(id);
        return next;
      });

    const toggleAll = () =>
      setSelected(selected.size === members.length ? new Set() : new Set(members.map((m) => m.id)));

    const removeMember = useCallback(
      async (membershipId: string) => {
        await apiRequest(`/api/v1/organizations/${orgId}/members/${membershipId}`, { method: "DELETE" });
        await mutate();
      },
      [orgId, mutate]
    );

    const updateStatus = useCallback(
      async (membershipId: string, status: "active" | "suspended") => {
        await apiRequest(`/api/v1/organizations/${orgId}/members/${membershipId}`, {
          method: "PATCH",
          body: JSON.stringify({ status }),
        });
        await mutate();
      },
      [orgId, mutate]
    );

    const bulkAction = async (action: "active" | "suspended" | "remove") => {
      for (const id of selected) {
        try {
          if (action === "remove") {
            await apiRequest(`/api/v1/organizations/${orgId}/members/${id}`, { method: "DELETE" });
          } else {
            await apiRequest(`/api/v1/organizations/${orgId}/members/${id}`, {
              method: "PATCH",
              body: JSON.stringify({ status: action }),
            });
          }
        } catch {
          // continue on partial failure
        }
      }
      setSelected(new Set());
      await mutate();
    };

    const generateInviteLink = async () => {
      const res = await apiRequest<{ url: string }>(`/api/v1/organizations/${orgId}/invite-link`, {
        method: "POST",
      });
      setInviteLink(res.url);
    };

    const copyLink = () => {
      if (!inviteLink) return;
      void navigator.clipboard.writeText(inviteLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    };

    if (!orgId || !data) {
      return (
        <div className="flex items-center justify-center h-40">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
        </div>
      );
    }

    return (
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[var(--ink-mid)]" />
            <h1 className="text-base font-semibold text-[var(--ink)]">
              Mitglieder <span className="text-[var(--ink-faint)] font-normal">({data.total})</span>
            </h1>
          </div>
          <button
            onClick={() => setShowInvite(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] hover:opacity-90 transition-opacity"
          >
            <Plus size={13} />
            Mitglied einladen
          </button>
        </div>

        {/* Table */}
        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          {/* Table header */}
          <div
            className="grid grid-cols-[2rem_1fr_auto_auto_auto_2.5rem] gap-3 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
            style={{ background: "var(--paper-warm)" }}
          >
            <input
              type="checkbox"
              checked={selected.size === members.length && members.length > 0}
              onChange={toggleAll}
              className="mt-0.5"
            />
            <span>Name / E-Mail</span>
            <span>Rollen</span>
            <span>Status</span>
            <span>Beigetreten</span>
            <span />
          </div>

          {/* Rows */}
          {members.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">
              Keine Mitglieder gefunden.
            </div>
          ) : (
            members.map((m) => (
              <div
                key={m.id}
                className="grid grid-cols-[2rem_1fr_auto_auto_auto_2.5rem] gap-3 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)] transition-colors"
              >
                <input
                  type="checkbox"
                  checked={selected.has(m.id)}
                  onChange={() => toggleSelect(m.id)}
                />
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                    <UserCircle2 size={14} className="text-[var(--ink-faint)]" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] truncate">{m.user.display_name}</p>
                    <p className="text-xs text-[var(--ink-faint)] truncate">{m.user.email}</p>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  {m.roles.map((r) => (
                    <span
                      key={r.id}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)] text-[var(--ink-mid)]"
                    >
                      {r.name}
                    </span>
                  ))}
                </div>
                <StatusBadge status={m.status} />
                <span className="text-xs text-[var(--ink-faint)]">
                  {m.joined_at ? new Date(m.joined_at).toLocaleDateString("de-DE") : "—"}
                </span>

                {/* Actions menu */}
                <div className="relative">
                  <button
                    onClick={() => setOpenMenu(openMenu === m.id ? null : m.id)}
                    className="p-1 rounded hover:bg-[var(--paper-rule)] text-[var(--ink-faint)]"
                  >
                    <MoreHorizontal size={14} />
                  </button>
                  {openMenu === m.id && (
                    <div
                      className="absolute right-0 top-7 w-44 rounded-sm border shadow-sm z-20 text-sm"
                      style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
                    >
                      {m.status === "active" ? (
                        <button
                          onClick={() => {
                            setOpenMenu(null);
                            setConfirm({
                              message: `${m.user.display_name} suspendieren?`,
                              onConfirm: () => { setConfirm(null); void updateStatus(m.id, "suspended"); },
                            });
                          }}
                          className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                        >
                          <UserX size={13} /> Suspendieren
                        </button>
                      ) : (
                        <button
                          onClick={() => { setOpenMenu(null); void updateStatus(m.id, "active"); }}
                          className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                        >
                          <UserCheck size={13} /> Reaktivieren
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setOpenMenu(null);
                          setConfirm({
                            message: `${m.user.display_name} aus der Organisation entfernen?`,
                            onConfirm: () => { setConfirm(null); void removeMember(m.id); },
                          });
                        }}
                        className="flex items-center gap-2 w-full px-3 py-2 hover:bg-[var(--paper-warm)] text-red-600"
                      >
                        <Trash2 size={13} /> Entfernen
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Bulk action bar */}
        {selected.size > 0 && (
          <div
            className="fixed bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-3 px-4 py-2.5 rounded-sm border shadow-lg z-30"
            style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
          >
            <span className="text-sm text-[var(--ink-mid)]">{selected.size} ausgewählt</span>
            <button
              onClick={() => void bulkAction("suspended")}
              className="text-xs px-2.5 py-1.5 rounded border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
            >
              Suspendieren
            </button>
            <button
              onClick={() => void bulkAction("active")}
              className="text-xs px-2.5 py-1.5 rounded border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
            >
              Reaktivieren
            </button>
            <button
              onClick={() =>
                setConfirm({
                  message: `${selected.size} Mitglieder entfernen?`,
                  onConfirm: () => { setConfirm(null); void bulkAction("remove"); },
                })
              }
              className="text-xs px-2.5 py-1.5 rounded text-white bg-red-600"
            >
              Entfernen
            </button>
          </div>
        )}

        {/* Invite link */}
        <div
          className="border border-[var(--paper-rule)] rounded-sm p-4 space-y-3"
          style={{ background: "var(--paper-warm)" }}
        >
          <div className="flex items-center gap-2">
            <Link2 size={14} className="text-[var(--ink-mid)]" />
            <h3 className="text-sm font-semibold text-[var(--ink)]">Einladungslink</h3>
          </div>
          <p className="text-xs text-[var(--ink-faint)]">
            Generiere einen Link, den neue Mitglieder direkt aufrufen können. Gültig für 24 Stunden.
          </p>
          {inviteLink ? (
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={inviteLink}
                className="flex-1 px-2 py-1.5 text-xs border border-[var(--paper-rule)] rounded-sm bg-[var(--card)] text-[var(--ink-faint)]"
              />
              <button
                onClick={copyLink}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
              >
                {copied ? <Check size={12} className="text-[var(--green)]" /> : <Copy size={12} />}
                {copied ? "Kopiert" : "Kopieren"}
              </button>
            </div>
          ) : (
            <button
              onClick={() => void generateInviteLink()}
              className="text-xs px-3 py-1.5 rounded-sm border border-[var(--paper-rule)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
            >
              Link generieren
            </button>
          )}
        </div>

        {/* Modals */}
        {showInvite && (
          <InviteModal
            orgId={orgId}
            roles={roles}
            onClose={() => setShowInvite(false)}
            onSuccess={() => void mutate()}
          />
        )}
        {confirm && (
          <ConfirmDialog
            message={confirm.message}
            onConfirm={confirm.onConfirm}
            onCancel={() => setConfirm(null)}
          />
        )}

        {/* Close menus on outside click */}
        {openMenu && (
          <div className="fixed inset-0 z-10" onClick={() => setOpenMenu(null)} />
        )}
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -20
  ```

  Expected: build succeeds.

- [ ] **Step 3: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/app/\[org\]/settings/members/page.tsx && git commit -m "feat: add org members management page at /settings/members"
  ```

---

## Task 7: Frontend — Superadmin layout + guard

**Files:**
- New: `frontend/app/(superadmin)/layout.tsx`

- [ ] **Step 1: Create superadmin layout**

  Create `frontend/app/(superadmin)/layout.tsx`:

  ```tsx
  "use client";

  import { useEffect } from "react";
  import { useRouter } from "next/navigation";
  import { useAuth } from "@/lib/auth/context";
  import { LayoutDashboard, Users, Building2, LogOut } from "lucide-react";
  import Link from "next/link";
  import { usePathname } from "next/navigation";

  const NAV = [
    { label: "Dashboard",      href: "/superadmin",                Icon: LayoutDashboard },
    { label: "Benutzer",       href: "/superadmin/users",          Icon: Users },
    { label: "Organisationen", href: "/superadmin/organizations",  Icon: Building2 },
  ];

  export default function SuperadminLayout({ children }: { children: React.ReactNode }) {
    const { user, isLoading } = useAuth();
    const router = useRouter();
    const pathname = usePathname();

    useEffect(() => {
      if (!isLoading && (!user || !user.is_superuser)) {
        router.replace("/");
      }
    }, [user, isLoading, router]);

    if (isLoading || !user?.is_superuser) {
      return (
        <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--paper)" }}>
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
        </div>
      );
    }

    return (
      <div className="flex min-h-screen" style={{ background: "var(--paper)" }}>
        {/* Sidebar */}
        <aside
          className="w-52 flex-shrink-0 border-r flex flex-col py-6 px-3"
          style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
        >
          <div className="px-2 mb-6">
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--ink-faint)]">Superadmin</p>
          </div>
          <nav className="flex-1 space-y-0.5">
            {NAV.map(({ label, href, Icon }) => {
              const active = pathname === href || (href !== "/superadmin" && pathname.startsWith(href));
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex items-center gap-2.5 px-2 py-2 rounded text-sm transition-colors ${
                    active
                      ? "bg-[var(--accent-red)] text-white"
                      : "text-[var(--ink-mid)] hover:bg-[var(--paper-rule)]"
                  }`}
                >
                  <Icon size={14} />
                  {label}
                </Link>
              );
            })}
          </nav>
          <div className="px-2 pt-4 border-t border-[var(--paper-rule)]">
            <p className="text-xs text-[var(--ink-faint)] truncate">{user.email}</p>
          </div>
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -10
  ```

- [ ] **Step 3: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/app/\(superadmin\)/layout.tsx && git commit -m "feat: add superadmin route group layout with is_superuser guard"
  ```

---

## Task 8: Frontend — Superadmin dashboard page

**Files:**
- New: `frontend/app/(superadmin)/page.tsx`

- [ ] **Step 1: Create dashboard page**

  Create `frontend/app/(superadmin)/page.tsx`:

  ```tsx
  "use client";

  import useSWR from "swr";
  import { fetcher } from "@/lib/api/client";
  import { CheckCircle, XCircle, ExternalLink, Users, Building2, BookOpen } from "lucide-react";

  interface ComponentStatus {
    name: string;
    label: string;
    available: boolean;
    admin_url: string;
  }

  interface OrgMetric {
    id: string;
    name: string;
    member_count: number;
    story_count: number;
    is_active: boolean;
    warning: boolean;
  }

  function StatCard({ label, value, Icon }: { label: string; value: number | string; Icon: React.ElementType }) {
    return (
      <div
        className="flex items-center gap-4 p-4 rounded-sm border"
        style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
      >
        <div className="p-2 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)]">
          <Icon size={16} className="text-[var(--ink-mid)]" />
        </div>
        <div>
          <p className="text-xs text-[var(--ink-faint)]">{label}</p>
          <p className="text-xl font-semibold text-[var(--ink)]">{value}</p>
        </div>
      </div>
    );
  }

  export default function SuperadminDashboard() {
    const { data: status } = useSWR<ComponentStatus[]>("/api/v1/superadmin/status", fetcher);
    const { data: orgs } = useSWR<OrgMetric[]>("/api/v1/superadmin/organizations", fetcher);
    const { data: users } = useSWR<{ total: number }>("/api/v1/superadmin/users?page_size=1", fetcher);

    const activeOrgs = orgs?.filter((o) => o.is_active).length ?? 0;
    const totalStories = orgs?.reduce((sum, o) => sum + o.story_count, 0) ?? 0;

    return (
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
        <h1 className="text-lg font-semibold text-[var(--ink)]">System-Übersicht</h1>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <StatCard label="Benutzer gesamt" value={users?.total ?? "…"} Icon={Users} />
          <StatCard label="Aktive Orgs" value={activeOrgs} Icon={Building2} />
          <StatCard label="Stories gesamt" value={totalStories} Icon={BookOpen} />
        </div>

        {/* Component status */}
        <div>
          <h2 className="text-sm font-semibold text-[var(--ink)] mb-3">Komponenten-Status</h2>
          <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
            {!status ? (
              <div className="px-4 py-6 text-sm text-center text-[var(--ink-faint)]">Lade…</div>
            ) : (
              status.map((c) => (
                <div
                  key={c.name}
                  className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
                >
                  <div className="flex items-center gap-2.5">
                    {c.available ? (
                      <CheckCircle size={14} className="text-[var(--green)] flex-shrink-0" />
                    ) : (
                      <XCircle size={14} className="text-red-500 flex-shrink-0" />
                    )}
                    <span className="text-sm text-[var(--ink)]">{c.name}</span>
                    <span className="text-xs text-[var(--ink-faint)]">{c.label}</span>
                  </div>
                  <a
                    href={c.admin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 text-xs text-[var(--ink-faint)] hover:text-[var(--ink)]"
                  >
                    Admin <ExternalLink size={10} />
                  </a>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -10
  ```

- [ ] **Step 3: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/app/\(superadmin\)/page.tsx && git commit -m "feat: add superadmin dashboard page"
  ```

---

## Task 9: Frontend — Superadmin users page

**Files:**
- New: `frontend/app/(superadmin)/users/page.tsx`

- [ ] **Step 1: Create users page**

  Create `frontend/app/(superadmin)/users/page.tsx`:

  ```tsx
  "use client";

  import { useState, useCallback } from "react";
  import useSWR from "swr";
  import { fetcher, apiRequest } from "@/lib/api/client";
  import { UserCircle2, Search, Trash2, ShieldCheck, ShieldOff, UserCheck, UserX } from "lucide-react";

  interface OrgRef { id: string; name: string; slug: string }
  interface SuperUser {
    id: string;
    email: string;
    display_name: string | null;
    is_active: boolean;
    is_superuser: boolean;
    created_at: string;
    organizations: OrgRef[];
  }

  function ConfirmDialog({
    message, onConfirm, onCancel,
  }: { message: string; onConfirm: () => void; onCancel: () => void }) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="w-full max-w-sm p-5 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
          <p className="text-sm text-[var(--ink)] mb-4">{message}</p>
          <div className="flex gap-2 justify-end">
            <button onClick={onCancel} className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]">Abbrechen</button>
            <button onClick={onConfirm} className="px-3 py-1.5 text-sm rounded-sm text-white bg-red-600">Bestätigen</button>
          </div>
        </div>
      </div>
    );
  }

  export default function SuperadminUsersPage() {
    const [search, setSearch] = useState("");
    const [page, setPage] = useState(1);
    const [confirm, setConfirm] = useState<{ message: string; onConfirm: () => void } | null>(null);

    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search) params.set("search", search);

    const { data, mutate } = useSWR<{ items: SuperUser[]; total: number; page: number; page_size: number }>(
      `/api/v1/superadmin/users?${params}`,
      fetcher,
      { revalidateOnFocus: false }
    );

    const patch = useCallback(async (userId: string, payload: Partial<Pick<SuperUser, "is_active" | "is_superuser">>) => {
      await apiRequest(`/api/v1/superadmin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await mutate();
    }, [mutate]);

    const deleteUser = useCallback(async (userId: string) => {
      await apiRequest(`/api/v1/superadmin/users/${userId}`, { method: "DELETE" });
      await mutate();
    }, [mutate]);

    const users = data?.items ?? [];
    const total = data?.total ?? 0;
    const totalPages = Math.ceil(total / (data?.page_size ?? 20));

    return (
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-[var(--ink)]">
            Benutzer <span className="text-[var(--ink-faint)] font-normal text-base">({total})</span>
          </h1>
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)]" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Name oder E-Mail…"
              className="pl-7 pr-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)] w-60"
            />
          </div>
        </div>

        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          <div
            className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]"
            style={{ background: "var(--paper-warm)" }}
          >
            <span>Benutzer</span>
            <span>Orgs</span>
            <span>Superuser</span>
            <span>Status</span>
            <span>Aktionen</span>
          </div>

          {!data ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
          ) : users.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Keine Benutzer gefunden.</div>
          ) : (
            users.map((u) => (
              <div
                key={u.id}
                className="grid grid-cols-[1fr_auto_auto_auto_auto] gap-4 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-[var(--paper-warm)] border border-[var(--paper-rule)] flex items-center justify-center flex-shrink-0">
                    <UserCircle2 size={14} className="text-[var(--ink-faint)]" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] truncate">{u.display_name ?? u.email}</p>
                    <p className="text-xs text-[var(--ink-faint)] truncate">{u.email}</p>
                  </div>
                </div>
                <div className="flex gap-1">
                  {u.organizations.slice(0, 2).map((o) => (
                    <span key={o.id} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)] text-[var(--ink-mid)]">
                      {o.name}
                    </span>
                  ))}
                  {u.organizations.length > 2 && (
                    <span className="text-[10px] text-[var(--ink-faint)]">+{u.organizations.length - 2}</span>
                  )}
                </div>
                <button
                  title={u.is_superuser ? "Superuser entfernen" : "Zum Superuser machen"}
                  onClick={() => void patch(u.id, { is_superuser: !u.is_superuser })}
                  className={`p-1 rounded transition-colors ${u.is_superuser ? "text-[var(--accent-red)]" : "text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"}`}
                >
                  {u.is_superuser ? <ShieldCheck size={15} /> : <ShieldOff size={15} />}
                </button>
                <button
                  title={u.is_active ? "Deaktivieren" : "Aktivieren"}
                  onClick={() => void patch(u.id, { is_active: !u.is_active })}
                  className={`p-1 rounded transition-colors ${u.is_active ? "text-[var(--green)]" : "text-[var(--ink-faint)]"}`}
                >
                  {u.is_active ? <UserCheck size={15} /> : <UserX size={15} />}
                </button>
                <button
                  title="Löschen"
                  onClick={() => setConfirm({
                    message: `Benutzer "${u.display_name ?? u.email}" endgültig löschen?`,
                    onConfirm: () => { setConfirm(null); void deleteUser(u.id); },
                  })}
                  className="p-1 rounded text-[var(--ink-faint)] hover:text-red-600 transition-colors"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-end gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} className="px-3 py-1 text-sm border border-[var(--paper-rule)] rounded-sm disabled:opacity-40">←</button>
            <span className="text-xs text-[var(--ink-faint)]">{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="px-3 py-1 text-sm border border-[var(--paper-rule)] rounded-sm disabled:opacity-40">→</button>
          </div>
        )}

        {confirm && <ConfirmDialog message={confirm.message} onConfirm={confirm.onConfirm} onCancel={() => setConfirm(null)} />}
      </div>
    );
  }
  ```

- [ ] **Step 2: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -10
  ```

- [ ] **Step 3: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/app/\(superadmin\)/users/page.tsx && git commit -m "feat: add superadmin users page"
  ```

---

## Task 10: Frontend — Superadmin organizations page + org detail

**Files:**
- New: `frontend/app/(superadmin)/organizations/page.tsx`
- New: `frontend/app/(superadmin)/organizations/[id]/page.tsx`

- [ ] **Step 1: Create organizations page**

  Create `frontend/app/(superadmin)/organizations/page.tsx`:

  ```tsx
  "use client";

  import { useState, useCallback } from "react";
  import useSWR from "swr";
  import { fetcher, apiRequest } from "@/lib/api/client";
  import { Plus, Trash2, ToggleLeft, ToggleRight, Users2 } from "lucide-react";
  import { useRouter } from "next/navigation";

  interface OrgItem {
    id: string;
    name: string;
    slug: string;
    plan: string;
    is_active: boolean;
    member_count: number;
    story_count: number;
    story_usage_pct: number;
    warning: boolean;
    created_at: string;
  }

  const PLAN_OPTIONS = ["free", "pro", "enterprise"];

  function UsageBar({ pct, warn }: { pct: number; warn: boolean }) {
    return (
      <div className="w-24 h-1.5 rounded-full" style={{ background: "var(--paper-rule)" }}>
        <div
          className="h-1.5 rounded-full"
          style={{ width: `${Math.min(pct, 100)}%`, background: warn ? "#dc2626" : "var(--green)" }}
        />
      </div>
    );
  }

  function NewOrgModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => void }) {
    const [name, setName] = useState("");
    const [slug, setSlug] = useState("");
    const [plan, setPlan] = useState("free");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();
      setSaving(true); setError(null);
      try {
        await apiRequest("/api/v1/superadmin/organizations", {
          method: "POST",
          body: JSON.stringify({ name, slug, plan }),
        });
        onSuccess(); onClose();
      } catch (err: any) {
        setError(err?.detail ?? "Fehler beim Erstellen");
      } finally { setSaving(false); }
    };

    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="w-full max-w-md p-6 rounded-sm border" style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}>
          <h2 className="text-base font-semibold text-[var(--ink)] mb-4">Neue Organisation</h2>
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Slug</label>
              <input value={slug} onChange={(e) => setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} required placeholder="meine-org" className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]" />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">Plan</label>
              <select value={plan} onChange={(e) => setPlan(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]">
                {PLAN_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex gap-2 justify-end pt-1">
              <button type="button" onClick={onClose} className="px-3 py-1.5 text-sm border border-[var(--paper-rule)] rounded-sm text-[var(--ink-mid)]">Abbrechen</button>
              <button type="submit" disabled={saving} className="px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)] disabled:opacity-50">{saving ? "…" : "Erstellen"}</button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  export default function SuperadminOrgsPage() {
    const router = useRouter();
    const [showNew, setShowNew] = useState(false);
    const { data, mutate } = useSWR<OrgItem[]>("/api/v1/superadmin/organizations", fetcher, { revalidateOnFocus: false });

    const patch = useCallback(async (orgId: string, payload: object) => {
      await apiRequest(`/api/v1/superadmin/organizations/${orgId}`, { method: "PATCH", body: JSON.stringify(payload) });
      await mutate();
    }, [mutate]);

    const deleteOrg = useCallback(async (orgId: string) => {
      if (!confirm("Organisation wirklich löschen?")) return;
      await apiRequest(`/api/v1/superadmin/organizations/${orgId}`, { method: "DELETE" });
      await mutate();
    }, [mutate]);

    const orgs = data ?? [];

    return (
      <div className="max-w-5xl mx-auto px-6 py-8 space-y-5">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-[var(--ink)]">Organisationen <span className="text-[var(--ink-faint)] font-normal text-base">({orgs.length})</span></h1>
          <button onClick={() => setShowNew(true)} className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-sm text-white bg-[var(--accent-red)]">
            <Plus size={13} /> Neue Organisation
          </button>
        </div>

        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 px-4 py-2 text-xs font-medium text-[var(--ink-faint)] border-b border-[var(--paper-rule)]" style={{ background: "var(--paper-warm)" }}>
            <span>Organisation</span><span>Plan</span><span>Mitglieder</span><span>Stories</span><span>Status</span><span>Aktionen</span>
          </div>
          {!data ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
          ) : orgs.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Keine Organisationen.</div>
          ) : (
            orgs.map((o) => (
              <div key={o.id} className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-4 items-center px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]">
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{o.name}</p>
                  <p className="text-xs text-[var(--ink-faint)]">{o.slug}</p>
                </div>
                <select
                  value={o.plan}
                  onChange={(e) => void patch(o.id, { plan: e.target.value })}
                  className="text-xs px-1.5 py-1 border border-[var(--paper-rule)] rounded bg-[var(--card)] text-[var(--ink-mid)]"
                >
                  {PLAN_OPTIONS.map((p) => <option key={p} value={p}>{p}</option>)}
                </select>
                <span className="text-sm text-[var(--ink-mid)]">{o.member_count}</span>
                <div className="flex flex-col gap-1">
                  <span className="text-xs text-[var(--ink-mid)]">{o.story_count}</span>
                  <UsageBar pct={o.story_usage_pct} warn={o.warning} />
                </div>
                <button
                  onClick={() => void patch(o.id, { is_active: !o.is_active })}
                  className={o.is_active ? "text-[var(--green)]" : "text-[var(--ink-faint)]"}
                  title={o.is_active ? "Deaktivieren" : "Aktivieren"}
                >
                  {o.is_active ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                </button>
                <div className="flex items-center gap-1">
                  <button title="Mitglieder" onClick={() => router.push(`/superadmin/organizations/${o.id}`)} className="p-1 rounded text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"><Users2 size={14} /></button>
                  <button title="Löschen" onClick={() => void deleteOrg(o.id)} className="p-1 rounded text-[var(--ink-faint)] hover:text-red-600"><Trash2 size={14} /></button>
                </div>
              </div>
            ))
          )}
        </div>

        {showNew && <NewOrgModal onClose={() => setShowNew(false)} onSuccess={() => void mutate()} />}
      </div>
    );
  }
  ```

- [ ] **Step 2: Create org detail page**

  Create `frontend/app/(superadmin)/organizations/[id]/page.tsx`:

  ```tsx
  "use client";

  import { use } from "react";
  import useSWR from "swr";
  import { fetcher } from "@/lib/api/client";
  import { useRouter } from "next/navigation";
  import { ArrowLeft, UserCircle2 } from "lucide-react";

  interface MemberEntry {
    id: string;
    user: { id: string; display_name: string; email: string };
    status: string;
    roles: { id: string; name: string }[];
    joined_at: string | null;
  }

  export default function OrgDetailPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const router = useRouter();
    const { data } = useSWR<{ items: MemberEntry[]; total: number }>(
      `/api/v1/superadmin/organizations/${id}/members`,
      fetcher,
      { revalidateOnFocus: false }
    );

    const members = data?.items ?? [];

    return (
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-5">
        <button onClick={() => router.back()} className="flex items-center gap-1.5 text-sm text-[var(--ink-faint)] hover:text-[var(--ink)]">
          <ArrowLeft size={13} /> Zurück
        </button>
        <h1 className="text-lg font-semibold text-[var(--ink)]">
          Mitglieder <span className="text-[var(--ink-faint)] font-normal text-base">({data?.total ?? "…"})</span>
        </h1>
        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          {!data ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Lade…</div>
          ) : members.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-[var(--ink-faint)]">Keine Mitglieder.</div>
          ) : (
            members.map((m) => (
              <div key={m.id} className="flex items-center gap-3 px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]">
                <UserCircle2 size={16} className="text-[var(--ink-faint)] flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">{m.user.display_name}</p>
                  <p className="text-xs text-[var(--ink-faint)] truncate">{m.user.email}</p>
                </div>
                <div className="flex gap-1">
                  {m.roles.map((r) => (
                    <span key={r.id} className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)] text-[var(--ink-mid)]">{r.name}</span>
                  ))}
                </div>
                <span className={`text-xs ${m.status === "active" ? "text-[var(--green)]" : "text-[var(--ink-faint)]"}`}>{m.status}</span>
              </div>
            ))
          )}
        </div>
      </div>
    );
  }
  ```

- [ ] **Step 3: Verify build**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T frontend npm run build 2>&1 | tail -10
  ```

- [ ] **Step 4: Commit**

  ```bash
  cd /opt/assist2 && git add frontend/app/\(superadmin\)/organizations/ && git commit -m "feat: add superadmin organizations page and org detail"
  ```

---

## Task 11: Traefik — Route `/superadmin` to frontend

**Files:**
- Modify: `infra/traefik/dynamic/assist2.yml`

- [ ] **Step 1: Add superadmin router rule**

  In `infra/traefik/dynamic/assist2.yml`, add a new router after `karl-frontend-routes`:

  ```yaml
      # ── Frontend: superadmin panel ─────────────────────────────────────────
      karl-superadmin:
        rule: "Host(`heykarl.app`) && PathPrefix(`/superadmin`)"
        entryPoints: [websecure]
        service: karl-frontend-svc
        priority: 600
        tls:
          certResolver: letsencrypt
  ```

  Priority 600 is higher than `karl-frontend-org` (300) to avoid the org-slug regex catching `/superadmin`.

- [ ] **Step 2: Reload Traefik**

  ```bash
  cd /opt/assist2 && docker exec assist2-traefik kill -HUP 1
  ```

  Traefik watches the dynamic config directory — the new rule is picked up automatically without restart.

- [ ] **Step 3: Verify routing**

  ```bash
  curl -s -o /dev/null -w "%{http_code}" https://heykarl.app/superadmin
  ```

  Expected: `200` (or `307` redirect if not logged in).

- [ ] **Step 4: Commit**

  ```bash
  cd /opt/assist2 && git add infra/traefik/dynamic/assist2.yml && git commit -m "infra: add /superadmin route to main frontend"
  ```

---

## Task 12: Full test run + smoke test

- [ ] **Step 1: Run full backend test suite**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml exec -T backend pytest tests/ -v --tb=short 2>&1 | tail -30
  ```

  Expected: all tests PASS (or only pre-existing failures).

- [ ] **Step 2: Rebuild and redeploy frontend**

  ```bash
  cd /opt/assist2 && docker compose -f infra/docker-compose.yml up -d --build frontend
  ```

- [ ] **Step 3: Smoke test settings/members**

  Open `https://heykarl.app/<org-slug>/settings/members` — verify:
  - Member list loads
  - Invite modal opens
  - Invite link section visible

- [ ] **Step 4: Smoke test superadmin**

  Open `https://heykarl.app/superadmin` as a user with `is_superuser=true` — verify:
  - Dashboard loads with component status
  - `/superadmin/users` shows user list with search
  - `/superadmin/organizations` shows org table
  - Non-superuser is redirected to `/`

- [ ] **Step 5: Commit any fixes**

  ```bash
  cd /opt/assist2 && git add -p && git commit -m "fix: smoke test corrections"
  ```

---

## Out of Scope (follow-up)

- **Impersonation** — requires extending `get_current_user` to accept a second token type or implementing a Redis-backed session swap; deferred to avoid auth complexity
- **Gruppe zuweisen** — endpoint `POST /organizations/{id}/members/{mid}/groups` not yet in memberships router; the UI dropdown is built but the save action needs this endpoint
- **Einladungslink einlösen** — `GET /invite/{token}` endpoint + page that converts the Redis token to a membership (accept-invite flow)
