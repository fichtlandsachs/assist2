"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api/client";

interface Signal { id: string; key: string; fact_category: string; pattern_type: string; pattern: string; confidence_boost: number; is_active: boolean; }

const CATEGORIES = ["context", "user_group", "problem", "benefit", "scope",
  "out_of_scope", "acceptance_criterion", "risk", "compliance", "dependency"];
const CAT_COLORS: Record<string, string> = {
  user_group: "#8b5cf6", problem: "#ef4444", benefit: "#22c55e",
  scope: "#f59e0b", out_of_scope: "#64748b", acceptance_criterion: "#06b6d4",
  risk: "#f97316", compliance: "#ec4899",
};

export default function ConversationSignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Signal | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ key: "", fact_category: "user_group", pattern_type: "keyword", pattern: "", confidence_boost: 0.2, is_active: true });

  async function load() {
    setLoading(true);
    try {
      const r = await authFetch("/api/v1/superadmin/conversation-engine/answer-signals");
      if (r.ok) {
        setSignals(await r.json());
        setError(null);
      } else if (r.status === 401) {
        setError("No session");
        if (typeof window !== "undefined") setTimeout(() => { window.location.href = "/login"; }, 1500);
      } else if (r.status === 403) {
        setError("Zugriff verweigert. Superadmin-Rechte erforderlich.");
      } else {
        const err = await r.json().catch(() => ({ detail: "Unbekannter Fehler" }));
        setError(typeof err.detail === "string" ? err.detail : err.error || `Fehler ${r.status}`);
      }
    } catch (e) {
      setError("Netzwerkfehler. Bitte prüfen Sie die Verbindung.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function save() {
    setSaving(true);
    const url = editing ? `/api/v1/superadmin/conversation-engine/answer-signals/${editing.id}` : "/api/v1/superadmin/conversation-engine/answer-signals";
    const res = await authFetch(url, { method: editing ? "PATCH" : "POST", body: JSON.stringify(form) });
    if (res.ok) { await load(); setOpen(false); }
    setSaving(false);
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>Antwortsignale</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-faint)" }}>
            Keyword- und Regex-Muster die Nutzertext Fact-Kategorien zuordnen
          </p>
        </div>
        <button onClick={() => { setEditing(null); setForm({ key: "", fact_category: "user_group", pattern_type: "keyword", pattern: "", confidence_boost: 0.2, is_active: true }); setOpen(true); }}
          className="neo-btn neo-btn--default neo-btn--sm">+ Neues Signal</button>
      </div>

      {loading ? <p style={{ color: "var(--ink-faint)" }}>Lade…</p> : error ? (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
          <button onClick={() => { setLoading(true); void load(); }} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
            Erneut versuchen
          </button>
        </div>
      ) : (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table text-sm">
            <thead><tr><th>Kategorie</th><th>Typ</th><th>Muster</th><th>Boost</th><th>Aktiv</th><th></th></tr></thead>
            <tbody>
              {signals.map(s => (
                <tr key={s.id}>
                  <td>
                    <span className="px-2 py-0.5 rounded-full text-xs"
                      style={{ background: (CAT_COLORS[s.fact_category] ?? "#94a3b8") + "22", color: CAT_COLORS[s.fact_category] ?? "#94a3b8" }}>
                      {s.fact_category}
                    </span>
                  </td>
                  <td className="text-xs" style={{ color: "var(--ink-faint)" }}>{s.pattern_type}</td>
                  <td><code className="text-xs" style={{ color: "var(--ink-mid)" }}>{s.pattern.slice(0, 60)}</code></td>
                  <td className="font-bold text-xs" style={{ color: "var(--ink)" }}>+{Math.round(s.confidence_boost * 100)}%</td>
                  <td>{s.is_active ? <span style={{ color: "#22c55e" }}>●</span> : <span style={{ color: "#94a3b8" }}>○</span>}</td>
                  <td>
                    <button onClick={() => {
                      setEditing(s);
                      setForm({ key: s.key, fact_category: s.fact_category, pattern_type: s.pattern_type, pattern: s.pattern, confidence_boost: s.confidence_boost, is_active: s.is_active });
                      setOpen(true);
                    }} className="neo-btn neo-btn--outline neo-btn--sm">Bearbeiten</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.4)" }}>
          <div className="ml-auto w-[420px] h-full overflow-y-auto shadow-2xl flex flex-col"
            style={{ background: "var(--paper)", borderLeft: "2px solid var(--paper-rule)" }}>
            <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "var(--paper-rule)" }}>
              <h2 className="font-bold text-sm">{editing ? "Signal bearbeiten" : "Neues Signal"}</h2>
              <button onClick={() => setOpen(false)} style={{ fontSize: 20, color: "var(--ink-faint)" }}>×</button>
            </div>
            <div className="flex-1 px-5 py-4 space-y-4">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Key</label>
                <input type="text" value={form.key} onChange={e => setForm(p => ({ ...p, key: e.target.value }))} className="neo-input w-full text-sm" placeholder="sig_user_group" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Fact-Kategorie</label>
                <select value={form.fact_category} onChange={e => setForm(p => ({ ...p, fact_category: e.target.value }))} className="neo-input w-full text-sm">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Typ</label>
                <select value={form.pattern_type} onChange={e => setForm(p => ({ ...p, pattern_type: e.target.value }))} className="neo-input w-full text-sm">
                  <option value="keyword">keyword</option>
                  <option value="regex">regex</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Muster (| für Alternativen)</label>
                <textarea value={form.pattern} onChange={e => setForm(p => ({ ...p, pattern: e.target.value }))}
                  rows={3} className="neo-input w-full text-sm font-mono resize-none" placeholder="als nutzer|als admin|als mitarbeiter" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Konfidenz-Boost (0.0 – 0.5)</label>
                <input type="number" min={0} max={0.5} step={0.05} value={form.confidence_boost}
                  onChange={e => setForm(p => ({ ...p, confidence_boost: Number(e.target.value) }))} className="neo-input w-full text-sm" />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
                <span>Aktiv</span>
              </label>
            </div>
            <div className="px-5 py-4 border-t flex gap-3" style={{ borderColor: "var(--paper-rule)" }}>
              <button onClick={() => void save()} disabled={saving} className="neo-btn neo-btn--default">{saving ? "Speichern…" : "Speichern"}</button>
              <button onClick={() => setOpen(false)} className="neo-btn neo-btn--outline">Abbrechen</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
