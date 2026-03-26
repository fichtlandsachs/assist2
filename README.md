# assist2

Eine KI-gestützte Plattform für generatives Lernen und maximale persönliche Unterstützung.

---

## Was ist assist2?

**assist2** begleitet Menschen in Lern- und Entwicklungsprozessen – individuell, adaptiv
und kontinuierlich. Das System versteht nicht nur Aufgaben, sondern auch die Person dahinter:
ihren Wissensstand, ihre Lernweise, ihre Ziele und ihren Fortschritt.

Anders als klassische Assistenzsysteme liegt der Schwerpunkt nicht auf der einmaligen
Beantwortung von Fragen, sondern auf dem **Aufbau nachhaltigen Verständnisses** durch
generative Lernprozesse. assist2 begleitet aktiv, erkennt Wissenslücken, passt Inhalte
an und entwickelt sich gemeinsam mit dem Lernenden weiter.

---

## Leitprinzipien

### 1. Prozessorientierung vor Ergebnisorientierung
Nicht die schnelle Antwort steht im Vordergrund, sondern der Weg dorthin.
assist2 führt Lernende durch strukturierte Prozesse: Verstehen → Anwenden →
Reflektieren → Vertiefen. Jede Interaktion ist Teil einer langen Lernkette.

### 2. Generatives Lernen
Wissen entsteht durch aktive Auseinandersetzung. assist2 stellt Fragen statt
Antworten zu liefern, fordert zur Eigenproduktion auf, gibt gezielte Impulse
und generiert maßgeschneiderte Übungen, Szenarien und Erklärungen – individuell
für jede Person und jeden Kontext.

### 3. Maximale persönliche Unterstützung
Das System kennt seinen Nutzer. Es führt ein dynamisches Lernprofil, erkennt
Muster (Motivationstiefs, Blockaden, Stärken) und passt Ton, Tempo und
Schwierigkeitsgrad jederzeit an. Unterstützung bedeutet hier: zur richtigen Zeit
das Richtige – weder zu viel noch zu wenig.

---

## Kernfunktionen

### Adaptiver Lernpfad
- Automatische Einschätzung des aktuellen Wissensstands (Onboarding-Diagnose)
- Dynamische Anpassung von Inhalten, Tempo und Schwierigkeitsgrad
- Lernziele werden gemeinsam definiert und laufend überprüft
- Verzweigungen im Lernpfad basierend auf Antwortqualität und Verhalten

### Generative Inhaltsproduktion
- Aufgaben, Übungen und Erklärungen werden in Echtzeit erzeugt – nie von der Stange
- Anpassung an Fachgebiet, Sprachniveau, Lernstil und verfügbare Zeit
- Szenario-basiertes Lernen: realitätsnahe Situationen statt abstrakter Theorie
- Lückentexte, Quizze, Reflexionsfragen, Fallstudien – alle generativ erstellt

### Persönliches Lernprofil
- Langzeitgedächtnis über alle Sitzungen hinweg
- Tracking von Stärken, Schwächen, Interessen und Lernhistorie
- Erkennung von Wiederholungsbedarfen (Spaced Repetition)
- Sichtbarmachen des eigenen Fortschritts (Lernkurven, Meilensteine)

### Aktive Begleitung & Coaching
- Proaktive Erinnerungen und Lernimpulse
- Motivation durch Anerkennung von Fortschritten
- Erkennung von Frustration oder Stagnation → automatische Kursanpassung
- Reflexionsgespräche nach abgeschlossenen Einheiten

### Prozess-Transparenz
- Jeder Schritt im Lernprozess ist nachvollziehbar dokumentiert
- Lernende sehen, warum welche Inhalte vorgeschlagen werden
- Lehrende / Coaches erhalten Einblick in Lernverläufe und können eingreifen

---

## Zielgruppe

| Zielgruppe | Anwendungsfall |
|---|---|
| Einzelpersonen | Selbstgesteuertes Lernen eines neuen Fachgebiets |
| Berufseinsteiger | Onboarding und Kompetenzaufbau im Job |
| Unternehmen | Mitarbeiterentwicklung, interne Weiterbildung |
| Bildungseinrichtungen | Digitale Lernbegleitung für Schüler/Studierende |
| Coaches & Trainer | KI-gestützte Begleitung ihrer Klientel |

---

## Technologie-Stack

| Schicht | Technologie |
|---|---|
| Laufzeit | Node.js 22 (TypeScript) |
| API-Server | Fastify |
| KI-Core | Anthropic Claude (claude-opus-4-6 / claude-sonnet-4-6) |
| Lernprofil-Speicher | PostgreSQL + pgvector |
| Spaced-Repetition-Engine | Eigene Implementierung (SM-2-Algorithmus) |
| Cache & Sessions | Redis |
| Hintergrundprozesse | BullMQ |
| Echtzeit-Kommunikation | WebSocket (Streaming) |
| Containerisierung | Docker / Docker Compose |
| Tests | Vitest |
| CI/CD | GitHub Actions |

---

## Schnellstart

```bash
git clone https://github.com/fichtlandsachs/assist2.git
cd assist2
npm install
cp .env.example .env
# ANTHROPIC_API_KEY und Datenbankverbindung in .env eintragen
npm run dev
```

---

## Projektstruktur

```
assist2/
├── src/
│   ├── api/                # HTTP- und WebSocket-Endpunkte
│   ├── learning/
│   │   ├── profile/        # Lernprofil-Verwaltung
│   │   ├── path/           # Adaptiver Lernpfad
│   │   ├── content/        # Generative Inhaltserzeugung
│   │   ├── repetition/     # Spaced-Repetition-Engine
│   │   └── coaching/       # Coaching- und Motivationslogik
│   ├── agents/             # KI-Agenten (Tutor, Coach, Assessor)
│   ├── memory/             # Langzeit- und Kurzzeit-Gedächtnis
│   ├── providers/          # KI-Provider-Adapter
│   ├── queue/              # Hintergrundaufgaben
│   ├── db/                 # Datenbankmodelle und Migrationen
│   └── config/
├── tests/
├── docker/
├── docs/
├── ARCHITECTURE.md
└── README.md
```

---

## Lizenz

MIT
