# Architektur – assist2

## Leitgedanke

assist2 ist eine **regelbasierte Dokumentations-Engine**, keine generative KI-Anwendung.
Der Unterschied ist architektonisch fundamental:

- Generative KI-Anwendung: LLM → Freitext → Nutzer
- assist2: Input → Normalisierung → Template-Matching → Regelprüfung → LLM (strukturiert) → Audit → Output

Das LLM ist ein **gesteuertes Werkzeug**, nicht der Entscheider.
Jede Ausgabe ist auf ihren Input zurückführbar oder explizit als offen markiert.

---

## Systemübersicht

```
┌─────────────────────────────────────────────────────────────────┐
│                          Clients                                │
│    Next.js Web-App  │  REST API  │  Jira Webhook               │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS
┌───────────────────────────▼─────────────────────────────────────┐
│                       FastAPI Backend                           │
│           Auth (JWT/API-Key) │ Routing │ Validation             │
└──────┬──────────────────────┬──────────────────────┬────────────┘
       │                      │                      │
┌──────▼──────┐   ┌───────────▼──────────┐  ┌───────▼───────────┐
│ Integration │   │   Dokumentations-    │  │  Compliance &     │
│   Layer     │   │      Engine          │  │  BCM Engine       │
│             │   │                      │  │                   │
│ Jira REST   │   │  Input Normalizer    │  │  NIS2 Mapper      │
│ Confluence  │   │  Template Engine     │  │  KRITIS Mapper    │
│ REST        │   │  SOP Generator       │  │  BIA Engine       │
└──────┬──────┘   │  Runbook Generator   │  │  Risiko Engine    │
       │          │  Diagram Generator   │  │  Recovery Engine  │
       │          │  Output Renderer     │  └───────┬───────────┘
       │          └───────────┬──────────┘          │
       │                      │                     │
┌──────▼──────────────────────▼─────────────────────▼────────────┐
│                         LiteLLM Proxy                          │
│         Provider-Router: Claude │ OpenAI │ Azure │ Lokal       │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│                      Persistenz-Schicht                        │
│  PostgreSQL + pgvector   │   Redis (Cache + Celery Queue)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Module im Detail

### 1. Input Normalizer

**Zweck:** Beliebige Eingaben (User Stories, Epics, Freitext, Jira-Tickets)
in ein einheitliches `ProcessModel` überführen.

**Ablauf:**
```
Rohtext / Jira-Ticket
        │
        ▼
Vorverarbeitung (Bereinigung, Spracherkennung)
        │
        ▼
LiteLLM → Claude (strukturierter Prompt mit JSON-Schema)
        │
        ▼
Validierung gegen ProcessModel (Pydantic)
        │
        ├── Fehlende Pflichtfelder → open_points[] ergänzen
        └── Confidence < 0.6      → derivation_status = INTERPRETED
```

**ProcessModel (Pydantic):**
```python
class ProcessModel(BaseModel):
    process_name: str
    actors: list[Actor]
    steps: list[ProcessStep]
    decisions: list[Decision]
    inputs: list[str]
    outputs: list[str]
    risks: list[Risk]
    controls: list[Control]
    dependencies: list[Dependency]
    open_points: list[OpenPoint]   # fehlende Infos, nie erfunden
    sources: list[SourceRef]       # Quell-Referenzen je Feld
```

**Kritische Regel im LLM-Prompt:**
```
Du analysierst strukturierte Eingaben und extrahierst
Prozessinformationen. Regel: Erfinde KEINE Informationen.
Wenn ein Pflichtfeld nicht aus dem Input ableitbar ist,
erzeuge einen open_point mit required=true.
Antworte ausschließlich im vorgegebenen JSON-Schema.
```

---

### 2. Template Engine

**Zweck:** YAML-basierte Templates laden, gegen ProcessModel validieren,
Sektionen befüllen, fehlende Pflichtkapitel markieren.

**Template-Format (YAML):**
```yaml
id: sop_v1
name: Standard Operating Procedure
version: "1.0"
required_sections:
  - purpose
  - scope
  - roles
  - process_flow
  - exceptions
  - risks
  - controls
  - compliance_mapping
  - open_points
optional_sections:
  - background
  - related_documents
rules:
  no_hallucination: true
  mark_missing: true
  require_source_refs: true
  min_confidence: 0.5
section_prompts:
  purpose: "Leite den Zweck des Prozesses aus {process_name} und {outputs} ab."
  risks: "Liste alle Risiken aus {risks}. Erfinde keine zusätzlichen."
```

**Starter-Templates (MVP):**
- `sop_v1.yaml` – Standard Operating Procedure
- `runbook_v1.yaml` – Technisches Runbook
- `incident_v1.yaml` – Incident Response Playbook

---

### 3. Dokumentations-Engine (Orchestrator)

**Ablauf einer Dokumentgenerierung:**
```
POST /api/v1/documents/generate
        │
        ▼
1. Input Normalizer → ProcessModel
        │
        ▼
2. Template laden + Validierung
   └── Fehlende Pflichtfelder? → open_points ergänzen
        │
        ▼
3. Sektion für Sektion generieren (LiteLLM)
   └── Jede Sektion: source_ref + confidence + derivation_status
        │
        ▼
4. Compliance Engine → ComplianceMapping
        │
        ▼
5. BCM Engine → BCMRecord (wenn bcm_required=true)
        │
        ▼
6. Diagram Generator → draw.io XML
        │
        ▼
7. Audit Layer → AuditEntries persistieren
        │
        ▼
8. Output Renderer → Markdown / DOCX / PDF
        │
        ▼
9. Optional: Confluence Export
```

---

### 4. LiteLLM Proxy

**Warum LiteLLM:**
- Einheitliches API-Interface für alle LLM-Provider
- Provider-Wechsel ohne Code-Änderung (nur `.env`)
- Retry-Logik, Fallback-Provider, Rate-Limiting
- Lokale Modelle (Ollama) über gleiche Schnittstelle

**Konfiguration:**
```yaml
# litellm_config.yaml
model_list:
  - model_name: primary
    litellm_params:
      model: anthropic/claude-sonnet-4-6
      api_key: os.environ/ANTHROPIC_API_KEY

  - model_name: fallback
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY

  - model_name: local
    litellm_params:
      model: ollama/llama3.2
      api_base: http://localhost:11434

router_settings:
  fallbacks: [{"primary": ["fallback"]}]
  num_retries: 3
```

**Python-Client:**
```python
import litellm

response = await litellm.acompletion(
    model="primary",
    messages=[...],
    response_format={"type": "json_object"},
    temperature=0.1,   # niedrig für deterministische Ausgaben
)
```

---

### 5. Compliance Engine

**Aufgabe:** Mapping von ProcessModel auf NIS2/KRITIS-Anforderungen.

**Bewertungslogik:**
```
Für jede Compliance-Anforderung:
  1. Suche in controls[] und steps[] nach Evidence
  2. Evidence gefunden + vollständig → MET
  3. Evidence gefunden + lückenhaft  → PARTIAL
  4. Keine Evidence                  → MISSING

NIEMALS automatisch MET setzen ohne explizite Evidence.
```

**NIS2-Bereiche (MVP):**
- Incident Handling (Art. 21 Abs. 2b)
- Risk Management (Art. 21 Abs. 2a)
- Access Control
- Business Continuity (Art. 21 Abs. 2c)
- Supply Chain Security (Art. 21 Abs. 2d)

**Output:**
```python
class ComplianceResult(BaseModel):
    framework: str               # "NIS2" | "KRITIS"
    coverage_score: float        # 0.0 – 1.0
    mappings: list[ComplianceMapping]
    missing_controls: list[str]
    audit_hints: list[str]
```

---

### 6. BCM Engine

**BIA-Berechnung:**
```python
class BIAResult(BaseModel):
    rto_minutes: int             # Recovery Time Objective
    rpo_minutes: int             # Recovery Point Objective
    mtd_minutes: int             # Maximum Tolerable Downtime
    operational_impact: str
    financial_impact: str
    regulatory_impact: str
    recovery_strategy: str       # "COLD" | "WARM" | "HOT"
    open_points: list[OpenPoint] # fehlende BIA-Daten
```

**Recovery-Flow-Generierung:**
```
Incident erkannt
      │
      ▼
Diagnose (automatisch generierter Schritt aus steps[])
      │
      ▼
Recovery-Strategie aktivieren (aus recovery_strategies[])
      │
      ▼
Verifikation (aus controls[])
      │
      ▼
Kommunikation (aus Kommunikationsplan)
```

---

### 7. Diagram Generator

**Mapping ProcessModel → draw.io XML:**

| ProcessModel-Element | draw.io-Element |
|---|---|
| `steps[]` | Rechteck-Node |
| `decisions[]` | Rauten-Node (Diamond) |
| `actors[]` | Swimlane |
| `dependencies[]` | Edge mit Label |
| `open_points[]` | Roter Rahmen, Warn-Icon |

**Ausgabe:**
```xml
<mxGraphModel>
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    <!-- Swimlane pro Actor -->
    <mxCell id="actor_1" value="IT-Operations" style="swimlane;" .../>
    <!-- Step als Rechteck -->
    <mxCell id="step_1" value="Incident erkennen" style="rounded=1;" .../>
    <!-- Decision als Raute -->
    <mxCell id="dec_1" value="Kritisch?" style="rhombus;" .../>
    <!-- Edge -->
    <mxCell id="edge_1" source="step_1" target="dec_1" .../>
  </root>
</mxGraphModel>
```

---

### 8. Jira & Confluence Integration

**Jira (Import):**
```python
# Epics und Stories importieren
GET /rest/api/3/search?jql=project=XY AND issuetype in (Epic, Story)

# Mapping: Jira Issue → ProcessModel Input
{
    "summary":     → process_name
    "description": → Rohtext für Normalizer
    "assignee":    → actors[]
    "labels":      → tags für Compliance-Mapping
    "components":  → dependencies[]
}
```

**Confluence (Export):**
```python
# Fertige SOP als Confluence-Seite anlegen
POST /rest/api/content
{
    "type": "page",
    "title": "SOP: {process_name}",
    "space": {"key": "COMPLIANCE"},
    "body": {
        "storage": {
            "value": "<html>...</html>",  # aus Markdown konvertiert
            "representation": "storage"
        }
    }
}
```

---

## Datenmodell (PostgreSQL)

```sql
-- Kern-Dokument
CREATE TABLE documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type        VARCHAR(50) NOT NULL,   -- 'sop'|'runbook'|'incident'
    template_id VARCHAR(50) NOT NULL,
    version     VARCHAR(20) NOT NULL DEFAULT '1.0',
    status      VARCHAR(20) NOT NULL DEFAULT 'draft',
                                        -- draft|review|approved
    content     JSONB NOT NULL,
    sources     JSONB NOT NULL DEFAULT '[]',
    jira_key    VARCHAR(50),            -- z.B. "PROJ-123"
    confluence_id VARCHAR(50),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- Templates
CREATE TABLE templates (
    id          VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    schema      JSONB NOT NULL,
    rules       JSONB NOT NULL,
    version     VARCHAR(20) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Prozessmodell (normalisierter Input)
CREATE TABLE processes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id),
    name            VARCHAR(200) NOT NULL,
    actors          JSONB NOT NULL DEFAULT '[]',
    steps           JSONB NOT NULL DEFAULT '[]',
    decisions       JSONB NOT NULL DEFAULT '[]',
    dependencies    JSONB NOT NULL DEFAULT '[]',
    open_points     JSONB NOT NULL DEFAULT '[]'
);

-- BCM-Daten
CREATE TABLE bcm_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id          UUID REFERENCES processes(id),
    rto_minutes         INTEGER,
    rpo_minutes         INTEGER,
    mtd_minutes         INTEGER,
    operational_impact  TEXT,
    financial_impact    TEXT,
    regulatory_impact   TEXT,
    recovery_strategy   VARCHAR(10),   -- COLD|WARM|HOT
    risks               JSONB NOT NULL DEFAULT '[]',
    recovery_strategies JSONB NOT NULL DEFAULT '[]',
    open_points         JSONB NOT NULL DEFAULT '[]'
);

-- Compliance-Mapping
CREATE TABLE compliance_mappings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id),
    framework       VARCHAR(20) NOT NULL,  -- NIS2|KRITIS
    requirement     VARCHAR(200) NOT NULL,
    status          VARCHAR(10) NOT NULL,  -- MET|PARTIAL|MISSING
    evidence        TEXT,
    gaps            JSONB NOT NULL DEFAULT '[]'
);

-- Audit & Traceability
CREATE TABLE audit_entries (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID REFERENCES documents(id),
    section             VARCHAR(100) NOT NULL,
    source              TEXT NOT NULL,
    derivation_status   VARCHAR(15) NOT NULL,  -- DIRECT|INTERPRETED|OPEN
    confidence          NUMERIC(3,2) NOT NULL, -- 0.00 – 1.00
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- Diagramme
CREATE TABLE diagrams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    type        VARCHAR(30) NOT NULL,  -- flowchart|swimlane|dependency
    drawio_xml  TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## API-Design

```
# Dokument-Generierung
POST   /api/v1/documents/generate
       Body: { input: str, template_id: str, jira_key?: str,
               bcm_required?: bool, compliance_frameworks?: list[str] }
       → { document_id, status, open_points_count, markdown_preview }

GET    /api/v1/documents/{id}
       → Vollständiges Dokument mit AuditEntries

GET    /api/v1/documents/{id}/gaps
       → Nur offene Punkte + fehlende Compliance-Anforderungen

GET    /api/v1/documents/{id}/diagram
       → draw.io XML + optional SVG

POST   /api/v1/documents/{id}/export/confluence
       → Dokument nach Confluence pushen

# Templates
GET    /api/v1/templates
POST   /api/v1/templates
PUT    /api/v1/templates/{id}

# Jira Import
GET    /api/v1/jira/projects
GET    /api/v1/jira/issues?jql=...
POST   /api/v1/jira/import/{issue_key}
       → normalisiert Issue, legt Document an

# Compliance
GET    /api/v1/documents/{id}/compliance
       → Coverage Score + fehlende Controls

# BCM
GET    /api/v1/documents/{id}/bcm
       → BIA + Recovery-Strategien + Risiken
```

---

## Implementierungs-Roadmap

### Phase 1 – Fundament
1. Projektstruktur + Docker Compose
2. PostgreSQL Schema + Alembic Migrationen
3. LiteLLM Proxy konfigurieren
4. Input Normalizer (Pydantic + LiteLLM)
5. Template Engine (YAML-Loader + Validator)
6. SOP Generator (Markdown-Output)
7. FastAPI Basis-Routen

### Phase 2 – Struktur & Visualisierung
8. Runbook + Incident Generator
9. Draw.io Generator (Flowchart + Swimlane)
10. DOCX-Export (python-docx)
11. PDF-Export (WeasyPrint)

### Phase 3 – Compliance & BCM
12. NIS2 Mapping Engine
13. BCM Engine (BIA + Risiko + Recovery)
14. Dependency Graph

### Phase 4 – Integrationen
15. Jira REST Client (Import)
16. Confluence REST Client (Export)
17. Webhook-Receiver (Jira-Trigger)

### Phase 5 – Qualität & Governance
18. Audit Traceability Layer (vollständig)
19. Review-Workflow (draft → review → approved)
20. Versionierung + Diff-Ansicht

---

## Architekturentscheidungen (ADRs)

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | Python statt Node.js | Stärkeres Ökosystem für Dokumenten-Verarbeitung (python-docx, WeasyPrint, PyMuPDF) |
| 2 | LiteLLM als Proxy | Provider-Unabhängigkeit; Wechsel von Claude auf OpenAI oder lokales Modell ohne Code-Änderung |
| 3 | Niedriges Temperature (0.1) | Deterministische, strukturierte Ausgaben; weniger Halluzinationen |
| 4 | YAML-Templates | Versionierbar in Git, von Compliance-Officers pflegbar ohne Code-Kenntnisse |
| 5 | Jira/Confluence im MVP | Kern-Workflow der Zielgruppe: Anforderungen kommen aus Jira, Ergebnisse gehen nach Confluence |
| 6 | JSONB für flexible Felder | Prozessmodelle variieren stark; JSONB ermöglicht Schema-Evolution ohne Migrationen |
| 7 | Celery für Generierung | Dokumentenerstellung dauert 15–60s; asynchron per Task Queue verhindert API-Timeouts |
