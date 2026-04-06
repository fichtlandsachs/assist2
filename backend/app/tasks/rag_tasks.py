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
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": "ionos-embed", "input": chunks},
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


async def _index_story_knowledge_async(story_id: str, org_id: str, org_slug: str, db: AsyncSession) -> None:
    """Index story + its ready/done DoD items, done features, passed test cases."""
    from app.models.document_chunk import DocumentChunk
    from app.models.user_story import UserStory
    from app.models.test_case import TestCase
    from app.models.feature import Feature, FeatureStatus
    from app.models.test_case import TestResult

    org_uuid = uuid.UUID(org_id)
    story_uuid = uuid.UUID(story_id)
    source_ref = f"story:{story_id}"
    source_url = f"/{org_slug}/stories/{story_id}"

    # Load story
    result = await db.execute(select(UserStory).where(UserStory.id == story_uuid))
    story = result.scalar_one_or_none()
    if story is None:
        logger.warning("index_story_knowledge: story %s not found", story_id)
        return

    source_title = f"Story: {story.title}"

    # Build raw chunks
    raw_chunks: list[str] = []

    # Story chunk
    parts = [story.title or ""]
    if story.description:
        parts.append(story.description)
    if story.acceptance_criteria:
        parts.append(story.acceptance_criteria)
    raw_chunks.append("\n".join(parts))

    # DoD items (stored as JSON in definition_of_done field)
    if story.definition_of_done:
        import json as _json
        try:
            dod_items = _json.loads(story.definition_of_done)
            for item in dod_items:
                text = item.get("text", "") if isinstance(item, dict) else str(item)
                if text.strip():
                    raw_chunks.append(text.strip())
        except Exception:
            pass

    # Done features
    feat_result = await db.execute(
        select(Feature).where(
            Feature.story_id == story_uuid,
            Feature.status == FeatureStatus.done,
        )
    )
    for feat in feat_result.scalars().all():
        parts = [feat.title or ""]
        if feat.description:
            parts.append(feat.description)
        raw_chunks.append("\n".join(parts))

    # Passed test cases
    tc_result = await db.execute(
        select(TestCase).where(
            TestCase.story_id == story_uuid,
            TestCase.result == TestResult.passed,
        )
    )
    for tc in tc_result.scalars().all():
        parts = [tc.title or ""]
        if tc.steps:
            parts.append(tc.steps)
        if tc.expected_result:
            parts.append(tc.expected_result)
        raw_chunks.append("\n".join(parts))

    if not raw_chunks:
        return

    # Embed all chunks
    try:
        embeddings = await _embed_chunks(raw_chunks)
    except Exception as e:
        logger.warning("index_story_knowledge: embedding failed for story %s: %s", story_id, e)
        return

    # Delete existing chunks for this story
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.org_id == org_uuid,
            DocumentChunk.source_ref == source_ref,
        )
    )

    # Insert new chunks
    for i, (chunk_text, embedding) in enumerate(zip(raw_chunks, embeddings)):
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        chunk = DocumentChunk(
            org_id=org_uuid,
            source_ref=source_ref,
            source_type="karl_story",
            source_url=source_url,
            source_title=source_title,
            file_hash=_sha256(chunk_text.encode()),
            chunk_index=i,
            chunk_text=chunk_text,
            embedding=embedding_str,
        )
        db.add(chunk)

    try:
        await db.commit()
        logger.info("index_story_knowledge: indexed %d chunks for story %s", len(raw_chunks), story_id)
    except Exception as e:
        await db.rollback()
        logger.error("index_story_knowledge: commit failed for story %s: %s", story_id, e)
        raise


@celery.task(name="rag_tasks.index_story_knowledge", bind=True, max_retries=3)
def index_story_knowledge(self, story_id: str, org_id: str, org_slug: str) -> dict:
    """Celery task: index story knowledge (story + DoD + features + test cases) into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_story_knowledge_async(story_id, org_id, org_slug, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "story_id": story_id}
    except Exception as exc:
        logger.error("index_story_knowledge failed for story %s: %s", story_id, exc)
        raise self.retry(exc=exc, countdown=60)


async def _index_jira_ticket_async(ticket_key: str, org_id: str, db: AsyncSession) -> None:
    """Index a single Jira ticket into pgvector. Silent no-op if Jira not configured."""
    from app.models.document_chunk import DocumentChunk
    from app.models.organization import Organization
    from app.models.jira_story import JiraStory

    org_uuid = uuid.UUID(org_id)

    # Load org to check Jira config
    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if org is None:
        return

    metadata = getattr(org, "metadata_", None) or {}
    jira_cfg = metadata.get("integrations", {}).get("jira", {})
    if not jira_cfg.get("base_url") or not jira_cfg.get("api_token_enc"):
        logger.debug("index_jira_ticket: Jira not configured for org %s — skipping", org_id)
        return

    jira_base_url = jira_cfg["base_url"].rstrip("/")

    # Load JiraStory record
    story_result = await db.execute(
        select(JiraStory).where(
            JiraStory.ticket_key == ticket_key.upper(),
            JiraStory.organization_id == org_uuid,
        )
    )
    jira_story = story_result.scalar_one_or_none()
    if jira_story is None:
        logger.warning("index_jira_ticket: ticket %s not found in DB", ticket_key)
        return

    summary = jira_story.source_summary or ticket_key
    content = jira_story.content or ""
    chunk_text = f"{ticket_key}: {summary}\n{content}"[:4000]
    source_ref = f"jira:{ticket_key}"
    source_url = f"{jira_base_url}/browse/{ticket_key}"
    source_title = f"Jira: {ticket_key} — {summary[:60]}"

    try:
        embeddings = await _embed_chunks([chunk_text])
    except Exception as e:
        logger.warning("index_jira_ticket: embedding failed for %s: %s", ticket_key, e)
        return

    # Delete existing chunk for this ticket
    await db.execute(
        delete(DocumentChunk).where(
            DocumentChunk.org_id == org_uuid,
            DocumentChunk.source_ref == source_ref,
        )
    )

    embedding_str = "[" + ",".join(str(x) for x in embeddings[0]) + "]"
    chunk = DocumentChunk(
        org_id=org_uuid,
        source_ref=source_ref,
        source_type="jira",
        source_url=source_url,
        source_title=source_title,
        file_hash=_sha256(chunk_text.encode()),
        chunk_index=0,
        chunk_text=chunk_text,
        embedding=embedding_str,
    )
    db.add(chunk)
    try:
        await db.commit()
        logger.info("index_jira_ticket: indexed ticket %s for org %s", ticket_key, org_id)
    except Exception as e:
        await db.rollback()
        logger.error("index_jira_ticket: commit failed for ticket %s: %s", ticket_key, e)
        raise


@celery.task(name="rag_tasks.index_jira_ticket", bind=True, max_retries=3)
def index_jira_ticket(self, ticket_key: str, org_id: str) -> dict:
    """Celery task: index a Jira ticket into pgvector."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_jira_ticket_async(ticket_key, org_id, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "ticket_key": ticket_key}
    except Exception as exc:
        logger.error("index_jira_ticket failed for %s: %s", ticket_key, exc)
        raise self.retry(exc=exc, countdown=60)


async def _index_confluence_space_async(org_id: str, db: AsyncSession) -> None:
    """Index all Confluence pages for the org. Silent no-op if Confluence not configured."""
    from app.models.document_chunk import DocumentChunk
    from app.models.organization import Organization

    org_uuid = uuid.UUID(org_id)

    org_result = await db.execute(select(Organization).where(Organization.id == org_uuid))
    org = org_result.scalar_one_or_none()
    if org is None:
        return

    metadata = getattr(org, "metadata_", None) or {}
    conf_cfg = metadata.get("integrations", {}).get("confluence", {})
    if not conf_cfg.get("base_url") or not conf_cfg.get("api_token_enc"):
        logger.debug("index_confluence_space: Confluence not configured for org %s — skipping", org_id)
        return

    conf_base_url = conf_cfg["base_url"].rstrip("/")
    space_keys: list[str] = conf_cfg.get("space_keys", [])
    api_token_enc: str = conf_cfg["api_token_enc"]
    conf_user: str = conf_cfg.get("user_email", "")

    if not space_keys:
        logger.debug("index_confluence_space: no space_keys configured for org %s", org_id)
        return

    # Decrypt token
    try:
        from app.core.security import decrypt_value
        api_token = decrypt_value(api_token_enc)
    except ImportError:
        api_token = api_token_enc  # fallback: treat as plaintext
    except Exception as e:
        logger.error("index_confluence_space: failed to decrypt Confluence token: %s", e)
        return

    import base64 as _base64
    auth_header = "Basic " + _base64.b64encode(f"{conf_user}:{api_token}".encode()).decode()
    headers = {"Authorization": auth_header, "Accept": "application/json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for space_key in space_keys:
            try:
                resp = await client.get(
                    f"{conf_base_url}/rest/api/content",
                    headers=headers,
                    params={"spaceKey": space_key, "type": "page", "limit": 50, "expand": "body.storage"},
                )
                resp.raise_for_status()
            except Exception as e:
                logger.warning("index_confluence_space: failed to list pages for space %s: %s", space_key, e)
                continue

            pages = resp.json().get("results", [])
            for page in pages:
                page_id = str(page.get("id", ""))
                page_title = page.get("title", "")
                body_html = page.get("body", {}).get("storage", {}).get("value", "")

                # Strip HTML tags for plaintext
                import re as _re
                body_text = _re.sub(r"<[^>]+>", " ", body_html).strip()
                body_text = _re.sub(r"\s+", " ", body_text)

                if not body_text:
                    continue

                full_text = f"{page_title}\n{body_text}"
                source_ref = f"confluence:{page_id}"
                source_url = f"{conf_base_url}/wiki/spaces/{space_key}/pages/{page_id}"
                source_title = f"Confluence: {page_title}"

                raw_chunks = _chunk_text(full_text)
                if not raw_chunks:
                    continue

                try:
                    embeddings = await _embed_chunks(raw_chunks)
                except Exception as e:
                    logger.warning("index_confluence_space: embedding failed for page %s: %s", page_id, e)
                    continue

                # Delete existing chunks for this page
                await db.execute(
                    delete(DocumentChunk).where(
                        DocumentChunk.org_id == org_uuid,
                        DocumentChunk.source_ref == source_ref,
                    )
                )

                for i, (chunk_text_item, embedding) in enumerate(zip(raw_chunks, embeddings)):
                    embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
                    chunk = DocumentChunk(
                        org_id=org_uuid,
                        source_ref=source_ref,
                        source_type="confluence",
                        source_url=source_url,
                        source_title=source_title,
                        file_hash=_sha256(chunk_text_item.encode()),
                        chunk_index=i,
                        chunk_text=chunk_text_item,
                        embedding=embedding_str,
                    )
                    db.add(chunk)

                try:
                    await db.commit()
                    logger.info("index_confluence_space: indexed page %s (%s)", page_id, page_title)
                except Exception as e:
                    await db.rollback()
                    logger.error("index_confluence_space: commit failed for page %s: %s", page_id, e)
                    continue  # skip this page, continue with others


@celery.task(name="rag_tasks.index_confluence_space", bind=True, max_retries=3)
def index_confluence_space(self, org_id: str) -> dict:
    """Celery task: index all Confluence pages for the org."""
    from app.config import get_settings

    async def run():
        engine = create_async_engine(
            get_settings().DATABASE_URL, echo=False, pool_pre_ping=True
        )
        SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        try:
            async with SessionLocal() as db:
                await _index_confluence_space_async(org_id, db)
        finally:
            await engine.dispose()

    try:
        asyncio.run(run())
        return {"status": "ok", "org_id": org_id}
    except Exception as exc:
        logger.error("index_confluence_space failed for org %s: %s", org_id, exc)
        raise self.retry(exc=exc, countdown=60)
