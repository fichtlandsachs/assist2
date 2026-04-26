"use client";

import { useEffect, useState, type ReactNode } from "react";
import { authFetch } from "@/lib/api/client";

interface Rule { id: string; key: string; rule_type: string; label: string; value_json: Record<string, unknown>; is_active: boolean; version: number; }
interface SizingRule { id: string; key: string; label: string; dimension: string; weight: number; thresholds_json: Record<string, unknown>; is_active: boolean; }
interface ReadinessRule { id: string; key: string; label: string; required_category: string; min_confidence: number; is_blocking: boolean; weight: number; is_active: boolean; }

type Tab = "conversation" | "sizing" | "readiness";

function Drawer({
  title,
  onClose,
  children,
  actions,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.4)" }}>
      <div className="ml-auto w-[460px] h-full flex flex-col shadow-2xl"
        style={{ background: "var(--paper)", borderLeft: "2px solid var(--paper-rule)" }}>
        <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "var(--paper-rule)" }}>
          <h2 className="font-bold text-sm">{title}</h2>
          <button onClick={onClose} style={{ fontSize: 20, color: "var(--ink-faint)" }}>×</button>
        </div>
        <div className="flex-1 px-5 py-4 space-y-4 overflow-y-auto">{children}</div>
        <div className="px-5 py-4 border-t flex gap-3" style={{ borderColor: "var(--paper-rule)" }}>{actions}</div>
      </div>
    </div>
  );
}

export default function ConversationRulesPage() {
  const [rules, setRules] = useState<Rule[]>([]);
  const [sizingRules, setSizingRules] = useState<SizingRule[]>([]);
  const [readinessRules, setReadinessRules] = useState<ReadinessRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("conversation");
  const [editingType, setEditingType] = useState<Tab>("conversation");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [formKey, setFormKey] = useState("");
  const [formLabel, setFormLabel] = useState("");
  const [formRuleType, setFormRuleType] = useState("question_limit");
  const [formJson, setFormJson] = useState("{}");
  const [formDimension, setFormDimension] = useState("user_groups");
  const [formWeight, setFormWeight] = useState("1.0");
  const [formRequiredCategory, setFormRequiredCategory] = useState("target_user");
  const [formMinConfidence, setFormMinConfidence] = useState("0.6");
  const [formBlocking, setFormBlocking] = useState(true);
  const [formActive, setFormActive] = useState(true);
  const [saving, setSaving] = useState(false);

  async function load() {
    try {
      const [r1, r2, r3] = await Promise.all([
        authFetch("/api/v1/superadmin/conversation-engine/rules"),
        authFetch("/api/v1/superadmin/conversation-engine/sizing-rules"),
        authFetch("/api/v1/superadmin/conversation-engine/readiness-rules"),
      ]);
      let hasError = false;
      if (r1.ok) {
        setRules(await r1.json());
      } else if (r1.status === 401) {
        setError("Nicht authentifiziert. Bitte melden Sie sich als Superadmin an.");
        hasError = true;
      } else {
        const err = await r1.json().catch(() => ({ error: "Unbekannter Fehler" }));
        setError(err.error || `Fehler ${r1.status}`);
        hasError = true;
      }
      if (r2.ok) {
        setSizingRules(await r2.json());
      } else if (!hasError) {
        if (r2.status === 401) {
          setError("Nicht authentifiziert. Bitte melden Sie sich als Superadmin an.");
        } else {
          const err = await r2.json().catch(() => ({ error: "Unbekannter Fehler" }));
          setError(err.error || `Fehler ${r2.status}`);
        }
        hasError = true;
      }
      if (r3.ok) {
        setReadinessRules(await r3.json());
      } else if (!hasError) {
        if (r3.status === 401) {
          setError("Nicht authentifiziert. Bitte melden Sie sich als Superadmin an.");
        } else {
          const err = await r3.json().catch(() => ({ error: "Unbekannter Fehler" }));
          setError(err.error || `Fehler ${r3.status}`);
        }
        hasError = true;
      }
      if (!hasError) setError(null);
    } catch (e) {
      setError("Netzwerkfehler. Bitte prüfen Sie die Verbindung.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { void load(); }, []);

  function openCreate(activeTab: Tab) {
    setEditingType(activeTab);
    setEditingId(null);
    setFormKey("");
    setFormLabel("");
    setFormRuleType("question_limit");
    setFormJson("{}");
    setFormDimension("user_groups");
    setFormWeight("1.0");
    setFormRequiredCategory("target_user");
    setFormMinConfidence("0.6");
    setFormBlocking(true);
    setFormActive(true);
    setOpen(true);
  }

  function openEditConversation(rule: Rule) {
    setEditingType("conversation");
    setEditingId(rule.id);
    setFormKey(rule.key);
    setFormLabel(rule.label);
    setFormRuleType(rule.rule_type);
    setFormJson(JSON.stringify(rule.value_json, null, 2));
    setFormActive(rule.is_active);
    setOpen(true);
  }

  function openEditSizing(rule: SizingRule) {
    setEditingType("sizing");
    setEditingId(rule.id);
    setFormKey(rule.key);
    setFormLabel(rule.label);
    setFormDimension(rule.dimension);
    setFormWeight(String(rule.weight));
    setFormJson(JSON.stringify(rule.thresholds_json, null, 2));
    setFormActive(rule.is_active);
    setOpen(true);
  }

  function openEditReadiness(rule: ReadinessRule) {
    setEditingType("readiness");
    setEditingId(rule.id);
    setFormKey(rule.key);
    setFormLabel(rule.label);
    setFormRequiredCategory(rule.required_category);
    setFormMinConfidence(String(rule.min_confidence));
    setFormBlocking(rule.is_blocking);
    setFormWeight(String(rule.weight));
    setFormActive(rule.is_active);
    setOpen(true);
  }

  async function save() {
    setSaving(true);
    try {
      if (editingType === "conversation") {
        let value_json = {};
        try { value_json = JSON.parse(formJson); } catch { value_json = {}; }
        const payload = { key: formKey, rule_type: formRuleType, label: formLabel, value_json, is_active: formActive };
        const url = editingId
          ? `/api/v1/superadmin/conversation-engine/rules/${editingId}`
          : "/api/v1/superadmin/conversation-engine/rules";
        const method = editingId ? "PATCH" : "POST";
        await authFetch(url, { method, body: JSON.stringify(payload) });
      }
      if (editingType === "sizing") {
        let thresholds_json = {};
        try { thresholds_json = JSON.parse(formJson); } catch { thresholds_json = {}; }
        const payload = {
          key: formKey,
          label: formLabel,
          dimension: formDimension,
          weight: parseFloat(formWeight) || 1.0,
          thresholds_json,
          is_active: formActive,
        };
        const url = editingId
          ? `/api/v1/superadmin/conversation-engine/sizing-rules/${editingId}`
          : "/api/v1/superadmin/conversation-engine/sizing-rules";
        const method = editingId ? "PATCH" : "POST";
        await authFetch(url, { method, body: JSON.stringify(payload) });
      }
      if (editingType === "readiness") {
        const payload = {
          key: formKey,
          label: formLabel,
          required_category: formRequiredCategory,
          min_confidence: parseFloat(formMinConfidence) || 0.6,
          is_blocking: formBlocking,
          weight: parseFloat(formWeight) || 1.0,
          is_active: formActive,
        };
        const url = editingId
          ? `/api/v1/superadmin/conversation-engine/readiness-rules/${editingId}`
          : "/api/v1/superadmin/conversation-engine/readiness-rules";
        const method = editingId ? "PATCH" : "POST";
        await authFetch(url, { method, body: JSON.stringify(payload) });
      }
      await load();
      setOpen(false);
    } catch {
      setError("Speichern fehlgeschlagen.");
    }
    setSaving(false);
  }

  const TABS = [
    { id: "conversation", label: "Gesprächsregeln", count: rules.length },
    { id: "sizing", label: "Sizing-Regeln", count: sizingRules.length },
    { id: "readiness", label: "Readiness-Regeln", count: readinessRules.length },
  ] as const;

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>Gesprächsregeln & Bewertungsregeln</h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--ink-faint)" }}>
          Steuert das Verhalten der Conversation Engine: Fragen-Limits, Sizing, Readiness
        </p>
      </div>
      <div className="flex justify-end">
        <button onClick={() => openCreate(tab)} className="neo-btn neo-btn--default neo-btn--sm">+ Neue Regel</button>
      </div>

      <div className="flex gap-0 border-b-2" style={{ borderColor: "var(--paper-rule2)" }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="px-4 py-2.5 text-sm font-medium"
            style={{
              color: tab === t.id ? "var(--ink)" : "var(--ink-faint)",
              borderBottom: tab === t.id ? "2px solid var(--accent-red)" : "2px solid transparent",
              marginBottom: "-2px", background: "transparent", cursor: "pointer",
            }}>
            {t.label} <span className="ml-1 text-xs opacity-60">({t.count})</span>
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
      ) : (
        <>
          {tab === "conversation" && (
            <div className="space-y-3">
              {rules.map((rule) => (
                <div key={rule.id} className="neo-card p-4 flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded-full"
                        style={{ background: "var(--paper-warm)", color: "var(--ink-mid)" }}>{rule.rule_type}</span>
                      {!rule.is_active && <span className="text-xs" style={{ color: "#94a3b8" }}>Inaktiv</span>}
                    </div>
                    <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>{rule.label}</p>
                    <p className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{rule.key}</p>
                    <pre className="text-xs mt-1 font-mono" style={{ color: "var(--ink-faint)" }}>
                      {JSON.stringify(rule.value_json, null, 2)}
                    </pre>
                  </div>
                  <button onClick={() => openEditConversation(rule)} className="neo-btn neo-btn--outline neo-btn--sm shrink-0">Bearbeiten</button>
                </div>
              ))}
            </div>
          )}
          {tab === "sizing" && (
            <div className="neo-card overflow-hidden p-0">
              <table className="neo-table text-sm">
                <thead><tr><th>Dimension</th><th>Label</th><th>Gewicht</th><th>Schwellenwerte</th><th>Aktiv</th><th /></tr></thead>
                <tbody>
                  {sizingRules.map(r => (
                    <tr key={r.id}>
                      <td className="font-mono text-xs" style={{ color: "var(--ink-mid)" }}>{r.dimension}</td>
                      <td style={{ color: "var(--ink)" }}>{r.label}</td>
                      <td className="font-bold" style={{ color: "var(--ink)" }}>{r.weight}×</td>
                      <td><pre className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{JSON.stringify(r.thresholds_json)}</pre></td>
                      <td>{r.is_active ? <span style={{ color: "#22c55e" }}>●</span> : <span style={{ color: "#94a3b8" }}>○</span>}</td>
                      <td><button onClick={() => openEditSizing(r)} className="neo-btn neo-btn--outline neo-btn--sm">Bearbeiten</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {tab === "readiness" && (
            <div className="neo-card overflow-hidden p-0">
              <table className="neo-table text-sm">
                <thead><tr><th>Kategorie</th><th>Label</th><th>Min. Konfidenz</th><th>Blockierend</th><th>Gewicht</th><th /></tr></thead>
                <tbody>
                  {readinessRules.map(r => (
                    <tr key={r.id}>
                      <td className="font-mono text-xs" style={{ color: "var(--ink-mid)" }}>{r.required_category}</td>
                      <td style={{ color: "var(--ink)" }}>{r.label}</td>
                      <td style={{ color: "var(--ink)" }}>{Math.round(r.min_confidence * 100)}%</td>
                      <td>{r.is_blocking ? <span style={{ color: "#ef4444" }}>✓ Blockierend</span> : <span style={{ color: "var(--ink-faint)" }}>Hinweis</span>}</td>
                      <td className="font-bold" style={{ color: "var(--ink)" }}>{r.weight}×</td>
                      <td><button onClick={() => openEditReadiness(r)} className="neo-btn neo-btn--outline neo-btn--sm">Bearbeiten</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {open && (
        <Drawer
          title={`${editingId ? "Bearbeiten" : "Neue Regel"} · ${
            editingType === "conversation" ? "Gesprächsregel" : editingType === "sizing" ? "Sizing-Regel" : "Readiness-Regel"
          }`}
          onClose={() => setOpen(false)}
          actions={
            <>
              <button onClick={() => void save()} disabled={saving} className="neo-btn neo-btn--default">
                {saving ? "Speichern…" : "Speichern"}
              </button>
              <button onClick={() => setOpen(false)} className="neo-btn neo-btn--outline">Abbrechen</button>
            </>
          }
        >
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Key</label>
            <input className="neo-input w-full text-sm" value={formKey} onChange={e => setFormKey(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Label</label>
            <input className="neo-input w-full text-sm" value={formLabel} onChange={e => setFormLabel(e.target.value)} />
          </div>

          {editingType === "conversation" && (
            <>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Rule Type</label>
                <select className="neo-input w-full text-sm" value={formRuleType} onChange={e => setFormRuleType(e.target.value)}>
                  {["question_limit", "fact_reuse", "mode_switch", "clarification", "fallback", "custom"].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>value_json</label>
                <textarea value={formJson} onChange={e => setFormJson(e.target.value)}
                  rows={8} className="neo-input w-full text-xs font-mono resize-none"
                  style={{ background: "var(--paper-warm)" }} />
              </div>
            </>
          )}

          {editingType === "sizing" && (
            <>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Dimension</label>
                <select className="neo-input w-full text-sm" value={formDimension} onChange={e => setFormDimension(e.target.value)}>
                  {["user_groups", "functions", "systems", "acceptance_criteria", "risks", "integrations", "custom"].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Gewicht</label>
                <input className="neo-input w-full text-sm" value={formWeight} onChange={e => setFormWeight(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>thresholds_json</label>
                <textarea value={formJson} onChange={e => setFormJson(e.target.value)}
                  rows={8} className="neo-input w-full text-xs font-mono resize-none"
                  style={{ background: "var(--paper-warm)" }} />
              </div>
            </>
          )}

          {editingType === "readiness" && (
            <>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>required_category</label>
                <select className="neo-input w-full text-sm" value={formRequiredCategory} onChange={e => setFormRequiredCategory(e.target.value)}>
                  {["target_user", "problem", "goal", "benefit", "affected_system", "process", "acceptance_criteria", "risks", "stakeholder", "priority", "custom"].map(v => <option key={v} value={v}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>min_confidence (0.0-1.0)</label>
                <input className="neo-input w-full text-sm" value={formMinConfidence} onChange={e => setFormMinConfidence(e.target.value)} />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Gewicht</label>
                <input className="neo-input w-full text-sm" value={formWeight} onChange={e => setFormWeight(e.target.value)} />
              </div>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={formBlocking} onChange={e => setFormBlocking(e.target.checked)} />
                <span>Blockierend</span>
              </label>
            </>
          )}

          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input type="checkbox" checked={formActive} onChange={e => setFormActive(e.target.checked)} />
            <span>Aktiv</span>
          </label>
        </Drawer>
      )}
    </div>
  );
}
