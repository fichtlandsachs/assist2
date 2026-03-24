"""Pydantic schemas for Nextcloud plugin responses."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class NextcloudFile(BaseModel):
    name: str
    href: str
    content_type: str
    last_modified: Optional[datetime] = None
    size: int = 0


class NextcloudFileList(BaseModel):
    files: List[NextcloudFile]
    nextcloud_url: str


class NextcloudUploadResult(BaseModel):
    ok: bool
    path: str
