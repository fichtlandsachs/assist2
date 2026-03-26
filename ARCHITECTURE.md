# Architektur – assist2

## Leitgedanke

Die Architektur von assist2 ist um einen zentralen Gedanken herum gebaut:
**Lernen ist kein einzelner Moment, sondern ein kontinuierlicher Prozess.**

Alle technischen Entscheidungen folgen daraus. Das System muss eine Person über
Wochen und Monate kennen, verstehen und begleiten – nicht nur die letzte Anfrage
beantworten. Daraus ergeben sich drei Kernanforderungen:

1. **Persistentes Personenverständnis** – Das System muss wissen, wer jemand ist,
   was er kann und wohin er will.
2. **Generative Anpassungsfähigkeit** – Inhalte entstehen zur Laufzeit, nie statisch.
3. **Proaktive Prozesssteuerung** – Das System wartet nicht, sondern begleitet aktiv.

---

## Systemübersicht

```
┌──────────────────────────────────────────────────────────────────┐
│                           Clients                                │
│         Web-App │ Mobile │ Embed (LMS, Intranet)                 │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS / WSS
┌────────────────────────────▼─────────────────────────────────────┐
│                        API-Schicht                               │
│               Fastify (REST + WebSocket-Streaming)               │
│         Auth │ Session │ Rate-Limiting │ Schema-Validierung       │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│                    Lern-Orchestrierung                           │
│                                                                  │
│  ┌──────────────────┐   ┌─────────────────┐  ┌───────────────┐  │
│  │  Session-Manager │   │  Lernpfad-Engine│  │ Coaching-     │  │
│  │                  │◄──►                 │◄─►│ Modul         │  │
│  │  Sitzungskontext,│   │  Adaptiver Pfad,│  │               │  │
│  │  Gesprächsfluss  │   │  Verzweigungen, │  │  Motivation,  │  │
│  └──────────────────┘   │  Meilensteine   │  │  Proaktivität │  │
│                         └─────────────────┘  └───────────────┘  │
└──────────┬──────────────────────┬────────────────────┬───────────┘
           │                      │                    │
┌──────────▼───────┐  ┌───────────▼────────┐  ┌───────▼──────────┐
│   KI-Agenten     │  │  Content-Generator │  │  Profil-System   │
│                  │  │                    │  │                  │
│  Tutor-Agent     │  │  Aufgaben          │  │  Lernprofil      │
│  Coach-Agent     │  │  Erklärungen       │  │  Stärken/Lücken  │
│  Assessor-Agent  │  │  Szenarien         │  │  Lernhistorie    │
│  Planner-Agent   │  │  Reflexionsfragen  │  │  Spaced-Rep.     │
└──────────┬───────┘  └───────────┬────────┘  └───────┬──────────┘
           │                      │                    │
┌──────────▼──────────────────────▼────────────────────▼───────────┐
│                        Persistenz-Schicht                        │
│                                                                  │
│  PostgreSQL                pgvector               Redis          │
│  (Profile, Lernhistorie,   (Embeddings,           (Sessions,     │
│   Fortschritt, Inhalte,     semantische Suche,     BullMQ-Queue, │
│   Audit)                    Ähnlichkeitsmatching)  Cache)        │
└──────────────────────────────────────────────────────────────────┘
```

---

## Kernkomponenten

### 1. Lernpfad-Engine

Die Lernpfad-Engine ist das Herzstück des Systems. Sie bestimmt zu jedem Zeitpunkt,
was als nächstes passiert – basierend auf dem Lernprofil, dem bisherigen Verlauf
und dem aktuellen Zustand.

**Zustandsmodell einer Lernsitzung:**

```
[Start / Diagnose]
        │
        ▼
[Wissenstand einschätzen] ──► Bekannt? ──► [Vertiefen / Verknüpfen]
        │                                          │
        ▼ Lücke erkannt                            ▼
[Neues Konzept einführen]              [Anwendungsaufgabe]
        │                                          │
        ▼                                          ▼
[Verständnis prüfen] ◄──────────────── [Reflexion]
        │
        ▼
Bestanden? ── Nein ──► [Alternativer Erklärungsweg]
        │
       Ja
        ▼
[Fortschritt speichern] ──► [Nächster Schritt im Pfad]
```

**Adaptivitätssignale** (steuern Verzweigungen):
- Antwortqualität und Reaktionszeit
- Anzahl der Wiederholungen bis zur korrekten Lösung
- Emotionale Signale (Frustration, Stagnation, Flow)
- Zeitpunkt der letzten Beschäftigung mit einem Thema (Vergessenskurve)

---

### 2. KI-Agenten

assist2 setzt auf spezialisierte Agenten, die zusammenarbeiten:

| Agent | Rolle | Modell |
|---|---|---|
| **Tutor-Agent** | Erklärt, führt durch Konzepte, beantwortet Fragen | claude-sonnet-4-6 |
| **Assessor-Agent** | Bewertet Antworten, erkennt Wissenslücken | claude-sonnet-4-6 |
| **Coach-Agent** | Motiviert, gibt Feedback, passt Ton an | claude-haiku-4-5 |
| **Planner-Agent** | Plant Lernpfade, setzt Meilensteine | claude-opus-4-6 |
| **Content-Agent** | Generiert Aufgaben, Szenarien, Übungen | claude-sonnet-4-6 |

Alle Agenten kommunizieren über einen gemeinsamen **Kontext-Bus** und greifen
auf dasselbe Lernprofil zu. Sie können sequenziell oder parallel agieren.

**Agenten-Interface:**

```typescript
interface LearningAgent {
  role: 'tutor' | 'assessor' | 'coach' | 'planner' | 'content';
  act(
    context: LearningContext,
    profile: LearnerProfile,
    input: AgentInput
  ): Promise<AgentOutput>;
}
```

---

### 3. Content-Generator

Alle Lerninhalte werden **zur Laufzeit generiert** – es gibt keine statische
Content-Datenbank. Das ermöglicht maximale Personalisierung.

**Generierungsparameter:**

```typescript
interface ContentRequest {
  topic: string;
  learnerLevel: 'beginner' | 'intermediate' | 'advanced';
  learningStyle: 'visual' | 'analytical' | 'practical';
  format: 'explanation' | 'exercise' | 'scenario' | 'quiz' | 'reflection';
  availableMinutes: number;
  previousErrors: ConceptGap[];
  language: string;
}
```

**Inhaltsformate:**
- **Erklärungen** – mit Analogien, Beispielen, schrittweisen Herleitungen
- **Übungsaufgaben** – mit gestuften Schwierigkeitsgraden
- **Szenarien** – realitätsnahe Situationen, die Theorie in Praxis überführen
- **Reflexionsfragen** – zur Aktivierung des Metakognition
- **Lückentexte & Quizze** – zum Abrufen von Gelerntem (Retrieval Practice)

---

### 4. Persönliches Lernprofil

Das Lernprofil ist der zentrale Wissensspeicher über eine Person.
Es wird bei jeder Interaktion gelesen und aktualisiert.

**Struktur:**

```typescript
interface LearnerProfile {
  id: string;
  goals: LearningGoal[];
  knowledgeMap: Map<Concept, MasteryLevel>;   // 0.0 – 1.0
  learningStyle: LearningStyleVector;
  preferredPace: 'slow' | 'medium' | 'fast';
  availableTimePerSession: number;            // Minuten
  streakDays: number;
  masteredConcepts: Concept[];
  openGaps: ConceptGap[];
  repetitionSchedule: SpacedRepEntry[];      // SM-2
  sessionHistory: LearningSession[];
  motivationProfile: MotivationProfile;
}
```

**Masterly-Tracking** – jedes Konzept wird auf einer Skala 0–1 bewertet:

```
0.0 – unbekannt
0.2 – erste Begegnung
0.5 – verstanden, aber noch unsicher
0.8 – sicher anwendbar
1.0 – gefestigt, kann es erklären
```

---

### 5. Spaced-Repetition-Engine

Basiert auf dem **SM-2-Algorithmus** (SuperMemo 2), angepasst für
gesprächsbasiertes Lernen.

**Ablauf:**

```
Nach jeder Interaktion mit einem Konzept:
  1. Bewertung der Antwortqualität (0–5)
  2. Berechnung des nächsten Wiederholungszeitpunkts
  3. Eintrag in den Repetitions-Schedule des Profils
  4. Beim nächsten Session-Start: fällige Wiederholungen priorisieren
```

**Integration in den Lernpfad:**
- Fällige Wiederholungen werden zu Beginn jeder Sitzung eingebaut
- Vergessene Konzepte werden mit angepasstem Erkläransatz neu eingeführt
- Visualisierung der Retention-Kurven im Nutzerdashboard

---

### 6. Coaching-Modul

Das Coaching-Modul überwacht den Lernprozess auf einer Meta-Ebene und
greift ein, wenn es nötig ist.

**Erkannte Muster und Reaktionen:**

| Muster | Reaktion |
|---|---|
| 3× gleicher Fehler | Alternativer Erklärungsweg, Perspektivwechsel |
| Sitzung < 2 Min. abgebrochen | Beim nächsten Start: kurze Check-in-Frage |
| 5 Tage keine Aktivität | Proaktive Erinnerung + niedrigschwelliger Einstieg |
| Sehr schnelle korrekte Antworten | Schwierigkeitsgrad erhöhen |
| Hohe Fehlerrate + lange Antwortzeiten | Tempo reduzieren, Aufmunterung |
| Meilenstein erreicht | Explizite Würdigung, Zusammenfassung des Fortschritts |

**Tonalität:** Der Coach-Agent passt Sprache und Ton dynamisch an –
sachlich-präzise bei analytischen Lernenden, ermutigend-warm bei
emotional orientierten.

---

### 7. Memory-System

Zwei Ebenen des Gedächtnisses:

| Ebene | Speicher | Inhalt | Lebensdauer |
|---|---|---|---|
| **Sitzungsgedächtnis** | Redis | Gesprächsverlauf, aktuelle Aufgabe | Sitzungsdauer |
| **Langzeitgedächtnis** | PostgreSQL + pgvector | Lernprofil, Konzeptkarten, Lernhistorie | Dauerhaft |

**Semantische Suche im Langzeitgedächtnis:**
- Alle gespeicherten Konzepte und Lerninhalte werden als Embeddings gespeichert
- Beim Start einer neuen Einheit: semantisch ähnliche frühere Interaktionen abrufen
- Dadurch: Anknüpfen an bekannte Konzepte, Vermeidung von Wiederholungen

---

## Prozessfluss – Vollständige Lernsitzung

```
Nutzer startet Sitzung
        │
        ▼
1. Profil laden
   └── Letzter Stand, offene Lücken, fällige Wiederholungen
        │
        ▼
2. Session-Planung (Planner-Agent)
   └── Ziel der Sitzung festlegen (Wiederholung? Neues Thema? Freies Erkunden?)
        │
        ▼
3. Einstieg
   └── Kurzes Check-in: "Wo stehst du heute? Wieviel Zeit hast du?"
        │
        ▼
4. Lernschleife (bis Sitzungsziel erreicht oder Zeit abgelaufen)
   │
   ├── Content-Agent generiert nächste Einheit
   ├── Tutor-Agent präsentiert / erklärt
   ├── Assessor-Agent wertet Antwort aus
   ├── Coach-Agent beobachtet, greift bei Bedarf ein
   └── Lernpfad-Engine entscheidet über nächsten Schritt
        │
        ▼
5. Abschluss der Sitzung
   ├── Reflexionsfrage ("Was war heute neu für dich?")
   ├── Fortschritt sichtbar machen
   ├── Nächsten Schritt ankündigen
   └── Profil aktualisieren (Mastery-Werte, Repetition-Schedule)
        │
        ▼
6. Post-Session
   └── Hintergrundprozess plant proaktive Erinnerungen (BullMQ)
```

---

## API-Endpunkte

```
POST   /v1/sessions              – Neue Lernsitzung starten
GET    /v1/sessions/:id          – Sitzungsstatus & Verlauf
POST   /v1/sessions/:id/message  – Nachricht senden, Antwort streamen
DELETE /v1/sessions/:id          – Sitzung beenden

GET    /v1/profile               – Eigenes Lernprofil abrufen
PATCH  /v1/profile               – Ziele / Präferenzen aktualisieren
GET    /v1/profile/progress      – Fortschrittsübersicht
GET    /v1/profile/schedule      – Fällige Wiederholungen

WS     /v1/stream                – Echtzeit-Streaming aller Agenten-Ausgaben
POST   /v1/webhooks/reminder     – Externer Trigger für Erinnerungen
```

---

## Sicherheit & Datenschutz

- Lernprofile enthalten sensible persönliche Daten → strikte Zugriffskontrolle
- Datensparsamkeit: nur was für den Lernprozess notwendig ist, wird gespeichert
- Nutzer können ihr Profil jederzeit einsehen, exportieren und löschen (DSGVO)
- Alle KI-Anfragen werden ohne Weiterleitung sensibler Profildaten an Dritte gestaltet
- Audit-Log aller Profilzugriffe und -änderungen

---

## Deployment

```
assist2/
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml        # Lokal: App + PG + Redis + Chroma
│   └── docker-compose.prod.yml
└── .github/
    └── workflows/
        ├── ci.yml                # Test, Lint, Typecheck
        └── deploy.yml
```

```
[Load Balancer]
      │
  ┌───┴────┐
  │ App ×n │   (horizontal skalierbar; Sessions sind Redis-backed)
  └───┬────┘
      │
  ┌───┴───────────────────────────────┐
  │  PostgreSQL  │  Redis  │  Chroma  │
  └───────────────────────────────────┘
```

---

## Architekturentscheidungen (ADRs)

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | Spezialisierte Agenten statt einem Generalisten | Klare Verantwortlichkeiten, bessere Steuerbarkeit, testbar |
| 2 | Rein generative Inhalte, keine statische Content-DB | Maximale Personalisierung, kein Content-Pflegeaufwand |
| 3 | SM-2 für Spaced Repetition | Bewährt, einfach implementierbar, nachvollziehbar für Nutzer |
| 4 | pgvector statt separater Vektordatenbank | SQL-Joins zwischen Profildaten und Embeddings; weniger Infrastruktur |
| 5 | Claude als primäres Modell | Stärke in langen Kontexten, Instruktionstreue, Mehrsprachigkeit |
| 6 | WebSocket-Streaming für alle Agenten-Ausgaben | Lernen fühlt sich lebendig an; kein Warten auf vollständige Antworten |
