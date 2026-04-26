"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type RetrievalMode = "hybrid" | "semantic";
type PresetKey = "balanced" | "precision" | "recall" | "architecture";

interface RetrievalPreset {
  label: string;
  mode: RetrievalMode;
  minScore: number;
  maxChunks: number;
  notes: string[];
}

const PRESETS: Record<PresetKey, RetrievalPreset> = {
  balanced: {
    label: "Balanced",
    mode: "hybrid",
    minScore: 0.2,
    maxChunks: 8,
    notes: [
      "Standardprofil fuer die meisten Fachanfragen.",
      "Gute Balance zwischen Recall und Praezision.",
    ],
  },
  precision: {
    label: "Precision",
    mode: "hybrid",
    minScore: 0.45,
    maxChunks: 5,
    notes: [
      "Nur starke Treffer werden gezeigt.",
      "Geeignet fuer kritische Entscheidungen und Governance-Fragen.",
    ],
  },
  recall: {
    label: "Recall",
    mode: "hybrid",
    minScore: 0.1,
    maxChunks: 12,
    notes: [
      "Breiter Suchraum fuer Exploration.",
      "Erhoeht Trefferanzahl auf Kosten der Treffergenauigkeit.",
    ],
  },
  architecture: {
    label: "Architecture Guard",
    mode: "hybrid",
    minScore: 0.3,
    maxChunks: 10,
    notes: [
      "Optimiert fuer Architekturfragen mit V3+-Quellen.",
      "In Kombination mit Trust Engine und Guardrail-Warnungen nutzen.",
    ],
  },
};

const STORAGE_KEY = "kb_retrieval_settings";

export default function Page() {
  const [preset, setPreset] = useState<PresetKey>("balanced");
  const [mode, setMode] = useState<RetrievalMode>(PRESETS.balanced.mode);
  const [minScore, setMinScore] = useState(String(PRESETS.balanced.minScore));
  const [maxChunks, setMaxChunks] = useState(String(PRESETS.balanced.maxChunks));
  const [orgIdDefault, setOrgIdDefault] = useState("");
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        preset?: PresetKey;
        mode?: RetrievalMode;
        minScore?: number;
        maxChunks?: number;
        orgIdDefault?: string;
        savedAt?: string;
      };
      if (parsed.preset && PRESETS[parsed.preset]) setPreset(parsed.preset);
      if (parsed.mode) setMode(parsed.mode);
      if (typeof parsed.minScore === "number") setMinScore(String(parsed.minScore));
      if (typeof parsed.maxChunks === "number") setMaxChunks(String(parsed.maxChunks));
      if (parsed.orgIdDefault) setOrgIdDefault(parsed.orgIdDefault);
      if (parsed.savedAt) setSavedAt(parsed.savedAt);
    } catch {
      // ignore malformed local storage
    }
  }, []);

  const parsedMinScore = useMemo(() => {
    const v = parseFloat(minScore);
    if (Number.isNaN(v)) return 0.2;
    return Math.min(1, Math.max(0, v));
  }, [minScore]);

  const parsedMaxChunks = useMemo(() => {
    const v = parseInt(maxChunks, 10);
    if (Number.isNaN(v)) return 8;
    return Math.min(20, Math.max(1, v));
  }, [maxChunks]);

  const qualityHint = useMemo(() => {
    if (parsedMinScore >= 0.45) return "Sehr praezise, geringer Recall";
    if (parsedMinScore >= 0.3) return "Praezise";
    if (parsedMinScore >= 0.2) return "Ausgewogen";
    return "Breiter Recall, mehr Rauschen moeglich";
  }, [parsedMinScore]);

  function applyPreset(nextPreset: PresetKey) {
    const p = PRESETS[nextPreset];
    setPreset(nextPreset);
    setMode(p.mode);
    setMinScore(String(p.minScore));
    setMaxChunks(String(p.maxChunks));
    setDirty(true);
  }

  function saveSettings() {
    const payload = {
      preset,
      mode,
      minScore: parsedMinScore,
      maxChunks: parsedMaxChunks,
      orgIdDefault: orgIdDefault.trim(),
      savedAt: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    setSavedAt(payload.savedAt);
    setDirty(false);
  }

  function resetDefaults() {
    const p = PRESETS.balanced;
    setPreset("balanced");
    setMode(p.mode);
    setMinScore(String(p.minScore));
    setMaxChunks(String(p.maxChunks));
    setOrgIdDefault("");
    setDirty(true);
  }

  const searchLink = `/knowledge/search?mode=${mode}&minScore=${parsedMinScore}&maxChunks=${parsedMaxChunks}${
    orgIdDefault.trim() ? `&orgId=${encodeURIComponent(orgIdDefault.trim())}` : ""
  }`;

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>KnowledgeBase - Retrieval-Regeln</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
            Retrieval-Konfiguration (Presets, Schwellwerte, Guardrail-orientierte Abstimmung)
          </p>
        </div>
        <Link
          href="/knowledge/help#search"
          className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50 shrink-0"
        >
          Hilfe
        </Link>
      </div>

      <div className="neo-card p-4 space-y-4">
        <div>
          <p className="text-xs font-semibold mb-2" style={{ color: "var(--ink-mid)" }}>Preset</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {(Object.keys(PRESETS) as PresetKey[]).map((k) => (
              <button
                key={k}
                onClick={() => applyPreset(k)}
                className="neo-btn neo-btn--outline neo-btn--sm justify-center"
                style={{
                  borderColor: preset === k ? "var(--accent-red)" : undefined,
                  color: preset === k ? "var(--ink)" : undefined,
                }}
              >
                {PRESETS[k].label}
              </button>
            ))}
          </div>
          <ul className="mt-2 space-y-1">
            {PRESETS[preset].notes.map((n) => (
              <li key={n} className="text-xs" style={{ color: "var(--ink-faint)" }}>- {n}</li>
            ))}
          </ul>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
              Retrieval-Modus
            </label>
            <select
              className="neo-input w-full text-sm"
              value={mode}
              onChange={(e) => { setMode(e.target.value as RetrievalMode); setDirty(true); }}
            >
              <option value="hybrid">hybrid (Semantic + BM25 + Trust)</option>
              <option value="semantic">semantic (nur Embedding)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
              Standard Org-ID (optional)
            </label>
            <input
              className="neo-input w-full text-sm font-mono"
              value={orgIdDefault}
              onChange={(e) => { setOrgIdDefault(e.target.value); setDirty(true); }}
              placeholder="UUID oder leer"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
              min_score (0.0 - 1.0)
            </label>
            <input
              className="neo-input w-full text-sm"
              value={minScore}
              onChange={(e) => { setMinScore(e.target.value); setDirty(true); }}
            />
            <p className="text-xs mt-1" style={{ color: "var(--ink-faint)" }}>
              Qualitaetsprofil: <span style={{ color: "var(--ink)" }}>{qualityHint}</span>
            </p>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
              max_chunks (1 - 20)
            </label>
            <input
              className="neo-input w-full text-sm"
              value={maxChunks}
              onChange={(e) => { setMaxChunks(e.target.value); setDirty(true); }}
            />
            <p className="text-xs mt-1" style={{ color: "var(--ink-faint)" }}>
              Hoehere Werte steigern Kontextabdeckung, aber auch Prompt-Laenge.
            </p>
          </div>
        </div>

        <div className="neo-card p-3" style={{ background: "var(--paper-warm)" }}>
          <p className="text-xs font-semibold mb-1" style={{ color: "var(--ink-mid)" }}>Wirksamkeit (Richtwerte)</p>
          <ul className="space-y-1">
            <li className="text-xs" style={{ color: "var(--ink-faint)" }}>- Direct Threshold bleibt bei 0.92 (Backend-seitig fixiert).</li>
            <li className="text-xs" style={{ color: "var(--ink-faint)" }}>- Context Threshold basiert auf min_score, mindestens 0.20.</li>
            <li className="text-xs" style={{ color: "var(--ink-faint)" }}>- Architektur-Queries profitieren von max_chunks 8-12 und hybrid mode.</li>
            <li className="text-xs" style={{ color: "var(--ink-faint)" }}>- Trust Guardrails gelten unabhaengig von diesen UI-Defaults.</li>
          </ul>
        </div>

        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="text-xs" style={{ color: "var(--ink-faint)" }}>
            {savedAt ? `Zuletzt gespeichert: ${new Date(savedAt).toLocaleString("de-DE")}` : "Noch nicht gespeichert"}
            {dirty ? " · Ungespeicherte Aenderungen" : ""}
          </div>
          <div className="flex gap-2">
            <button onClick={resetDefaults} className="neo-btn neo-btn--outline neo-btn--sm">Reset</button>
            <button onClick={saveSettings} className="neo-btn neo-btn--default neo-btn--sm">Speichern</button>
            <Link href={searchLink} className="neo-btn neo-btn--outline neo-btn--sm">
              In Such-Testkonsole uebernehmen
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
