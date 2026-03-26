"""Nextcloud WebDAV client for listing org files."""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

import httpx

from app.config import get_settings
from app.schemas.nextcloud import NextcloudFile, NextcloudFileList

logger = logging.getLogger(__name__)

_DAV_NS = "DAV:"

_PROPFIND_BODY = b"""<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:displayname/>
    <d:getcontenttype/>
    <d:getlastmodified/>
    <d:getcontentlength/>
  </d:prop>
</d:propfind>"""


def _parse_webdav_response(xml_text: str, org_slug: str) -> List[NextcloudFile]:
    """Parse PROPFIND XML, skip root folder, return up to 10 files sorted by date desc."""
    root = ET.fromstring(xml_text)
    files: List[NextcloudFile] = []

    for response in root.findall(f"{{{_DAV_NS}}}response"):
        href_el = response.find(f"{{{_DAV_NS}}}href")
        if href_el is None:
            continue
        href = href_el.text or ""

        # Skip the directory itself
        if href.rstrip("/").endswith(f"Organizations/{org_slug}"):
            continue

        propstat = response.find(f"{{{_DAV_NS}}}propstat")
        if propstat is None:
            continue

        status_el = propstat.find(f"{{{_DAV_NS}}}status")
        if status_el is None or "200 OK" not in (status_el.text or ""):
            continue

        prop = propstat.find(f"{{{_DAV_NS}}}prop")
        if prop is None:
            continue

        content_type_el = prop.find(f"{{{_DAV_NS}}}getcontenttype")
        content_type = (content_type_el.text or "") if content_type_el is not None else ""

        # Skip directories
        if not content_type or content_type == "httpd/unix-directory":
            continue

        name_el = prop.find(f"{{{_DAV_NS}}}displayname")
        name = (name_el.text or href.split("/")[-1]) if name_el is not None else href.split("/")[-1]

        last_modified: Optional[datetime] = None
        lm_el = prop.find(f"{{{_DAV_NS}}}getlastmodified")
        if lm_el is not None and lm_el.text:
            try:
                last_modified = datetime.strptime(lm_el.text, "%a, %d %b %Y %H:%M:%S %Z")
            except ValueError:
                logger.debug(f"Could not parse last_modified date: {lm_el.text!r}")

        size_el = prop.find(f"{{{_DAV_NS}}}getcontentlength")
        try:
            size = int(size_el.text) if size_el is not None and size_el.text else 0
        except ValueError:
            size = 0

        files.append(NextcloudFile(
            name=name,
            href=href,
            content_type=content_type,
            last_modified=last_modified,
            size=size,
        ))

    files.sort(key=lambda f: f.last_modified or datetime.min, reverse=True)
    return files[:10]


class NextcloudService:
    async def _list_at_path(self, dav_path: str) -> List[NextcloudFile]:
        """PROPFIND a given DAV path (depth 1). Returns empty list on error."""
        settings = get_settings()
        url = (
            f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/"
            f"{settings.NEXTCLOUD_ADMIN_USER}/{dav_path.strip('/')}/"
        )
        auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.request(
                    "PROPFIND", url, auth=auth,
                    headers={"Depth": "1", "Content-Type": "application/xml"},
                    content=_PROPFIND_BODY,
                )
                resp.raise_for_status()
                # Use last path segment as slug for directory-skip logic
                slug = dav_path.strip("/").split("/")[-1]
                return _parse_webdav_response(resp.text, slug)
        except Exception as e:
            logger.warning(f"Nextcloud WebDAV failed for path '{dav_path}': {e}")
            return []

    async def list_files(self, org_slug: str) -> NextcloudFileList:
        """
        PROPFIND /remote.php/dav/files/admin/Organizations/{org_slug}/
        Returns up to 10 most recent files. Returns empty list on any error.
        """
        files = await self._list_at_path(f"Organizations/{org_slug}")
        return NextcloudFileList(files=files, nextcloud_url=get_settings().NEXTCLOUD_URL)

    async def list_personal_files(self, user_email: str) -> NextcloudFileList:
        """List files from Users/{user_email}/ personal folder."""
        files = await self._list_at_path(f"Users/{user_email}")
        return NextcloudFileList(files=files, nextcloud_url=get_settings().NEXTCLOUD_URL)

    async def upload_story_pdf(self, org_slug: str, story_id: str, pdf_bytes: bytes) -> str:
        """Upload a PDF to Organizations/{org_slug}/Docs/{story_id}.pdf via WebDAV."""
        settings = get_settings()
        dav_base = (
            f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/"
            f"{settings.NEXTCLOUD_ADMIN_USER}"
        )
        auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
        dest_path = f"Organizations/{org_slug}/Docs/{story_id}.pdf"
        url = f"{dav_base}/{dest_path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Ensure Docs sub-folder exists (405 = already exists, that's fine)
            docs_folder_url = f"{dav_base}/Organizations/{org_slug}/Docs/"
            r = await client.request("MKCOL", docs_folder_url, auth=auth)
            if r.status_code not in (201, 405):
                pass  # folder may already exist

            resp = await client.put(url, content=pdf_bytes, auth=auth)
            resp.raise_for_status()

        return dest_path

    async def upload_story_docs(self, org_slug: str, story_id: str, content: bytes, ext: str = "json") -> str:
        """Upload story documentation to Organizations/{org_slug}/Docs/{story_id}.{ext}"""
        settings = get_settings()
        dav_base = f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/{settings.NEXTCLOUD_ADMIN_USER}"
        auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
        dest_path = f"Organizations/{org_slug}/Docs/{story_id}.{ext}"
        url = f"{dav_base}/{dest_path}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.request("MKCOL", f"{dav_base}/Organizations/{org_slug}/Docs/", auth=auth)
            if r.status_code not in (201, 405):
                pass
            resp = await client.put(url, content=content, auth=auth)
            resp.raise_for_status()
        return dest_path


nextcloud_service = NextcloudService()
