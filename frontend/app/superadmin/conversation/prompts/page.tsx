"use client";

import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api/client";

interface PromptTemplate {
  id: string;
  key: string;
  mode: string;
  phase: string;
  prompt_text: string;
  is_active: boolean;
  version: number;
}

const PHASE_LABELS: Record<string, string> = {
  system: "System-Prompt", fact_extract: "Fact-Extraktion", question_plan: "Fragen-Planung",
  sizing: "Story-Sizing", readiness: "Story-Readiness", structure_proposal: "Strukturvorschlag",
};

export default function ConversationPromptsPage() {
  const [templates, setTemplates] = useState<PromptTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PromptTemplate | null>(null);
  const [editing, setEditing] = useState(false);
  const [formText, setFormText] = useState("");
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const r = await authFetch("/api/v1/superadmin/conversation-engine/prompt-templates");
      if (r.ok) {
        const data: PromptTemplate[] = await r.json();
        // Show only latest version per key
        const latest = Object.values(
          data.reduce<Record<string, PromptTemplate>>((acc, t) => {
            if (!acc[t.key] || t.version > acc[t.key].version) acc[t.key] = t;
            return acc;
          }, {})
        );
        setTemplates(latest);
        if (latest.length && !selected) setSelected(latest[0]);
        setError(null);
      } else if (r.status === 401) {
        setError("Nicht authentifiziert. Bitte melden Sie sich als Superadmin an.");
      } else {
        const err = await r.json().catch(() => ({ error: "Unbekannter Fehler" }));
        setError(err.error || `Fehler ${r.status}`);
      }
    } catch (e) {
      setError("Netzwerkfehler. Bitte prüfen Sie die Verbindung.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);

  async function saveNewVersion() {
    if (!selected) return;
    setSaving(true);
    const res = await authFetch("/api/v1/superadmin/conversation-engine/prompt-templates", {
      method: "POST",
      body: JSON.stringify({ key: selected.key, mode: selected.mode, phase: selected.phase, prompt_text: formText }),
    });
    if (res.ok) { await load(); setEditing(false); }
    setSaving(false);
  }

  const grouped = templates.reduce<Record<string, PromptTemplate[]>>((acc, t) => {
    acc[t.mode] = acc[t.mode] ?? [];
    acc[t.mode].push(t);
    return acc;
  }, {});

  return (
    <div className="flex gap-4 h-[calc(100vh-180px)]">
      {/* Left: template list */}
      <div className="w-64 shrink-0 overflow-y-auto space-y-4">
        <div>
          <h1 className="text-base font-bold" style={{ color: "var(--ink)" }}>Prompt-Vorlagen</h1>
          <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>Versionsverwaltet</p>
        </div>
        {loading ? <p style={{ color: "var(--ink-faint)" }}>Lade…</p> : error ? (
          <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
            <p style={{ color: "#92400e" }}>⚠️ {error}</p>
            <button onClick={() => { setLoading(true); void load(); }} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
              Erneut versuchen
            </button>
          </div>
        ) : (
          Object.entries(grouped).map(([mode, tpls]) => (
            <div key={mode}>
              <p className="text-[10px] font-bold uppercase tracking-wide mb-1.5" style={{ color: "var(--ink-faint)" }}>{mode}</p>
              <div className="space-y-1">
                {tpls.map(t => (
                  <button key={t.id} onClick={() => { setSelected(t); setEditing(false); }}
                    className="w-full text-left px-3 py-2 rounded-sm text-xs transition-all"
                    style={{
                      background: selected?.id === t.id ? "var(--accent-red)" : "var(--paper-warm)",
                      color: selected?.id === t.id ? "#fff" : "var(--ink)",
                    }}>
                    <p className="font-medium">{PHASE_LABELS[t.phase] ?? t.phase}</p>
                    <p className="text-[10px] opacity-70">v{t.version} · {t.key}</p>
                  </button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Right: editor */}
      {selected && (
        <div className="flex-1 neo-card p-5 flex flex-col gap-4 overflow-hidden">
          <div className="flex items-start justify-between shrink-0">
            <div>
              <h2 className="font-bold" style={{ color: "var(--ink)" }}>{PHASE_LABELS[selected.phase] ?? selected.phase}</h2>
              <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>
                {selected.key} · Version {selected.version} · Modus: {selected.mode}
              </p>
            </div>
            {!editing ? (
              <button onClick={() => { setFormText(selected.prompt_text); setEditing(true); }}
                className="neo-btn neo-btn--default neo-btn--sm">Neue Version erstellen</button>
            ) : (
              <div className="flex gap-2">
                <button onClick={() => void saveNewVersion()} disabled={saving} className="neo-btn neo-btn--default neo-btn--sm">
                  {saving ? "Speichern…" : "Als neue Version speichern"}
                </button>
                <button onClick={() => setEditing(false)} className="neo-btn neo-btn--outline neo-btn--sm">Abbrechen</button>
              </div>
            )}
          </div>

          <div className="flex-1 overflow-hidden">
            {editing ? (
              <textarea value={formText} onChange={e => setFormText(e.target.value)}
                className="w-full h-full neo-input text-sm font-mono resize-none"
                style={{ background: "var(--paper-warm)", minHeight: 400 }} />
            ) : (
              <pre className="text-sm font-mono whitespace-pre-wrap overflow-y-auto h-full p-3 rounded-sm"
                style={{ background: "var(--paper-warm)", color: "var(--ink)", lineHeight: 1.7 }}>
                {selected.prompt_text}
              </pre>
            )}
          </div>

          {editing && (
            <p className="text-xs shrink-0" style={{ color: "var(--ink-faint)" }}>
              Verfügbare Variablen: {"{context}"}, {"{user_text}"}, {"{known_facts}"}, {"{missing_required}"}, {"{asked_keys}"}, {"{facts_summary}"}, {"{available_blocks}"}, {"{max_questions}"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
