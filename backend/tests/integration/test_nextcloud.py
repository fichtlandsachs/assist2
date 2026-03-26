"""Integration tests for Nextcloud proxy endpoints."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.models.user import User
from app.schemas.nextcloud import NextcloudFile, NextcloudFileList


def _mock_file_list() -> NextcloudFileList:
    return NextcloudFileList(
        files=[
            NextcloudFile(
                name="report.pdf",
                href="/remote.php/dav/files/admin/Organizations/test-org/report.pdf",
                content_type="application/pdf",
                last_modified=None,
                size=1024,
            )
        ],
        nextcloud_url="https://cloud.example.com",
    )


# ---------------------------------------------------------------------------
# GET /organizations/{org_id}/nextcloud/files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_org_files_requires_membership(
    client: AsyncClient,
    auth_headers: dict,
):
    """A random org_id that test_user is not a member of → 403."""
    random_org_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/organizations/{random_org_id}/nextcloud/files",
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_org_files_success(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """Owner of the org can list org files; service is mocked."""
    with patch(
        "app.routers.nextcloud.nextcloud_service.list_files",
        new=AsyncMock(return_value=_mock_file_list()),
    ):
        resp = await client.get(
            f"/api/v1/organizations/{test_org.id}/nextcloud/files",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert len(data["files"]) == 1
    assert data["files"][0]["name"] == "report.pdf"
    assert "nextcloud_url" in data


# ---------------------------------------------------------------------------
# GET /organizations/{org_id}/nextcloud/files/personal
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_personal_files_requires_membership(
    client: AsyncClient,
    auth_headers: dict,
):
    """A random org_id → 403 for personal files too."""
    resp = await client.get(
        f"/api/v1/organizations/{uuid.uuid4()}/nextcloud/files/personal",
        headers=auth_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_personal_files_success(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """Member can list personal files; returns empty list."""
    empty = NextcloudFileList(files=[], nextcloud_url="https://cloud.example.com")
    with patch(
        "app.routers.nextcloud.nextcloud_service.list_personal_files",
        new=AsyncMock(return_value=empty),
    ):
        resp = await client.get(
            f"/api/v1/organizations/{test_org.id}/nextcloud/files/personal",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["files"] == []
    assert data["nextcloud_url"] == "https://cloud.example.com"


# ---------------------------------------------------------------------------
# POST /organizations/{org_id}/nextcloud/files/personal/upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_personal_file_requires_membership(
    client: AsyncClient,
    auth_headers: dict,
):
    """Upload without membership → 403."""
    resp = await client.post(
        f"/api/v1/organizations/{uuid.uuid4()}/nextcloud/files/personal/upload",
        headers=auth_headers,
        files={"file": ("hello.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_personal_file_success(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """File upload to personal folder returns ok=True and the expected path."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.raise_for_status = MagicMock()

    mock_mkcol_response = MagicMock()
    mock_mkcol_response.status_code = 201

    mock_httpx_client = AsyncMock()
    mock_httpx_client.request = AsyncMock(return_value=mock_mkcol_response)
    mock_httpx_client.put = AsyncMock(return_value=mock_response)
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.nextcloud.httpx.AsyncClient", return_value=mock_httpx_client), \
         patch("app.routers.nextcloud.get_settings") as mock_get_settings:
        settings = MagicMock()
        settings.NEXTCLOUD_INTERNAL_URL = "http://nextcloud"
        settings.NEXTCLOUD_ADMIN_USER = "admin"
        settings.NEXTCLOUD_ADMIN_APP_PASSWORD = "secret"
        mock_get_settings.return_value = settings

        resp = await client.post(
            f"/api/v1/organizations/{test_org.id}/nextcloud/files/personal/upload",
            headers=auth_headers,
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "test.txt" in data["path"]
    assert "Users" in data["path"]


# ---------------------------------------------------------------------------
# GET /organizations/{org_id}/nextcloud/files/download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_file_requires_membership(
    client: AsyncClient,
    auth_headers: dict,
):
    """Download without membership → 403."""
    resp = await client.get(
        f"/api/v1/organizations/{uuid.uuid4()}/nextcloud/files/download",
        params={"path": "some/file.pdf"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# POST /organizations/{org_id}/nextcloud/files/upload  (org-level upload)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_org_file_requires_membership(
    client: AsyncClient,
    auth_headers: dict,
):
    """Org-level upload without membership → 403."""
    resp = await client.post(
        f"/api/v1/organizations/{uuid.uuid4()}/nextcloud/files/upload",
        headers=auth_headers,
        files={"file": ("doc.pdf", b"pdfdata", "application/pdf")},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_upload_org_file_success(
    client: AsyncClient,
    auth_headers: dict,
    test_org: Organization,
):
    """Org owner can upload a file to the org folder."""
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.raise_for_status = MagicMock()

    mock_httpx_client = AsyncMock()
    mock_httpx_client.put = AsyncMock(return_value=mock_response)
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.nextcloud.httpx.AsyncClient", return_value=mock_httpx_client), \
         patch("app.routers.nextcloud.get_settings") as mock_get_settings:
        settings = MagicMock()
        settings.NEXTCLOUD_INTERNAL_URL = "http://nextcloud"
        settings.NEXTCLOUD_ADMIN_USER = "admin"
        settings.NEXTCLOUD_ADMIN_APP_PASSWORD = "secret"
        mock_get_settings.return_value = settings

        resp = await client.post(
            f"/api/v1/organizations/{test_org.id}/nextcloud/files/upload",
            headers=auth_headers,
            files={"file": ("report.pdf", b"pdfcontent", "application/pdf")},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "report.pdf" in data["path"]
    assert "Organizations" in data["path"]
