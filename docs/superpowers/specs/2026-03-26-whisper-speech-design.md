# Design: Open-Source Spracherkennung via faster-whisper

**Datum:** 2026-03-26
**Status:** Approved
**Scope:** Selbst-gehostete Spracherkennung für die VoiceRecorder-Komponente in der User-Story-Erstellung

---

## 1. Überblick

Ein selbst-gehosteter `faster-whisper`-Service ersetzt den bisherigen Placeholder im `VoiceRecorder`. Aufnahmen werden vom Browser an das Backend gesendet, das sie intern an den Whisper-Container weiterleitet. Kein externer API-Call, keine Kosten.

---

## 2. Architektur

```
Browser (VoiceRecorder)
    ↓ POST /api/v1/ai/transcribe (multipart, audio/webm)
Backend (FastAPI) — Auth: Bearer JWT
    ↓ httpx → POST http://assist2-whisper:9000/v1/audio/transcriptions
faster-whisper Container (onerahmet/openai-whisper-asr-webservice)
    Model: small | Engine: faster_whisper | Quantization: int8
    ← {"text": "..."}
Backend
    ← {"text": "..."}
Frontend → füllt Story-Felder per onTranscription()
```

---

## 3. Neue Dateien

| Datei | Zweck |
|---|---|
| `backend/app/routers/ai.py` | `POST /api/v1/ai/transcribe` Endpoint |
| `backend/tests/unit/test_transcribe.py` | Unit-Tests (Whisper gemockt) |

## 4. Geänderte Dateien

| Datei | Änderung |
|---|---|
| `infra/docker-compose.yml` | `whisper`-Service hinzufügen |
| `infra/.env.example` | `WHISPER_URL` Placeholder |
| `backend/app/config.py` | `WHISPER_URL: str` Setting |
| `backend/app/main.py` | `ai_router` einbinden |
| `frontend/components/voice/VoiceRecorder.tsx` | Echter API-Call statt Placeholder |

---

## 5. Docker-Service

```yaml
whisper:
  image: onerahmet/openai-whisper-asr-webservice:latest
  container_name: assist2-whisper
  environment:
    ASR_MODEL: small
    ASR_ENGINE: faster_whisper
    ASR_QUANTIZATION: int8
  networks:
    - internal
  restart: unless-stopped
```

- Kein Port nach außen — nur intern erreichbar vom Backend
- `int8`-Quantisierung für optimale CPU-Performance
- `small`-Modell: gute Genauigkeit auf Deutsch, ~244 MB, akzeptable CPU-Latenz

---

## 6. Backend-Endpoint

**`POST /api/v1/ai/transcribe`**

- Input: `multipart/form-data`, Feld `file` (audio/webm, audio/ogg, audio/mp4)
- Auth: Bearer JWT (wie alle anderen Endpoints)
- Response: `{"text": "..."}`
- Fehler: Whisper nicht erreichbar → HTTP 503

```python
@router.post("/ai/transcribe")
async def transcribe(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> dict:
    audio = await file.read()
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.WHISPER_URL}/v1/audio/transcriptions",
            files={"file": (file.filename, audio, file.content_type)},
            data={"model": "whisper-1", "language": "de"},
        )
        resp.raise_for_status()
    return {"text": resp.json()["text"]}
```

---

## 7. Config

```python
# backend/app/config.py
WHISPER_URL: str = "http://assist2-whisper:9000"
```

```bash
# infra/.env.example
WHISPER_URL=http://assist2-whisper:9000
```

---

## 8. Frontend

**`VoiceRecorder.tsx`** — `onstop`-Handler:

```typescript
const blob = new Blob(chunksRef.current, { type: "audio/webm" });
const form = new FormData();
form.append("file", blob, "recording.webm");
try {
  const res = await apiRequest<{ text: string }>("/api/v1/ai/transcribe", {
    method: "POST",
    body: form,
    // kein Content-Type Header — Browser setzt multipart boundary automatisch
  });
  onTranscription(res.text);
} catch {
  onTranscription("");  // leise fehlschlagen
} finally {
  setProcessing(false);
  stream.getTracks().forEach(t => t.stop());
}
```

---

## 9. Tests

**`test_transcribe.py`:**
- `test_transcribe_success` — Whisper gemockt, gibt `{"text": "Hallo"}` zurück → 200
- `test_transcribe_whisper_down` — Whisper-Service nicht erreichbar → 503
- `test_transcribe_requires_auth` — kein JWT → 401

---

## 10. Nicht in diesem Scope

- Automatische Spracherkennung (language=auto) — folgt nach Evaluation
- GPU-Beschleunigung
- Streaming-Transkription (Echtzeit)
- Weitere Sprachen als Deutsch initial
