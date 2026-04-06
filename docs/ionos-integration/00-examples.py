"""
00-examples.py — Runnable examples for IONOS AI API integration.

Run individual examples:
  python docs/ionos-integration/00-examples.py chat
  python docs/ionos-integration/00-examples.py models
  python docs/ionos-integration/00-examples.py embed
  python docs/ionos-integration/00-examples.py rag
"""
import asyncio
import os
import sys

IONOS_API_BASE = os.environ.get("IONOS_API_BASE", "https://openai.ionos.com/openai")
IONOS_API_KEY = os.environ.get("IONOS_API_KEY", "")


def example_chat():
    """Minimal chat completion via IONOS OpenAI-compatible API."""
    import openai

    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=30,
        max_retries=0,
    )

    response = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct",
        messages=[
            {"role": "system", "content": "Du bist ein hilfreicher Assistent."},
            {"role": "user",   "content": "Erkläre den Unterschied zwischen Story Points und Stunden."},
        ],
        max_tokens=512,
        temperature=0.4,
        stream=False,
    )

    text = response.choices[0].message.content
    usage = response.usage
    print(f"[chat] response ({usage.prompt_tokens} in / {usage.completion_tokens} out):\n{text}\n")


async def example_models():
    """Fetch and print all available models from IONOS /v1/models."""
    import httpx

    async with httpx.AsyncClient(
        base_url=f"{IONOS_API_BASE}/v1",
        headers={"Authorization": f"Bearer {IONOS_API_KEY}"},
        timeout=15,
    ) as client:
        resp = await client.get("/models")
        resp.raise_for_status()
        models = resp.json().get("data", [])

    print(f"[models] {len(models)} models available:")
    for m in sorted(models, key=lambda x: x["id"]):
        print(f"  {m['id']}")
    print()


def example_embed():
    """Generate embeddings via IONOS /v1/embeddings."""
    import openai

    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=20,
    )

    texts = [
        "Als Produktmanager möchte ich User Stories bewerten können.",
        "Als Entwickler möchte ich automatische Tests generieren.",
    ]

    response = client.embeddings.create(
        model="BAAI/bge-m3",
        input=texts,
    )

    for i, item in enumerate(response.data):
        vec = item.embedding
        print(f"[embed] text[{i}]: {len(vec)}-dim vector, first 3 dims: {vec[:3]}")
    print()


def example_rag_internal():
    """RAG with internal pgvector — shows the raw building blocks."""
    import openai
    client = openai.OpenAI(
        api_key=IONOS_API_KEY,
        base_url=f"{IONOS_API_BASE}/v1",
        timeout=20,
    )
    query = "Welche Definition of Ready gilt für User Stories?"
    embed_resp = client.embeddings.create(model="BAAI/bge-m3", input=[query])
    query_vec = embed_resp.data[0].embedding
    print(f"[rag] query embedded: {len(query_vec)}-dim")

    # pgvector search (pseudo-code — real impl in rag_service.py):
    # chunks = await db.execute(
    #     "SELECT content FROM documents ORDER BY embedding <-> $1 LIMIT 3",
    #     [query_vec]
    # )
    chunks = ["[simulated chunk 1]", "[simulated chunk 2]"]

    context = "\n\n".join(f"[Kontext]\n{c}" for c in chunks)
    prompt = f"{context}\n\nFrage: {query}\n\nAntwort:"

    resp = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-70B-Instruct",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=512,
        temperature=0.2,
    )
    print(f"[rag] answer: {resp.choices[0].message.content[:200]}\n")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "chat"
    if not IONOS_API_KEY:
        print("ERROR: IONOS_API_KEY not set. Export it before running.")
        sys.exit(1)

    if cmd == "chat":
        example_chat()
    elif cmd == "models":
        asyncio.run(example_models())
    elif cmd == "embed":
        example_embed()
    elif cmd == "rag":
        example_rag_internal()
    else:
        print(f"Unknown command: {cmd}. Use: chat | models | embed | rag")
        sys.exit(1)
