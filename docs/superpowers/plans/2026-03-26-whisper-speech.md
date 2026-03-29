# Whisper Speech Recognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add self-hosted speech-to-text via faster-whisper so the VoiceRecorder component sends real audio to the backend instead of showing a placeholder.

**Architecture:** A `onerahmet/openai-whisper-asr-webservice` Docker container runs internally on port 9000. The FastAPI backend exposes `POST /api/v1/ai/transcribe` (Bearer JWT required) which proxies the audio file to the whisper container and returns `{"text": "..."}`. The frontend VoiceRecorder replaces its placeholder with a real `fetch` call.

**Tech Stack:** Python/FastAPI, httpx, onerahmet/openai-whisper-asr-webservice (faster-whisper, small model, int8), Next.js/TypeScript, Docker Compose

---

## File Map

| Action | File | Purpose |
|---|---|---|
| Modify | `infra/docker-compose.yml` | Add whisper service |
| Modify | `backend/app/config.py` | Add `WHISPER_URL` setting |
| Create | `backend/app/routers/ai.py` | `POST /api/v1/ai/transcribe` endpoint |
| Modify | `backend/app/main.py` | Register ai_router |
| Create | `backend/tests/unit/test_transcribe.py` | Unit tests (whisper mocked) |
| Modify | `frontend/components/voice/VoiceRecorder.tsx` | Real API call |

---

### Task 1: Docker service + config

**Files:**
- Modify: `infra/docker-compose.yml`
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add whisper service to docker-compose.yml**

Open `infra/docker-compose.yml`. After the `nextcloud:` service block (around line 343), add:

```yaml
  whisper:
    image: onerahmet/openai-whisper-asr-webservice:latest
    container_name: assist2-whisper
    restart: unless-stopped
    environment:
      ASR_MODEL: small
      ASR_ENGINE: faster_whisper
      ASR_QUANTIZATION: int8
    networks:
      - internal
```

No ports — only reachable internally by the backend.

- [ ] **Step 2: Add WHISPER_URL to config.py**

Open `backend/app/config.py`. After the `NEXTCLOUD_ADMIN_APP_PASSWORD` line (line 67), add:

```python
    # Whisper ASR
    WHISPER_URL: str = "http://assist2-whisper:9000"
```

- [ ] **Step 3: Add WHISPER_URL placeholder to .env.example**

Open `infra/.env.example`. Add at the end:

```bash
# Whisper ASR (self-hosted)
WHISPER_URL=http://assist2-whisper:9000
```

- [ ] **Step 4: Commit**

```bash
git add infra/docker-compose.yml backend/app/config.py infra/.env.example
git commit -m "feat(whisper): add whisper docker service and WHISPER_URL config"
```

---

### Task 2: Backend transcribe endpoint + tests (TDD)

**Files:**
- Create: `backend/tests/unit/test_transcribe.py`
- Create: `backend/app/routers/ai.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_transcribe.py`:

```python
"""Unit tests for POST /api/v1/ai/transcribe — whisper proxied, mocked."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import UploadFile
from io import BytesIO


def make_whisper_response(status_code: int, text: str = "Hallo Welt") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value={"text": text})
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError
        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=resp
        )
    return resp


@pytest.mark.asyncio
async def test_transcribe_success():
    """Whisper responds 200 → endpoint returns {text: '...'}."""
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"fake-audio-bytes")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_whisper_response(200, "Hallo Welt")
        )
        result = await transcribe(file=mock_file, current_user=mock_user)

    assert result == {"text": "Hallo Welt"}


@pytest.mark.asyncio
async def test_transcribe_whisper_down():
    """Whisper not reachable → ConnectError → 503 HTTPException."""
    import httpx
    from fastapi import HTTPException
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"audio")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        with pytest.raises(HTTPException) as exc_info:
            await transcribe(file=mock_file, current_user=mock_user)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_transcribe_whisper_error_status():
    """Whisper returns 500 → raise_for_status raises → 503 HTTPException."""
    from fastapi import HTTPException
    from app.routers.ai import transcribe
    from app.models.user import User

    mock_user = MagicMock(spec=User)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.read = AsyncMock(return_value=b"audio")
    mock_file.filename = "recording.webm"
    mock_file.content_type = "audio/webm"

    with patch("app.routers.ai.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=make_whisper_response(500)
        )
        with pytest.raises(HTTPException) as exc_info:
            await transcribe(file=mock_file, current_user=mock_user)

    assert exc_info.value.status_code == 503
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_transcribe.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'app.routers.ai'`

- [ ] **Step 3: Create backend/app/routers/ai.py**

```python
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
        return {"text": resp.json()["text"]}
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Whisper service error: %s", e)
        raise HTTPException(status_code=503, detail="Transkriptions-Service nicht erreichbar")
```

- [ ] **Step 4: Register router in main.py**

Open `backend/app/main.py`. After the nextcloud_router import (line 12), add:

```python
from app.routers.ai import router as ai_router
```

After the nextcloud_router include (line 98), add:

```python
app.include_router(ai_router, prefix="/api/v1", tags=["AI"])
```

- [ ] **Step 5: Run tests — all should pass**

```bash
docker exec assist2-backend pytest backend/tests/unit/test_transcribe.py -v
```

Expected output:
```
test_transcribe_success PASSED
test_transcribe_whisper_down PASSED
test_transcribe_whisper_error_status PASSED
3 passed
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ai.py backend/app/main.py backend/tests/unit/test_transcribe.py
git commit -m "feat(whisper): add POST /api/v1/ai/transcribe endpoint with tests"
```

---

### Task 3: Frontend VoiceRecorder — real API call

**Files:**
- Modify: `frontend/components/voice/VoiceRecorder.tsx`

- [ ] **Step 1: Replace placeholder with real fetch in VoiceRecorder.tsx**

Open `frontend/components/voice/VoiceRecorder.tsx`. Replace the entire file content with:

```typescript
"use client";
import { useState, useRef } from "react";
import { Mic, Square } from "lucide-react";
import { getAccessToken } from "@/lib/api/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
}

export function VoiceRecorder({ onTranscription }: VoiceRecorderProps) {
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    chunksRef.current = [];
    mediaRecorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    mediaRecorder.onstop = async () => {
      setProcessing(true);
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      const form = new FormData();
      form.append("file", blob, "recording.webm");
      try {
        const token = getAccessToken();
        const res = await fetch(`${API_BASE}/api/v1/ai/transcribe`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
          // No Content-Type header — browser sets multipart boundary automatically
        });
        if (res.ok) {
          const data = await res.json() as { text: string };
          onTranscription(data.text);
        } else {
          onTranscription("");
        }
      } catch {
        onTranscription("");
      } finally {
        setProcessing(false);
        stream.getTracks().forEach(t => t.stop());
      }
    };
    mediaRecorder.start();
    setRecording(true);
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
    setRecording(false);
  };

  return (
    <div className="flex items-center gap-2">
      {!recording ? (
        <button
          type="button"
          onClick={() => void startRecording()}
          className="flex items-center gap-2 px-3 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Mic size={16} />
          Aufnehmen
        </button>
      ) : (
        <button
          type="button"
          onClick={stopRecording}
          className="flex items-center gap-2 px-3 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-sm font-medium transition-colors animate-pulse"
        >
          <Square size={16} />
          Stopp
        </button>
      )}
      {processing && <span className="text-sm text-slate-500">Verarbeite...</span>}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles without errors**

```bash
docker exec assist2-frontend npm run build 2>&1 | tail -20
```

Expected: build succeeds (exit 0), no TypeScript errors in VoiceRecorder.tsx.

- [ ] **Step 3: Deploy whisper container**

```bash
cd /opt/assist2/infra
docker compose pull whisper
docker compose up -d whisper
docker compose up -d --no-deps --build backend
```

Wait ~60 seconds for the whisper model to download, then verify:

```bash
docker logs assist2-whisper 2>&1 | tail -5
```

Expected: `INFO: Application startup complete.`

- [ ] **Step 4: Commit**

```bash
git add frontend/components/voice/VoiceRecorder.tsx
git commit -m "feat(whisper): wire VoiceRecorder to real transcribe endpoint"
```

---

## Deployment Note

The whisper container downloads the `small` model (~244 MB) on first start. This happens once and is not persisted between container restarts (no volume needed — the image layer caches it). Startup takes ~60 seconds on first run.

To smoke-test end-to-end manually:
1. Open a story in the UI → voice recorder button → record a short phrase → stop
2. The transcribed text should appear in the description field
3. Backend log: `POST /api/v1/ai/transcribe 200`
