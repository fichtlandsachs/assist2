# Governance: Zwei-Ebenen-Kontrollmodell

## Zielbild

Operative Nutzer (BAs, POs, Entwickler) sehen keinerlei ISO- oder NIS2-Sprache. Sie erhalten kontextuelle, verständliche Hinweise direkt in der User-Story: Was sie tun sollen, warum es wichtig ist, welche Fragen sie stellen müssen, welche Nachweise erwartet werden. Admins und Auditoren konfigurieren im Hintergrund, welche Controls wann greifen, und sehen die vollständige Governance-Schicht mit Framework-Mappings und Auditpfad.

---

## Fachliches Modell (Zwei-Ebenen-Modell)

### Ebene 1 – Nutzerhinweis (user layer)
Sichtbar für alle operativen Nutzer. Enthält ausschließlich Klartext:
- **user_title**: kurzer, verständlicher Kontrolltitel
- **user_explanation**: Warum das relevant ist (ohne ISO-Referenz)
- **user_action**: Was konkret zu tun ist
- **user_guiding_questions**: Liste von Leitfragen (JSONB)
- **user_evidence_needed**: Welche Nachweise erwartet werden (JSONB)

### Ebene 2 – Governance-Schicht (governance layer)
Nur für Admins/Auditoren sichtbar. Enthält:
- **title** + **description**: technischer Kontrolltitel
- **control_type**: preventive / detective / corrective / compensating
- **framework_refs**: ISO 27001:2022 A.x.x, NIS2 Art.x, ISO 9001:8.x (JSONB)
- **control_objective**: Was dieser Control formal sicherstellt
- **review_interval_days**: Wie oft der Control überprüft werden muss
- **implementation_status** + **maturity_level** pro Capability-Zuweisung

---

## Datenmodell

### Änderung: `controls` Tabelle (Migration 0061)

Neue Spalten:
```sql
user_title          VARCHAR(500) NULL
user_explanation    TEXT NULL
user_action         TEXT NULL
user_guiding_questions  JSONB NULL DEFAULT '[]'
user_evidence_needed    JSONB NULL DEFAULT '[]'
```

Das bestehende `Control`-Modell bleibt vollständig erhalten. Die Nutzer-Ebene ist eine additive Erweiterung.

### Keine neuen Tabellen für MVP

Hint-Engine, approval_rules, review_rules etc. sind späterer Ausbau. Der MVP fokussiert auf die Anreicherung der bestehenden Kontrollstruktur.

---

## Admin-UI-Konzept

Datei: `frontend/app/[org]/compliance/page.tsx` (bestehend)

Tab "Controls & Capabilities" bekommt eine Control-Detailansicht mit zwei Panels:

**Linkes Panel (Nutzer-Ebene):**
- user_title (Feld)
- user_explanation (Textarea)
- user_action (Textarea)
- user_guiding_questions (Liste mit Add/Remove)
- user_evidence_needed (Liste mit Add/Remove)

**Rechtes Panel (Governance-Ebene):**
- title, description, control_type
- framework_refs (Tags)
- implementation_status, review_interval_days
- Capability-Zuweisungen (read-only Liste)

Die Trennung macht visuell klar: links = was der Nutzer sieht, rechts = was der Admin konfiguriert.

Neue Komponente: `frontend/components/governance/ControlEditor.tsx`

---

## Nutzer-UI-Konzept

Datei: `frontend/components/governance/StoryCompliancePanel.tsx` (bestehend)

Zeigt je relevantem Control:
- `user_title` als Überschrift (Fallback auf `title`)
- `user_explanation` als Erklärungstext
- `user_action` als Action-Box (farblich hervorgehoben)
- `user_guiding_questions` als nummerierte Liste
- `user_evidence_needed` als Checkliste

Kein ISO-Kürzel, kein framework_ref, keine technische Kontrolltypbezeichnung.

---

## Rollen

| Rolle | Sieht Nutzer-Ebene | Sieht Governance-Ebene | Kann Controls bearbeiten |
|-------|-------------------|----------------------|--------------------------|
| BA / PO / Developer | ✓ | ✗ | ✗ |
| Admin | ✓ | ✓ | ✓ |
| Auditor (zukünftig) | ✓ | ✓ | ✗ |

Die Trennung erfolgt durch separate API-Felder: `/relevant-controls` gibt nur user_layer zurück; Admin-CRUD-Endpoints geben alle Felder zurück.

---

## Technische Umsetzung

### Backend

**Migration 0061**: ALTER TABLE controls ADD COLUMN user_title, user_explanation, user_action, user_guiding_questions, user_evidence_needed

**Model**: `Control` um 5 Felder erweitern

**Schemas**: `ControlCreate`/`ControlUpdate`/`ControlRead` um user_layer-Felder erweitern; neues `ControlUserView` ohne Governance-Felder für operative Endpunkte

**Service**: keine Änderung nötig

**Router** `user_stories.py`:
- `GET /user-stories/{story_id}/relevant-controls` gibt `ControlUserView` (nur user_layer) zurück

### Frontend

**Typen** (`types/index.ts`): `Control` um user_layer-Felder erweitern; `ControlUserView` Typ hinzufügen

**`StoryCompliancePanel.tsx`**: User-Layer-Felder anzeigen (user_title, user_explanation, user_action, Leitfragen, Nachweise)

**`ControlEditor.tsx`** (neu): Two-panel Admin-Editor für Controls

**`ControlCapabilityMap.tsx`**: Control-Auswahl öffnet `ControlEditor` im rechten Bereich

---

## MVP vs. Ausbau

### MVP (diese Implementierung)
- User-Layer-Felder auf `Control`
- Admin-Editor mit zwei Panels
- Story-Compliance-Panel zeigt nur Nutzer-Ebene
- Bestehende Capability-Scoping-Logik bleibt unverändert

### Ausbau (spätere Iterationen)
- Hint-Engine: automatische Hinweisgenerierung basierend auf Story-Eigenschaften
- Evidence-Management: Nachweise hochladen und verlinken
- Review-Workflow: Fälligkeiten, Erinnerungen, Genehmigungen
- Audit-Trail: Änderungshistorie für Controls
- Framework-Mapping-UI: visuelles Mapping auf ISO/NIS2-Kapitel

---

## Test-/Validierungskonzept

- Unit: Migration läuft durch, neue Felder werden gespeichert und gelesen
- Integration: Admin kann Control mit user_layer anlegen; Story-Compliance-Panel zeigt user_title statt title
- E2E: BA sieht kein ISO-Kürzel im Compliance-Panel

---

## Typische Fehlentscheidungen

- **Separate Tabelle für user_layer**: Unnötige Komplexität; additive Spalten auf `controls` sind ausreichend
- **User-Layer im Frontend filtern**: Governance-Felder dürfen nie an operative Endpunkte gesendet werden — das Filtern muss im Schema/Router passieren, nicht im Frontend
- **Leere user_title ignorieren**: Falls user_title leer, auf `title` fallen (Fallback), um Brüche zu vermeiden

---

## Management-Zusammenfassung

Operative Nutzer sehen kontextuelle, verständliche Hinweise ohne Compliance-Jargon. Admins pflegen beide Ebenen über einen klaren zwei-Panel-Editor. Die Implementierung erweitert das bestehende Control-Modell additiv — kein Breaking Change, kein Datenverlust. Governance-Frameworks (ISO 27001, NIS2, ISO 9001) bleiben intern gemappt und sind für operative Nutzer vollständig unsichtbar.
