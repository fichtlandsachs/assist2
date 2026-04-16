"""Helpers for the Story Refinement Panel (Stufe 1).

Responsibilities:
- Build the story-aware system prompt
- Extract <!--proposal {...}--> from assistant output
- Extract <!--score:N--> from assistant output
"""
from __future__ import annotations

import json
import re
from typing import Optional


# ── System prompt ──────────────────────────────────────────────────────────────

_REFINEMENT_SYSTEM = """\
Du bist ein erfahrener Scrum Master, der hilft, User Stories präzise, umsetzbar und \
outcome-fokussiert zu formulieren.

STORY-KONTEXT (aktuelle Story):
Titel: {title}
Beschreibung: {description}
Akzeptanzkriterien: {acceptance_criteria}
Priorität: {priority}
Status: {status}
Epic: {epic_title}
Projekt: {project_name}

DEINE AUFGABE:
1. Stelle gezielte Rückfragen, wenn Businessnutzen, Outcome, Zielgruppe oder \
   Akzeptanzkriterien unklar oder schwach sind.
2. Stelle maximal 2 offene Fragen gleichzeitig.
3. Wenn du einen Revisionsvorschlag machst, formuliere ihn vollständig und schließe \
   die Antwort mit einem Vorschlagsblock ab (HTML-Kommentar, damit er nicht als Code \
   gerendert wird):
   <!--proposal
   {{"title": "...", "description": "...", "acceptance_criteria": "..."}}
   -->
   Lasse Felder weg, die du nicht änderst.
4. Bewerte nach jeder Antwort die Story-Qualität (0–100) und hänge sie an:
   <!--score:75-->
   Kriterien: Vollständigkeit (Rolle/Funktion/Nutzen), messbarer Outcome, \
   Given/When/Then AK, realistische Umsetzbarkeit.

VERHALTENSREGELN:
- Antworte auf Deutsch, verwende Markdown für Struktur.
- Erfinde keine internen Quellen, Dokumente oder Ticket-Nummern.
- Wenn RAG-Kontext vorhanden ist, zitiere Quellen direkt im Satz mit ihrem Titel.
- Priorität: Outcome > Businessnutzen > technische Details.
"""


def build_system_prompt(
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[str],
    priority: str,
    status: str,
    epic_title: Optional[str],
    project_name: Optional[str],
) -> str:
    return _REFINEMENT_SYSTEM.format(
        title=title,
        description=description or "(nicht angegeben)",
        acceptance_criteria=acceptance_criteria or "(nicht angegeben)",
        priority=priority,
        status=status,
        epic_title=epic_title or "(kein Epic)",
        project_name=project_name or "(kein Projekt)",
    )


# ── Proposal extraction ───────────────────────────────────────────────────────

_PROPOSAL_RE = re.compile(
    r"<!--proposal\s*\n(.*?)\n-->",
    re.DOTALL,
)


def extract_proposal(text: str) -> Optional[dict]:
    """Extract <!--proposal {...}--> from assistant output. Returns dict or None."""
    m = _PROPOSAL_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
        if not isinstance(data, dict):
            return None
        allowed = {"title", "description", "acceptance_criteria"}
        return {k: v for k, v in data.items() if k in allowed} or None
    except (json.JSONDecodeError, ValueError):
        return None


# ── Score extraction ──────────────────────────────────────────────────────────

_SCORE_RE = re.compile(r"<!--score:(-?\d+)-->")


def extract_score(text: str) -> Optional[int]:
    """Extract <!--score:N--> from assistant output. Returns 0–100 or None."""
    m = _SCORE_RE.search(text)
    if not m:
        return None
    return max(0, min(100, int(m.group(1))))
