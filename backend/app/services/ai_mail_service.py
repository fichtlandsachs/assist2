"""AI-based email topic clustering using Claude."""
from __future__ import annotations

import json
import logging
from typing import Optional

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


def _make_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().ANTHROPIC_API_KEY)


def _parse_json(raw: str) -> list:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


BATCH_SIZE = 20


def _cluster_batch(messages: list[dict], client: anthropic.Anthropic) -> list[dict]:
    lines = []
    for m in messages:
        subject = (m.get("subject") or "(kein Betreff)")[:100]
        sender = (m.get("sender_name") or m.get("sender_email") or "Unbekannt")[:60]
        snippet = (m.get("snippet") or "")[:120]
        lines.append(f'id={m["id"]} | Von: {sender} | Betreff: {subject} | Inhalt: {snippet}')

    email_list = "\n".join(lines)
    prompt = f"""Analysiere diese {len(messages)} E-Mails und weise jedem eine inhaltliche Gruppe (topic_cluster) zu.

{email_list}

Regeln:
- Gleiche Bestellung/Anfrage/Thema → gleicher Cluster-Name
- Cluster-Name = konkretes deutsches Thema, z.B. "Amazon Bestellung #112-234", "Gorenje Reparatur", "Newsletter Fahrrad-XXL", "DHL Versand", "Strato Rechnung"
- Referenznummern aus Betreff/Inhalt verwenden wenn vorhanden
- Re:/AW:/FW:-Ketten → gleicher Cluster wie Original
- Max. 55 Zeichen pro Name

Antworte NUR mit JSON-Array:
[{{"id":"uuid","topic_cluster":"Name"}}]"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text
    return _parse_json(raw)


def cluster_messages_sync(
    messages: list[dict],  # [{id, subject, sender_email, sender_name, snippet}]
) -> list[dict]:  # [{id, topic_cluster}]
    """
    Send email summaries to Claude in batches and get back topic_cluster labels.
    Runs synchronously (for use in Celery tasks).
    """
    if not messages:
        return []

    settings = get_settings()
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set — skipping topic clustering")
        return []

    client = _make_client()
    all_results: list[dict] = []

    for i in range(0, len(messages), BATCH_SIZE):
        batch = messages[i:i + BATCH_SIZE]
        try:
            results = _cluster_batch(batch, client)
            all_results.extend(results)
            logger.info("topic_cluster batch %d-%d: %d clusters", i, i + len(batch), len({r.get("topic_cluster") for r in results}))
        except Exception as e:
            logger.error("topic_cluster batch failed: %s", e)

    return all_results
