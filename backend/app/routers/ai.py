"""AI utility routes — transcription, chat streaming, story extraction."""
import json
import logging
from typing import AsyncIterator

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# ── System prompts ────────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "Du bist ein hilfreicher KI-Assistent für ein agiles Entwicklungsteam. "
        "Antworte präzise, professionell und auf Deutsch, es sei denn, der Nutzer schreibt in einer anderen Sprache."
    ),
    "docs": (
        "Du bist ein Experte für technische Dokumentation. "
        "Hilf beim Erstellen, Verbessern und Strukturieren von Dokumenten."
    ),
    "tasks": (
        "Du bist ein agiler Coach und Projektmanager. "
        "Hilf bei der Planung, Priorisierung und Strukturierung von User Stories und Aufgaben."
    ),
}

EXTRACT_SYSTEM_PROMPT = (
    "Du bist ein Experte für agile Anforderungsanalyse. "
    "Analysiere das folgende Transkript eines Gesprächs und extrahiere strukturierte Informationen. "
    "Antworte NUR mit einem JSON-Objekt in exakt diesem Format:\n"
    '{"story": ["Als ... möchte ich ... damit ..."], '
    '"accept": ["Gegeben ..., wenn ..., dann ..."], '
    '"tests": ["TC-01: ..."], '
    '"release": ["v1.0: ..."]}\n'
    "Wenn keine Information für eine Kategorie vorhanden ist, gib ein leeres Array zurück."
)


# ── Request schemas ───────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    mode: str = "chat"
    org_id: str | None = None


class ExtractStoryRequest(BaseModel):
    transcript: str
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
) -> StreamingResponse:
    """Stream an Anthropic chat response as Server-Sent Events."""
    settings = get_settings()
    system_prompt = CHAT_SYSTEM_PROMPTS.get(body.mode, CHAT_SYSTEM_PROMPTS["chat"])
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def event_stream() -> AsyncIterator[str]:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    yield f"data: {text}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("AI chat stream error: %s", exc)
            yield "data: [ERROR]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/ai/extract-story")
async def extract_story(
    body: ExtractStoryRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Extract structured story data from a conversation transcript."""
    if len(body.transcript) < 80:
        return {"story": [], "accept": [], "tests": [], "release": []}

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=EXTRACT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": body.transcript}],
    )
    raw = response.content[0].text.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("AI extract-story returned non-JSON: %s", raw[:200])
        return {"story": [], "accept": [], "tests": [], "release": []}

    return {
        "story": data.get("story", []),
        "accept": data.get("accept", []),
        "tests": data.get("tests", []),
        "release": data.get("release", []),
    }
