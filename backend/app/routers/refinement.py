"""Story Refinement Panel — REST + SSE endpoints.

Routes (all prefixed /api/v1):
  GET    /stories/{story_id}/refinement          → load or 404
  POST   /stories/{story_id}/refinement          → create / reset session
  POST   /stories/{story_id}/refinement/chat     → SSE stream
  POST   /stories/{story_id}/refinement/apply    → apply proposal field to story
  DELETE /stories/{story_id}/refinement          → delete session
"""
from __future__ import annotations

import asyncio
import logging
import uuid as _uuid_module
from datetime import datetime, timezone
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_story import UserStory
from app.models.epic import Epic
from app.models.project import Project
from app.models.story_refinement import StoryRefinementSession
from app.services.story_refinement_service import (
    build_system_prompt,
    extract_proposal,
    extract_score,
)
from app.services.rag_service import retrieve as rag_retrieve

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_story_or_404(
    story_id: _uuid_module.UUID,
    org_id: _uuid_module.UUID,
    db: AsyncSession,
) -> UserStory:
    result = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.organization_id == org_id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story nicht gefunden")
    return story


async def _get_session_or_404(
    story_id: _uuid_module.UUID,
    db: AsyncSession,
) -> StoryRefinementSession:
    result = await db.execute(
        select(StoryRefinementSession).where(
            StoryRefinementSession.story_id == story_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Keine aktive Refinement-Session")
    return session


async def _resolve_epic_title(epic_id, db: AsyncSession) -> str | None:
    if not epic_id:
        return None
    res = await db.execute(select(Epic.title).where(Epic.id == epic_id))
    return res.scalar_one_or_none()


async def _resolve_project_name(project_id, db: AsyncSession) -> str | None:
    if not project_id:
        return None
    res = await db.execute(select(Project.name).where(Project.id == project_id))
    return res.scalar_one_or_none()


def _session_to_dict(s: StoryRefinementSession) -> dict:
    return {
        "id": str(s.id),
        "story_id": str(s.story_id),
        "organization_id": str(s.organization_id),
        "stage": s.stage,
        "messages": s.messages,
        "last_proposal": s.last_proposal,
        "quality_score": s.quality_score,
        "readiness_state": s.readiness_state,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    org_id: str


class ChatRequest(BaseModel):
    message: str
    org_id: str


class ApplyRequest(BaseModel):
    field: str   # "title" | "description" | "acceptance_criteria"
    value: str
    org_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stories/{story_id}/refinement")
async def get_session(
    story_id: _uuid_module.UUID,
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_story_or_404(story_id, _uuid_module.UUID(org_id), db)
    result = await db.execute(
        select(StoryRefinementSession).where(
            StoryRefinementSession.story_id == story_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Keine aktive Refinement-Session")
    return _session_to_dict(session)


@router.post("/stories/{story_id}/refinement")
async def create_session(
    story_id: _uuid_module.UUID,
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    org_uuid = _uuid_module.UUID(body.org_id)
    await _get_story_or_404(story_id, org_uuid, db)

    # Upsert: if session exists, reset it; otherwise create new
    result = await db.execute(
        select(StoryRefinementSession).where(
            StoryRefinementSession.story_id == story_id
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.messages = []
        session.last_proposal = None
        session.quality_score = None
        session.readiness_state = None
        session.updated_at = datetime.now(timezone.utc)
    else:
        session = StoryRefinementSession(
            story_id=story_id,
            organization_id=org_uuid,
            created_by_id=current_user.id,
        )
        db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


@router.post("/stories/{story_id}/refinement/chat")
async def chat_stream(
    story_id: _uuid_module.UUID,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    org_uuid = _uuid_module.UUID(body.org_id)
    story = await _get_story_or_404(story_id, org_uuid, db)
    session = await _get_session_or_404(story_id, db)

    settings = get_settings()

    # Resolve Epic/Project names for context
    epic_title = await _resolve_epic_title(story.epic_id, db)
    project_name = await _resolve_project_name(story.project_id, db)

    system_prompt = build_system_prompt(
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        priority=story.priority.value if story.priority else "medium",
        status=story.status.value if story.status else "draft",
        epic_title=epic_title,
        project_name=project_name,
    )

    # RAG retrieval (800 ms timeout, non-blocking)
    rag_context = ""
    try:
        rag_result = await asyncio.wait_for(
            rag_retrieve(body.message, org_uuid, db),
            timeout=0.8,
        )
        if rag_result.mode in ("direct", "context") and rag_result.chunks:
            _label = {
                "confluence": "[Confluence]",
                "jira": "[Jira]",
                "karl_story": "[Karl Story]",
                "user_action": "[Team-Wissen]",
                "nextcloud": "[Dokument]",
            }
            rag_context = "\n\n".join(
                f"{_label.get(c.source_type, '[Kontext]')} {c.source_title or ''}\n{c.text}"
                for c in rag_result.chunks
            )
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("RAG error in refinement (suppressed): %s", exc)

    if rag_context:
        full_system = (
            system_prompt
            + f"\n\n---\nRelevanter Kontext aus dem Workspace:\n\n{rag_context}\n\n---\n"
        )
    else:
        full_system = system_prompt

    # Build message list for LLM
    history = session.messages or []
    llm_messages = [{"role": "system", "content": full_system}]
    llm_messages += [{"role": m["role"], "content": m["content"]} for m in history]
    llm_messages.append({"role": "user", "content": body.message})

    # Persist user message before streaming starts
    new_messages = history + [
        {"role": "user", "content": body.message, "ts": datetime.now(timezone.utc).isoformat()}
    ]
    session.messages = new_messages
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    async def event_stream() -> AsyncIterator[str]:
        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        full_response = ""
        for model in ("ionos-reasoning", "ionos-quality", "ionos-fast"):
            try:
                stream = await oai.chat.completions.create(
                    model=model,
                    max_tokens=2048,
                    messages=llm_messages,
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if not delta:
                        continue
                    full_response += delta
                    sse_payload = delta.replace("\n", "\ndata: ")
                    yield f"data: {sse_payload}\n\n"

                # After stream completes: persist assistant message + extract metadata
                proposal = extract_proposal(full_response)
                score = extract_score(full_response)

                result = await db.execute(
                    select(StoryRefinementSession).where(
                        StoryRefinementSession.story_id == story_id
                    )
                )
                s = result.scalar_one_or_none()
                if s:
                    s.messages = (s.messages or []) + [
                        {
                            "role": "assistant",
                            "content": full_response,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }
                    ]
                    if proposal is not None:
                        s.last_proposal = proposal
                    if score is not None:
                        s.quality_score = score
                    s.updated_at = datetime.now(timezone.utc)
                    await db.commit()

                yield "data: [DONE]\n\n"
                return

            except Exception as exc:
                logger.warning("Refinement stream error (model=%s): %s", model, exc)
                continue

        yield "data: [ERROR]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/stories/{story_id}/refinement/apply")
async def apply_proposal(
    story_id: _uuid_module.UUID,
    body: ApplyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    allowed_fields = {"title", "description", "acceptance_criteria"}
    if body.field not in allowed_fields:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Feld: {body.field}")

    org_uuid = _uuid_module.UUID(body.org_id)
    story = await _get_story_or_404(story_id, org_uuid, db)
    session = await _get_session_or_404(story_id, db)

    setattr(story, body.field, body.value)

    # Clear proposal after applying
    session.last_proposal = None
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True, "field": body.field}


@router.delete("/stories/{story_id}/refinement")
async def reset_session(
    story_id: _uuid_module.UUID,
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _get_story_or_404(story_id, _uuid_module.UUID(org_id), db)
    result = await db.execute(
        select(StoryRefinementSession).where(
            StoryRefinementSession.story_id == story_id
        )
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
    return {"ok": True}
