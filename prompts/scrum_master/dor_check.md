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
3. Sind Acceptance Criteria definiert, messbar und im Gegeben/Wenn/Dann-Format?
4. Ist Priority gesetzt?
5. Sind Story Points geschätzt?
6. Gibt es offene Abhängigkeiten die die Story blockieren?

### Businessnutzen & Outcome (kritische Prüfung)
7. Ist der Businessnutzen im „damit …"-Teil vorhanden?
8. Beschreibt der Nutzen einen echten **Outcome** (messbare Veränderung für Nutzer oder Business)?
   - SCHWACH (nicht akzeptabel): „damit es besser wird", „um die UX zu verbessern", „zur Optimierung"
   - STARK (akzeptabel): „damit Support-Anfragen um 30 % sinken", „damit Nutzer den Prozess ohne Rückfrage abschließen"
9. Ist erkennbar, **wer** konkret profitiert und **was sich messbar ändert**?
10. Ist der Nutzen aus Nutzerperspektive formuliert (kein reiner technischer Output wie „API wird gebaut")?

## Ausgabe
Gib das vollständige ScrumMasterAI-Artefakt zurück.
Wenn Felder fehlen: liste sie in `missing_fields` auf.
Wenn der Businessnutzen nur vage oder output-orientiert ist: trage ihn als `missing_fields`-Eintrag
mit Schweregrad HIGH ein und formuliere eine konkrete Nachfrage.
Wenn die Story BLOCKING ist: erkläre klar warum in `findings`.
