# app/services/crawl/chunking_service.py
"""Structure-aware chunking for extracted documentation pages."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Optional

APPROX_CHARS_PER_TOKEN = 4


@dataclass
class Chunk:
    chunk_uid: str
    chunk_index: int
    total_chunks: int
    text: str
    section_path: list[str]
    metadata: dict


class ChunkingService:
    def __init__(
        self,
        target_tokens: int = 800,
        overlap_tokens: int = 120,
        max_tokens: int = 1200,
    ) -> None:
        self.target_chars = target_tokens * APPROX_CHARS_PER_TOKEN
        self.overlap_chars = overlap_tokens * APPROX_CHARS_PER_TOKEN
        self.max_chars = max_tokens * APPROX_CHARS_PER_TOKEN

    def chunk_page(
        self,
        canonical_url: str,
        page_title: str,
        sections: list[dict],
        plain_text: str,
        source_metadata: dict,
    ) -> list[Chunk]:
        """Split page content into structured chunks with metadata."""
        raw_chunks = self._split_sections(sections, plain_text)
        chunks: list[Chunk] = []
        for i, (section_path, text) in enumerate(raw_chunks):
            uid = self._chunk_uid(canonical_url, i, text)
            meta = {
                **source_metadata,
                "canonical_url": canonical_url,
                "page_title": page_title,
                "section_path": " > ".join(section_path) if section_path else page_title,
                "chunk_index": i,
                "content_hash": hashlib.sha256(text.encode()).hexdigest(),
            }
            chunks.append(Chunk(
                chunk_uid=uid,
                chunk_index=i,
                total_chunks=0,
                text=text,
                section_path=section_path,
                metadata=meta,
            ))

        total = len(chunks)
        for c in chunks:
            c.total_chunks = total
            c.metadata["total_chunks_for_page"] = total

        return chunks

    def _split_sections(
        self, sections: list[dict], plain_text: str
    ) -> list[tuple[list[str], str]]:
        if not sections:
            return list(self._split_text([], plain_text))

        result: list[tuple[list[str], str]] = []
        heading_stack: list[str] = []

        for section in sections:
            heading = section.get("heading", "")
            level = section.get("level", 0)
            body = section.get("body_text", "")

            heading_stack = heading_stack[: max(0, level - 1)]
            if heading:
                heading_stack = heading_stack + [heading]

            section_text = f"{heading}\n\n{body}".strip() if heading else body
            if not section_text:
                continue

            result.extend(self._split_text(list(heading_stack), section_text))

        return result if result else list(self._split_text([], plain_text))

    def _split_text(
        self, section_path: list[str], text: str
    ):
        if len(text) <= self.max_chars:
            yield section_path, text
            return

        paragraphs = re.split(r"\n\n+", text)
        buffer = ""
        for para in paragraphs:
            if len(buffer) + len(para) + 2 > self.target_chars and buffer:
                yield section_path, buffer.strip()
                buffer = buffer[-self.overlap_chars:] + "\n\n" + para
            else:
                buffer = (buffer + "\n\n" + para).lstrip()

        if buffer.strip():
            yield section_path, buffer.strip()

    def _chunk_uid(self, canonical_url: str, index: int, text: str) -> str:
        raw = f"{canonical_url}|{index}|{hashlib.md5(text[:200].encode()).hexdigest()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
