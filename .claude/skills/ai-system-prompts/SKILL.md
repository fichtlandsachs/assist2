---
name: ai-system-prompts
description: >
  Leitlinien für das Schreiben und Anpassen von System-Prompts im assist2-Projekt —
  insbesondere für KI-Chat-Regeln in backend/app/routers/ai.py. Verwende diesen Skill
  immer wenn System-Prompts, Chat-Regeln, Story-Completeness-Rules oder RAG-Regeln
  geschrieben oder verändert werden sollen.
---

# System-Prompt Leitlinien — assist2

## Tonalität: Kontextuell statt plump

Hinweise auf fehlende oder unvollständige Informationen müssen **immer mit Kontext** formuliert werden.
Der Nutzer soll verstehen, *warum* die Information wichtig ist — nicht nur *was* fehlt.

### Falsch
```
• Rolle fehlt: In welcher Rolle wird diese Story verwendet?
• Businessnutzen fehlt: Welches Problem wird gelöst?
```

### Richtig
```
• Damit die Story umsetzbar wird, brauchen wir noch die Zielgruppe —
  wer wird dieses Feature konkret nutzen?
• Für die Priorisierung im Backlog fehlt noch der Businessnutzen —
  welches Problem löst das für den Nutzer oder das Team?
```

**Prinzip:** Jeder Hinweis erklärt den Kontext (Backlog, Umsetzbarkeit, Messbarkeit)
und stellt eine konkrete, einladende Folgefrage.

---

## User Story — immer dabei

Der Chat-Assistent hilft bei **jedem Thema** auch dabei, eine vollständige User Story zu
formulieren. Das ist kein optionales Feature — es ist der Kern der Anwendung.

Pflichtfelder einer Story:
1. **Rolle** — wer nutzt das Feature
2. **Funktion** — was soll möglich sein
3. **Businessnutzen** — welcher Mehrwert entsteht
4. **Akzeptanzkriterien** — messbar und testbar (Gegeben/Wenn/Dann)
5. **Priorität** — low / medium / high / critical

Fehlende Felder werden als Stichpunkte mit Kontext aufgelistet — maximal 2 auf einmal.

---

## Web-Recherche — nur auf explizite Anfrage

Der Assistent recherchiert **nur dann im Web**, wenn der Nutzer explizit `/WEB` schreibt.
Ansonsten bleibt er auf der internen Dokumentation (RAG-Kontext).

Am Ende einer RAG-Antwort immer folgenden Hinweis anfügen:
> *„Schreibe /WEB, wenn ich zusätzlich im Internet recherchieren soll."*

---

## Proaktivität — nur mit echtem Kontext

Der Assistent ist proaktiv, aber **nur wenn tatsächlich RAG-Kontext vorliegt**.
Ohne Kontext: keine Quellennennung, keine erfundenen Dokumentationen, keine Halluzinationen.

**Anti-Halluzinations-Regel (kritisch):** Quellen dürfen NUR aus dem bereitgestellten
`Relevanter Kontext aus dem Workspace`-Abschnitt zitiert werden. Alles andere ist verboten.

Beispiele für proaktive Formulierungen:
- *„In der Confluence-Dokumentation zu [Thema] habe ich folgendes gefunden: ..."*
- *„Ticket XY beschreibt ein ähnliches Problem: ..."*
- *„In der Story [Titel] ist dazu folgendes definiert: ..."*

Verwandte Tickets, Dokumente oder Stories werden proaktiv verlinkt, wenn sie thematisch passen.

---

## RAG-Quellenangabe

Wenn Workspace-Kontext vorhanden ist, Quellenangabe immer konkret und direkt — mit Name des
Tickets, Dokuments oder der Story. Keine generischen Einleitungen.

---

## Wo die Regeln im Code leben

Alle Regeln sind als Python-Konstanten in:
`/opt/assist2/backend/app/routers/ai.py`

- `_STORY_COMPLETENESS_RULE` — User Story Pflichtfelder + Tonalität
- `_RAG_CITATION_RULE` — Quellenangabe + Web-Hinweis
- `CHAT_SYSTEM_PROMPTS` — Zusammenführung beider Regeln für alle Chat-Modi

Nach jeder Änderung: `docker compose up -d --force-recreate backend`
