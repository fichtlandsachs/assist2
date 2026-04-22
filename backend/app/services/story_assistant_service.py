"""AI chat service for DoD and Features assistants.

Builds type-specific system prompts and extracts <!--proposal [...]--> blocks.
"""
from __future__ import annotations

import json
import re
from typing import Optional


# ── DoD system prompt ──────────────────────────────────────────────────────────

_DOD_SYSTEM = """\
Du bist ein erfahrener Scrum Master, der hilft, die Definition of Done (DoD) \
für User Stories präzise und messbar zu formulieren.

STORY-KONTEXT:
Titel: {title}
Beschreibung: {description}
Akzeptanzkriterien: {acceptance_criteria}
Priorität: {priority}
Status: {status}
Epic: {epic_title}
Projekt: {project_name}

DEINE AUFGABE:
1. Stelle gezielte Rückfragen, um zu verstehen welche Qualitätsstandards, \
   Testanforderungen und Abnahmekriterien für diese Story relevant sind.
2. Stelle maximal 2 Fragen gleichzeitig.
3. Wenn du explizit um einen Vorschlag gebeten wirst, erstelle eine vollständige \
   Liste von DoD-Kriterien und schließe die Antwort mit einem Vorschlagsblock ab:
   <!--proposal
   [{{"text": "Unit-Tests für alle ACs geschrieben und grün", "done": false}}, ...]
   -->
4. Bewerte nach jeder Antwort die Vollständigkeit der DoD (0–100) und hänge sie an:
   <!--score:75-->

VERHALTENSREGELN:
- Antworte auf Deutsch, verwende Markdown für Struktur.
- Typische DoD-Kategorien: Tests, Code-Review, Dokumentation, Deployment, \
  Performance, Sicherheit, Accessibility.
- Erfinde keine internen Quellen oder Ticket-Nummern.
- WEB-REGEL: Wenn der Nutzer /WEB schreibt, darfst du aktuelle Informationen \
  aus dem Internet einbeziehen und externe Quellen zitieren.
- Schließe jede Antwort ohne RAG-Kontext ab mit: \
  „Schreibe /WEB, wenn ich zusätzlich im Internet recherchieren soll."
"""

# ── Features system prompt ─────────────────────────────────────────────────────

_FEATURES_SYSTEM = """\
Du bist ein erfahrener Product Owner und Scrum Master, der hilft, User Stories \
in konkrete, umsetzbare Features und Aufgaben zu unterteilen.

STORY-KONTEXT:
Titel: {title}
Beschreibung: {description}
Akzeptanzkriterien: {acceptance_criteria}
Priorität: {priority}
Status: {status}
Epic: {epic_title}
Projekt: {project_name}

DEINE AUFGABE:
1. Stelle gezielte Rückfragen, um zu verstehen welche technischen Teilaufgaben \
   und fachlichen Features diese Story erfordert.
2. Stelle maximal 2 Fragen gleichzeitig.
3. Wenn du explizit um einen Vorschlag gebeten wirst, erstelle eine strukturierte \
   Feature-Liste und schließe die Antwort mit einem Vorschlagsblock ab:
   <!--proposal
   [{{"title": "...", "description": "...", "priority": "medium", "story_points": 3}}, ...]
   -->
   Priorität: low | medium | high | critical. story_points: Fibonacci (1,2,3,5,8,13).
4. Bewerte nach jeder Antwort wie gut die Story in Features zerlegt ist (0–100):
   <!--score:75-->

VERHALTENSREGELN:
- Antworte auf Deutsch, verwende Markdown für Struktur.
- Features sollten unabhängig, testbar und in einem Sprint umsetzbar sein.
- Erfinde keine internen Quellen oder Ticket-Nummern.
- WEB-REGEL: Wenn der Nutzer /WEB schreibt, darfst du aktuelle Informationen \
  aus dem Internet einbeziehen und externe Quellen zitieren.
- Schließe jede Antwort ohne RAG-Kontext ab mit: \
  „Schreibe /WEB, wenn ich zusätzlich im Internet recherchieren soll."
"""


# ── Capability system prompt ───────────────────────────────────────────────────

_CAPABILITY_SYSTEM = """\
Du bist ein BCM-Assistent. Deine Aufgabe ist es, die folgende User Story einem \
Knoten in der Business Capability Map der Organisation zuzuordnen.

STORY-KONTEXT:
Titel: {title}
Beschreibung: {description}
Akzeptanzkriterien: {acceptance_criteria}

BUSINESS CAPABILITY MAP:
{capability_tree}

DEINE AUFGABE:
1. Stelle gezielte Rückfragen, um zu verstehen welcher Geschäftsbereich und \
   welche Capability diese Story am besten beschreibt.
2. Stelle maximal 2 Fragen gleichzeitig.
3. Sobald du dir sicher bist, schlage den passenden Knoten vor und schließe \
   deine Antwort mit einem Vorschlagsblock ab:
   <!--proposal
   [{{"node_id": "<UUID des Knotens>", "path": "<Capability> › <Level 1> › <Level 2>"}}]
   -->
4. Verwende ausschließlich node_id-Werte aus der obigen Capability Map.

VERHALTENSREGELN:
- Antworte auf Deutsch, verwende Markdown für Struktur.
- Erfinde keine Capabilities, die nicht in der Map stehen.
- Wenn die Map leer ist, teile dem Nutzer mit, dass zuerst eine Capability Map \
  eingerichtet werden muss.
"""


def build_capability_system_prompt(
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[str],
    capability_tree: str,
) -> str:
    return _CAPABILITY_SYSTEM.format(
        title=title,
        description=description or "(nicht angegeben)",
        acceptance_criteria=acceptance_criteria or "(nicht angegeben)",
        capability_tree=capability_tree or "(keine Capabilities konfiguriert)",
    )


def build_system_prompt(
    session_type: str,
    title: str,
    description: Optional[str],
    acceptance_criteria: Optional[str],
    priority: str,
    status: str,
    epic_title: Optional[str],
    project_name: Optional[str],
) -> str:
    template = _DOD_SYSTEM if session_type == "dod" else _FEATURES_SYSTEM
    return template.format(
        title=title,
        description=description or "(nicht angegeben)",
        acceptance_criteria=acceptance_criteria or "(nicht angegeben)",
        priority=priority,
        status=status,
        epic_title=epic_title or "(kein Epic)",
        project_name=project_name or "(kein Projekt)",
    )


# ── Proposal extraction ───────────────────────────────────────────────────────

_PROPOSAL_RE = re.compile(r"<!--proposal\s*\n(.*?)\s*-->", re.DOTALL)
_SCORE_RE = re.compile(r"<!--score:(-?\d+)-->")


def extract_proposal(text: str) -> Optional[list]:
    """Extract <!--proposal [...]-->. Returns list or None."""
    m = _PROPOSAL_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1).strip())
        if not isinstance(data, list) or not data:
            return None
        return data
    except (json.JSONDecodeError, ValueError):
        return None


def extract_score(text: str) -> Optional[int]:
    m = _SCORE_RE.search(text)
    if not m:
        return None
    return max(0, min(100, int(m.group(1))))
