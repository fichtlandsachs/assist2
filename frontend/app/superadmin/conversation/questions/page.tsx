"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api/client";

interface QuestionBlock {
  id: string;
  key: string;
  category: string;
  label: string;
  question_text: string;
  follow_up_text: string | null;
  priority: number;
  is_required: boolean;
  is_active: boolean;
  version: number;
}

const CATEGORIES = ["context", "user_group", "problem", "benefit", "scope",
  "out_of_scope", "acceptance_criterion", "risk", "compliance", "dependency"];
const CAT_COLORS: Record<string, string> = {
  context: "#3b82f6", user_group: "#8b5cf6", problem: "#ef4444",
  benefit: "#22c55e", scope: "#f59e0b", out_of_scope: "#64748b",
  acceptance_criterion: "#06b6d4", risk: "#f97316", compliance: "#ec4899", dependency: "#a78bfa",
};

export default function ConversationQuestionsPage() {
  const [blocks, setBlocks] = useState<QuestionBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [catFilter, setCatFilter] = useState("");
  const [editing, setEditing] = useState<QuestionBlock | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    key: "", category: "user_group", label: "", question_text: "",
    follow_up_text: "", priority: 3, is_required: false, is_active: true,
  });

  async function load() {
    setLoading(true);
    try {
      const r = await authFetch("/api/v1/superadmin/conversation-engine/question-blocks");
      if (r.ok) {
        setBlocks(await r.json());
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

  const filtered = catFilter ? blocks.filter(b => b.category === catFilter) : blocks;
  const categories = [...new Set(blocks.map(b => b.category))];

  function openEdit(b: QuestionBlock) {
    setForm({ key: b.key, category: b.category, label: b.label, question_text: b.question_text,
      follow_up_text: b.follow_up_text ?? "", priority: b.priority, is_required: b.is_required, is_active: b.is_active });
    setEditing(b);
    setOpen(true);
  }
  function openCreate() {
    setForm({ key: "", category: "user_group", label: "", question_text: "", follow_up_text: "", priority: 3, is_required: false, is_active: true });
    setEditing(null);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    const url = editing ? `/api/v1/superadmin/conversation-engine/question-blocks/${editing.id}` : "/api/v1/superadmin/conversation-engine/question-blocks";
    const res = await authFetch(url, { method: editing ? "PATCH" : "POST", body: JSON.stringify(form) });
    if (res.ok) { await load(); setOpen(false); }
    setSaving(false);
  }

  async function deactivate(id: string) {
    await authFetch(`/api/v1/superadmin/conversation-engine/question-blocks/${id}`, { method: "DELETE" });
    await load();
  }

  return (
    <div className="max-w-4xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>Fragebausteine</h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--ink-faint)" }}>
            Fragen die der Question Planner bei fehlenden Informationen stellt
          </p>
        </div>
        <button onClick={openCreate} className="neo-btn neo-btn--default neo-btn--sm">+ Neuer Fragebaustein</button>
      </div>

      {/* Category filter */}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => setCatFilter("")}
          className="px-3 py-1.5 text-xs rounded-full border-2 transition-all"
          style={{ borderColor: !catFilter ? "var(--accent-red)" : "var(--paper-rule)", color: !catFilter ? "var(--accent-red)" : "var(--ink-faint)" }}>
          Alle ({blocks.length})
        </button>
        {categories.map(c => (
          <button key={c} onClick={() => setCatFilter(c)}
            className="px-3 py-1.5 text-xs rounded-full border-2 transition-all"
            style={{ borderColor: catFilter === c ? (CAT_COLORS[c] ?? "var(--accent-red)") : "var(--paper-rule)",
              color: catFilter === c ? (CAT_COLORS[c] ?? "var(--accent-red)") : "var(--ink-faint)" }}>
            {c} ({blocks.filter(b => b.category === c).length})
          </button>
        ))}
      </div>

      {loading ? <p style={{ color: "var(--ink-faint)" }}>Lade…</p> : error ? (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
          <button onClick={() => { setLoading(true); void load(); }} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
            Erneut versuchen
          </button>
        </div>
      ) : blocks.length === 0 ? (
        <p style={{ color: "var(--ink-faint)" }}>Keine Fragebausteine vorhanden.</p>
      ) : (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table text-sm">
            <thead>
              <tr>
                <th>Priorität</th>
                <th>Kategorie</th>
                <th>Frage</th>
                <th>Pflicht</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filtered.sort((a, b) => a.priority - b.priority).map(b => (
                <tr key={b.id}>
                  <td><span className="font-bold text-lg" style={{ color: "var(--ink)" }}>{b.priority}</span></td>
                  <td>
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium"
                      style={{ background: (CAT_COLORS[b.category] ?? "#94a3b8") + "22",
                        color: CAT_COLORS[b.category] ?? "#94a3b8" }}>
                      {b.category}
                    </span>
                  </td>
                  <td>
                    <p className="font-medium text-xs" style={{ color: "var(--ink)" }}>{b.label}</p>
                    <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)", maxWidth: 320 }}
                      title={b.question_text}>
                      {b.question_text.slice(0, 80)}{b.question_text.length > 80 ? "…" : ""}
                    </p>
                  </td>
                  <td>{b.is_required ? <span style={{ color: "#ef4444" }}>✓ Pflicht</span> : <span style={{ color: "var(--ink-faint)" }}>Optional</span>}</td>
                  <td>
                    <span className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: b.is_active ? "#22c55e22" : "#94a3b822",
                        color: b.is_active ? "#22c55e" : "#94a3b8" }}>
                      {b.is_active ? "Aktiv" : "Inaktiv"}
                    </span>
                  </td>
                  <td>
                    <div className="flex gap-2">
                      <button onClick={() => openEdit(b)} className="neo-btn neo-btn--outline neo-btn--sm">Bearbeiten</button>
                      {b.is_active && (
                        <button onClick={() => void deactivate(b.id)}
                          className="neo-btn neo-btn--sm text-xs"
                          style={{ color: "#ef4444", borderColor: "#ef444433" }}>Deaktivieren</button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {open && (
        <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.4)" }}>
          <div className="ml-auto w-[480px] h-full overflow-y-auto shadow-2xl flex flex-col"
            style={{ background: "var(--paper)", borderLeft: "2px solid var(--paper-rule)" }}>
            <div className="flex items-center justify-between px-5 py-4 border-b"
              style={{ borderColor: "var(--paper-rule)" }}>
              <h2 className="font-bold text-sm">{editing ? "Fragebaustein bearbeiten" : "Neuer Fragebaustein"}</h2>
              <button onClick={() => setOpen(false)} style={{ fontSize: 20, color: "var(--ink-faint)" }}>×</button>
            </div>
            <div className="flex-1 px-5 py-4 space-y-4">
              {[
                { label: "Key", key: "key", ph: "q_user_group" },
                { label: "Label", key: "label", ph: "Nutzergruppe" },
              ].map(f => (
                <div key={f.key}>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>{f.label}</label>
                  <input type="text" value={(form as Record<string, unknown>)[f.key] as string}
                    onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                    placeholder={f.ph} className="neo-input w-full text-sm" />
                </div>
              ))}
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Kategorie</label>
                <select value={form.category} onChange={e => setForm(p => ({ ...p, category: e.target.value }))} className="neo-input w-full text-sm">
                  {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Fragetext</label>
                <textarea value={form.question_text} onChange={e => setForm(p => ({ ...p, question_text: e.target.value }))}
                  rows={3} className="neo-input w-full text-sm resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Follow-up (optional)</label>
                <textarea value={form.follow_up_text} onChange={e => setForm(p => ({ ...p, follow_up_text: e.target.value }))}
                  rows={2} className="neo-input w-full text-sm resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Priorität (1=kritisch, 10=optional)</label>
                <input type="number" min={1} max={10} value={form.priority}
                  onChange={e => setForm(p => ({ ...p, priority: Number(e.target.value) }))} className="neo-input w-full text-sm" />
              </div>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.is_required} onChange={e => setForm(p => ({ ...p, is_required: e.target.checked }))} />
                  <span>Pflichtfeld</span>
                </label>
                <label className="flex items-center gap-2 text-sm cursor-pointer">
                  <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
                  <span>Aktiv</span>
                </label>
              </div>
            </div>
            <div className="px-5 py-4 border-t flex gap-3" style={{ borderColor: "var(--paper-rule)" }}>
              <button onClick={() => void save()} disabled={saving} className="neo-btn neo-btn--default">
                {saving ? "Speichern…" : "Speichern"}
              </button>
              <button onClick={() => setOpen(false)} className="neo-btn neo-btn--outline">Abbrechen</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
