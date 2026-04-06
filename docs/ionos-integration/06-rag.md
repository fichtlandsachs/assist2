# RAG — Zwei Modi

## Modus 1: Internes RAG (Standard)

```
Query → IONOS Embeddings (BAAI/bge-m3)
      → pgvector Similarity Search (Top-K Chunks)
      → Prompt-Builder (context injection)
      → IONOS Chat Completion
```

**Aktivierung:** automatisch wenn RAG-Chunks im Index vorhanden sind.
**Code:** `backend/app/services/rag_service.py` — Funktion `retrieve()`
**Embedding-Modell:** konfigurierbar über LiteLLM-Alias `ionos-embed`

## Modus 2: IONOS Document Collections (optional)

Nur wenn Feature-Flag `rag_ionos` aktiv (`AI_FEATURE_FLAGS=...,rag_ionos`).

Nutzt die nativen IONOS-Endpunkte:
- `POST /collections` — Collection anlegen
- `POST /collections/{id}/documents` — Dokumente hochladen
- `POST /collections/{id}/query` — Semantische Suche

**Wichtig:** Diese Endpunkte sind NICHT die OpenAI-kompatiblen Endpunkte.
Sie werden in einem separaten Service-Modul (`ionos_collections_service.py`)
isoliert — nie im Haupt-AI-Pfad gemischt.

## Abstraktion

```python
# rag_service.py — einheitliche Schnittstelle für beide Modi
async def retrieve(query: str, org_id: UUID, db: AsyncSession) -> RagResult:
    if settings.ai_feature_enabled("rag_ionos") and org_uses_ionos_collections(org_id):
        return await _retrieve_ionos_collections(query, org_id)
    return await _retrieve_pgvector(query, org_id, db)
```

## Prompt-Builder

```python
def build_rag_prompt(query: str, chunks: list[str], data: AISuggestRequest) -> str:
    context_block = "\n\n".join(f"[Kontext]\n{c}" for c in chunks)
    return (
        f"{context_block}\n\n"
        f"Story-Titel: {data.title}\n"
        f"Beschreibung: {data.description or '(leer)'}\n"
        f"Akzeptanzkriterien: {data.acceptance_criteria or '(leer)'}\n\n"
        f"Analysiere diese Story gegen die Definition of Ready. Antworte als JSON."
    )
```

Modularer Prompt-Builder → testbar, unabhängig vom Retrieval-Mechanismus.
