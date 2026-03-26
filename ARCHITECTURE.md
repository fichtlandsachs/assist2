# Architektur – assist2

## Überblick

assist2 folgt einer **Schichtenarchitektur** mit klar getrennten Verantwortlichkeiten. Die Kernidee ist die strikte Trennung zwischen:

1. **Eingangskanal** (API, Webhooks, CLI)
2. **Orchestrierung** (Agenten, Aufgabenverwaltung)
3. **Ausführung** (Tools, KI-Provider)
4. **Persistenz** (Datenbank, Vektorspeicher, Cache)

```
┌──────────────────────────────────────────────────────────────┐
│                        Clients                               │
│         Web-UI │ CLI │ externe Systeme (Webhooks)            │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTPS / WSS
┌────────────────────────▼─────────────────────────────────────┐
│                      API-Schicht                             │
│              Fastify  (REST + WebSocket)                     │
│   Authentifizierung │ Rate-Limiting │ Request-Validation     │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│                 Orchestrierungs-Schicht                      │
│                                                              │
│  ┌─────────────────┐        ┌────────────────────────────┐  │
│  │  Task-Manager   │◄──────►│  Agent-Runtime             │  │
│  │  (BullMQ)       │        │  (Planen, Ausführen,       │  │
│  └─────────────────┘        │   Reflektieren)            │  │
│                             └────────────────────────────┘  │
└──────────────┬──────────────────────────┬────────────────────┘
               │                          │
┌──────────────▼──────────┐  ┌────────────▼───────────────────┐
│    KI-Provider-Adapter  │  │        Tool-Registry           │
│                         │  │                                │
│  ┌──────────────────┐   │  │  ┌──────────┐ ┌────────────┐  │
│  │  Anthropic Claude│   │  │  │ WebSearch│ │ FileSystem │  │
│  └──────────────────┘   │  │  └──────────┘ └────────────┘  │
│  ┌──────────────────┐   │  │  ┌──────────┐ ┌────────────┐  │
│  │  OpenAI GPT      │   │  │  │ CodeExec │ │ HTTP/API   │  │
│  └──────────────────┘   │  │  └──────────┘ └────────────┘  │
│  ┌──────────────────┐   │  │  ┌──────────────────────────┐ │
│  │  Lokales Modell  │   │  │  │  (erweiterbar via Plugin) │ │
│  └──────────────────┘   │  │  └──────────────────────────┘ │
└─────────────────────────┘  └────────────────────────────────┘
               │                          │
┌──────────────▼──────────────────────────▼────────────────────┐
│                      Persistenz-Schicht                      │
│                                                              │
│  PostgreSQL          pgvector / Chroma        Redis          │
│  (Aufgaben,          (Embeddings,             (Cache,        │
│   Sessions,           Langzeitgedächtnis)      Queue)        │
│   Audit-Log)                                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## Komponenten im Detail

### 1. API-Schicht

**Technologie:** Fastify + `@fastify/websocket`

- **REST-Endpunkte** für synchrone Anfragen (kurze Aufgaben, Statusabfragen)
- **WebSocket-Endpunkte** für Streaming-Antworten und Echtzeit-Updates
- **Middleware:** JWT-Authentifizierung, API-Key-Support, Zod-basierte Schema-Validierung
- **Webhook-Receiver:** Verarbeitet eingehende Events von GitHub, Slack u.a.

```
POST   /v1/tasks          – Neue Aufgabe erstellen
GET    /v1/tasks/:id      – Aufgabenstatus abfragen
DELETE /v1/tasks/:id      – Aufgabe abbrechen
WS     /v1/stream         – Streaming-Kanal
POST   /v1/webhooks/:src  – Webhook-Eingang
```

---

### 2. Orchestrierungs-Schicht

#### Task-Manager (BullMQ)

- Nimmt Aufgaben entgegen und legt sie in eine persistente Redis-Queue
- Unterstützt **Prioritäten**, **Wiederholungslogik** und **Timeouts**
- Parallele Worker verarbeiten Aufgaben nebenläufig

#### Agent-Runtime

Der Kern von assist2. Implementiert den **ReAct-Loop** (Reason → Act → Observe):

```
┌─────────────────────────────────────────┐
│              ReAct-Loop                 │
│                                         │
│  1. Aufgabe analysieren (Reason)        │
│  2. Tool oder Antwort wählen (Act)      │
│  3. Ergebnis auswerten (Observe)        │
│  4. Schritt 1 wiederholen oder          │
│     Aufgabe abschließen                 │
└─────────────────────────────────────────┘
```

- **Planungsmodul:** Zerlegt komplexe Aufgaben in Teilschritte (Chain-of-Thought)
- **Reflexionsmodul:** Erkennt Fehler und passt den Plan an
- **Parallelisierung:** Unabhängige Teilaufgaben werden gleichzeitig ausgeführt

---

### 3. KI-Provider-Adapter

Ein einheitliches Interface abstrahiert alle KI-Backends:

```typescript
interface AIProvider {
  complete(prompt: Message[], options: CompletionOptions): Promise<CompletionResult>;
  stream(prompt: Message[], options: CompletionOptions): AsyncIterable<string>;
  embed(text: string): Promise<number[]>;
}
```

**Implementierungen:**
- `AnthropicProvider` – Claude 3.x / Claude 4.x via Anthropic SDK
- `OpenAIProvider` – GPT-4o, o1 via OpenAI SDK
- `LocalProvider` – Lokale Modelle via Ollama-API

Der Provider wird pro Aufgabe oder global konfiguriert.

---

### 4. Tool-Registry

Tools sind **eigenständige, testbare Module** mit einem standardisierten Interface:

```typescript
interface Tool {
  name: string;
  description: string;
  inputSchema: ZodSchema;
  execute(input: unknown, context: ToolContext): Promise<ToolResult>;
}
```

| Tool | Funktion |
|---|---|
| `web_search` | DuckDuckGo / SerpAPI-Suche |
| `read_file` | Lokale Dateien lesen |
| `write_file` | Dateien erstellen / bearbeiten |
| `run_code` | Python/JS in Sandbox ausführen |
| `http_request` | Externe APIs aufrufen |
| `github_*` | GitHub-Operationen (Issues, PRs, Code) |

Neue Tools können als npm-Pakete eingebunden werden (Plugin-System).

---

### 5. Memory-System

Zwei Gedächtnisebenen:

| Ebene | Speicher | Zweck |
|---|---|---|
| **Kurzzeitgedächtnis** | In-Memory / Redis | Aktueller Konversationsverlauf |
| **Langzeitgedächtnis** | pgvector / Chroma | Vergangene Sitzungen, Wissensbasis |

- Inhalte werden beim Speichern automatisch **vektorisiert** (Embeddings)
- Bei neuen Anfragen werden semantisch ähnliche Erinnerungen abgerufen (RAG)

---

### 6. Persistenz-Schicht

#### PostgreSQL
- Aufgaben, Sitzungen, Nutzerkonten, Audit-Log
- Schema-Migrationen mit `node-pg-migrate`

#### pgvector / Chroma
- Speicherung und Suche von Embeddings
- Semantische Ähnlichkeitssuche (cosine similarity)

#### Redis
- Session-Cache
- BullMQ-Queue-Backend
- Rate-Limiting-Counter

---

## Datenfluss – Beispiel

```
Nutzer sendet: "Erstelle ein GitHub-Issue für Bug #42"

1. API nimmt POST /v1/tasks entgegen
2. Task-Manager legt Aufgabe in Queue
3. Worker startet Agent-Runtime
4. Agent analysiert Aufgabe (Reason)
5. Agent wählt Tool: github_create_issue (Act)
6. Tool führt GitHub-API-Call aus
7. Agent wertet Ergebnis aus (Observe)
8. Aufgabe abgeschlossen → Antwort an Nutzer
```

---

## Sicherheit

- Alle externen Eingaben werden mit **Zod** validiert
- Code-Ausführung in **isolierten Sandbox-Containern** (gVisor / Firecracker)
- Secrets werden ausschließlich über Umgebungsvariablen übergeben (kein Hardcoding)
- **Audit-Log** aller Aktionen in PostgreSQL
- Rate-Limiting pro API-Key und IP
- JWT mit kurzer Laufzeit + Refresh-Token-Rotation

---

## Deployment

```
assist2/
├── docker/
│   ├── Dockerfile          # Multi-stage Build
│   ├── docker-compose.yml  # Lokale Entwicklungsumgebung
│   └── docker-compose.prod.yml
└── .github/
    └── workflows/
        ├── ci.yml          # Tests + Lint bei jedem Push
        └── deploy.yml      # Deploy auf Merge in main
```

### Empfohlene Produktionsumgebung

```
[Load Balancer]
      │
  ┌───┴────┐
  │ App x2 │  (assist2-Container, horizontal skalierbar)
  └───┬────┘
      │
  ┌───┴──────────────────────┐
  │  PostgreSQL  │  Redis    │
  └──────────────────────────┘
```

---

## Entscheidungsprotokoll (ADRs)

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | Fastify statt Express | 3× höherer Durchsatz, natives TypeScript-Support |
| 2 | BullMQ statt einfacher Async-Queue | Persistenz, Retry-Logik, Monitoring out-of-the-box |
| 3 | pgvector statt separater Vektordatenbank | Weniger Infrastruktur, SQL-Joins über Daten und Vektoren möglich |
| 4 | Zod für Schemas | Laufzeit-Validierung + TypeScript-Typen aus einer Quelle |
