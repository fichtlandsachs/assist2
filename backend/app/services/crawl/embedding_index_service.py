# app/services/crawl/embedding_index_service.py
"""Embed chunks and upsert into document_chunks (pgvector) for global shared content."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

import httpx
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.document_chunk import DocumentChunk, SourceType
from app.services.crawl.chunking_service import Chunk

logger = logging.getLogger(__name__)


class EmbeddingIndexService:
    def __init__(self, batch_size: int = 32) -> None:
        self.batch_size = batch_size

    async def embed_and_upsert(
        self,
        db: AsyncSession,
        source_id: uuid.UUID,
        page_canonical_url: str,
        chunks: list[Chunk],
        source_key: str,
    ) -> int:
        """Embed chunks and upsert into document_chunks. Returns count upserted."""
        if not chunks:
            return 0

        settings = get_settings()
        texts = [c.text for c in chunks]
        embeddings = await self._batch_embed(texts, settings)

        if len(embeddings) != len(chunks):
            logger.error(
                "Embedding count mismatch: %d texts vs %d embeddings",
                len(texts), len(embeddings),
            )
            raise RuntimeError("Embedding batch size mismatch")

        # Delete stale chunks for this page
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.source_ref == page_canonical_url,
                DocumentChunk.source_type == SourceType.external_docs,
            )
        )

        # Insert new chunks
        for chunk, embedding in zip(chunks, embeddings):
            dc = DocumentChunk(
                id=uuid.uuid4(),
                org_id=None,
                source_ref=page_canonical_url,
                source_type=SourceType.external_docs,
                source_url=chunk.metadata.get("canonical_url"),
                source_title=chunk.metadata.get("page_title"),
                file_hash=chunk.chunk_uid,
                chunk_index=chunk.chunk_index,
                chunk_text=chunk.text,
                embedding=embedding,
                zone_id=None,
                is_global=True,
            )
            db.add(dc)

        await db.commit()
        logger.info("Upserted %d chunks for %s", len(chunks), page_canonical_url)
        return len(chunks)

    async def delete_page_chunks(self, db: AsyncSession, canonical_url: str) -> None:
        await db.execute(
            delete(DocumentChunk).where(
                DocumentChunk.source_ref == canonical_url,
                DocumentChunk.source_type == SourceType.external_docs,
            )
        )
        await db.commit()

    async def _batch_embed(self, texts: list[str], settings) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{settings.LITELLM_URL}/v1/embeddings",
                    headers={"Authorization": f"Bearer {settings.LITELLM_API_KEY}"},
                    json={"model": "ionos-embed", "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()["data"]
                data.sort(key=lambda x: x["index"])
                results.extend([item["embedding"] for item in data])
        return results
