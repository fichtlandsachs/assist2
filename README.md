# assist2

Ein KI-gestütztes Assistenzsystem der zweiten Generation – modular, erweiterbar und produktionsreif.

## Projektbeschreibung

**assist2** ist eine moderne, KI-basierte Assistenzplattform, die Nutzern und Entwicklern ermöglicht, komplexe Aufgaben über eine einheitliche Schnittstelle zu automatisieren und zu delegieren. Das System baut auf den Erfahrungen des Vorgängerprojekts auf und löst dessen Limitierungen durch eine saubere Komponentenarchitektur, austauschbare KI-Provider und eine robuste Aufgabenverwaltung.

### Kernfunktionen

- **Aufgaben-Orchestrierung** – Zerlegung komplexer Anfragen in atomare, sequenzielle oder parallele Teilaufgaben
- **Multi-Provider-KI** – Unterstützung für Anthropic Claude, OpenAI und lokale Modelle über einen einheitlichen Adapter
- **Tool-System** – Erweiterbare Werkzeuge (Dateizugriff, Web-Suche, Code-Ausführung, API-Calls)
- **Persistente Kontexte** – Sitzungs- und Langzeitgedächtnis über eine Vektordatenbank
- **REST- & WebSocket-API** – Für die Integration in bestehende Workflows und UIs
- **Webhook-Support** – Reaktion auf externe Ereignisse (GitHub, Slack, CI/CD-Pipelines)

### Zielgruppe

- Entwicklerinnen und Entwickler, die repetitive Aufgaben automatisieren wollen
- Teams, die einen internen KI-Assistenten betreiben möchten
- Unternehmen, die KI-Workflows in bestehende Systeme integrieren

---

## Schnellstart

```bash
# Repository klonen
git clone https://github.com/fichtlandsachs/assist2.git
cd assist2

# Abhängigkeiten installieren
npm install

# Umgebungsvariablen konfigurieren
cp .env.example .env
# .env anpassen (API-Keys, Datenbankverbindung, etc.)

# Entwicklungsserver starten
npm run dev
```

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| Laufzeit | Node.js 22 (TypeScript) |
| API-Server | Fastify |
| KI-Integration | Anthropic SDK, OpenAI SDK |
| Datenbank | PostgreSQL (strukturierte Daten) |
| Vektordatenbank | pgvector / Chroma |
| Cache | Redis |
| Queue | BullMQ (Redis-backed) |
| Containerisierung | Docker / Docker Compose |
| Tests | Vitest, Supertest |
| CI/CD | GitHub Actions |

---

## Projektstruktur

```
assist2/
├── src/
│   ├── api/            # HTTP- und WebSocket-Endpunkte
│   ├── agents/         # Agenten-Logik und Orchestrierung
│   ├── tools/          # Tool-Implementierungen
│   ├── providers/      # KI-Provider-Adapter
│   ├── memory/         # Kontext- und Gedächtnisverwaltung
│   ├── queue/          # Aufgabenwarteschlange
│   ├── db/             # Datenbankmodelle und Migrationen
│   └── config/         # Konfigurationsverwaltung
├── tests/
├── docker/
├── docs/
├── ARCHITECTURE.md
└── README.md
```

---

## Lizenz

MIT – siehe [LICENSE](LICENSE)
