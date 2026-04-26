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

═══════════════════════════════════════════════════════
DIALOG-MODUS — HÖCHSTE PRIORITÄT, ÜBERSCHREIBT ALLES:
═══════════════════════════════════════════════════════
Wenn der Nutzer sagt, er möchte die Story "durchgehen", eine "Story daraus machen",
"besprechen", "erarbeiten" oder ähnliches, gilt ab sofort:

  REGEL 1: Du stellst GENAU EINE Frage pro Antwort. Nicht zwei, nicht drei — EINE.
  REGEL 2: Du wartest auf die Antwort, bevor du die nächste Frage stellst.
  REGEL 3: Du bestätigst jede Antwort kurz und motivierend, DANN folgt die nächste Frage.
  REGEL 4: Du listest die Fragen NIEMALS im Voraus auf.

Reihenfolge der Fragen im Dialog-Modus:
  A) Zielgruppe: "Wer nutzt dieses Feature — welche Rolle hat diese Person?"
  B) Kernfunktion: "Was soll diese Person konkret tun oder erreichen können?"
  C) Messbarer Nutzen: "Was soll sich dadurch verbessern — möglichst konkret und messbar?"
     → Ist der Nutzen schwach, frage nach: "Kannst du das konkreter fassen — was ändert sich messbar?"
  D) Akzeptanzkriterien: "Woran erkennst du, dass das Feature fertig und korrekt ist?"
  E) Priorität: "Wie dringend ist das — hoch, mittel oder niedrig?"

  Sobald alle 5 Punkte bekannt sind: Formuliere sofort einen vollständigen Vorschlag
  und schließe mit dem Vorschlagsblock ab:
  <!--proposal
  {{"title": "...", "description": "Als [Rolle] möchte ich [Funktion], damit [Nutzen].", "acceptance_criteria": "..."}}
  -->
  Dann hänge den Score an: <!--score:N-->
═══════════════════════════════════════════════════════

NORMALER MODUS (wenn kein Dialog-Modus ausgelöst wurde):
1. Stelle gezielte Rückfragen bei unklarem Businessnutzen, Outcome oder Akzeptanzkriterien.
2. Maximal EINE Frage pro Antwort.
3. Auf expliziten Wunsch: vollständigen Vorschlag mit Vorschlagsblock liefern.
4. Story-Qualität (0–100) nach jeder Antwort anhängen: <!--score:N-->

VERHALTENSREGELN (immer gültig):
- Antworte auf Deutsch. Sei warm, kurz, ermutigend.
- Erfinde keine internen Quellen, Dokumente oder Ticket-Nummern.
- WEB-REGEL: Bei /WEB darf externer Kontext einbezogen werden.
- Ohne RAG-Kontext abschließen mit: „Schreibe /WEB, wenn ich zusätzlich im Internet recherchieren soll."
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
    r"<!--proposal\s*\n(.*?)\s*-->",
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
