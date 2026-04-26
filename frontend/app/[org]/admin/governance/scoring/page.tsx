"use client";

import { use, useState } from "react";
import { BarChart3, Save } from "lucide-react";
import { useScoringSchemes, type ScoringScheme, type ScaleLabel } from "@/lib/hooks/useGovernance";
import { authFetch } from "@/lib/api/client";
import { mutate as globalMutate } from "swr";

interface PageProps {
  params: Promise<{ org: string }>;
}

const COLOR_OPTIONS = ["gray", "red", "amber", "green", "blue", "violet"];

const COLOR_MAP: Record<string, string> = {
  gray:   "bg-gray-100 text-gray-700",
  red:    "bg-red-100 text-red-700",
  amber:  "bg-amber-100 text-amber-700",
  green:  "bg-green-100 text-green-700",
  blue:   "bg-blue-100 text-blue-700",
  violet: "bg-violet-100 text-violet-700",
};

function ScoreLabelEditor({ label, onChange }: { label: ScaleLabel; onChange: (l: ScaleLabel) => void }) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
      <span className={`w-8 h-8 rounded flex items-center justify-center text-sm font-bold shrink-0 ${COLOR_MAP[label.color] ?? "bg-gray-100 text-gray-700"}`}>
        {label.value}
      </span>
      <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-2">
        <input
          type="text"
          value={label.label}
          onChange={e => onChange({ ...label, label: e.target.value })}
          placeholder="Bezeichnung"
          className="px-2 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
        />
        <input
          type="text"
          value={label.description}
          onChange={e => onChange({ ...label, description: e.target.value })}
          placeholder="Beschreibung"
          className="px-2 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
        />
        <select
          value={label.color}
          onChange={e => onChange({ ...label, color: e.target.value })}
          className="px-2 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
        >
          {COLOR_OPTIONS.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
    </div>
  );
}

function SchemeCard({ scheme }: { scheme: ScoringScheme }) {
  const [labels, setLabels] = useState<ScaleLabel[]>(scheme.scale_labels);
  const [trafficLight, setTrafficLight] = useState(scheme.traffic_light);
  const [formula, setFormula] = useState(scheme.formula ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await authFetch(`/api/v1/governance/scoring-schemes/${scheme.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scale_labels: labels, traffic_light: trafficLight, formula }),
      });
      await globalMutate("/api/v1/governance/scoring-schemes");
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)]">
        <div>
          <h2 className="text-sm font-semibold text-[var(--ink-strong)] flex items-center gap-2">
            {scheme.name}
            {scheme.is_default && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-violet-100 text-violet-700 font-medium">Standard</span>
            )}
          </h2>
          <p className="text-xs text-[var(--ink-muted)] mt-0.5">
            Skala {scheme.scale_min}–{scheme.scale_max} · {scheme.slug}
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg disabled:opacity-60"
        >
          <Save className="h-3.5 w-3.5" />
          {saving ? "Speichern…" : saved ? "✓ Gespeichert" : "Speichern"}
        </button>
      </div>

      <div className="p-5 space-y-5">
        {/* Scale labels */}
        <div>
          <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider mb-3">Bewertungsstufen</p>
          <div className="space-y-2">
            {labels.map((label, i) => (
              <ScoreLabelEditor
                key={label.value}
                label={label}
                onChange={l => {
                  const updated = [...labels];
                  updated[i] = l;
                  setLabels(updated);
                }}
              />
            ))}
          </div>
        </div>

        {/* Traffic light */}
        <div>
          <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider mb-3">Ampellogik</p>
          <div className="grid grid-cols-3 gap-3">
            {[
              { key: "green",  label: "Grün",  color: "bg-green-100 border-green-300" },
              { key: "yellow", label: "Gelb",  color: "bg-amber-100 border-amber-300" },
              { key: "red",    label: "Rot",   color: "bg-red-100 border-red-300"     },
            ].map(({ key, label, color }) => (
              <div key={key} className={`p-3 rounded-lg border ${color}`}>
                <p className="text-xs font-medium mb-2">{label}</p>
                <div className="space-y-1">
                  {["min_score", "max_score"].map(threshold => {
                    const tlGroup = trafficLight[key] as Record<string, number> ?? {};
                    if (threshold === "max_score" && key !== "red") return null;
                    if (threshold === "min_score" && key === "red") return null;
                    return (
                      <div key={threshold} className="flex items-center gap-1">
                        <span className="text-xs text-[var(--ink-muted)] w-16">
                          {threshold === "min_score" ? "ab ≥" : "bis ≤"}
                        </span>
                        <input
                          type="number" step={0.1} min={0} max={3}
                          value={tlGroup[threshold] ?? ""}
                          onChange={e => setTrafficLight(tl => ({
                            ...tl,
                            [key]: { ...(tl[key] as Record<string, unknown> ?? {}), [threshold]: parseFloat(e.target.value) }
                          }))}
                          className="w-16 px-2 py-1 text-xs bg-white border border-white/80 rounded"
                        />
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Formula */}
        <div>
          <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1 uppercase tracking-wider">
            Formel (Anzeige)
          </label>
          <input
            type="text"
            value={formula}
            onChange={e => setFormula(e.target.value)}
            placeholder="z.B. weighted_average(scores, weights)"
            className="w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg font-mono focus:outline-none focus:border-violet-400"
          />
        </div>

        {/* Preview */}
        <div className="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
          <p className="text-xs font-medium text-[var(--ink-muted)] mb-3 uppercase tracking-wider">Vorschau</p>
          <div className="flex gap-3 flex-wrap">
            {labels.map(l => (
              <div key={l.value} className={`px-3 py-2 rounded-lg text-sm ${COLOR_MAP[l.color] ?? ""}`}>
                <span className="font-bold">{l.value}</span>
                <span className="ml-1.5">{l.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ScoringPage({ params }: PageProps) {
  const { org } = use(params);
  const { data: schemes } = useScoringSchemes();

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <BarChart3 className="h-5 w-5 text-violet-500" />
          Scoring & Bewertungslogik
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Bewertungsskalen, Ampellogik und Formeln konfigurieren
        </p>
      </div>

      <div className="space-y-5">
        {!schemes || schemes.length === 0 ? (
          <div className="text-center py-12 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
            <BarChart3 className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-[var(--ink-muted)]">Keine Scoring-Schemas. Seed-Daten laden.</p>
          </div>
        ) : (
          schemes.map(s => <SchemeCard key={s.id} scheme={s} />)
        )}
      </div>
    </div>
  );
}
