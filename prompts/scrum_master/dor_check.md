# DoR-Check Prompt

## Aufgabe
Prüfe die folgende User Story auf Vollständigkeit gemäß der Definition of Ready.

## Input
Story-Objekt:
```json
{{story}}
```

## Prüfschritte
1. Ist der Titel vorhanden und verständlich?
2. Hat die Beschreibung das Format "Als [Rolle] möchte ich [Aktion], damit [Nutzen]"?
3. Sind Acceptance Criteria definiert?
4. Ist Priority gesetzt?
5. Sind Story Points geschätzt?
6. Gibt es offene Abhängigkeiten die die Story blockieren?

## Ausgabe
Gib das vollständige ScrumMasterAI-Artefakt zurück.
Wenn Felder fehlen: liste sie in `missing_fields` auf.
Wenn die Story BLOCKING ist: erkläre klar warum in `findings`.
