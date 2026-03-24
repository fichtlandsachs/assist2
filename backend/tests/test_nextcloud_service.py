"""Tests for NextcloudService WebDAV client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_list_files_returns_empty_on_error():
    """Returns empty list when Nextcloud is unreachable."""
    from app.services.nextcloud_service import nextcloud_service

    with patch("app.services.nextcloud_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.request = AsyncMock(side_effect=Exception("Connection refused"))
        mock_cls.return_value = mock_client

        result = await nextcloud_service.list_files("test-org")

    assert result.files == []
    assert result.nextcloud_url is not None


@pytest.mark.asyncio
async def test_list_files_parses_webdav_response():
    """Parses DAV XML response and returns file list, skipping the root folder."""
    from app.services.nextcloud_service import nextcloud_service

    xml_response = """<?xml version="1.0"?>
<d:multistatus xmlns:d="DAV:">
  <d:response>
    <d:href>/remote.php/dav/files/admin/Organizations/test-org/</d:href>
    <d:propstat>
      <d:prop><d:getcontenttype>httpd/unix-directory</d:getcontenttype></d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
  <d:response>
    <d:href>/remote.php/dav/files/admin/Organizations/test-org/Projektplan.docx</d:href>
    <d:propstat>
      <d:prop>
        <d:displayname>Projektplan.docx</d:displayname>
        <d:getcontenttype>application/vnd.openxmlformats-officedocument.wordprocessingml.document</d:getcontenttype>
        <d:getlastmodified>Mon, 24 Mar 2026 10:00:00 GMT</d:getlastmodified>
        <d:getcontentlength>12345</d:getcontentlength>
      </d:prop>
      <d:status>HTTP/1.1 200 OK</d:status>
    </d:propstat>
  </d:response>
</d:multistatus>"""

    with patch("app.services.nextcloud_service.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_resp = MagicMock()
        mock_resp.status_code = 207
        mock_resp.text = xml_response
        mock_resp.raise_for_status = MagicMock()
        mock_client.request = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_client

        result = await nextcloud_service.list_files("test-org")

    assert len(result.files) == 1
    assert result.files[0].name == "Projektplan.docx"
    assert "wordprocessingml" in result.files[0].content_type
    assert result.files[0].size == 12345
