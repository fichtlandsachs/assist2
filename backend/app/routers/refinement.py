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

import re as _re

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.deps import get_current_user, get_db
from app.models.user import User
from app.core.story_filter import active_stories
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
from app.services.system_settings_service import get_runtime_settings
from app.services.web_search_service import web_search as do_web_search

_MARKER_RE = _re.compile(r"<!--(?:proposal[\s\S]*?|score:-?\d+)-->", _re.DOTALL)

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

    runtime_settings = await get_runtime_settings(db)

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

    # /WEB detection — strip signal from LLM input, keep visible in chat history
    _WEB_SIGNAL = "/WEB"
    web_requested = _WEB_SIGNAL in body.message.upper()
    clean_message = body.message.replace(_WEB_SIGNAL, "").replace(_WEB_SIGNAL.lower(), "").strip()
    display_message = body.message

    base_system = system_prompt
    if rag_context:
        base_system += f"\n\n---\nRelevanter Kontext aus dem Workspace:\n\n{rag_context}\n\n---\n"

    history = session.messages or []

    # Persist user message before streaming starts
    session.messages = history + [
        {"role": "user", "content": display_message, "ts": datetime.now(timezone.utc).isoformat()}
    ]
    session.updated_at = datetime.now(timezone.utc)
    await db.commit()

    async def event_stream() -> AsyncIterator[str]:
        import json as _json
        # Real web search when /WEB requested
        web_result = None
        if web_requested:
            try:
                web_result = await asyncio.wait_for(
                    do_web_search(
                        clean_message or display_message,
                        runtime_settings,
                        org_uuid,
                        current_user.id,
                    ),
                    timeout=12.0,
                )
            except (asyncio.TimeoutError, Exception) as exc:
                logger.warning("web_search error in refinement (suppressed): %s", exc)

        full_system = base_system
        if web_result:
            full_system += f"\n\n---\nWeb-Suchergebnisse:\n\n{web_result.text}\n\n---\n"
        elif web_requested:
            full_system += "\n\n[WEB-SUCHE angefordert, aber kein Search-Provider konfiguriert. Antworte auf Basis des vorhandenen Kontexts.]"

        llm_messages = [{"role": "system", "content": full_system}]
        llm_messages += [
            {"role": m["role"], "content": _MARKER_RE.sub("", m["content"]).replace(_WEB_SIGNAL, "").strip()}
            for m in history
        ]
        llm_messages.append({"role": "user", "content": clean_message or display_message})

        oai = AsyncOpenAI(
            api_key=runtime_settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{runtime_settings.LITELLM_URL}/v1",
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

                # After stream: persist assistant message + extract metadata
                proposal = extract_proposal(full_response)
                score = extract_score(full_response)
                logger.debug("Refinement persist: proposal=%s score=%s", proposal, score)

                async with AsyncSessionLocal() as persist_db:
                    result = await persist_db.execute(
                        select(StoryRefinementSession).where(
                            StoryRefinementSession.story_id == story_id
                        )
                    )
                    s = result.scalar_one_or_none()
                    if s:
                        assistant_msg: dict = {
                            "role": "assistant",
                            "content": full_response,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        }
                        if web_result:
                            assistant_msg["web_cost_usd"] = web_result.cost_usd
                            assistant_msg["web_provider"] = web_result.provider
                        s.messages = list(s.messages or []) + [assistant_msg]
                        if proposal is not None:
                            s.last_proposal = proposal
                        if score is not None:
                            s.quality_score = score
                        s.updated_at = datetime.now(timezone.utc)
                        await persist_db.commit()

                if web_result:
                    cost_data = _json.dumps({"cost": web_result.cost_usd, "provider": web_result.provider})
                    yield f"data: [WEBRESULT:{cost_data}]\n\n"
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

    # Remove only the applied field from the proposal; clear entirely if nothing remains
    if session.last_proposal:
        remaining = {k: v for k, v in session.last_proposal.items() if k != body.field and v}
        session.last_proposal = remaining if remaining else None
    session.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return {"ok": True, "field": body.field}


class DismissRequest(BaseModel):
    org_id: str


@router.post("/stories/{story_id}/refinement/dismiss")
async def dismiss_proposal(
    story_id: _uuid_module.UUID,
    body: DismissRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear last_proposal without modifying the story — user dismissed the suggestion."""
    await _get_story_or_404(story_id, _uuid_module.UUID(body.org_id), db)
    result = await db.execute(
        select(StoryRefinementSession).where(
            StoryRefinementSession.story_id == story_id
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.last_proposal = None
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return {"ok": True}


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
