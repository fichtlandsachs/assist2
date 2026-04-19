"""Story Assistant — DoD and Features AI chat (SSE streaming).

Routes (all prefixed /api/v1):
  GET    /stories/{story_id}/assistant/{session_type}       → load or 404
  POST   /stories/{story_id}/assistant/{session_type}       → create / reset session
  POST   /stories/{story_id}/assistant/{session_type}/chat  → SSE stream
  POST   /stories/{story_id}/assistant/{session_type}/dismiss
  DELETE /stories/{story_id}/assistant/{session_type}       → delete session

session_type: "dod" | "features"
"""
from __future__ import annotations

import asyncio
import logging
import re as _re
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

from app.database import AsyncSessionLocal
from app.deps import get_current_user, get_db
from app.models.user import User
from app.models.user_story import UserStory
from app.models.epic import Epic
from app.models.project import Project
from app.models.story_assistant_session import StoryAssistantSession
from app.services.story_assistant_service import (
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

_ALLOWED_TYPES = {"dod", "features"}
_MARKER_RE = _re.compile(r"<!--(?:proposal[\s\S]*?|score:-?\d+)-->", _re.DOTALL)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_type(session_type: str) -> None:
    if session_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=422, detail=f"Ungültiger session_type: {session_type}")


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


def _session_to_dict(s: StoryAssistantSession) -> dict:
    return {
        "id": str(s.id),
        "story_id": str(s.story_id),
        "organization_id": str(s.organization_id),
        "session_type": s.session_type,
        "messages": s.messages,
        "last_proposal": s.last_proposal,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    org_id: str


class ChatRequest(BaseModel):
    message: str
    org_id: str


class DismissRequest(BaseModel):
    org_id: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stories/{story_id}/assistant/{session_type}")
async def get_session(
    story_id: _uuid_module.UUID,
    session_type: str,
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_type(session_type)
    await _get_story_or_404(story_id, _uuid_module.UUID(org_id), db)
    result = await db.execute(
        select(StoryAssistantSession).where(
            StoryAssistantSession.story_id == story_id,
            StoryAssistantSession.session_type == session_type,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Keine aktive Session")
    return _session_to_dict(session)


@router.post("/stories/{story_id}/assistant/{session_type}")
async def create_session(
    story_id: _uuid_module.UUID,
    session_type: str,
    body: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_type(session_type)
    org_uuid = _uuid_module.UUID(body.org_id)
    await _get_story_or_404(story_id, org_uuid, db)

    result = await db.execute(
        select(StoryAssistantSession).where(
            StoryAssistantSession.story_id == story_id,
            StoryAssistantSession.session_type == session_type,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.messages = []
        session.last_proposal = None
        session.updated_at = datetime.now(timezone.utc)
    else:
        session = StoryAssistantSession(
            story_id=story_id,
            organization_id=org_uuid,
            session_type=session_type,
            created_by_id=current_user.id,
        )
        db.add(session)
    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)


@router.post("/stories/{story_id}/assistant/{session_type}/chat")
async def chat_stream(
    story_id: _uuid_module.UUID,
    session_type: str,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    _validate_type(session_type)
    org_uuid = _uuid_module.UUID(body.org_id)
    story = await _get_story_or_404(story_id, org_uuid, db)

    result = await db.execute(
        select(StoryAssistantSession).where(
            StoryAssistantSession.story_id == story_id,
            StoryAssistantSession.session_type == session_type,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Keine aktive Session")

    runtime_settings = await get_runtime_settings(db)
    epic_title = await _resolve_epic_title(story.epic_id, db)
    project_name = await _resolve_project_name(story.project_id, db)

    system_prompt = build_system_prompt(
        session_type=session_type,
        title=story.title,
        description=story.description,
        acceptance_criteria=story.acceptance_criteria,
        priority=story.priority.value if story.priority else "medium",
        status=story.status.value if story.status else "draft",
        epic_title=epic_title,
        project_name=project_name,
    )

    # RAG retrieval (800ms timeout, non-blocking)
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
        logger.warning("RAG error in assistant (suppressed): %s", exc)

    # /WEB detection — strip signal from LLM input, keep visible in chat history
    _WEB_SIGNAL = "/WEB"
    web_requested = _WEB_SIGNAL in body.message.upper()
    clean_message = body.message.replace(_WEB_SIGNAL, "").replace(_WEB_SIGNAL.lower(), "").strip()
    display_message = body.message

    base_system = system_prompt
    if rag_context:
        base_system += f"\n\n---\nRelevanter Kontext aus dem Workspace:\n\n{rag_context}\n\n---\n"

    history = session.messages or []

    # Persist user message before streaming (keep /WEB visible in chat history)
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
                logger.warning("web_search error in assistant (suppressed): %s", exc)

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

                proposal = extract_proposal(full_response)
                score = extract_score(full_response)
                logger.debug("Assistant persist (%s): proposal=%s score=%s", session_type, proposal, score)

                async with AsyncSessionLocal() as persist_db:
                    res = await persist_db.execute(
                        select(StoryAssistantSession).where(
                            StoryAssistantSession.story_id == story_id,
                            StoryAssistantSession.session_type == session_type,
                        )
                    )
                    s = res.scalar_one_or_none()
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
                        s.updated_at = datetime.now(timezone.utc)
                        await persist_db.commit()

                if web_result:
                    cost_data = _json.dumps({"cost": web_result.cost_usd, "provider": web_result.provider})
                    yield f"data: [WEBRESULT:{cost_data}]\n\n"
                yield "data: [DONE]\n\n"
                return

            except Exception as exc:
                logger.warning("Assistant stream error (model=%s): %s", model, exc)
                continue

        yield "data: [ERROR]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/stories/{story_id}/assistant/{session_type}/dismiss")
async def dismiss_proposal(
    story_id: _uuid_module.UUID,
    session_type: str,
    body: DismissRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_type(session_type)
    await _get_story_or_404(story_id, _uuid_module.UUID(body.org_id), db)
    result = await db.execute(
        select(StoryAssistantSession).where(
            StoryAssistantSession.story_id == story_id,
            StoryAssistantSession.session_type == session_type,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        session.last_proposal = None
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()
    return {"ok": True}


@router.delete("/stories/{story_id}/assistant/{session_type}")
async def delete_session(
    story_id: _uuid_module.UUID,
    session_type: str,
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _validate_type(session_type)
    await _get_story_or_404(story_id, _uuid_module.UUID(org_id), db)
    result = await db.execute(
        select(StoryAssistantSession).where(
            StoryAssistantSession.story_id == story_id,
            StoryAssistantSession.session_type == session_type,
        )
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()
    return {"ok": True}
