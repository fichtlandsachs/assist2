# heykarl — Funktionsbeschreibung
**Stand: April 2026**

heykarl ist eine KI-native agile Arbeitsplattform für Entwicklungsteams. Der Kern ist das kollaborative Arbeiten an User Stories, unterstützt durch eingebettete KI-Assistenz, Spracheingabe, Jira- und Confluence-Integration sowie automatisierte Dokumentation.

---

## 1. User Stories

Das zentrale Objekt der Plattform. Eine Story durchläuft einen definierten Lebenszyklus und kann auf allen Ebenen durch KI angereichert werden.

### Felder
| Feld | Beschreibung |
|------|-------------|
| Titel | Pflichtfeld, max. 500 Zeichen |
| Beschreibung | Freitext (Als … möchte ich … damit …) |
| Akzeptanzkriterien | Freitext oder strukturierte Liste |
| Status | draft → in_review → ready → in_progress → testing → done → archived |
| Priorität | low / medium / high / critical |
| Story Points | Schätzung (ganze Zahl) |
| Epic | Zuordnung zu einem Epic |
| Projekt | Zuordnung zu einem Projekt |
| Qualitätsscore | 0–100, berechnet durch KI |
| DoR bestanden | Boolean, automatisch nach Readiness-Prüfung |
| Jira-Ticket | Verknüpfter Ticket-Key (z. B. ABC-123) + URL |
| Confluence-Seite | URL der generierten Dokumentationsseite |
| Zielgruppe | Für automatische Dokumentation |
| Dokumentation | Zusatzinfos, Workarounds, Version |

### Status-Workflow
```
draft → in_review → ready → in_progress → testing → done
                                                      ↓
                                                  archived
```

### Story erstellen (`/stories/new`)
Zweispaltige Seite: linke Spalte Formular, rechte Spalte KI-Assistent.

- Alle Felder editierbar
- **Sprachaufnahme**: Mikrofon-Button nimmt Audio auf (16 kHz PCM WAV), sendet an Faster-Whisper, schreibt Ergebnis in die Beschreibung
- **Keyword-Routing**: Gesprochene Keywords (`Titel:`, `Beschreibung:`, `Akzeptanzkriterien:` / `AC:`) verteilen den transkribierten Text automatisch auf die richtigen Felder
- Sofortige KI-Unterstützung über den rechten Assistenten-Tab

### Story bearbeiten (`/stories/[id]`)
Vollständige Detail-Ansicht mit fünf Tabs:

**Tab: Story**
Alle Kernfelder editierbar. Status-Wechsel per Dropdown. Jira-Verknüpfung mit Sync-Statusanzeige und Divergenz-Warnung.

**Tab: Definition of Done**
Interaktive Checkliste. Items können manuell gepflegt oder per KI-Chat generiert werden (`StoryDoDChatPanel`). Jedes Item hat einen Abhak-Status.

**Tab: Testfälle**
Strukturierte Testfälle mit Steps, erwartetem Ergebnis und tatsächlichem Ergebnis. Status: pending / in_progress / passed / failed / skipped. KI kann Testfälle aus Akzeptanzkriterien vorschlagen.

**Tab: Features**
Sub-Features der Story (eigene Entitäten). Jedes Feature hat Titel, Beschreibung, Status, Priorität, Story Points und optionale Jira-Verknüpfung. KI-Chat kann Features strukturieren.

**Tab: Dokumentation**
- KI-generierte Sektionen: Zusammenfassung, Changelog-Eintrag, Gliederung, technische Notizen, Business-Value, technische Spezifikation
- Manuelle Felder: Zielgruppe, Zusatzinfos, Workarounds, Dokumentationsversion
- Confluence-Sync: Vergleich, Push und automatische Hierarchie-Erstellung (Projekt → Epic → Story)

### KI-Assistent im Bearbeitungsmodus (`StoryRefinementPanel`)
Chat-basierter Assistent mit drei Phasen:
1. **Schärfen** — Präzisierung von Titel, Beschreibung, Akzeptanzkriterien
2. **Qualität** — Bewertung nach DoR-Kriterien, Qualitätsscore
3. **Kontext** — Einbeziehung von Team-Wissen, Confluence, Jira

Vorschläge können per Drag-and-Drop oder Klick in die Formularfelder übernommen werden. Web-Recherche auf Befehl (`/WEB`).

### Story Readiness (`/stories/readiness`)
Dashboard aller zugewiesenen Stories mit Readiness-Bewertung:
- Zustand: implementation_ready / partially_ready / not_ready
- Blocker-Liste
- Fehlende Eingaben
- Abhängigkeiten & Risiken
- Empfohlene nächste Schritte
- Verlauf (History) pro Story

### Story aufteilen
Bestehende Stories können in kleinere Teil-Stories zerlegt werden (Splitting). Die Original-Story wird als Eltern-Story markiert (`is_split = true`).

---

## 2. Epics

Gruppierung von User Stories zu größeren Themen.

### Felder
- Titel, Beschreibung
- Status: planning / in_progress / done / archived
- Projekt-Zuordnung (optional)
- Verknüpfte Stories (1:N)
- Prozessänderungen (aggregiert aus Stories)

### Epic-Board (`/stories/epics/board`)
Kanban-Ansicht aller Epics nach Status. Direkter Link zur Detail-Seite.

### Epic-Detail (`/stories/epics/[id]`)
- Alle Felder editierbar
- Vollständige Story-Liste des Epics
- „Neue Story"-Button übergibt `epic_id` und ggf. `project_id` vorausgefüllt an die Story-Erstellung
- Prozessänderungs-Aggregation (was hat sich im Epic geändert)

---

## 3. Features

Sub-Features einzelner User Stories.

### Felder
- Titel, Beschreibung
- Status: draft / in_progress / testing / done / archived
- Priorität, Story Points
- Story-Zuordnung (Pflicht), Epic-Zuordnung (optional)
- Jira-Ticket (optional)

### Features-Board (`/stories/features/board`)
Kanban-Ansicht aller Features nach Status mit Projekt-Filter.

---

## 4. Projekte

Strukturierungsebene über Epics und Stories.

### Felder
- Name, Beschreibung
- Status: planning / active / done / archived
- Deadline, Aufwand, Komplexität
- Farbe (für Visualisierung)
- Owner

### Projekt-Detail (`/project/[id]`)
- Editierbare Beschreibung
- Story-Statusverteilung als Fortschrittsbalken
- Metriken: Ø Qualitätsscore, Story Points gesamt, Stories erledigt %, Klarheit %, Risiko %
- Verlinkung zu Stories-Board (gefiltert) und direkter „Neue Story"-Button (mit vorausgefüllter `project_id`)
- Epic-Liste mit Direktlinks
- Feature-Statusübersicht

---

## 5. KI-Funktionen

### Spracheingabe
- Aufnahme über Mikrofon (Web Audio API, 16 kHz PCM → WAV)
- Transkription über lokalen Faster-Whisper-Service
- Keyword-Parsing verteilt Text auf Titel, Beschreibung und Akzeptanzkriterien

### Story-Extraktion
Freitext oder Transkript → strukturierte Story (Titel, User-Story-Format, Akzeptanzkriterien, Testfälle, Features, Releases). Mindestlänge: 80 Zeichen.

### Story-Refinement (Chat)
Mehrstufiger Chat-Assistent im Bearbeitungs- und Erstellungsmodus. Streaming via Server-Sent Events. Extrahiert Vorschläge für alle Kernfelder. Web-Recherche auf `/WEB`-Befehl.

### DoD-Assistent
Chat generiert Definition-of-Done-Items auf Basis der Story-Inhalte und Team-Konventionen.

### Features-Assistent
Chat strukturiert Features auf Basis von Beschreibung und Akzeptanzkriterien.

### Story Readiness Evaluation
Automatische Bewertung nach konfigurierbaren DoR-Kriterien. Liefert Zustand, Blocker, Empfehlungen. Ergebnisse werden gecacht und versioniert gespeichert.

### RAG-Chat (`/ai-workspace`)
Chat-Interface mit RAG-Kontext aus:
- Confluence-Seiten
- Jira-Tickets
- heykarl-Stories
- Nextcloud-Dateien
- Team-Wissen (compact-chat-Indexierung)

Modi: Chat (agiler Coach), Docs (technische Dokumentation), Tasks (Projektmanagement). Streaming mit Source-Tracking und Hallucinations-Erkennung.

### Dokumentations-Generierung
KI erstellt auf Knopfdruck: Zusammenfassung, Changelog-Eintrag, Gliederung, technische Notizen, Business-Value, technische Spezifikation.

---

## 6. Integrationen

### Jira
- Ticket-Suche und -Anzeige aus konfigurierten Projekten
- Ticket → User Story Transformation (KI)
- Sync-Vorschau: Diff zwischen Jira und heykarl (Titel, Beschreibung, Features, Testfälle)
- Sync anwenden: Jira-Änderungen nach heykarl übernehmen
- Story nach Jira pushen: Main-Ticket + Features + Testfälle + DoD-Items als Jira-Subtasks
- Divergenz-Warnung in Story-Karte und Detail-Ansicht
- Auth: Atlassian OAuth 2.0 oder Basic Auth (API-Token)

### Confluence
- Indexierung von Spaces für den RAG-Chat
- Seiten als Dropdown in den Dokumentations-Einstellungen (kein manuelles ID-Tippen)
- Story-Dokumentation publizieren: Automatische Hierarchie (Standard-Parent → Projekt → Epic → Story)
- Bei Änderung der Epic-/Projekt-Zuordnung wird die Confluence-Seite automatisch verschoben
- Sync-Check: Diff zwischen heykarl-Docs und Confluence-Seite
- Auth: Basic Auth (Benutzername + API-Token)

### Nextcloud
- Datei-Browser für Org-Gruppen-Ordner und persönliche Ordner
- Upload in Gruppen- oder persönlichen Ordner
- Download (Streaming)
- Hochgeladene Dateien werden automatisch für RAG indexiert

### Kalender
- Provider: Google Calendar, Outlook / Microsoft 365
- Mehrere Kalender pro Org
- Konfigurierbare Sync-Intervalle

### E-Mail (Posteingang)
- IMAP-Anbindung
- Eingehende E-Mails als Aufgaben / Stories interpretierbar
- RAG-Clustering der Inhalte

---

## 7. Dashboard (`/dashboard`)

- KPIs: Done %, Active Stories, Velocity (Story Points), Total Points
- Burndown-Chart (Ist vs. Plan)
- Quick Actions: Board, Sprint Planning, Story erstellen
- Letzte 5 Stories mit Status-Badge
- Karl's Tipp (kontextueller KI-Hinweis basierend auf Fortschritt)

---

## 8. Compliance (`/compliance`)

- DoR-Übersicht: Welche Stories erfüllen die Definition of Ready?
- Qualitätsscore-Verteilung über alle Stories
- Konfigurierbare DoR-Regeln (Mindest-Score, Pflichtfelder)

---

## 9. Benutzer & Organisationen

### Authentifizierung
- Registrierung und Login über Authentik (OIDC)
- OAuth-Login: Atlassian, GitHub
- JWT (Access + Refresh Token), Redis-Blacklist für Logout

### Rollen
| Rolle | Berechtigung |
|-------|-------------|
| Owner | Vollzugriff inkl. Org-Löschung |
| Admin | Alles außer Org-Löschung |
| Member | Stories lesen/schreiben, keine Settings |
| Viewer | Nur lesend |

### Multi-Tenancy
- Eine Person kann Mitglied mehrerer Organisationen sein
- Alle Daten sind strikt nach `organization_id` isoliert
- Einladungen per E-Mail (Status: invited → active)

---

## 10. Einstellungen (`/settings`)

| Bereich | Inhalt |
|---------|--------|
| Allgemein | Org-Name, Slug, Beschreibung |
| Profil | Anzeigename, E-Mail, Sprache (DE/EN), Zeitzone, verknüpfte Accounts |
| Mitglieder | Einladungen, Rollenvergabe, Entfernen |
| E-Mail | IMAP-Konfiguration |
| Kalender | Provider, Sync-Einstellungen |
| Jira | URL, Credentials, Test-Verbindung |
| Confluence | URL, Credentials, Standard-Space, Standard-Parent-Seite, Test-Verbindung, Index-Trigger |
| KI | DoR-Kriterien, Mindestscore, eigene Regeln |

---

## 11. Admin-Bereich

### Org-Admin (`/admin`)
- Org-Settings
- Mitgliederverwaltung
- Integrations-Status
- Billing-Übersicht
- PDF-Export-Konfiguration (Theme, Format, Header/Footer, Logo)

### SuperAdmin (`/(superadmin)`)
- Alle Benutzer org-übergreifend
- Alle Organisationen
- Org-Detail: Billing-Override, Config-Override, Feature-Flags, Audit-Logs

---

## 12. Workflows (`/workflows`)

- n8n-Workflows pro Organisation
- Manuelles Auslösen
- Ausführungshistorie mit Status, Logs, Ergebnissen

---

## 13. Sprache & Theme

### Sprachen
Vollständige Übersetzung in Deutsch und Englisch (620+ Schlüssel). Umschaltbar pro Benutzer.

### Themes
| Theme | Beschreibung |
|-------|-------------|
| karl (Standard) | Schwarze Pixel-Schatten, klare Typografie, starke Kontraste |
| agile | Warme Paper-Palette, Notebook-Ästhetik |
| paperwork | Serif-Schriften, klassisches Dokument-Look |

Theme wird in `localStorage` persistiert, Bootstrap-Script verhindert Flash beim Laden.

---

## 14. Technischer Stack (Überblick)

| Schicht | Technologie |
|---------|------------|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS, SWR |
| Backend | FastAPI (Python 3.12), SQLAlchemy async, Alembic |
| Datenbank | PostgreSQL 16 |
| Cache / Queue | Redis 7, Celery |
| KI / LLM | LiteLLM → IONOS AI (ionos-reasoning / quality / fast), Anthropic Claude (Fallback) |
| Sprache | Faster-Whisper (lokal, small-Modell, int8) |
| Auth | Authentik (OIDC), JWT |
| Routing | Traefik v3 (TLS, Middleware) |
| Dateien | Nextcloud (WebDAV) |
| Workflows | n8n |
