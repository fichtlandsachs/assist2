"""AI utility routes — transcription, chat streaming, story extraction."""
import asyncio
import json
import logging
import re
import uuid as _uuid_module
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.user import User
from app.services.rag_service import retrieve as rag_retrieve

logger = logging.getLogger(__name__)
router = APIRouter()

# ── System prompts ────────────────────────────────────────────────────────────

_NO_MARKUP = (
    "FORMATIERUNGSREGEL (zwingend): Antworte ausschließlich in reinem Fließtext ohne jede Formatierung.\n"
    "Verboten sind ohne Ausnahme:\n"
    "Sternchen oder Unterstriche für Fett/Kursiv/Durchgestrichen, "
    "Rauten (#) für Überschriften jeder Ebene, "
    "Bindestriche (-), Sternchen (*) oder Nummern (1.) als Listen-Präfixe, "
    "Backticks (`) oder Dreifach-Backticks (```) für Code, "
    "Trennlinien aus --- oder ===, "
    "HTML-Tags, Tabellen mit |, "
    "ASCII-Diagramme und Rahmen (┌ ─ │ └ etc.), "
    "Emojis.\n"
    "Absätze werden durch eine Leerzeile getrennt. "
    "Aufzählungen schreibst du als Fließtext: 'Erstens ... Zweitens ... Drittens ...'. "
    "Wenn eine reine Auflistung unvermeidbar ist, trenne Einträge nur durch Zeilenumbruch ohne Präfix-Zeichen. "
    "Code und technische Konzepte beschreibst du verbal in vollständigen Sätzen, nicht als Code-Block. "
    "Tiefe und Qualität der Antwort bleiben unverändert — nur die Formatierung entfällt."
)

CHAT_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "Du bist ein hilfreicher KI-Assistent für ein agiles Entwicklungsteam. "
        "Antworte präzise, professionell und auf Deutsch, es sei denn, der Nutzer schreibt in einer anderen Sprache. "
        "Wenn der Nutzer ein Bild (Mockup, Screenshot, Wireframe) einfügt, beschreibe es detailliert als UX/UI-Mockup: "
        "Layout, Komponenten, Benutzerfluss und mögliche Anforderungen, die sich daraus ableiten lassen. "
        + _NO_MARKUP
    ),
    "docs": (
        "Du bist ein Experte für technische Dokumentation. "
        "Hilf beim Erstellen, Verbessern und Strukturieren von Dokumenten. "
        + _NO_MARKUP
    ),
    "tasks": (
        "Du bist ein agiler Coach und Projektmanager. "
        "Hilf bei der Planung, Priorisierung und Strukturierung von User Stories und Aufgaben. "
        + _NO_MARKUP
    ),
}

EXTRACT_SYSTEM_PROMPT = (
    "Du bist ein Experte für agile Anforderungsanalyse. "
    "Analysiere das folgende Transkript eines Gesprächs und extrahiere strukturierte Informationen. "
    "Antworte NUR mit einem JSON-Objekt in exakt diesem Format:\n"
    '{"title": "Kurzer prägnanter Titel der User Story", '
    '"story": ["Als ... möchte ich ... damit ..."], '
    '"accept": ["Gegeben ..., wenn ..., dann ..."], '
    '"tests": ["TC-01: ..."], '
    '"release": ["v1.0: ..."], '
    '"features": [{"title": "Feature-Titel", "description": "Kurze Beschreibung"}]}\n'
    "Wenn keine Information für eine Kategorie vorhanden ist, gib ein leeres Array zurück. "
    "Der title ist immer ein kurzer, prägnanter Satz (max. 80 Zeichen). "
    "Features sind konkrete, implementierbare Teilfunktionen der User Story."
)


# ── Request schemas ───────────────────────────────────────────────────────────

class ChatImageSource(BaseModel):
    type: str = "base64"
    media_type: str
    data: str


class ChatContentBlock(BaseModel):
    type: str  # "text" or "image"
    text: str | None = None
    source: ChatImageSource | None = None


class ChatMessage(BaseModel):
    role: str
    content: str | list[ChatContentBlock]

    def to_text(self) -> str:
        """Extract plain text for transcript/compact use."""
        if isinstance(self.content, str):
            return self.content
        return " ".join(b.text for b in self.content if b.type == "text" and b.text)


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    mode: str = "chat"
    org_id: str | None = None


class ExtractStoryRequest(BaseModel):
    transcript: str
    org_id: str | None = None


class CompactChatRequest(BaseModel):
    messages: list[ChatMessage]
    org_id: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ai/transcribe")
async def transcribe(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Proxy audio file to faster-whisper and return transcribed text."""
    settings = get_settings()
    audio = await file.read()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.WHISPER_URL}/v1/audio/transcriptions",
                files={"file": (file.filename, audio, file.content_type)},
                data={"model": "whisper-1", "language": "de"},
            )
            resp.raise_for_status()
            return {"text": resp.json().get("text", "")}
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Whisper service error: %s", e)
        raise HTTPException(status_code=503, detail="Transkriptions-Service nicht erreichbar")


@router.post("/ai/chat")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream a chat response via LiteLLM as Server-Sent Events."""
    settings = get_settings()
    system_prompt = CHAT_SYSTEM_PROMPTS.get(body.mode, CHAT_SYSTEM_PROMPTS["chat"])

    def _build_content(m: ChatMessage) -> str | list:
        if isinstance(m.content, str):
            return m.content
        blocks = []
        for b in m.content:
            if b.type == "image" and b.source:
                # Convert Anthropic image format → OpenAI image_url format
                blocks.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{b.source.media_type};base64,{b.source.data}"},
                })
            else:
                blocks.append({"type": "text", "text": b.text or ""})
        return blocks

    # RAG retrieval — 800ms timeout, never blocks response on failure
    rag_context = ""
    if body.org_id:
        try:
            last_user_text = next(
                (m.to_text() for m in reversed(body.messages) if m.role == "user"), ""
            )
            if last_user_text:
                rag_result = await asyncio.wait_for(
                    rag_retrieve(last_user_text, _uuid_module.UUID(body.org_id), db),
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
        except Exception:
            pass  # RAG failure is never fatal

    messages = [{"role": "system", "content": system_prompt}]
    if rag_context:
        messages.append({"role": "system", "content": f"Relevanter Kontext:\n\n{rag_context}"})
    messages += [{"role": m.role, "content": _build_content(m)} for m in body.messages]

    async def event_stream() -> AsyncIterator[str]:
        try:
            oai = AsyncOpenAI(
                api_key=settings.LITELLM_API_KEY or "sk-assist2",
                base_url=f"{settings.LITELLM_URL}/v1",
            )
            stream = await oai.chat.completions.create(
                model="ionos-reasoning",
                max_tokens=2048,
                messages=messages,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield f"data: {delta}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("AI chat stream error: %s", exc)
            yield "data: [ERROR]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/ai/compact-chat")
async def compact_chat(
    body: CompactChatRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Summarize a chat conversation into a compact context for AI requests."""
    if len(body.messages) < 2:
        return {"summary": ""}

    settings = get_settings()
    transcript = "\n".join(
        f"{'Nutzer' if m.role == 'user' else 'KI'}: {m.to_text()}"
        for m in body.messages
    )

    system = (
        "Du bist ein Experte für Gesprächszusammenfassungen. "
        "Fasse das folgende Gespräch in einem kompakten, strukturierten Kontext zusammen. "
        "Behalte alle wichtigen Informationen, Anforderungen und Entscheidungen. "
        "Schreibe in der dritten Person und verwende Stichpunkte wo sinnvoll. "
        "Maximale Länge: 500 Wörter."
    )
    try:
        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-assist2",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        resp = await oai.chat.completions.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": transcript},
            ],
        )
        summary = resp.choices[0].message.content or ""
        # Index chat summary as user action knowledge (fire-and-forget)
        if body.org_id and len(summary) > 100:
            caller_org_ids = {str(m.organization_id) for m in (current_user.memberships or [])}
            if body.org_id in caller_org_ids:
                try:
                    from app.tasks.rag_tasks import index_user_action
                    index_user_action.delay(
                        body.org_id,
                        "chat_summary",
                        summary,
                        str(current_user.id),
                    )
                except Exception:
                    pass  # never block response for indexing failure
        return {"summary": summary}
    except Exception as exc:
        logger.error("AI compact-chat error: %s", exc)
        raise HTTPException(status_code=503, detail="KI-Service nicht erreichbar")


@router.post("/ai/extract-story")
async def extract_story(
    body: ExtractStoryRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Extract structured story data from a conversation transcript."""
    empty = {"title": "", "story": [], "accept": [], "tests": [], "release": []}
    if len(body.transcript) < 80:
        return empty

    settings = get_settings()
    try:
        from openai import AsyncOpenAI
        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-assist2",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        resp = await oai.chat.completions.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[
                {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                {"role": "user", "content": body.transcript},
            ],
        )
        raw = (resp.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.error("AI extract-story error: %s", exc)
        return empty

    # Strip markdown code fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("AI extract-story JSON error: %s | raw: %s", e, raw[:500])
        return empty

    return {
        "title": data.get("title", ""),
        "story": data.get("story", []),
        "accept": data.get("accept", []),
        "tests": data.get("tests", []),
        "release": data.get("release", []),
        "features": data.get("features", []),
    }
