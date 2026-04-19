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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_current_user, get_db
from app.models.user import User
from app.services.rag_service import retrieve as rag_retrieve
from app.schemas.grounded_chat import (
    GroundedChatRequest,
    GroundedChatResponse,
    CitationSchema,
    ValidationFindingSchema,
    UsedSourceSchema,
)

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

_NO_HALLUCINATION_RULE = (
    "ANTI-HALLUZINATIONS-REGEL (höchste Priorität, überschreibt alle anderen Regeln): "
    "Du darfst NIEMALS interne Ressourcen erfinden — keine Wiki-Seiten, keine Confluence-Artikel, "
    "keine Ticket-Nummern, keine Dokumentationspfade, keine Links — die nicht im bereitgestellten "
    "Workspace-Kontext stehen. Wenn du eine Quelle nicht im Kontext findest, existiert sie für dich nicht. "
    "Wenn der Nutzer nach einem Link, einer Seite oder einem Dokument fragt und du keinen Kontext dazu hast, "
    "antworte IMMER genau so: "
    "'Leider konnte ich den internen Unterlagen nichts finden. Mit /WEB kann ich noch einmal extern schauen, welche Informationen ich für dich finden kann. Du musst mir aber genau sagen, wonach ich suchen soll.' "
    "Wenn du dir bei einer Information nicht sicher bist: sage es offen. "
    "Besser eine ehrliche 'Ich weiß es nicht'-Antwort als eine falsche."
)

_STORY_COMPLETENESS_RULE = (
    "USER-STORY-QUALITÄTSREGEL: "
    "Wenn der Nutzer fragt, ob eine User Story existiert oder nach einer bestehenden Story sucht: "
    "Prüfe ZUERST den Workspace-Kontext auf [Karl Story]-Einträge. "
    "Wenn eine passende Story gefunden wurde, nenne sie direkt mit Titel, Status und Link — erfinde KEINE neue. "
    "Wenn keine Story im Kontext gefunden wurde, helfe dabei eine neue zu erstellen und frage nach den Pflichtfeldern: "
    "(1) Rolle — wer nutzt das Feature, (2) Funktion — was soll möglich sein, "
    "(3) Businessnutzen — welcher messbare Outcome entsteht, (4) Akzeptanzkriterien — messbar und testbar, (5) Priorität. "
    "BUSINESSNUTZEN-QUALITÄTSPRÜFUNG: Ist ein Businessnutzen vorhanden, prüfe ob er einen echten Outcome beschreibt. "
    "Schwacher Nutzen ('damit es besser wird', 'um die UX zu verbessern') muss konkretisiert werden. "
    "Ein guter Businessnutzen benennt: wer profitiert, was sich messbar ändert und welchen Wert das erzeugt "
    "(z.B. 'damit Support-Anfragen um 30 % sinken' oder 'damit Nutzer den Prozess ohne Rückfragen abschließen'). "
    "Fehlt ein konkreter Outcome, stelle eine einladende Rückfrage: "
    "'Was soll sich für [Rolle] konkret verändern, wenn dieses Feature live ist — gibt es eine Kennzahl oder ein Verhalten, das sich messbar verbessern soll?' "
    "Fehlen Informationen, gib einen kontextuellen Hinweis — maximal 2 Punkte auf einmal. "
    "Sobald alle Pflichtfelder vorhanden sind UND der Businessnutzen einen echten Outcome beschreibt, erstelle die Story ohne weitere Rückfragen."
)

_RAG_CITATION_RULE = (
    "QUELLENREGEL — KRITISCH: "
    "Zitiere AUSSCHLIESSLICH Quellen, die dir im Abschnitt 'Relevanter Kontext aus dem Workspace' "
    "explizit bereitgestellt wurden. Jede Quelle dort enthält einen Titel — nutze genau diesen. "
    "Wenn Kontext vorhanden ist, nenne den Quelltitel direkt im Satz, z.B.: "
    "'Laut **[Titel]** ...' oder 'In **[Titel]** steht: ...'. "
    "Nenne im Fließtext NIEMALS URLs, Pfade oder Links — also keine Zeichenfolgen wie "
    "'/demo/stories/...', 'https://...' oder ähnliche Pfadangaben. Gib niemals Rohe IDs oder UUIDs aus. "
    "STORY-SONDERREGEL: Wenn eine [Karl Story]-Quelle gefunden wurde aber keine Dokumentation, antworte: "
    "'Dokumentation habe ich dazu nicht gefunden, aber es gibt eine User Story dazu: [Titel] (Status: [Status aus Titel]).' "
    "Wenn KEIN Workspace-Kontext bereitgestellt wurde: "
    "Erfinde KEINE Quellen. Erwähne KEINE Dokumentation, Tickets oder Stories. "
    "Antworte ausschließlich auf Basis deines allgemeinen Wissens. "
    "Schließe bei vorhandenem Kontext ab mit: 'Schreibe /WEB, wenn ich zusätzlich im Internet recherchieren soll.' "
    "WEBSUCHE-REGEL: Wenn der Nutzer '/WEB' schreibt, recherchiere im Internet und ergänze mit aktuellen Quellen."
)

CHAT_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "Du bist ein hilfreicher KI-Assistent für ein agiles Entwicklungsteam. "
        "Antworte präzise, professionell und auf Deutsch, es sei denn, der Nutzer schreibt in einer anderen Sprache. "
        "Strukturiere deine Antworten mit Markdown: Überschriften (##), Aufzählungen (- oder 1.), "
        "Fettschrift (**) für wichtige Begriffe und Code-Blöcke (```) wo sinnvoll. "
        "Wenn der Nutzer ein Bild (Mockup, Screenshot, Wireframe) einfügt, beschreibe es detailliert als UX/UI-Mockup: "
        "Layout, Komponenten, Benutzerfluss und mögliche Anforderungen, die sich daraus ableiten lassen. "
        + _STORY_COMPLETENESS_RULE
    ),
    "docs": (
        "Du bist ein Experte für technische Dokumentation. "
        "Hilf beim Erstellen, Verbessern und Strukturieren von Dokumenten. "
        "Verwende Markdown für klare Strukturierung: Überschriften, Listen, Tabellen und Code-Blöcke. "
        + _STORY_COMPLETENESS_RULE
    ),
    "tasks": (
        "Du bist ein agiler Coach und Projektmanager. "
        "Hilf bei der Planung, Priorisierung und Strukturierung von User Stories und Aufgaben. "
        "Strukturiere Antworten mit Markdown: Aufzählungen, nummerierten Listen und Überschriften für klare Gliederung. "
        + _STORY_COMPLETENESS_RULE
    ),
}

EXTRACT_SYSTEM_PROMPT = (
    "Du bist ein Experte für agile Anforderungsanalyse. "
    "Analysiere das folgende Transkript und extrahiere ALLE vorhandenen Informationen vollständig. "
    "Antworte NUR mit einem JSON-Objekt in exakt diesem Format:\n"
    '{"title": "Kurzer prägnanter Titel der User Story (max. 80 Zeichen)", '
    '"story": ["Als [Rolle] möchte ich [Funktion], damit [Businessnutzen]."], '
    '"accept": ["Gegeben [Vorbedingung], wenn [Aktion], dann [Ergebnis]."], '
    '"dod": ["Die Implementierung ist abgeschlossen wenn ...", "Code wurde reviewed", "Tests sind grün"], '
    '"tests": ["TC-01: [Testbeschreibung]", "TC-02: ..."], '
    '"release": ["v1.0: [Scope]"], '
    '"features": [{"title": "Feature-Titel", "description": "Konkrete Beschreibung der Teilfunktion"}]}\n'
    "Regeln:\n"
    "- Extrahiere ALLE Akzeptanzkriterien aus dem Gespräch — auch implizite.\n"
    "- Leite DoD-Kriterien aus den Abnahmekriterien und technischen Anforderungen ab (z.B. Tests grün, Review abgeschlossen, Dokumentation aktuell).\n"
    "- Leite Testfälle direkt aus den Akzeptanzkriterien ab (mindestens 1 TC pro Kriterium).\n"
    "- Features sind konkrete, implementierbare Teilfunktionen — trenne sie granular auf.\n"
    "- Wenn keine Information für eine Kategorie vorhanden ist, gib ein leeres Array zurück.\n"
    "- Erfinde keine Informationen, die nicht im Transkript stehen."
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
                f"{settings.WHISPER_URL}/asr",
                params={"task": "transcribe", "language": "de", "output": "json", "encode": "false"},
                files={"audio_file": (file.filename, audio, file.content_type)},
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
    # ── Billing gate ──────────────────────────────────────────────────────────
    settings = get_settings()
    if settings.BILLING_ENABLED and body.org_id and not current_user.is_superuser:
        import uuid as _uuid_mod
        from app.services.billing_service import billing_service as _billing
        has_access = await _billing.check_access_cached(_uuid_mod.UUID(body.org_id), db)
        if not has_access:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Kein aktives Abonnement",
                    "code": "BILLING_REQUIRED",
                    "message": "Der AI-Chat erfordert ein aktives Abonnement.",
                    "upgrade_url": f"/{body.org_id}/settings?tab=billing",
                },
            )
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
    rag_chunks: list = []
    rag_context = ""
    if body.org_id:
        try:
            # Build RAG query from last user message + recent context (last 3 turns)
            # so short follow-up questions ("hast du schon eine story?") still find the right content
            recent_texts = [m.to_text() for m in body.messages[-6:] if m.to_text().strip()]
            rag_query = " ".join(recent_texts)[-800:]  # cap at 800 chars
            if rag_query:
                rag_result = await asyncio.wait_for(
                    rag_retrieve(rag_query, _uuid_module.UUID(body.org_id), db),
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
                    def _fmt_chunk(c) -> str:
                        label = _label.get(c.source_type, "[Kontext]")
                        title = c.source_title or ""
                        return f"{label} {title}\n{c.text}"

                    rag_context = "\n\n".join(_fmt_chunk(c) for c in rag_result.chunks)
                    rag_chunks = list(rag_result.chunks)

                    # Enrich karl_story chunks: attach linked Jira + Confluence sources
                    from app.models.user_story import UserStory as _UserStory
                    _extra_sources: list = []
                    _seen_refs: set = set()
                    for _c in rag_result.chunks:
                        if _c.source_type != "karl_story" or not _c.source_url:
                            continue
                        # source_ref format: "story:{uuid}" — extract uuid from URL instead
                        # source_url: "/{org_slug}/stories/{uuid}"
                        _parts = (_c.source_url or "").rstrip("/").split("/")
                        _story_id_str = _parts[-1] if _parts else None
                        if not _story_id_str or _story_id_str in _seen_refs:
                            continue
                        _seen_refs.add(_story_id_str)
                        try:
                            from types import SimpleNamespace as _NS
                            _story_uuid = _uuid_module.UUID(_story_id_str)
                            _story_res = await db.execute(
                                select(_UserStory).where(_UserStory.id == _story_uuid)
                            )
                            _story = _story_res.scalar_one_or_none()
                            if _story:
                                if _story.jira_ticket_key and _story.jira_ticket_url:
                                    _extra_sources.append(_NS(
                                        source_type="jira",
                                        source_title=f"Jira: {_story.jira_ticket_key}",
                                        source_url=_story.jira_ticket_url,
                                        indexed_at=None,
                                    ))
                                if _story.confluence_page_url:
                                    from app.models.document_chunk import DocumentChunk as _DC
                                    from urllib.parse import unquote_plus as _uq
                                    _conf_chunk = await db.execute(
                                        select(_DC.source_title).where(
                                            _DC.org_id == _story.organization_id,
                                            _DC.source_type == "confluence",
                                            _DC.source_url == _story.confluence_page_url,
                                        ).limit(1)
                                    )
                                    _conf_title = _conf_chunk.scalar_one_or_none()
                                    if not _conf_title:
                                        # Fall back to last URL path segment
                                        _url_seg = _story.confluence_page_url.rstrip("/").split("/")[-1]
                                        _conf_title = _uq(_url_seg).replace("+", " ") or "Confluence-Dokumentation"
                                    _extra_sources.append(_NS(
                                        source_type="confluence",
                                        source_title=_conf_title,
                                        source_url=_story.confluence_page_url,
                                        indexed_at=None,
                                    ))
                        except Exception:
                            pass
                    rag_chunks.extend(_extra_sources)
        except asyncio.TimeoutError:
            pass  # RAG timeout is normal under load
        except Exception as rag_exc:
            logger.warning("RAG retrieval error (suppressed): %s", rag_exc)

    if rag_context:
        rag_block = (
            _NO_HALLUCINATION_RULE + " "
            + _RAG_CITATION_RULE
            + f"\n\n---\nRelevanter Kontext aus dem Workspace:\n\n{rag_context}\n\n---\n"
        )
    else:
        rag_block = (
            "KEINE INTERNEN QUELLEN VERFÜGBAR: Für diese Anfrage wurden keine internen Dokumente, "
            "Tickets oder Wiki-Seiten gefunden. Erwähne keine internen Quellen, erfinde keine Links, "
            "Seitentitel oder Ticket-Nummern. Antworte ausschließlich auf Basis deines allgemeinen Wissens. "
            "Wenn der Nutzer nach internen Quellen oder Links fragt, antworte: "
            "'Leider konnte ich den internen Unterlagen nichts finden. Mit /WEB kann ich noch einmal extern schauen, welche Informationen ich für dich finden kann. Du musst mir aber genau sagen, wonach ich suchen soll.'\n\n"
        )
    full_system = rag_block + system_prompt
    messages = [{"role": "system", "content": full_system}]
    messages += [{"role": m.role, "content": _build_content(m)} for m in body.messages]

    # Quellenpflicht: Antwort muss mit Quellenangabe beginnen wenn Kontext vorhanden
    _SOURCE_PREFIX = "Ich habe in der "
    _NO_SOURCE_MSG = "Leider konnte ich den internen Unterlagen nichts finden. Mit /WEB kann ich noch einmal extern schauen, welche Informationen ich für dich finden kann. Du musst mir aber genau sagen, wonach ich suchen soll."
    _HALLUCINATION_PATTERNS = (
        "ich habe in der confluence",
        "ich habe in der jira",
        "ich habe in der dokumentation",
        "ich habe in der wiki",
        "ich habe folgendes in der",
        "laut confluence",
        "laut der dokumentation",
        "laut unserer dokumentation",
        "in unserer dokumentation",
        "in unserer wiki",
    )

    async def event_stream() -> AsyncIterator[str]:
        # Quellenpflicht: Ohne RAG-Kontext sofort feste Antwort senden, kein LLM-Aufruf
        if not rag_context and any(
            p in (body.messages[-1].to_text() if body.messages else "").lower()
            for p in ("doku", "dokumentation", "confluence", "jira", "wiki", "ticket", "quelle", "link", "seite")
        ):
            yield f"data: {_NO_SOURCE_MSG}\n\n"
            yield "data: [DONE]\n\n"
            return

        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        for model in ("ionos-reasoning", "ionos-quality", "ionos-fast"):
            try:
                stream = await oai.chat.completions.create(
                    model=model,
                    max_tokens=2048,
                    messages=messages,
                    stream=True,
                )
                buffer = ""
                output_text = ""
                hallucination_detected = False
                async for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if not delta:
                        continue
                    output_text += delta
                    if not rag_context and not hallucination_detected:
                        buffer += delta
                        if len(buffer) > 120:
                            buffer = buffer[-120:]
                        if any(p in buffer.lower() for p in _HALLUCINATION_PATTERNS):
                            hallucination_detected = True
                            logger.warning("Hallucination detected in stream, aborting model %s", model)
                            break
                    # SSE requires each line to be a separate data: field
                    sse_payload = delta.replace("\n", "\ndata: ")
                    yield f"data: {sse_payload}\n\n"

                # Track usage (fire-and-forget via Celery)
                if body.org_id and not hallucination_detected:
                    import uuid as _uid
                    from app.services.billing_service import billing_service as _billing
                    input_chars = sum(len(str(m.get("content", ""))) for m in messages)
                    # Rough token estimate: chars / 4
                    _billing.record_usage(
                        org_id=_uid.UUID(body.org_id),
                        user_id=current_user.id,
                        model=model,
                        provider="litellm",
                        feature="chat",
                        input_tokens=input_chars // 4,
                        output_tokens=len(output_text) // 4,
                        cost_usd=0.0,  # enriched by LiteLLM callback
                    )

                if hallucination_detected:
                    yield f"data: {_NO_SOURCE_MSG}\n\n"
                elif rag_chunks:
                    seen: set = set()
                    sources_data = []
                    for c in rag_chunks:
                        key = c.source_url or c.source_title or c.source_type
                        if key in seen:
                            continue
                        seen.add(key)
                        _type_label = {
                            "confluence": "Confluence",
                            "jira": "Jira",
                            "karl_story": "Karl Story",
                            "nextcloud": "Dokument",
                            "user_action": "Team-Wissen",
                        }.get(c.source_type, c.source_type)
                        sources_data.append({
                            "title": c.source_title or _type_label,
                            "url": c.source_url or None,
                            "type": _type_label,
                        })
                    yield f"data: [SOURCES]{json.dumps(sources_data)}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as exc:
                logger.warning("AI chat model %s failed, trying next: %s", model, exc)
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
        "Du bist ein Experte für agile Anforderungsanalyse. "
        "Fasse das folgende Gespräch vollständig und strukturiert zusammen — so, dass daraus eine vollständige User Story extrahiert werden kann. "
        "Bewahre ALLE folgenden Informationen lückenlos: "
        "Rollen/Akteure, funktionale Anforderungen, Businessnutzen, Akzeptanzkriterien, Testfälle, Features, Randbedingungen, offene Fragen und Entscheidungen. "
        "Lasse nichts weg, was für die Umsetzung oder Qualitätssicherung relevant sein könnte. "
        "Gliedere die Zusammenfassung in: Kontext, Anforderungen, Akzeptanzkriterien, Features, Offene Punkte."
    )
    try:
        oai = AsyncOpenAI(
            api_key=settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        resp = None
        for _model in ("ionos-quality", "claude-haiku-4-5"):
            try:
                resp = await oai.chat.completions.create(
                    model=_model,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": transcript},
                    ],
                )
                break
            except Exception as _exc:
                logger.warning("compact-chat model %s failed (%s), trying next", _model, _exc)

        # Fallback: if all models fail (e.g. content filter), use truncated raw transcript
        if resp is None:
            logger.warning("compact-chat: all models failed, falling back to raw transcript")
            return {"summary": transcript[-3000:]}

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


@router.post("/ai/chat/grounded")
async def grounded_chat(
    body: GroundedChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroundedChatResponse:
    """Structured, evidence-grounded chat endpoint.

    Enforces source policy, evidence qualification, grounded generation,
    answer validation, and confidence scoring. No streaming — returns full
    structured response with citations, validation findings, and metadata.
    """
    from app.ai.evidence import qualify_evidence
    from app.ai.policy import PolicyEngine, PolicyConfig, FALLBACK_MESSAGE
    from app.ai.validator import validate_answer
    from app.ai.confidence import score_confidence
    from app.ai.grounded_gen import generate_grounded

    settings = get_settings()
    user_text = next(
        (m["content"] for m in reversed(body.messages) if m.get("role") == "user"), ""
    )

    # 1. Source policy
    policy_cfg = PolicyConfig(
        web_signal=settings.CHAT_WEB_SIGNAL,
        web_requires_signal=settings.CHAT_WEB_REQUIRES_SIGNAL,
        min_evidence_count=settings.CHAT_MIN_EVIDENCE_COUNT,
        min_relevance_score=settings.CHAT_MIN_RELEVANCE_SCORE,
        fallback_on_insufficient=True,
        policy_mode=body.policy_mode,
    )
    engine = PolicyEngine(policy_cfg)
    web_allowed = settings.CHAT_WEB_SIGNAL in user_text

    # 2. RAG retrieval
    rag_chunks: list = []
    if body.org_id:
        try:
            rag_result = await asyncio.wait_for(
                rag_retrieve(user_text, _uuid_module.UUID(body.org_id), db),
                timeout=1.5,
            )
            if rag_result.mode in ("direct", "context"):
                rag_chunks = rag_result.chunks
        except Exception as exc:
            logger.warning("Grounded chat RAG retrieval failed: %s", exc)

    # 3. Evidence qualification
    evidence = qualify_evidence(
        chunks=rag_chunks,
        web_allowed=web_allowed,
        min_relevance=policy_cfg.min_relevance_score,
        min_usable=policy_cfg.min_evidence_count,
    )

    # 4. Policy decision
    decision = engine.evaluate(user_text, evidence)

    if decision.fallback_applied or not decision.allowed:
        return GroundedChatResponse(
            answer=settings.CHAT_FALLBACK_MESSAGE,
            summary=settings.CHAT_FALLBACK_MESSAGE,
            confidence="UNGROUNDED",
            grounded=False,
            blocked=decision.blocked,
            fallback_applied=decision.fallback_applied,
            source_mode=decision.source_mode,
            policy_mode=decision.policy_mode,
            warnings=[decision.reason or "insufficient_evidence"],
        )

    # 5. Grounded generation
    structured = await generate_grounded(user_text, evidence)

    answer_text = structured.get("summary", "") or "\n".join(structured.get("facts", []))

    # 6. Validation
    validation = validate_answer(
        answer=answer_text,
        evidence=evidence,
        policy_mode=decision.policy_mode,
        web_allowed=web_allowed,
        user_text=user_text,
    )

    if not validation.passed:
        blocking = validation.blocking_findings
        return GroundedChatResponse(
            answer=settings.CHAT_FALLBACK_MESSAGE,
            summary=settings.CHAT_FALLBACK_MESSAGE,
            confidence="UNGROUNDED",
            grounded=False,
            blocked=True,
            fallback_applied=False,
            source_mode=decision.source_mode,
            policy_mode=decision.policy_mode,
            validation_findings=[
                ValidationFindingSchema(**vars(f)) for f in validation.findings
            ],
            warnings=[f.message for f in blocking],
        )

    # 7. Confidence scoring
    confidence = score_confidence(evidence, validation.passed, decision.allowed)

    # 8. Build citations and used_sources
    citations = [
        CitationSchema(
            source_type=e.source_type,
            source_name=e.source_name,
            excerpt_location=e.excerpt_location,
            relevance_score=e.relevance_score,
        )
        for e in evidence.usable
    ]
    used_sources = [
        UsedSourceSchema(
            source_type=e.source_type,
            source_name=e.source_name,
            url=e.excerpt_location,
            relevance_score=e.relevance_score,
            freshness_score=e.freshness_score,
            authority_score=e.authority_score,
            usable=e.usable_for_answer,
        )
        for e in evidence.items
    ]

    return GroundedChatResponse(
        answer=answer_text,
        summary=structured.get("summary", ""),
        facts=structured.get("facts", []),
        assumptions=structured.get("assumptions", []),
        uncertainties=structured.get("uncertainties", []),
        open_questions=structured.get("open_questions", []),
        recommendations=structured.get("recommendations", []),
        citations=citations,
        warnings=structured.get("warnings", []),
        validation_findings=[
            ValidationFindingSchema(**vars(f)) for f in validation.findings
        ],
        confidence=confidence.level,
        grounded=True,
        blocked=False,
        fallback_applied=False,
        policy_mode=decision.policy_mode,
        source_mode=decision.source_mode,
        used_sources=used_sources,
    )


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
            api_key=settings.LITELLM_API_KEY or "sk-heykarl",
            base_url=f"{settings.LITELLM_URL}/v1",
        )
        raw = ""
        for _model in ("ionos-quality", "claude-haiku-4-5"):
            try:
                resp = await oai.chat.completions.create(
                    model=_model,
                    max_tokens=2048,
                    messages=[
                        {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                        {"role": "user", "content": body.transcript},
                    ],
                )
                raw = (resp.choices[0].message.content or "").strip()
                break
            except Exception as _exc:
                logger.warning("extract-story model %s failed (%s), trying next", _model, _exc)
        if not raw:
            raise RuntimeError("All extract-story models failed")
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
