# Admin User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin-UI unter `admin.heykarl.app/users` zeigt alle Nutzer mit System-Präsenz und ermöglicht konsistente Löschung (Authentik + Nextcloud + DB); zusätzlich können Nutzer sich selbst in den Einstellungen löschen.

**Architecture:** Gemeinsamer `UserDeletionService` orchestriert die Löschung best-effort (Authentik → Nextcloud → DB). Zwei Backend-Endpoints nutzen diesen Service: Superadmin-Endpoint für Admin-UI, `/users/me`-Endpoint für Self-Service. Admin-Frontend erhält neue `/users`-Seite mit 2-stufigem Bestätigungs-Dialog. Hauptfrontend erhält Danger-Zone-Sektion in den Settings.

**Tech Stack:** FastAPI + SQLAlchemy async (Backend), httpx (externe APIs), Next.js 15 + Tailwind (Frontend), pytest + AsyncMock (Tests)

---

## File Map

### Neu erstellen
- `backend/app/services/user_deletion_service.py` — Orchestrierungslogik (Authentik → Nextcloud → DB)
- `backend/tests/unit/test_user_deletion_service.py` — Unit-Tests für den Service
- `admin-frontend/app/(protected)/users/page.tsx` — Nutzerliste
- `admin-frontend/components/UserDeleteModal.tsx` — 2-stufiger Bestätigungs-Dialog

### Modifizieren
- `backend/app/services/authentik_client.py` — `delete_user(authentik_id)` ergänzen
- `backend/app/routers/superadmin.py` — `GET /superadmin/users` + `DELETE /superadmin/users/{id}`
- `backend/app/routers/users.py` — `DELETE /users/me`
- `admin-frontend/types.ts` — `AdminUser` + `DeleteResult` Types
- `admin-frontend/lib/api.ts` — `fetchUsers` + `deleteUser` Funktionen
- `admin-frontend/app/(protected)/layout.tsx` — Nav-Eintrag "Nutzer"
- `frontend/app/[org]/settings/page.tsx` — Danger-Zone-Sektion

---

## Task 1: Authentik Client — `delete_user`

**Files:**
- Modify: `backend/app/services/authentik_client.py`
- Test: `backend/tests/unit/test_authentik_client.py`

- [ ] **Step 1: Failing test schreiben**

```python
# In backend/tests/unit/test_authentik_client.py — am Ende der Datei ergänzen
@pytest.mark.asyncio
async def test_delete_user_success():
    """delete_user() sends DELETE to /api/v3/core/users/{id}/ and succeeds on 204."""
    from app.services.authentik_client import authentik_client
    from unittest.mock import AsyncMock, patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.delete = AsyncMock(return_value=mock_resp)

    with patch("app.services.authentik_client.httpx.AsyncClient", return_value=mock_client):
        await authentik_client.delete_user("42")

    mock_client.delete.assert_called_once()
    call_args = mock_client.delete.call_args
    assert "/42/" in call_args[0][0]


@pytest.mark.asyncio
async def test_delete_user_not_found_is_ok():
    """delete_user() treats 404 as success (user already gone)."""
    from app.services.authentik_client import authentik_client
    from unittest.mock import AsyncMock, patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.delete = AsyncMock(return_value=mock_resp)

    with patch("app.services.authentik_client.httpx.AsyncClient", return_value=mock_client):
        # should not raise
        await authentik_client.delete_user("99")
```

- [ ] **Step 2: Test ausführen — muss FEHLSCHLAGEN**

```bash
cd /opt/assist2 && make shell
# Im Container:
pytest tests/unit/test_authentik_client.py::test_delete_user_success -v
```
Erwartet: `AttributeError: 'AuthentikClient' object has no attribute 'delete_user'`

- [ ] **Step 3: `delete_user` in AuthentikClient implementieren**

In `backend/app/services/authentik_client.py` nach der `get_user_by_email`-Methode einfügen (vor `authentik_client = AuthentikClient()`):

```python
    async def delete_user(self, authentik_id: str) -> None:
        """Delete a user in Authentik by their authentik_id (pk).
        Treats 404 as success — user already gone."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                f"{self._users_url}{authentik_id}/",
                headers=self._api_headers,
            )
        if resp.status_code not in (204, 404):
            raise Exception(f"Authentik delete failed: HTTP {resp.status_code}")
```

- [ ] **Step 4: Tests ausführen — müssen GRÜN sein**

```bash
pytest tests/unit/test_authentik_client.py::test_delete_user_success tests/unit/test_authentik_client.py::test_delete_user_not_found_is_ok -v
```
Erwartet: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/authentik_client.py backend/tests/unit/test_authentik_client.py
git commit -m "feat: add delete_user to AuthentikClient"
```

---

## Task 2: UserDeletionService

**Files:**
- Create: `backend/app/services/user_deletion_service.py`
- Create: `backend/tests/unit/test_user_deletion_service.py`

- [ ] **Step 1: Failing tests schreiben**

Datei `backend/tests/unit/test_user_deletion_service.py` erstellen:

```python
"""Unit tests for UserDeletionService."""
import uuid
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


def _make_user(
    *,
    authentik_id: str | None = "ak-42",
    atlassian_account_id: str | None = None,
    github_id: int | None = None,
) -> User:
    u = User(
        id=uuid.uuid4(),
        email="test@example.com",
        display_name="Test User",
        authentik_id=authentik_id,
        atlassian_account_id=atlassian_account_id,
        github_id=github_id,
        is_active=True,
    )
    return u


@pytest.mark.asyncio
async def test_delete_user_success_all_systems(db: AsyncSession):
    """delete_user() calls Authentik + Nextcloud + DB deletion and returns all success."""
    from app.services.user_deletion_service import user_deletion_service

    user = _make_user(authentik_id="ak-42")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.services.user_deletion_service.authentik_client.delete_user",
        new_callable=AsyncMock,
    ) as mock_ak, patch(
        "app.services.user_deletion_service.user_deletion_service._delete_nextcloud_user",
        new_callable=AsyncMock,
    ) as mock_nc:
        result = await user_deletion_service.delete_user(db, user.id)

    assert result["authentik"]["success"] is True
    assert result["nextcloud"]["success"] is True
    assert result["database"]["success"] is True
    mock_ak.assert_called_once_with("ak-42")
    mock_nc.assert_called_once_with("test@example.com")


@pytest.mark.asyncio
async def test_delete_user_authentik_fails_but_db_still_deleted(db: AsyncSession):
    """When Authentik fails, deletion continues and DB is still deleted."""
    from app.services.user_deletion_service import user_deletion_service

    user = _make_user(authentik_id="ak-99")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    user_id = user.id

    with patch(
        "app.services.user_deletion_service.authentik_client.delete_user",
        new_callable=AsyncMock,
        side_effect=Exception("Authentik timeout"),
    ), patch(
        "app.services.user_deletion_service.user_deletion_service._delete_nextcloud_user",
        new_callable=AsyncMock,
    ):
        result = await user_deletion_service.delete_user(db, user_id)

    assert result["authentik"]["success"] is False
    assert "Authentik timeout" in result["authentik"]["error"]
    assert result["database"]["success"] is True


@pytest.mark.asyncio
async def test_delete_user_no_authentik_id_skips_authentik(db: AsyncSession):
    """When authentik_id is None, Authentik step is skipped but marked success."""
    from app.services.user_deletion_service import user_deletion_service

    user = _make_user(authentik_id=None)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    with patch(
        "app.services.user_deletion_service.authentik_client.delete_user",
        new_callable=AsyncMock,
    ) as mock_ak, patch(
        "app.services.user_deletion_service.user_deletion_service._delete_nextcloud_user",
        new_callable=AsyncMock,
    ):
        result = await user_deletion_service.delete_user(db, user.id)

    mock_ak.assert_not_called()
    assert result["authentik"]["success"] is True
    assert result["authentik"].get("skipped") is True


@pytest.mark.asyncio
async def test_delete_user_not_found_raises(db: AsyncSession):
    """delete_user() raises ValueError when user not found."""
    from app.services.user_deletion_service import user_deletion_service

    with pytest.raises(ValueError, match="not found"):
        await user_deletion_service.delete_user(db, uuid.uuid4())
```

- [ ] **Step 2: Tests ausführen — müssen FEHLSCHLAGEN**

```bash
pytest tests/unit/test_user_deletion_service.py -v
```
Erwartet: `ImportError: cannot import name 'user_deletion_service'`

- [ ] **Step 3: UserDeletionService implementieren**

Datei `backend/app/services/user_deletion_service.py` erstellen:

```python
"""Orchestrates consistent user deletion across Authentik, Nextcloud, and the local DB."""
import logging
import uuid

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.story_embedding import StoryEmbedding
from app.models.user import User
from app.models.user_story import UserStory
from app.services.authentik_client import authentik_client

logger = logging.getLogger(__name__)


class UserDeletionService:
    async def delete_user(self, db: AsyncSession, user_id: uuid.UUID) -> dict:
        """Delete a user from all systems, best-effort.

        Execution order: Authentik → Nextcloud → DB.
        DB is always attempted regardless of external failures.

        Returns a dict with per-system results:
          {
            "authentik": {"success": bool, "skipped": bool, "error": str},
            "nextcloud":  {"success": bool, "error": str},
            "database":   {"success": bool, "deleted_embeddings": int, "error": str},
          }
        """
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")

        email = user.email
        authentik_id = user.authentik_id

        results: dict = {}

        # ── 1. Authentik ────────────────────────────────────────────────────
        if authentik_id:
            try:
                await authentik_client.delete_user(authentik_id)
                results["authentik"] = {"success": True}
            except Exception as exc:
                logger.warning("Authentik delete failed for %s: %s", user_id, exc)
                results["authentik"] = {"success": False, "error": str(exc)}
        else:
            results["authentik"] = {"success": True, "skipped": True}

        # ── 2. Nextcloud ────────────────────────────────────────────────────
        try:
            await self._delete_nextcloud_user(email)
            results["nextcloud"] = {"success": True}
        except Exception as exc:
            logger.warning("Nextcloud delete failed for %s: %s", user_id, exc)
            results["nextcloud"] = {"success": False, "error": str(exc)}

        # ── 3. Database ─────────────────────────────────────────────────────
        try:
            # Delete vector embeddings for stories created by this user
            subq = select(UserStory.id).where(UserStory.created_by_id == user_id)
            emb_result = await db.execute(
                delete(StoryEmbedding)
                .where(StoryEmbedding.story_id.in_(subq))
                .returning(StoryEmbedding.id)
            )
            deleted_embeddings = len(emb_result.fetchall())

            # Hard-delete the user (FK cascades handle memberships, etc.)
            await db.delete(user)
            await db.commit()

            results["database"] = {
                "success": True,
                "deleted_embeddings": deleted_embeddings,
            }
        except Exception as exc:
            await db.rollback()
            logger.error("DB delete failed for %s: %s", user_id, exc)
            results["database"] = {"success": False, "error": str(exc)}

        return results

    async def _delete_nextcloud_user(self, email: str) -> None:
        """Delete a Nextcloud user via OCS API. Username = email address."""
        settings = get_settings()
        url = (
            f"{settings.NEXTCLOUD_INTERNAL_URL}/ocs/v1.php/cloud/users/"
            f"{email}"
        )
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.delete(
                url,
                auth=(
                    settings.NEXTCLOUD_ADMIN_USER,
                    settings.NEXTCLOUD_ADMIN_APP_PASSWORD,
                ),
                headers={"OCS-APIRequest": "true"},
            )
        # 200 = deleted, 404 = not found (already gone — treat as success)
        if resp.status_code not in (200, 404):
            raise Exception(f"Nextcloud OCS returned HTTP {resp.status_code}: {resp.text[:200]}")


user_deletion_service = UserDeletionService()
```

- [ ] **Step 4: Tests ausführen — müssen GRÜN sein**

```bash
pytest tests/unit/test_user_deletion_service.py -v
```
Erwartet: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/user_deletion_service.py backend/tests/unit/test_user_deletion_service.py
git commit -m "feat: add UserDeletionService with best-effort multi-system deletion"
```

---

## Task 3: Backend — `GET /superadmin/users`

**Files:**
- Modify: `backend/app/routers/superadmin.py`

- [ ] **Step 1: Endpoint am Ende von `superadmin.py` ergänzen**

Am Ende der Datei (vor dem letzten Block) einfügen:

```python
# ── User management ────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return all active users with system presence and org memberships."""
    from sqlalchemy.orm import selectinload
    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.story_embedding import StoryEmbedding
    from app.models.user_story import UserStory

    result = await db.execute(
        select(User)
        .where(User.deleted_at.is_(None))
        .options(
            selectinload(User.memberships).selectinload(Membership.organization)
        )
        .order_by(User.created_at.desc())
    )
    users = result.scalars().all()

    output = []
    for u in users:
        # Count embeddings for stories created by this user
        emb_count_res = await db.execute(
            select(func.count())
            .select_from(StoryEmbedding)
            .where(
                StoryEmbedding.story_id.in_(
                    select(UserStory.id).where(UserStory.created_by_id == u.id)
                )
            )
        )
        embedding_count: int = emb_count_res.scalar() or 0

        orgs = [
            {
                "id": str(m.organization.id),
                "name": m.organization.name,
                "slug": m.organization.slug,
            }
            for m in u.memberships
            if m.status == "active" and m.organization is not None
        ]

        output.append({
            "id": str(u.id),
            "email": u.email,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
            "is_active": u.is_active,
            "is_superuser": u.is_superuser,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "created_at": u.created_at.isoformat(),
            "has_authentik": u.authentik_id is not None,
            "has_nextcloud": True,  # all users have Nextcloud by default
            "has_atlassian": u.atlassian_account_id is not None,
            "has_github": u.github_id is not None,
            "embedding_count": embedding_count,
            "organizations": orgs,
        })

    return output
```

- [ ] **Step 2: Import `UserStory` am Anfang der Datei ergänzen**

In `backend/app/routers/superadmin.py` den vorhandenen Import-Block anpassen — `UserStory` ist bereits importiert (`from app.models.user_story import UserStory`), also prüfen ob schon vorhanden. Falls nicht, ergänzen:

```python
from app.models.user_story import UserStory
```

- [ ] **Step 3: Manuell testen**

```bash
# Im Backend-Container:
curl -H "Authorization: Bearer <admin-token>" http://localhost:8000/api/v1/superadmin/users | python3 -m json.tool | head -50
```
Erwartet: JSON-Array mit User-Objekten.

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/superadmin.py
git commit -m "feat: add GET /superadmin/users endpoint"
```

---

## Task 4: Backend — `DELETE /superadmin/users/{user_id}` + `DELETE /users/me`

**Files:**
- Modify: `backend/app/routers/superadmin.py`
- Modify: `backend/app/routers/users.py`

- [ ] **Step 1: DELETE-Endpoint in `superadmin.py` ergänzen**

Direkt nach dem `list_users`-Endpoint einfügen:

```python
@router.delete("/users/{user_id}")
async def delete_user_admin(
    user_id: uuid.UUID,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a user from all systems. Admin cannot delete themselves."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account via admin endpoint")
    from app.services.user_deletion_service import user_deletion_service
    try:
        results = await user_deletion_service.delete_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"user_id": str(user_id), "results": results}
```

`uuid` ist bereits in `superadmin.py` importiert — falls nicht: `import uuid` oben ergänzen.

- [ ] **Step 2: `DELETE /users/me` in `users.py` ergänzen**

Am Ende von `backend/app/routers/users.py` einfügen:

```python
class DeleteAccountRequest(BaseModel):
    refresh_token: str | None = None


@router.delete(
    "/users/me",
    status_code=200,
    summary="Delete my own account from all systems",
)
async def delete_my_account(
    data: DeleteAccountRequest = DeleteAccountRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Self-service account deletion. Removes user from Authentik, Nextcloud, and DB."""
    from app.services.user_deletion_service import user_deletion_service
    results = await user_deletion_service.delete_user(db, current_user.id)
    return {"user_id": str(current_user.id), "results": results}
```

`BaseModel` ist bereits in `users.py` importiert.

- [ ] **Step 3: Manuell testen (Admin-Endpoint)**

```bash
curl -X DELETE \
  -H "Authorization: Bearer <admin-token>" \
  http://localhost:8000/api/v1/superadmin/users/<some-test-user-uuid>
```
Erwartet: `{"user_id": "...", "results": {"authentik": {...}, "nextcloud": {...}, "database": {...}}}`

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/superadmin.py backend/app/routers/users.py
git commit -m "feat: add DELETE /superadmin/users/{id} and DELETE /users/me"
```

---

## Task 5: Admin Frontend — Types + API-Funktionen

**Files:**
- Modify: `admin-frontend/types.ts`
- Modify: `admin-frontend/lib/api.ts`

- [ ] **Step 1: Types in `admin-frontend/types.ts` ergänzen**

Am Ende der Datei anhängen:

```typescript
export interface AdminUserOrg {
  id: string;
  name: string;
  slug: string;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at: string | null;
  created_at: string;
  has_authentik: boolean;
  has_nextcloud: boolean;
  has_atlassian: boolean;
  has_github: boolean;
  embedding_count: number;
  organizations: AdminUserOrg[];
}

export interface SystemDeleteResult {
  success: boolean;
  skipped?: boolean;
  error?: string;
  deleted_embeddings?: number;
}

export interface DeleteUserResult {
  user_id: string;
  results: {
    authentik: SystemDeleteResult;
    nextcloud: SystemDeleteResult;
    database: SystemDeleteResult;
  };
}
```

- [ ] **Step 2: API-Funktionen in `admin-frontend/lib/api.ts` ergänzen**

Am Ende der Datei anhängen:

```typescript
export async function fetchUsers(): Promise<AdminUser[]> {
  return adminFetch<AdminUser[]>("/api/v1/superadmin/users");
}

export async function deleteUser(userId: string): Promise<DeleteUserResult> {
  return adminFetch<DeleteUserResult>(`/api/v1/superadmin/users/${userId}`, {
    method: "DELETE",
  });
}
```

Imports in `api.ts` ergänzen (oben):

```typescript
import type { ComponentStatus, OrgMetrics, ConfigMap, AdminUser, DeleteUserResult } from "@/types";
```

- [ ] **Step 3: TypeScript-Check**

```bash
cd /opt/assist2/admin-frontend && npx tsc --noEmit
```
Erwartet: keine Fehler

- [ ] **Step 4: Commit**

```bash
git add admin-frontend/types.ts admin-frontend/lib/api.ts
git commit -m "feat: add AdminUser types and fetchUsers/deleteUser API functions"
```

---

## Task 6: Admin Frontend — `UserDeleteModal` Komponente

**Files:**
- Create: `admin-frontend/components/UserDeleteModal.tsx`

- [ ] **Step 1: Komponente erstellen**

Datei `admin-frontend/components/UserDeleteModal.tsx` erstellen:

```typescript
"use client";

import { useState } from "react";
import type { AdminUser, DeleteUserResult, SystemDeleteResult } from "@/types";
import { deleteUser } from "@/lib/api";

interface Props {
  user: AdminUser;
  onClose: () => void;
  onDeleted: (result: DeleteUserResult) => void;
}

type Stage = "confirm" | "verify" | "result";

function SystemRow({ name, result }: { name: string; result: SystemDeleteResult }) {
  const ok = result.success;
  return (
    <div className="flex items-start gap-2 py-1.5 border-b last:border-0" style={{ borderColor: "rgba(35,31,31,0.08)" }}>
      <span
        className="mt-0.5 text-xs font-bold w-4 shrink-0"
        style={{ color: ok ? "#526b5e" : "var(--warn)", fontFamily: "var(--font-mono)" }}
      >
        {ok ? "✓" : "✗"}
      </span>
      <div>
        <span className="text-xs font-medium" style={{ fontFamily: "var(--font-mono)", color: "var(--ink)" }}>
          {name}
        </span>
        {result.skipped && (
          <span className="ml-2 text-xs" style={{ color: "var(--ink-faint)" }}>nicht verknüpft</span>
        )}
        {!ok && result.error && (
          <p className="text-xs mt-0.5" style={{ color: "var(--warn)" }}>{result.error}</p>
        )}
        {ok && result.deleted_embeddings !== undefined && result.deleted_embeddings > 0 && (
          <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{result.deleted_embeddings} Embeddings gelöscht</p>
        )}
      </div>
    </div>
  );
}

export default function UserDeleteModal({ user, onClose, onDeleted }: Props) {
  const [stage, setStage] = useState<Stage>("confirm");
  const [emailInput, setEmailInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DeleteUserResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDelete = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await deleteUser(user.id);
      setResult(res);
      setStage("result");
      onDeleted(res);
    } catch (e) {
      setError("Löschung fehlgeschlagen. Bitte erneut versuchen.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ background: "rgba(35,31,31,0.4)" }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="w-full max-w-md rounded-xl border-2 p-6 space-y-4"
        style={{
          background: "#FFFFFF",
          borderColor: "rgba(35,31,31,0.12)",
          boxShadow: "6px 6px 0 rgba(0,0,0,0.08)",
        }}
      >
        {/* Stage 1 — Bestätigung */}
        {stage === "confirm" && (
          <>
            <h2 className="text-base font-semibold" style={{ color: "var(--ink)", fontFamily: "var(--font-serif)" }}>
              Account löschen?
            </h2>
            <p className="text-sm" style={{ color: "var(--ink-mid)" }}>
              Der Account von <strong>{user.display_name}</strong> ({user.email}) wird endgültig aus allen Systemen entfernt:
            </p>
            <ul className="text-sm space-y-1 pl-4 list-disc" style={{ color: "var(--ink-mid)" }}>
              <li>assist2 Datenbank (inkl. Memberships)</li>
              {user.has_authentik && <li>Authentik (Identity Provider)</li>}
              {user.has_nextcloud && <li>Nextcloud</li>}
              {user.embedding_count > 0 && <li>{user.embedding_count} Story-Embeddings (Vektor-DB)</li>}
            </ul>
            <p className="text-xs font-medium" style={{ color: "var(--warn)" }}>
              Diese Aktion kann nicht rückgängig gemacht werden.
            </p>
            <div className="flex gap-2 pt-2">
              <button
                onClick={onClose}
                className="flex-1 px-4 py-2 text-sm rounded-lg border-2 transition-all"
                style={{ borderColor: "rgba(35,31,31,0.15)", color: "var(--ink-mid)" }}
              >
                Abbrechen
              </button>
              <button
                onClick={() => setStage("verify")}
                className="flex-1 px-4 py-2 text-sm rounded-lg border-2 font-medium transition-all"
                style={{ background: "var(--warn)", borderColor: "var(--warn)", color: "#fff" }}
              >
                Weiter →
              </button>
            </div>
          </>
        )}

        {/* Stage 2 — E-Mail-Bestätigung */}
        {stage === "verify" && (
          <>
            <h2 className="text-base font-semibold" style={{ color: "var(--ink)", fontFamily: "var(--font-serif)" }}>
              Endgültig löschen
            </h2>
            <p className="text-sm" style={{ color: "var(--ink-mid)" }}>
              Zur Bestätigung bitte E-Mail-Adresse eingeben:
            </p>
            <code
              className="block text-xs px-3 py-2 rounded border"
              style={{ background: "var(--paper-warm)", borderColor: "rgba(35,31,31,0.1)", color: "var(--ink)", fontFamily: "var(--font-mono)" }}
            >
              {user.email}
            </code>
            <input
              type="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder={user.email}
              className="w-full px-3 py-2 text-sm rounded-lg border-2 outline-none"
              style={{
                borderColor: emailInput === user.email ? "#526b5e" : "rgba(35,31,31,0.15)",
                fontFamily: "var(--font-mono)",
                color: "var(--ink)",
              }}
              autoFocus
            />
            {error && (
              <p className="text-xs" style={{ color: "var(--warn)" }}>{error}</p>
            )}
            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setStage("confirm")}
                className="flex-1 px-4 py-2 text-sm rounded-lg border-2 transition-all"
                style={{ borderColor: "rgba(35,31,31,0.15)", color: "var(--ink-mid)" }}
              >
                Zurück
              </button>
              <button
                onClick={handleDelete}
                disabled={emailInput !== user.email || loading}
                className="flex-1 px-4 py-2 text-sm rounded-lg border-2 font-medium transition-all disabled:opacity-40"
                style={{ background: "var(--warn)", borderColor: "var(--warn)", color: "#fff" }}
              >
                {loading ? "Löschen…" : "Endgültig löschen"}
              </button>
            </div>
          </>
        )}

        {/* Stage 3 — Ergebnis */}
        {stage === "result" && result && (
          <>
            <h2 className="text-base font-semibold" style={{ color: "var(--ink)", fontFamily: "var(--font-serif)" }}>
              Löschung abgeschlossen
            </h2>
            <div className="space-y-0">
              <SystemRow name="Authentik" result={result.results.authentik} />
              <SystemRow name="Nextcloud" result={result.results.nextcloud} />
              <SystemRow name="Datenbank" result={result.results.database} />
            </div>
            {!result.results.database.success && (
              <p className="text-xs" style={{ color: "var(--warn)" }}>
                Datenbankfehler — User möglicherweise nicht vollständig gelöscht.
              </p>
            )}
            <button
              onClick={onClose}
              className="w-full px-4 py-2 text-sm rounded-lg border-2 font-medium"
              style={{ borderColor: "rgba(35,31,31,0.15)", color: "var(--ink)" }}
            >
              Schließen
            </button>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript-Check**

```bash
cd /opt/assist2/admin-frontend && npx tsc --noEmit
```
Erwartet: keine Fehler

- [ ] **Step 3: Commit**

```bash
git add admin-frontend/components/UserDeleteModal.tsx
git commit -m "feat: add UserDeleteModal with 2-step confirmation"
```

---

## Task 7: Admin Frontend — `/users` Seite + Nav

**Files:**
- Create: `admin-frontend/app/(protected)/users/page.tsx`
- Modify: `admin-frontend/app/(protected)/layout.tsx`

- [ ] **Step 1: Nav-Eintrag in `layout.tsx` ergänzen**

In `admin-frontend/app/(protected)/layout.tsx` das `map`-Array der Nav-Links erweitern:

```typescript
// Vorher:
{ href: "/dashboard", label: "Komponenten" },
{ href: "/resources", label: "Ressourcen" },
{ href: "/settings/system", label: "Einstellungen" },

// Nachher:
{ href: "/dashboard", label: "Komponenten" },
{ href: "/resources", label: "Ressourcen" },
{ href: "/users", label: "Nutzer" },
{ href: "/settings/system", label: "Einstellungen" },
```

- [ ] **Step 2: `/users` Seite erstellen**

Verzeichnis anlegen und Datei `admin-frontend/app/(protected)/users/page.tsx` erstellen:

```typescript
"use client";

import { useEffect, useState, useMemo } from "react";
import { fetchUsers } from "@/lib/api";
import type { AdminUser, DeleteUserResult } from "@/types";
import UserDeleteModal from "@/components/UserDeleteModal";

const SYSTEM_BADGES: { key: keyof AdminUser; label: string; color: string }[] = [
  { key: "has_authentik",  label: "authentik",  color: "#4B5563" },
  { key: "has_nextcloud",  label: "nextcloud",  color: "#0082C9" },
  { key: "has_atlassian",  label: "atlassian",  color: "#0052CC" },
  { key: "has_github",     label: "github",     color: "#24292E" },
];

function SystemBadge({ label, active, color }: { label: string; active: boolean; color: string }) {
  return (
    <span
      className="inline-block text-xs px-1.5 py-0.5 rounded border"
      style={{
        fontFamily: "var(--font-mono)",
        fontSize: "9px",
        letterSpacing: ".04em",
        background: active ? `${color}18` : "transparent",
        color: active ? color : "var(--ink-faint)",
        borderColor: active ? `${color}40` : "rgba(35,31,31,0.08)",
        opacity: active ? 1 : 0.5,
      }}
    >
      {label}
    </span>
  );
}

function Avatar({ user }: { user: AdminUser }) {
  if (user.avatar_url) {
    return (
      <img
        src={user.avatar_url}
        alt={user.display_name}
        className="w-8 h-8 rounded-full object-cover border"
        style={{ borderColor: "rgba(35,31,31,0.1)" }}
      />
    );
  }
  return (
    <div
      className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold select-none shrink-0"
      style={{
        background: "var(--paper-warm)",
        color: "var(--ink-mid)",
        border: "1px solid rgba(35,31,31,0.1)",
        fontFamily: "var(--font-serif)",
      }}
    >
      {user.display_name.charAt(0).toUpperCase()}
    </div>
  );
}

export default function UsersPage() {
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null);
  const [deletedIds, setDeletedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchUsers()
      .then(setUsers)
      .catch(() => setError("Nutzerliste konnte nicht geladen werden."));
  }, []);

  const filtered = useMemo(() => {
    if (!users) return [];
    const q = search.toLowerCase();
    return users.filter(
      (u) =>
        !deletedIds.has(u.id) &&
        (u.display_name.toLowerCase().includes(q) || u.email.toLowerCase().includes(q))
    );
  }, [users, search, deletedIds]);

  function handleDeleted(result: DeleteUserResult) {
    if (result.results.database.success) {
      setDeletedIds((prev) => new Set([...prev, result.user_id]));
    }
  }

  function formatDate(iso: string | null) {
    if (!iso) return "–";
    return new Date(iso).toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>
            Nutzer
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
            Alle Accounts · inkl. System-Verknüpfungen
          </p>
        </div>
        {users && (
          <span className="text-xs px-3 py-1 rounded-full" style={{ background: "var(--paper-warm)", color: "var(--ink-faint)" }}>
            {filtered.length} Nutzer
          </span>
        )}
      </div>

      {/* Suchfeld */}
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Name oder E-Mail suchen…"
        className="w-full px-3 py-2 text-sm rounded-lg border-2 outline-none"
        style={{
          borderColor: "rgba(35,31,31,0.12)",
          fontFamily: "var(--font-body)",
          color: "var(--ink)",
          background: "#fff",
        }}
      />

      {error && (
        <p className="text-sm" style={{ color: "var(--warn)" }}>{error}</p>
      )}

      {!users && !error && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade…</p>
      )}

      {/* Tabelle */}
      {users && (
        <div className="border-2 rounded-xl overflow-hidden" style={{ borderColor: "rgba(35,31,31,0.1)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "var(--paper-warm)", borderBottom: "2px solid rgba(35,31,31,0.08)" }}>
                <th className="text-left px-4 py-2.5 text-xs font-semibold" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>Nutzer</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>Systeme</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>Orgs</th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>Letzter Login</th>
                <th className="px-4 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm" style={{ color: "var(--ink-faint)" }}>
                    {search ? "Keine Treffer." : "Keine Nutzer gefunden."}
                  </td>
                </tr>
              )}
              {filtered.map((user) => (
                <tr
                  key={user.id}
                  className="border-t"
                  style={{ borderColor: "rgba(35,31,31,0.06)" }}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar user={user} />
                      <div>
                        <div className="font-medium" style={{ color: "var(--ink)" }}>
                          {user.display_name}
                          {user.is_superuser && (
                            <span className="ml-1.5 text-xs px-1 py-0.5 rounded" style={{ background: "#231F1F", color: "#fff", fontFamily: "var(--font-mono)", fontSize: "9px" }}>
                              superadmin
                            </span>
                          )}
                        </div>
                        <div className="text-xs" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {SYSTEM_BADGES.map(({ key, label, color }) => (
                        <SystemBadge key={key} label={label} active={!!user[key]} color={color} />
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {user.organizations.length === 0 ? (
                        <span className="text-xs" style={{ color: "var(--ink-faint)" }}>–</span>
                      ) : (
                        user.organizations.map((org) => (
                          <span
                            key={org.id}
                            className="text-xs px-1.5 py-0.5 rounded border"
                            style={{ fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--ink-mid)", borderColor: "rgba(35,31,31,0.1)", background: "var(--paper-warm)" }}
                          >
                            {org.name}
                          </span>
                        ))
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-mono)" }}>
                    {formatDate(user.last_login_at)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => setDeleteTarget(user)}
                      className="px-2.5 py-1 text-xs rounded-lg border-2 transition-all"
                      style={{
                        fontFamily: "var(--font-mono)",
                        color: "var(--warn)",
                        borderColor: "rgba(139,94,82,.2)",
                        background: "transparent",
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(139,94,82,.08)"; }}
                      onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                    >
                      Löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {deleteTarget && (
        <UserDeleteModal
          user={deleteTarget}
          onClose={() => setDeleteTarget(null)}
          onDeleted={(result) => {
            handleDeleted(result);
            setDeleteTarget(null);
          }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 3: TypeScript-Check**

```bash
cd /opt/assist2/admin-frontend && npx tsc --noEmit
```
Erwartet: keine Fehler

- [ ] **Step 4: Build-Check**

```bash
cd /opt/assist2 && docker compose -f infra/docker-compose.yml build admin-frontend
```
Erwartet: Build erfolgreich

- [ ] **Step 5: Commit**

```bash
git add admin-frontend/app/\(protected\)/users/ admin-frontend/app/\(protected\)/layout.tsx
git commit -m "feat: add /users admin page with delete modal and nav entry"
```

---

## Task 8: Hauptfrontend — Danger Zone in User-Settings

**Files:**
- Modify: `frontend/app/[org]/settings/page.tsx`

- [ ] **Step 1: Danger-Zone-State und Handler ergänzen**

In `frontend/app/[org]/settings/page.tsx` oben in der Komponente (nach den bestehenden `useState`-Deklarationen) ergänzen:

```typescript
// Account deletion state
const [deleteStage, setDeleteStage] = useState<"idle" | "confirm" | "verify" | "deleting" | "done">("idle");
const [deleteEmailInput, setDeleteEmailInput] = useState("");
const [deleteError, setDeleteError] = useState<string | null>(null);
const { logout } = useAuth();

const handleDeleteAccount = async () => {
  setDeleteStage("deleting");
  setDeleteError(null);
  try {
    await apiRequest("/api/v1/users/me", { method: "DELETE" });
    setDeleteStage("done");
    setTimeout(async () => {
      await logout();
    }, 2000);
  } catch {
    setDeleteError("Fehler beim Löschen. Bitte erneut versuchen.");
    setDeleteStage("verify");
  }
};
```

`useAuth` ist bereits in der Datei importiert (`import { useAuth } from "@/lib/auth/context"`).

- [ ] **Step 2: Danger-Zone-UI am Ende der Settings-Seite einfügen**

Am Ende der return-Anweisung, nach dem letzten bestehenden `<section>`-Block, vor dem schließenden `</div>` der Hauptseite einfügen:

```tsx
{/* ── Danger Zone ─────────────────────────────────────────────────── */}
<section className="mt-10 border-t-2 pt-8" style={{ borderColor: "rgba(139,94,82,.2)" }}>
  <h2 className="text-base font-semibold mb-1" style={{ color: "var(--warn)" }}>
    Gefahrenzone
  </h2>
  <p className="text-sm mb-4" style={{ color: "var(--ink-mid)" }}>
    Das Löschen deines Accounts entfernt alle deine Daten aus allen Systemen — dauerhaft und unwiderruflich.
  </p>

  {deleteStage === "idle" && (
    <button
      onClick={() => setDeleteStage("confirm")}
      className="px-4 py-2 text-sm rounded-lg border-2 font-medium transition-all"
      style={{ borderColor: "rgba(139,94,82,.4)", color: "var(--warn)", background: "transparent" }}
    >
      Account löschen…
    </button>
  )}

  {deleteStage === "confirm" && (
    <div className="p-4 rounded-xl border-2 space-y-3 max-w-md" style={{ borderColor: "rgba(139,94,82,.3)", background: "rgba(139,94,82,.04)" }}>
      <p className="text-sm font-medium" style={{ color: "var(--warn)" }}>
        Account wirklich löschen?
      </p>
      <ul className="text-sm space-y-0.5 pl-4 list-disc" style={{ color: "var(--ink-mid)" }}>
        <li>Alle Memberships werden entfernt</li>
        <li>Authentik-Account wird gelöscht</li>
        <li>Nextcloud-Account wird gelöscht</li>
        <li>Alle Story-Embeddings werden gelöscht</li>
      </ul>
      <div className="flex gap-2 pt-1">
        <button
          onClick={() => setDeleteStage("idle")}
          className="px-3 py-1.5 text-xs rounded-lg border-2"
          style={{ borderColor: "rgba(35,31,31,0.15)", color: "var(--ink-mid)" }}
        >
          Abbrechen
        </button>
        <button
          onClick={() => setDeleteStage("verify")}
          className="px-3 py-1.5 text-xs rounded-lg border-2 font-medium"
          style={{ background: "var(--warn)", borderColor: "var(--warn)", color: "#fff" }}
        >
          Weiter →
        </button>
      </div>
    </div>
  )}

  {(deleteStage === "verify" || deleteStage === "deleting") && (
    <div className="p-4 rounded-xl border-2 space-y-3 max-w-md" style={{ borderColor: "rgba(139,94,82,.3)", background: "rgba(139,94,82,.04)" }}>
      <p className="text-sm" style={{ color: "var(--ink-mid)" }}>
        Zur Bestätigung E-Mail-Adresse eingeben:
      </p>
      <code
        className="block text-xs px-3 py-2 rounded border"
        style={{ background: "var(--paper-warm)", borderColor: "rgba(35,31,31,0.1)", color: "var(--ink)", fontFamily: "var(--font-mono)" }}
      >
        {user?.email}
      </code>
      <input
        type="email"
        value={deleteEmailInput}
        onChange={(e) => setDeleteEmailInput(e.target.value)}
        placeholder={user?.email ?? ""}
        className="w-full px-3 py-2 text-sm rounded-lg border-2 outline-none"
        style={{
          borderColor: deleteEmailInput === user?.email ? "#526b5e" : "rgba(35,31,31,0.15)",
          fontFamily: "var(--font-mono)",
          color: "var(--ink)",
        }}
        disabled={deleteStage === "deleting"}
      />
      {deleteError && (
        <p className="text-xs" style={{ color: "var(--warn)" }}>{deleteError}</p>
      )}
      <div className="flex gap-2">
        <button
          onClick={() => { setDeleteStage("confirm"); setDeleteEmailInput(""); setDeleteError(null); }}
          disabled={deleteStage === "deleting"}
          className="px-3 py-1.5 text-xs rounded-lg border-2 disabled:opacity-40"
          style={{ borderColor: "rgba(35,31,31,0.15)", color: "var(--ink-mid)" }}
        >
          Zurück
        </button>
        <button
          onClick={handleDeleteAccount}
          disabled={deleteEmailInput !== user?.email || deleteStage === "deleting"}
          className="px-3 py-1.5 text-xs rounded-lg border-2 font-medium disabled:opacity-40"
          style={{ background: "var(--warn)", borderColor: "var(--warn)", color: "#fff" }}
        >
          {deleteStage === "deleting" ? "Löschen…" : "Endgültig löschen"}
        </button>
      </div>
    </div>
  )}

  {deleteStage === "done" && (
    <p className="text-sm" style={{ color: "#526b5e" }}>
      Account gelöscht. Du wirst in Kürze abgemeldet…
    </p>
  )}
</section>
```

`user` kommt aus dem bestehenden `useAuth()`-Hook — prüfen ob die Variable `user` in der Komponente bereits verfügbar ist (sie ist bereits via `const { user } = useAuth()` vorhanden).

- [ ] **Step 3: TypeScript-Check**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit
```
Erwartet: keine Fehler

- [ ] **Step 4: Build-Check**

```bash
cd /opt/assist2 && docker compose -f infra/docker-compose.yml build frontend
```
Erwartet: Build erfolgreich

- [ ] **Step 5: Commit**

```bash
git add frontend/app/\[org\]/settings/page.tsx
git commit -m "feat: add danger zone account deletion to user settings"
```

---

## Task 9: Deployment + Smoke-Test

- [ ] **Step 1: Alle Services neu starten**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build backend admin-frontend frontend
```

- [ ] **Step 2: Backend Health-Check**

```bash
curl https://heykarl.app/api/v1/health
```
Erwartet: `{"status": "ok"}`

- [ ] **Step 3: Smoke-Test Users-Endpoint**

```bash
# Admin-Token aus Browser-DevTools holen, dann:
curl -H "Authorization: Bearer <admin-token>" https://heykarl.app/api/v1/superadmin/users | python3 -m json.tool | head -30
```
Erwartet: JSON-Array mit mindestens einem User-Objekt.

- [ ] **Step 4: Admin-UI prüfen**

`https://admin.heykarl.app/users` im Browser öffnen.
Checkliste:
- [ ] Nutzerliste lädt korrekt
- [ ] System-Badges zeigen korrekte Verknüpfungen
- [ ] Suchfeld filtert in Echtzeit
- [ ] "Löschen"-Button öffnet Modal Stufe 1
- [ ] Falsche E-Mail blockiert Stufe-2-Button
- [ ] Korrekte E-Mail aktiviert "Endgültig löschen"-Button
- [ ] Ergebnis-Summary nach Löschung sichtbar

- [ ] **Step 5: Finaler Commit falls nötig**

```bash
git add -A && git commit -m "chore: deployment smoke-test complete"
```
