# assist2

**Compliance-fähiges Prozessdokumentationssystem mit BCM-Fokus**

Automatisierte Generierung strukturierter Prozessdokumentation, Draw.io-Diagramme
und Compliance-Analysen (NIS2 / KRITIS / BCM) aus User Stories, Anforderungen
und technischen Artefakten.

assist2 ist kein generischer Textgenerator – sondern eine **regelbasierte,
templategetriebene, auditierbare Dokumentations-Engine**.

---

## Was ist assist2?

Compliance-Dokumentation entsteht heute durch manuelle, fehleranfällige Arbeit:
Consultants lesen User Stories, leiten Prozesse ab, füllen Templates aus,
prüfen gegen NIS2/KRITIS-Anforderungen und pflegen Draw.io-Diagramme.

assist2 automatisiert genau diesen Prozess – mit einem entscheidenden Unterschied
zu generischen KI-Tools: **Das System erfindet keine Informationen.**
Fehlende Daten werden explizit markiert, Compliance wird nie automatisch bestätigt,
jede Ableitung ist auf ihre Quelle zurückführbar.

---

## Kernfunktionen

### Prozessdokumentation
Generiert vollständige, strukturierte Dokumente aus Roheingaben:
- **SOP** (Standard Operating Procedures)
- **Runbooks**
- **Incident Response Playbooks**
- **Change-Management-Prozesse**
- **Backup & Recovery Prozesse**

Jedes Dokument enthält: Zweck, Scope, Rollen, Ablauf, Ausnahmen,
Risiken, Controls, Abhängigkeiten und explizit markierte offene Punkte.

### Template Engine
Regelbasierte Templates mit Pflichtkapiteln, optionalen Sektionen
und Qualitätsregeln. Templates sind als YAML-Dateien versionierbar.

### Draw.io Diagramm-Generierung
Automatische Erzeugung von:
- Flowcharts
- Swimlane-Diagrammen (rollenbasiert)
- Entscheidungsbäumen
- Recovery-Flows
- Dependency Graphs

Output: draw.io XML (mxGraphModel), optional SVG/PNG.

### Compliance Layer (NIS2 / KRITIS)
Mapping von Prozessen auf regulatorische Anforderungen mit
ehrlicher Bewertung: **erfüllt / teilweise / nicht vorhanden** –
niemals automatische Compliance-Bestätigung.

### Business Continuity Management (BCM)
- Business Impact Analysis (RTO, RPO, MTD)
- Risikoanalyse mit Wahrscheinlichkeit und Impact
- Recovery-Strategien (Cold / Warm / Hot)
- Notfallprozesse und Kommunikationspläne
- Testszenarien für Failover und Recovery

### Audit & Traceability
Jeder generierte Abschnitt trägt:
- Quell-Referenz (Story / Requirement)
- Ableitungsstatus: `DIRECT` | `INTERPRETED` | `OPEN`
- Confidence Level (0.0 – 1.0)

### Jira & Confluence Integration (MVP)
- User Stories und Epics direkt aus Jira importieren
- Fertige Dokumente nach Confluence exportieren
- Bidirektionales Linking zwischen Dokumenten und Tickets

---

## Qualitätsregeln (nicht verhandelbar)

Das System darf **NICHT**:
- Inhalte halluzinieren
- fehlende Daten erfinden
- Compliance automatisch bestätigen

Stattdessen:
- fehlende Informationen als `[OFFEN]` markieren
- Annahmen explizit kennzeichnen
- offene Punkte in dediziertem Abschnitt ausweisen

---

## Zielgruppe

| Zielgruppe | Anwendungsfall |
|---|---|
| IT-Security-Teams | NIS2/KRITIS-Dokumentation automatisieren |
| BCM-Verantwortliche | BIA, Recovery-Pläne, Testszenarien erstellen |
| Compliance-Officers | Audit-fähige Nachweise erzeugen |
| IT-Betrieb | SOPs und Runbooks aus Ticket-Daten generieren |
| Berater | Kundendokumentation strukturiert und nachvollziehbar liefern |

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI |
| LLM-Proxy | LiteLLM (Provider-agnostisch: Claude, OpenAI, Azure, lokal) |
| KI-Primärmodell | Anthropic Claude (claude-sonnet-4-6) |
| Datenbank | PostgreSQL 16 + pgvector |
| Migrationen | Alembic |
| ORM | SQLAlchemy 2.0 |
| Task Queue | Celery + Redis |
| Frontend | Next.js 15 (App Router), shadcn/ui, Tailwind CSS |
| Diagramme | draw.io XML-Generierung (mxGraphModel) |
| Export | Markdown, DOCX (python-docx), PDF (WeasyPrint) |
| Integrationen | Jira REST API, Confluence REST API |
| Containerisierung | Docker / Docker Compose |
| Tests | pytest, httpx |
| CI/CD | GitHub Actions |

---

## MVP Scope

Phase 1 (implementiert zuerst):
- SOP Generator
- Runbook Generator
- Draw.io Export (Flowchart + Swimlane)
- Basis NIS2 Mapping
- Einfache BIA (RTO/RPO)
- Markdown + DOCX Export
- Jira Import / Confluence Export
- Offene Punkte Kennzeichnung

---

## Schnellstart

```bash
git clone https://github.com/fichtlandsachs/assist2.git
cd assist2
cp .env.example .env
# LITELLM_API_BASE, ANTHROPIC_API_KEY, DB-URL,
# JIRA_URL, JIRA_TOKEN, CONFLUENCE_URL eintragen
docker compose up
```

---

## Projektstruktur

```
assist2/
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI Routen
│   │   ├── engine/
│   │   │   ├── normalizer/   # Input Normalisierung
│   │   │   ├── templates/    # Template Engine + YAML-Templates
│   │   │   ├── generators/   # SOP, Runbook, Incident Generator
│   │   │   ├── compliance/   # NIS2/KRITIS Mapping Engine
│   │   │   ├── bcm/          # BIA, Risiko, Recovery Engine
│   │   │   └── diagrams/     # Draw.io XML Generator
│   │   ├── integrations/
│   │   │   ├── jira/         # Jira REST Client
│   │   │   └── confluence/   # Confluence REST Client
│   │   ├── models/           # SQLAlchemy Modelle
│   │   ├── schemas/          # Pydantic Schemas
│   │   └── audit/            # Traceability Layer
│   ├── alembic/              # Datenbankmigrationen
│   └── tests/
├── frontend/
│   ├── app/                  # Next.js App Router
│   └── components/
│       └── ui/               # shadcn/ui Komponenten
├── templates/                # YAML Template-Definitionen
├── docker-compose.yml
└── .env.example
```

---

## Nicht-Ziele

- Freie Textgenerierung ohne Struktur
- Ungeprüfte technische Aussagen
- Fehlende Traceability
- „Fake Compliance"

---

## Lizenz

MIT
