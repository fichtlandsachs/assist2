"use client";

import Link from "next/link";

const sections = [
  {
    id: "sources",
    title: "Wissensquellen",
    path: "/knowledge/sources",
    purpose: "Externe Quellen anlegen und verwalten.",
    actions: [
      "Quelle mit source_key, base_url und config_json anlegen",
      "Initial Ingest und Refresh starten",
      "Quelle deindexieren oder deaktivieren/aktivieren",
      "Chunk-Volumen pro Quelle überwachen",
    ],
    tips: [
      "Nutze stabile source_keys ohne Leerzeichen.",
      "Setze include_url_prefixes und allowed_domains restriktiv.",
      "Bei Strukturänderungen der Doku zuerst Preview testen.",
    ],
  },
  {
    id: "ingest",
    title: "Ingest Monitor",
    path: "/knowledge/ingest",
    purpose: "Runs, Fehler und Seiten-Coverage je Quelle analysieren.",
    actions: [
      "Run-Status und Dauer pro Job einsehen",
      "Fehlgeschlagene Seiten mit Fehlerdetails prüfen",
      "Retry-Failures für fehlgeschlagene Seiten triggern",
      "Seitenstatus (pending/running/failed/...) filtern",
    ],
    tips: [
      "Bei vielen Fehlern zuerst robots/timeout/selectors prüfen.",
      "Auto-Refresh nur bei aktiven Jobs einschalten.",
      "Vergleiche failed und fetched_at für zeitliche Muster.",
    ],
  },
  {
    id: "search",
    title: "Such-Testkonsole",
    path: "/knowledge/search",
    purpose: "Hybrid- und Semantic-Retrieval mit Scores live testen.",
    actions: [
      "Queries im Hybrid-Modus gegen Trust/BM25/Semantic prüfen",
      "Min Score und Max Chunks feinjustieren",
      "Guardrail-Warnings und Konflikte analysieren",
      "Chunk-Details inkl. Score-Aufschlüsselung einsehen",
    ],
    tips: [
      "Starte mit min_score 0.20 und erhöhe schrittweise.",
      "Für Fehlersuche zuerst semantic-only testen.",
      "Bei Architekturfragen auf V3+ Quellenabdeckung achten.",
    ],
  },
  {
    id: "trust",
    title: "Trust Engine",
    path: "/knowledge/trust",
    purpose: "Trust-Klassen, Scoring-Logik und Hard Rules verstehen.",
    actions: [
      "V1-V5 Klassen und Eligibility je Kontext prüfen",
      "Kategorien und Composite-Score nachvollziehen",
      "Gewichte in der Hybrid-Formel interpretieren",
      "Hard Rules und Query-Kontext-Regeln prüfen",
    ],
    tips: [
      "V2 Draft ist in Produktion immer gesperrt.",
      "Community nie für Security/Compliance verwenden.",
      "V5/V4 Quellen für kritische Aussagen priorisieren.",
    ],
  },
  {
    id: "index",
    title: "Index & Coverage",
    path: "/knowledge/index",
    purpose: "Embedding-Coverage und Chunk-Inhalt operativ auditieren.",
    actions: [
      "Coverage-Quote und fehlende Embeddings überwachen",
      "Chunk-Verteilung je Quelle vergleichen",
      "Chunk-Browser mit Volltextfilter nutzen",
      "Chunk-Metadaten und Indizierungszeit kontrollieren",
    ],
    tips: [
      "Chunks ohne Embedding tauchen im Retrieval nicht auf.",
      "Nutze Volltextsuche für Delta-Analysen nach Re-Ingest.",
      "Achte auf unplausibel kurze Chunk-Texte als Extraktionssignal.",
    ],
  },
];

export default function KnowledgeHelpPage() {
  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase Hilfe</h1>
          <p className="text-sm text-gray-500 mt-1">
            Bedienhilfe und Best Practices fuer alle implementierten KnowledgeBase-Bereiche
          </p>
        </div>
      </div>

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
        Diese Seite beschreibt den operativen Ablauf vom Quellen-Onboarding bis zur Retrieval-Qualitaetspruefung.
        Fuer jeden Bereich findest du Zweck, Hauptaktionen und kurze Praxis-Tipps.
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

            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1">Tipps</p>
              <ul className="space-y-1">
                {s.tips.map((t) => (
                  <li key={t} className="text-sm text-gray-600">- {t}</li>
                ))}
              </ul>
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
