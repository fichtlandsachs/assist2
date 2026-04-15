"""Service: generate story embeddings and run pgvector similarity search."""
from __future__ import annotations

import hashlib
import logging
import uuid

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.story_embedding import StoryEmbedding
from app.models.user_story import UserStory

logger = logging.getLogger(__name__)

EMBED_MODEL = "ionos-embed"
SIMILAR_THRESHOLD = 0.70
TOP_K = 10


def _content_for_story(story: UserStory) -> str:
    """Build the text that gets embedded for a story."""
    return f"{story.title}\n{story.description or ''}\n{story.acceptance_criteria or ''}"


def _sha256(text_: str) -> str:
    return hashlib.sha256(text_.encode()).hexdigest()


async def _call_litellm_embed(text_: str) -> list[float]:
    """Call LiteLLM /v1/embeddings. Returns 1024-dim vector."""
    settings = get_settings()
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.LITELLM_API_KEY:
        headers["Authorization"] = f"Bearer {settings.LITELLM_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.LITELLM_URL}/v1/embeddings",
            headers=headers,
            json={"model": EMBED_MODEL, "input": [text_]},
        )
        resp.raise_for_status()

    data = resp.json()["data"]
    embedding: list[float] = data[0]["embedding"]
    return embedding


async def embed_story(story_id: str, org_id: str, db: AsyncSession) -> None:
    """
    Generate and upsert the embedding for a story.
    Skips silently if the content has not changed since the last embedding.
    """
    story_uuid = uuid.UUID(story_id)
    org_uuid = uuid.UUID(org_id)

    result = await db.execute(select(UserStory).where(UserStory.id == story_uuid))
    story = result.scalar_one_or_none()
    if story is None:
        logger.warning("embed_story: story %s not found, skipping", story_id)
        return

    content = _content_for_story(story)
    content_hash = _sha256(content)

    # Check existing embedding — skip if content unchanged
    existing_result = await db.execute(
        select(StoryEmbedding).where(StoryEmbedding.story_id == story_uuid)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None and existing.content_hash == content_hash:
        logger.debug("embed_story: content unchanged for story %s, skipping", story_id)
        return

    try:
        embedding_floats = await _call_litellm_embed(content)
    except Exception as e:
        logger.error("embed_story: LiteLLM call failed for story %s: %s", story_id, e)
        raise

    if existing is None:
        row = StoryEmbedding(
            organization_id=org_uuid,
            story_id=story_uuid,
            embedding=embedding_floats,
            content_hash=content_hash,
            model_used=EMBED_MODEL,
        )
        db.add(row)
    else:
        existing.embedding = embedding_floats
        existing.content_hash = content_hash
        existing.model_used = EMBED_MODEL

    await db.commit()
    logger.info("embed_story: upserted embedding for story %s", story_id)


async def find_similar_stories(
    story_id: str, org_id: str, db: AsyncSession
) -> list[tuple[uuid.UUID, float]]:
    """
    Run pgvector cosine similarity search against story_embeddings.
    Returns up to TOP_K results as (story_id_uuid, similarity_float) tuples,
    ordered by descending similarity, excluding the query story itself.
    Only returns rows with similarity >= SIMILAR_THRESHOLD.
    """
    story_uuid = uuid.UUID(story_id)
    org_uuid = uuid.UUID(org_id)

    # Load the query embedding
    emb_result = await db.execute(
        select(StoryEmbedding.embedding).where(StoryEmbedding.story_id == story_uuid)
    )
    embedding_str = emb_result.scalar_one_or_none()
    if embedding_str is None:
        logger.warning("find_similar_stories: no embedding for story %s", story_id)
        return []

    result = await db.execute(
        text("""
            SELECT story_id, 1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
            FROM story_embeddings
            WHERE organization_id = :org_id
              AND story_id != :exclude_id
              AND 1 - (embedding <=> CAST(:query_vec AS vector)) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
        """),
        {
            "query_vec": embedding_str,
            "org_id": str(org_uuid),
            "exclude_id": str(story_uuid),
            "threshold": SIMILAR_THRESHOLD,
            "limit": TOP_K,
        },
    )
    rows = result.fetchall()
    return [(uuid.UUID(str(row[0])), float(row[1])) for row in rows]
