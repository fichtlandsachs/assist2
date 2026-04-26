"use client";

import { use, useState } from "react";
import { GitMerge, Edit2, Save, X, AlertTriangle, CheckCircle } from "lucide-react";
import { useGates, updateGate, type GateDefinition } from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string }>;
}

const GATE_COLORS: Record<string, { bg: string; border: string; dot: string }> = {
  G1: { bg: "bg-sky-50",     border: "border-sky-200",     dot: "bg-sky-400" },
  G2: { bg: "bg-violet-50",  border: "border-violet-200",  dot: "bg-violet-500" },
  G3: { bg: "bg-amber-50",   border: "border-amber-200",   dot: "bg-amber-500" },
  G4: { bg: "bg-emerald-50", border: "border-emerald-200", dot: "bg-emerald-500" },
};

function GateCard({ gate, onSave }: { gate: GateDefinition; onSave: (id: string, data: Record<string, unknown>) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Partial<GateDefinition>>({});
  const [saving, setSaving] = useState(false);
  const colors = GATE_COLORS[gate.phase] ?? GATE_COLORS.G1;

  const val = (key: keyof GateDefinition) =>
    form[key] !== undefined ? form[key] : gate[key];

  const set = (key: keyof GateDefinition, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleSave = async () => {
    setSaving(true);
    try {
      await onSave(gate.id, form);
      setEditing(false);
      setForm({});
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const cls = "w-full px-3 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded focus:outline-none focus:border-violet-400";

  return (
    <div className={`rounded-xl border-2 ${colors.border} ${colors.bg} overflow-hidden`}>
      {/* Gate Header */}
      <div className="flex items-center gap-3 px-5 py-4">
        <div className={`w-10 h-10 rounded-lg ${colors.dot} flex items-center justify-center`}>
          <span className="text-white font-bold text-sm">{gate.phase}</span>
        </div>
        <div className="flex-1">
          <h2 className="text-base font-semibold text-[var(--ink-strong)]">{gate.name}</h2>
          <p className="text-xs text-[var(--ink-muted)]">v{gate.version} · {gate.status}</p>
        </div>
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded-lg hover:border-violet-400 transition-colors"
          >
            <Edit2 className="h-3.5 w-3.5" /> Bearbeiten
          </button>
        ) : (
          <div className="flex gap-2">
            <button onClick={handleSave} disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-violet-600 text-white rounded-lg disabled:opacity-60">
              <Save className="h-3.5 w-3.5" />
              {saving ? "Speichern…" : "Speichern"}
            </button>
            <button onClick={() => { setEditing(false); setForm({}); }}
              className="p-1.5 rounded-lg hover:bg-white">
              <X className="h-4 w-4 text-[var(--ink-muted)]" />
            </button>
          </div>
        )}
      </div>

      {/* Gate Body */}
      <div className="px-5 pb-5 grid grid-cols-1 md:grid-cols-2 gap-4 border-t border-white/60">
        <div className="pt-4 space-y-3">
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Beschreibung</p>
            {editing ? (
              <textarea className={cls + " resize-y"} rows={3}
                value={val("description") as string ?? ""}
                onChange={e => set("description", e.target.value)} />
            ) : (
              <p className="text-sm text-[var(--ink-mid)]">{gate.description ?? "–"}</p>
            )}
          </div>
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Mindest-Gesamtscore</p>
            {editing ? (
              <input type="number" step={0.1} min={0} max={3} className="w-24 px-3 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded"
                value={val("min_total_score") as number ?? ""}
                onChange={e => set("min_total_score", parseFloat(e.target.value))} />
            ) : (
              <p className="text-sm font-bold text-[var(--ink-strong)]">
                {gate.min_total_score !== null ? `≥ ${gate.min_total_score}` : "–"}
              </p>
            )}
          </div>
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Hard-Stop-Schwellwert</p>
            {editing ? (
              <input type="number" min={0} max={3} className="w-24 px-3 py-1.5 text-sm bg-white border border-[var(--border-subtle)] rounded"
                value={val("hard_stop_threshold") as number ?? 1}
                onChange={e => set("hard_stop_threshold", parseInt(e.target.value))} />
            ) : (
              <p className="text-sm text-[var(--ink-mid)]">Score ≤ {gate.hard_stop_threshold} → Block</p>
            )}
          </div>
        </div>

        <div className="pt-4 space-y-3">
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Freigaberollen</p>
            {editing ? (
              <textarea className={cls + " resize-y"} rows={2}
                value={(val("approver_roles") as string[] ?? []).join("\n")}
                onChange={e => set("approver_roles", e.target.value.split("\n").filter(Boolean))}
                placeholder="Eine Rolle pro Zeile" />
            ) : (
              <div className="flex flex-wrap gap-1">
                {(gate.approver_roles ?? []).map((r, i) => (
                  <span key={i} className="px-2 py-0.5 bg-white border border-[var(--border-subtle)] rounded text-xs text-[var(--ink-mid)]">
                    {r}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Pflicht-Controls (Slugs)</p>
            {editing ? (
              <textarea className={cls + " resize-y"} rows={3}
                value={(val("required_fixed_control_slugs") as string[] ?? []).join("\n")}
                onChange={e => set("required_fixed_control_slugs", e.target.value.split("\n").filter(Boolean))}
                placeholder="Einen Slug pro Zeile" />
            ) : (
              <div className="flex flex-wrap gap-1 max-h-24 overflow-auto">
                {(gate.required_fixed_control_slugs ?? []).map((s, i) => (
                  <span key={i} className="px-2 py-0.5 bg-white border border-[var(--border-subtle)] rounded text-xs font-mono text-[var(--ink-mid)]">
                    {s}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Outcomes */}
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-2">Mögliche Ergebnisse</p>
            <div className="flex gap-2">
              {[
                { key: "go",             label: "Go",              color: "bg-green-100 text-green-700" },
                { key: "conditional_go", label: "Conditional Go",  color: "bg-amber-100 text-amber-700" },
                { key: "no_go",          label: "No Go",           color: "bg-red-100 text-red-700"    },
              ].map(({ key, label, color }) => (
                <span key={key} className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium ${color}`}>
                  {key === "go" ? <CheckCircle className="h-3 w-3" /> : key === "no_go" ? <AlertTriangle className="h-3 w-3" /> : null}
                  {label}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {editing && (
        <div className="px-5 pb-4">
          <label className="block text-xs font-medium mb-1 text-[var(--ink-muted)]">Änderungsgrund</label>
          <input className={cls}
            placeholder="Kurze Begründung für die Änderung"
            onChange={e => set("change_reason" as keyof GateDefinition, e.target.value)} />
        </div>
      )}
    </div>
  );
}

export default function GatesPage({ params }: PageProps) {
  const { org } = use(params);
  const { data: gates, mutate } = useGates();

  const handleSave = async (id: string, data: Record<string, unknown>) => {
    await updateGate(id, data);
    mutate();
  };

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <GitMerge className="h-5 w-5 text-violet-500" />
          Gate-Modelle
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          G1–G4 Freigabetore — Anforderungen, Scores und Freigaberollen
        </p>
      </div>

      {/* Gate flow visualization */}
      <div className="flex items-center gap-2 overflow-x-auto py-2">
        {["G1", "G2", "G3", "G4"].map((g, i) => (
          <div key={g} className="flex items-center gap-2 shrink-0">
            <div className={`px-4 py-2 rounded-lg text-sm font-semibold ${GATE_COLORS[g].bg} border ${GATE_COLORS[g].border} text-[var(--ink-strong)]`}>
              {g}
            </div>
            {i < 3 && <span className="text-[var(--ink-muted)]">→</span>}
          </div>
        ))}
      </div>

      {/* Gate Cards */}
      <div className="space-y-5">
        {!gates || gates.length === 0 ? (
          <div className="text-center py-12 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
            <GitMerge className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-[var(--ink-muted)]">Keine Gate-Definitionen gefunden. Bitte Seed-Daten laden.</p>
          </div>
        ) : (
          gates.map(gate => (
            <GateCard key={gate.id} gate={gate} onSave={handleSave} />
          ))
        )}
      </div>
    </div>
  );
}
