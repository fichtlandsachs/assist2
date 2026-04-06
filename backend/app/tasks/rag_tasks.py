"""Celery task: index Nextcloud org documents into pgvector."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid
import xml.etree.ElementTree as ET

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.celery_app import celery

logger = logging.getLogger(__name__)

# Chunk size in approximate characters (512 tokens ≈ 2000 chars), overlap ≈ 200 chars
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

SUPPORTED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "txt",
    "text/x-markdown": "txt",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _extract_text(content: bytes, file_type: str) -> str:
    """Extract plain text from PDF, DOCX, or TXT bytes."""
    if file_type == "pdf":
        import pdfplumber
        import io
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)

    if file_type == "docx":
        from docx import Document
        import io
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # txt / md
    return content.decode("utf-8", errors="replace")


def _chunk_text(text: str) -> list[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return [c for c in chunks if c]


async def _list_org_files(org_slug: str) -> list[dict]:
    """PROPFIND Nextcloud for org files. Returns list of {href, content_type}."""
    from app.config import get_settings
    settings = get_settings()

    expected_prefix = (
        f"/remote.php/dav/files/{settings.NEXTCLOUD_ADMIN_USER}/Organizations/{org_slug}/"
    )

    propfind_body = b"""<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:">
  <d:prop><d:getcontenttype/></d:prop>
</d:propfind>"""

    url = (
        f"{settings.NEXTCLOUD_INTERNAL_URL}/remote.php/dav/files/"
        f"{settings.NEXTCLOUD_ADMIN_USER}/Organizations/{org_slug}/"
    )
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            "PROPFIND", url, auth=auth,
            headers={"Depth": "1", "Content-Type": "application/xml"},
            content=propfind_body,
        )
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    DAV = "DAV:"
    files = []
    for response in root.findall(f"{{{DAV}}}response"):
        href_el = response.find(f"{{{DAV}}}href")
        if href_el is None:
            continue
        href = href_el.text or ""
        # Skip root folder itself
        if href.rstrip("/").endswith(f"Organizations/{org_slug}"):
            continue
        # Validate href prefix to prevent path traversal
        if not href.startswith(expected_prefix):
            logger.warning("Skipping href with unexpected prefix (possible path traversal): %s", href)
            continue
        if "/../" in href or href.endswith("/.."):
            logger.warning("Skipping href with traversal segments: %s", href)
            continue
        propstat = response.find(f"{{{DAV}}}propstat")
        if propstat is None:
            continue
        prop = propstat.find(f"{{{DAV}}}prop")
        if prop is None:
            continue
        ct_el = prop.find(f"{{{DAV}}}getcontenttype")
        ct = (ct_el.text or "") if ct_el is not None else ""
        if ct and ct != "httpd/unix-directory":
            files.append({"href": href, "content_type": ct})
    return files


async def _download_file(href: str) -> bytes:
    """Download a file from Nextcloud WebDAV by full href path."""
    from app.config import get_settings
    settings = get_settings()
    url = f"{settings.NEXTCLOUD_INTERNAL_URL}{href}"
    auth = (settings.NEXTCLOUD_ADMIN_USER, settings.NEXTCLOUD_ADMIN_APP_PASSWORD)
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
    return resp.content


async def _embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Embed a list of text chunks via LiteLLM in a single batch call."""
    if not chunks:
        return []
    from app.config import get_settings
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/embeddings",
            headers=headers,
            json={"model": "text-embedding-3-small", "input": chunks},
        )
        resp.raise_for_status()
    data = resp.json()["data"]
    # API returns items sorted by index — sort defensively
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]


async def _index_org_documents_async(org_id: str, org_slug: str, db: AsyncSession) -> None:
    """Core indexing logic — separated for testability."""
    from app.models.document_chunk import DocumentChunk

    org_uuid = uuid.UUID(org_id)
    files = await _list_org_files(org_slug)

    for file_info in files:
        href = file_info["href"]
        content_type = file_info["content_type"]
        file_type = SUPPORTED_TYPES.get(content_type)

        if file_type is None:
            logger.warning("Skipping unsupported file type '%s': %s", content_type, href)
            continue

        try:
            content = await _download_file(href)
        except Exception as e:
            logger.warning("Failed to download %s: %s", href, e)
            continue

        file_hash = _sha256(content)

        # Check if file changed since last index
        existing_hash_result = await db.execute(
            select(DocumentChunk.file_hash)
            .where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.source_ref == href,
            )
            .limit(1)
        )
        existing_hash = existing_hash_result.scalar_one_or_none()
        if existing_hash == file_hash:
            logger.debug("Skipping unchanged file: %s", href)
            continue

        try:
            extracted = _extract_text(content, file_type)
        except Exception as e:
            logger.warning("Text extraction failed for %s: %s", href, e)
            continue

        chunks = _chunk_text(extracted)
        if not chunks:
            continue

        try:
            embeddings = await _embed_chunks(chunks)
        except Exception as e:
            logger.warning("Embedding failed for %s: %s", href, e)
            continue

        # Delete old chunks for this file
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.org_id == org_uuid,
                DocumentChunk.source_ref == href,
            )
        )

        # Insert new chunks with embeddings
        for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            chunk = DocumentChunk(
                org_id=org_uuid,
                source_ref=href,
                source_type="nextcloud",
                source_url=None,
                source_title=href.rsplit("/", 1)[-1],
                file_hash=file_hash,
                chunk_index=i,
                chunk_text=chunk_text,
                embedding=embedding_str,
            )
            db.add(chunk)

        try:
            await db.commit()
            logger.info("Indexed %d chunks for %s", len(chunks), href)
        except Exception as e:
            await db.rollback()
            logger.error("Failed to commit chunks for %s: %s", href, e)
            raise


@celery.task(name="rag_tasks.index_org_documents", bind=True, max_retries=3)
def index_org_documents(self, org_id: str, org_slug: str) -> dict:
    """Celery task: index all Nextcloud org files into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_org_documents_async(org_id, org_slug, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "org_id": org_id}
    except Exception as exc:
        logger.error("index_org_documents failed for org %s: %s", org_id, exc)
        raise self.retry(exc=exc, countdown=60)
