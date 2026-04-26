"use client";

import Link from "next/link";

const sections = [
  {
    id: "rules",
    title: "Regelkonfiguration",
    path: "/conversation/rules",
    purpose: "Gespraechs-, Sizing- und Readiness-Regeln konfigurieren.",
    actions: [
      "Regeln je Typ anlegen und bearbeiten",
      "JSON-Felder direkt in der UI pflegen",
      "Aktiv/Inaktiv-Status pro Regel steuern",
      "Versionierte Regelanpassungen transparent halten",
    ],
  },
  {
    id: "signals",
    title: "Antwortsignale",
    path: "/conversation/signals",
    purpose: "Muster (keyword/regex/llm) auf Faktkategorien abbilden.",
    actions: [
      "Signal pro Faktkategorie anlegen",
      "Pattern-Type und Pattern anpassen",
      "confidence_boost kalibrieren",
      "Signale gezielt aktivieren/deaktivieren",
    ],
  },
  {
    id: "profiles",
    title: "Dialogprofile",
    path: "/conversation/profiles",
    purpose: "Ton, Modus und Basisverhalten der Engine je Profil steuern.",
    actions: [
      "Profile fuer unterschiedliche Nutzungsszenarien anlegen",
      "Aktive Profile gegen Testkonsole validieren",
      "Profilwechsel mit Regeln und Fragebausteinen abstimmen",
    ],
  },
  {
    id: "questions",
    title: "Fragebausteine",
    path: "/conversation/questions",
    purpose: "Wiederverwendbare Fragen und Follow-ups strukturieren.",
    actions: [
      "Frageblöcke nach Kategorie/Phase pflegen",
      "Pflichtfragen und Prioritaeten definieren",
      "Follow-up-Logik fuer Informationsluecken hinterlegen",
    ],
  },
  {
    id: "prompts",
    title: "Prompt Templates",
    path: "/conversation/prompts",
    purpose: "System-/Task-Prompts zentral verwalten.",
    actions: [
      "Template-Versionen dokumentieren",
      "Prompt-Anpassungen schrittweise testen",
      "Rollen und Moduswechsel konsistent abbilden",
    ],
  },
  {
    id: "testconsole",
    title: "Testkonsole",
    path: "/conversation/testconsole",
    purpose: "Regeln, Signale und Profile in Testlaeufen verifizieren.",
    actions: [
      "Dialog-Varianten und Edge Cases durchspielen",
      "Fact-Extraction und Mapping-Ausgabe pruefen",
      "Regelwirkung vor Produktivsetzung absichern",
    ],
  },
];

export default function ConversationHelpPage() {
  return (
    <div className="max-w-6xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Conversation Engine Hilfe</h1>
        <p className="text-sm text-gray-500 mt-1">
          Schnellreferenz fuer alle implementierten Admin-Bereiche der Conversation Engine
        </p>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
        Nutze diese Hilfe als Navigations- und Betriebsleitfaden. Beginne typischerweise mit
        Profilen/Fragebausteinen, konfiguriere danach Signale und Regeln und validiere alles
        in der Testkonsole.
      </div>

      <div className="space-y-3">
        {sections.map((s) => (
          <section key={s.id} id={s.id} className="bg-white border rounded-lg p-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">{s.title}</h2>
                <p className="text-sm text-gray-500">{s.purpose}</p>
              </div>
              <Link
                href={s.path}
                className="text-sm border px-3 py-1.5 rounded-md hover:bg-gray-50 whitespace-nowrap"
              >
                Bereich oeffnen
              </Link>
            </div>

            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1">Typische Aktionen</p>
              <ul className="space-y-1">
                {s.actions.map((a) => (
                  <li key={a} className="text-sm text-gray-700">- {a}</li>
                ))}
              </ul>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
