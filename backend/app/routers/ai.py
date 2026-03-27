"""AI utility routes — transcription, etc."""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.config import get_settings
from app.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


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
