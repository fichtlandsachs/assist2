"use client";

import { useState } from "react";
import Link from "next/link";

const TRUST_CLASSES = [
  {
    id: "V5",
    label: "V5 — Verbindlich",
    color: "bg-purple-600",
    textColor: "text-purple-700",
    bgLight: "bg-purple-50",
    border: "border-purple-200",
    description: "Höchste Autorität. Hersteller-Dokumentation und Normen/Standards. Ergebnis hat Vorrang vor allen anderen Quellen.",
    categories: ["manufacturer", "standard_norm"],
    eligible: { security: true, compliance: true, general: true, architecture: true },
    badge: "Alle Kontexte",
    badgeCls: "bg-green-100 text-green-700",
  },
  {
    id: "V4",
    label: "V4 — Offiziell freigegeben",
    color: "bg-blue-600",
    textColor: "text-blue-700",
    bgLight: "bg-blue-50",
    border: "border-blue-200",
    description: "Intern freigegebene Dokumentation. Führend für eigene Prozesse und Entscheidungen.",
    categories: ["internal_approved"],
    eligible: { security: true, compliance: true, general: true, architecture: true },
    badge: "Alle Kontexte",
    badgeCls: "bg-green-100 text-green-700",
  },
  {
    id: "V3",
    label: "V3 — Geprüfte externe Quelle",
    color: "bg-teal-600",
    textColor: "text-teal-700",
    bgLight: "bg-teal-50",
    border: "border-teal-200",
    description: "Partner-Dokumentation, extern geprüfte Quellen. Für allgemeine und Architektur-Kontexte geeignet.",
    categories: ["partner"],
    eligible: { security: false, compliance: false, general: true, architecture: true },
    badge: "General + Architektur",
    badgeCls: "bg-blue-100 text-blue-700",
  },
  {
    id: "V2",
    label: "V2 — Intern (Entwurf)",
    color: "bg-yellow-500",
    textColor: "text-yellow-700",
    bgLight: "bg-yellow-50",
    border: "border-yellow-200",
    description: "Interne Entwürfe / ungeprüfte interne Dokumente. In Produktionsmodus vollständig gesperrt.",
    categories: ["internal_draft"],
    eligible: { security: false, compliance: false, general: false, architecture: false },
    badge: "NICHT produktiv",
    badgeCls: "bg-red-100 text-red-700",
  },
  {
    id: "V1",
    label: "V1 — Community / unterstützend",
    color: "bg-gray-500",
    textColor: "text-gray-700",
    bgLight: "bg-gray-50",
    border: "border-gray-200",
    description: "Community-Quellen. Nie für Security- oder Compliance-Kontexte. Nur unterstützende Rolle.",
    categories: ["community"],
    eligible: { security: false, compliance: false, general: true, architecture: false },
    badge: "Nur General",
    badgeCls: "bg-gray-100 text-gray-600",
  },
];

const CATEGORY_PROFILES: Record<string, {
  label: string;
  trust_class: string;
  scores: Record<string, number>;
  description: string;
}> = {
  manufacturer: {
    label: "Hersteller-Dokumentation",
    trust_class: "V5",
    description: "z. B. SAP Help Portal, Salesforce Docs, Microsoft Learn — führend für Produktstandards",
    scores: { authority: 0.95, standard: 0.90, context: 0.80, freshness: 0.70, governance: 0.85, traceability: 0.90 },
  },
  internal_approved: {
    label: "Intern freigegeben",
    trust_class: "V4",
    description: "Freigegebene interne Prozessdokumentation, Handbücher, Betriebsanweisungen",
    scores: { authority: 0.85, standard: 0.70, context: 0.90, freshness: 0.75, governance: 0.80, traceability: 0.85 },
  },
  standard_norm: {
    label: "Norm / Standard",
    trust_class: "V5",
    description: "ISO-Normen, NIST, BPMN-Standard — methodisch höchste Autorität",
    scores: { authority: 0.90, standard: 0.95, context: 0.75, freshness: 0.65, governance: 0.90, traceability: 0.85 },
  },
  partner: {
    label: "Partner-Dokumentation",
    trust_class: "V3",
    description: "Externe Partner-Doku, Integration-Guides von zertifizierten Partnern",
    scores: { authority: 0.65, standard: 0.60, context: 0.65, freshness: 0.60, governance: 0.55, traceability: 0.60 },
  },
  internal_draft: {
    label: "Intern (Entwurf)",
    trust_class: "V2",
    description: "Interne Entwurfsdokumente — im Produktionsmodus vollständig gesperrt",
    scores: { authority: 0.50, standard: 0.40, context: 0.60, freshness: 0.60, governance: 0.30, traceability: 0.40 },
  },
  community: {
    label: "Community",
    trust_class: "V1",
    description: "StackOverflow, Community-Foren — nur unterstützend, nie für Security/Compliance",
    scores: { authority: 0.30, standard: 0.25, context: 0.40, freshness: 0.40, governance: 0.15, traceability: 0.20 },
  },
};

const SCORING_WEIGHTS = [
  { dim: "authority", label: "Authority", weight: 0.25, desc: "Wie maßgeblich ist die Quelle für das Thema?" },
  { dim: "standard", label: "Standard-Konformität", weight: 0.20, desc: "Einhaltung von Normen und Standards" },
  { dim: "context", label: "Kontextrelevanz", weight: 0.20, desc: "Passt der Inhalt zum Query-Kontext?" },
  { dim: "freshness", label: "Aktualität", weight: 0.15, desc: "Wie aktuell ist der Inhalt (age_days / 365)?" },
  { dim: "governance", label: "Governance", weight: 0.10, desc: "Dokumentierte Pflege- und Freigabeprozesse" },
  { dim: "traceability", label: "Nachvollziehbarkeit", weight: 0.10, desc: "Quellen- und Änderungsnachverfolgung" },
];

const HARD_RULES = [
  { rule: "Entwürfe immer gesperrt", desc: "internal_draft-Quellen sind in der Produktionsumgebung vollständig gesperrt (is_global ignoriert).", cls: "bg-red-50 border-red-200 text-red-800" },
  { rule: "Community nie für Security/Compliance", desc: "community-Quellen können bei Security- oder Compliance-Anfragen nie genutzt werden — unabhängig vom Score.", cls: "bg-orange-50 border-orange-200 text-orange-800" },
  { rule: "Architektur-Guard: mind. 2 V3+-Quellen", desc: "Für Architektur-Anfragen müssen mind. 2 Chunks mit Trust-Class ≥ V3 vorliegen, sonst erscheint eine Guardrail-Warnung.", cls: "bg-yellow-50 border-yellow-200 text-yellow-800" },
  { rule: "ExternalSource.is_enabled-Gate", desc: "Chunks einer deaktivierten Quelle werden sofort aus dem pgvector-Index entfernt und sind nicht retrieval-fähig.", cls: "bg-blue-50 border-blue-200 text-blue-800" },
];

const HYBRID_WEIGHTS = [
  { label: "Semantic (Embedding)", weight: 0.35, color: "bg-blue-500" },
  { label: "Keyword (BM25)", weight: 0.15, color: "bg-teal-500" },
  { label: "Entity Match", weight: 0.15, color: "bg-green-500" },
  { label: "Trust", weight: 0.20, color: "bg-purple-500" },
  { label: "Kontext-Match", weight: 0.10, color: "bg-orange-400" },
  { label: "Aktualität", weight: 0.05, color: "bg-yellow-400" },
];

function ScoreBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex-1 bg-gray-200 rounded-full h-1.5">
      <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${value * 100}%` }} />
    </div>
  );
}

function TrustClassCard({ tc }: { tc: typeof TRUST_CLASSES[number] }) {
  return (
    <div className={`border ${tc.border} rounded-lg overflow-hidden`}>
      <div className={`${tc.bgLight} px-4 py-3 flex items-center justify-between`}>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-2 py-0.5 rounded text-white ${tc.color}`}>{tc.id}</span>
          <span className={`font-semibold text-sm ${tc.textColor}`}>{tc.label}</span>
        </div>
        <span className={`text-xs px-2 py-0.5 rounded-full ${tc.badgeCls}`}>{tc.badge}</span>
      </div>
      <div className="px-4 py-3 space-y-2">
        <p className="text-sm text-gray-700">{tc.description}</p>
        <div className="flex gap-2 flex-wrap">
          {tc.categories.map(c => (
            <span key={c} className="text-xs bg-white border px-2 py-0.5 rounded">{c}</span>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 pt-1">
          {(Object.entries(tc.eligible) as [string, boolean][]).map(([ctx, ok]) => (
            <div key={ctx} className="flex items-center gap-1.5 text-xs">
              <span className={`w-4 h-4 rounded-full flex items-center justify-center text-white text-xs ${ok ? "bg-green-500" : "bg-red-400"}`}>
                {ok ? "✓" : "✗"}
              </span>
              <span className="text-gray-600 capitalize">{ctx}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function CategoryProfileCard({ key: catKey, profile }: { key: string; profile: typeof CATEGORY_PROFILES[string] }) {
  const composite = Object.entries(profile.scores).reduce((acc, [dim, v]) => {
    const w = SCORING_WEIGHTS.find(s => s.dim === dim)?.weight ?? 0;
    return acc + w * v;
  }, 0);
  const tc = TRUST_CLASSES.find(t => t.id === profile.trust_class);

  return (
    <div className="bg-white border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-semibold text-sm">{profile.label}</span>
          {tc && (
            <span className={`ml-2 text-xs font-bold px-1.5 py-0.5 rounded text-white ${tc.color}`}>{tc.id}</span>
          )}
        </div>
        <span className="text-xs font-mono text-gray-500">Score: {composite.toFixed(3)}</span>
      </div>
      <p className="text-xs text-gray-500">{profile.description}</p>
      <div className="space-y-1.5">
        {SCORING_WEIGHTS.map(w => (
          <div key={w.dim} className="flex items-center gap-2 text-xs">
            <span className="w-28 text-gray-500 shrink-0">{w.label}</span>
            <ScoreBar value={profile.scores[w.dim] ?? 0} color="bg-blue-400" />
            <span className="font-mono w-8 text-right text-gray-700">{(profile.scores[w.dim] ?? 0).toFixed(2)}</span>
            <span className="text-gray-300 w-10 text-right">×{w.weight}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TrustPage() {
  const [tab, setTab] = useState<"classes" | "profiles" | "scoring" | "rules">("classes");

  const tabs = [
    { id: "classes" as const, label: "Trust-Klassen V1–V5" },
    { id: "profiles" as const, label: "Quellkategorien" },
    { id: "scoring" as const, label: "Scoring-Formel" },
    { id: "rules" as const, label: "Hard Rules" },
  ];

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase — Trust Engine</h1>
          <p className="text-sm text-gray-500 mt-1">
            Multi-dimensionale Quellenbewertung · 6 Scoring-Dimensionen · Hard Eligibility Rules
          </p>
        </div>
        <Link
          href="/knowledge/help#trust"
          className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50 shrink-0"
        >
          Hilfe
        </Link>
      </div>

      <div className="flex border-b border-gray-200">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{t.label}</button>
        ))}
      </div>

      {tab === "classes" && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
            <strong>Trust-Klassen</strong> bestimmen die Retrieval-Berechtigung einer Quelle.
            Klasse V5 hat Vorrang bei Konflikten. Hard Rules sperren bestimmte Klassen für bestimmte Kontexte vollständig.
          </div>
          {TRUST_CLASSES.map(tc => <TrustClassCard key={tc.id} tc={tc} />)}
        </div>
      )}

      {tab === "profiles" && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
            Jede Quellkategorie hat Standard-Trust-Dimensionen. Der <strong>Composite Score</strong> ergibt sich als
            gewichtete Summe aller 6 Dimensionen und steuert das Ranking im Hybrid Retrieval.
          </div>
          {Object.entries(CATEGORY_PROFILES).map(([k, p]) => (
            <CategoryProfileCard key={k} profile={p} />
          ))}
        </div>
      )}

      {tab === "scoring" && (
        <div className="space-y-4">
          <div className="bg-white border rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-sm">Hybrid Retrieval — Score-Formel</h3>
            <code className="block bg-gray-50 border rounded p-3 text-sm font-mono">
              final_score = semantic×0.35 + keyword×0.15 + entity×0.15 + trust×0.20 + context×0.10 + freshness×0.05
            </code>
            <div className="space-y-2">
              {HYBRID_WEIGHTS.map(w => (
                <div key={w.label} className="flex items-center gap-3 text-sm">
                  <div className="flex items-center gap-2 flex-1">
                    <div className={`w-3 h-3 rounded ${w.color} shrink-0`} />
                    <span>{w.label}</span>
                  </div>
                  <div className="w-48 bg-gray-100 rounded-full h-2">
                    <div className={`h-2 rounded-full ${w.color}`} style={{ width: `${w.weight * 100 / 0.35}%` }} />
                  </div>
                  <span className="font-mono text-xs w-8 text-right">{(w.weight * 100).toFixed(0)}%</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border rounded-lg p-4 space-y-3">
            <h3 className="font-semibold text-sm">Trust Score — Composite-Berechnung</h3>
            <code className="block bg-gray-50 border rounded p-3 text-sm font-mono">
              trust_score = authority×0.25 + standard×0.20 + context×0.20 + freshness×0.15 + governance×0.10 + traceability×0.10
            </code>
            <div className="space-y-1.5">
              {SCORING_WEIGHTS.map(w => (
                <div key={w.dim} className="flex items-start gap-3 text-sm">
                  <span className="w-36 text-gray-700 shrink-0">{w.label} ({(w.weight * 100).toFixed(0)}%)</span>
                  <span className="text-gray-500 text-xs mt-0.5">{w.desc}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border rounded-lg p-4 space-y-2">
            <h3 className="font-semibold text-sm">Freshness-Berechnung</h3>
            <code className="block bg-gray-50 border rounded p-3 text-sm font-mono">
              freshness = max(0.1, 1.0 - age_days / 365.0)
            </code>
            <p className="text-sm text-gray-600">
              Chunks verlieren über ein Jahr langsam ihren Freshness-Score (10% Minimum).
              Freshness fließt mit 5% in den Final Score ein.
            </p>
          </div>
        </div>
      )}

      {tab === "rules" && (
        <div className="space-y-3">
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-4 text-sm text-blue-800">
            <strong>Hard Rules</strong> werden vor dem Scoring geprüft. Eine verletzte Hard Rule
            schließt die Quelle unabhängig vom Score vollständig aus dem Retrieval aus.
          </div>
          {HARD_RULES.map((r, i) => (
            <div key={i} className={`border rounded-lg p-4 ${r.cls}`}>
              <p className="font-semibold text-sm mb-1">{r.rule}</p>
              <p className="text-sm">{r.desc}</p>
            </div>
          ))}
          <div className="bg-white border rounded-lg p-4 space-y-2">
            <h3 className="font-semibold text-sm">Query-Kontext-Klassifikation</h3>
            <p className="text-sm text-gray-600">
              Jede Suchanfrage wird automatisch einem oder mehreren Kontexten zugeordnet (Regex-basiert):
            </p>
            <div className="space-y-1.5 mt-2">
              {[
                { ctx: "security", desc: "security, permission, auth, oauth, mfa, encrypt, role, firewall, …" },
                { ctx: "compliance", desc: "compliance, audit, regulation, GDPR, SOX, ISO 27001, certification, …" },
                { ctx: "architecture", desc: "architecture, integration, API, middleware, event-driven, deployment, …" },
                { ctx: "general", desc: "Alle anderen Anfragen (immer vorhanden)" },
              ].map(({ ctx, desc }) => (
                <div key={ctx} className="flex gap-2 text-xs">
                  <code className="bg-gray-100 text-gray-700 px-1.5 py-0.5 rounded font-mono shrink-0">{ctx}</code>
                  <span className="text-gray-500">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
