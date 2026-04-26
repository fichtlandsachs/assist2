"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listConversationRules, createConversationRule, updateConversationRule,
  listSizingRules, createSizingRule, updateSizingRule,
  listReadinessRules, createReadinessRule, updateReadinessRule,
  type ConversationRule, type SizingRule, type ReadinessRule,
} from "@/lib/api";

// ── Help texts ────────────────────────────────────────────────────────────────

const HELP = {
  conversation: {
    title: "Gesprächsregeln",
    description:
      "Gesprächsregeln steuern das Verhalten der Conversation Engine während eines Dialogs. " +
      "Sie definieren z. B. wie viele Fragen pro Runde gestellt werden, wann ein Moduswechsel " +
      "ausgelöst wird, ob Fakten wiederverwendet werden dürfen und wie auf unvollständige " +
      "Antworten reagiert wird.",
    fields: [
      { name: "key", desc: "Eindeutiger technischer Bezeichner (z. B. max_questions_per_round)" },
      { name: "rule_type", desc: "Kategorie der Regel: question_limit | fact_reuse | mode_switch | clarification | fallback" },
      { name: "label", desc: "Verständlicher Name der Regel, erscheint in Logs und Übersichten" },
      { name: "value_json", desc: "JSON-Konfiguration der Regel, z. B. { \"max\": 3 } oder { \"min_confidence\": 0.7 }" },
    ],
    examples: [
      { rule_type: "question_limit", label: "Max. Fragen pro Runde", value_json: { max: 3 } },
      { rule_type: "fact_reuse", label: "Faktwiederverwendung ab Konfidenz", value_json: { min_confidence: 0.75 } },
      { rule_type: "mode_switch", label: "Wechsel zu Review bei vollständigem Protokoll", value_json: { trigger: "protocol_complete" } },
    ],
  },
  sizing: {
    title: "Sizing-Regeln",
    description:
      "Sizing-Regeln legen fest, wie Stories anhand mehrerer Dimensionen bewertet und in " +
      "T-Shirt-Größen (XS/S/M/L/XL) eingeteilt werden. Jede Dimension (z. B. Anzahl Nutzergruppen, " +
      "betroffene Systeme) hat eigene Schwellenwerte und ein Gewicht im Gesamtscore.",
    fields: [
      { name: "key", desc: "Eindeutiger Bezeichner (z. B. size_by_user_groups)" },
      { name: "dimension", desc: "Messdimension: user_groups | functions | systems | acceptance_criteria | risks" },
      { name: "label", desc: "Anzeigename der Dimension" },
      { name: "weight", desc: "Gewichtung dieser Dimension im Gesamtscore (0.0–2.0, Standard 1.0)" },
      { name: "thresholds_json", desc: 'Schwellenwerte je Größe, z. B. { "XS": 1, "S": 2, "M": 4, "L": 7, "XL": 10 }' },
    ],
    examples: [
      { dimension: "user_groups", label: "Nutzergruppen", weight: 1.0, thresholds_json: { XS: 1, S: 2, M: 4, L: 7, XL: 10 } },
      { dimension: "systems", label: "Betroffene Systeme", weight: 1.2, thresholds_json: { XS: 1, S: 2, M: 3, L: 5, XL: 8 } },
    ],
  },
  readiness: {
    title: "Readiness-Regeln",
    description:
      "Readiness-Regeln bestimmen, ob eine Story bereit zur Ausarbeitung ist. Jede Regel prüft " +
      "ob ein bestimmter Faktkategorie-Slot gefüllt ist und welche Mindest-Konfidenz erreicht sein " +
      "muss. Blocking-Regeln verhindern den Abschluss, wenn sie nicht erfüllt sind.",
    fields: [
      { name: "key", desc: "Eindeutiger Bezeichner (z. B. require_target_user)" },
      { name: "required_category", desc: "Faktkategorie die vorhanden sein muss (z. B. target_user, problem, goal)" },
      { name: "label", desc: "Beschreibung der Anforderung" },
      { name: "min_confidence", desc: "Mindest-Konfidenz des Fakts (0.0–1.0, Standard 0.6)" },
      { name: "is_blocking", desc: "Wenn true: Story kann nicht abgeschlossen werden solange Regel nicht erfüllt" },
      { name: "weight", desc: "Gewicht im Readiness-Score (0.0–2.0)" },
    ],
    examples: [
      { required_category: "target_user", label: "Zielgruppe muss bekannt sein", min_confidence: 0.6, is_blocking: true, weight: 1.0 },
      { required_category: "problem", label: "Problem muss beschrieben sein", min_confidence: 0.5, is_blocking: true, weight: 1.0 },
      { required_category: "goal", label: "Ziel muss definiert sein", min_confidence: 0.6, is_blocking: false, weight: 0.8 },
    ],
  },
};

type Tab = "conversation" | "sizing" | "readiness";

// ── Shared helpers ─────────────────────────────────────────────────────────────

function Badge({ active }: { active: boolean }) {
  return active
    ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Aktiv</span>
    : <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">Inaktiv</span>;
}

function JsonDisplay({ value }: { value: Record<string, unknown> }) {
  return (
    <pre className="text-xs bg-gray-50 border rounded px-2 py-1 font-mono overflow-x-auto max-w-xs">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

// ── Conversation Rule drawer ───────────────────────────────────────────────────

const RULE_TYPES = ["question_limit", "fact_reuse", "mode_switch", "clarification", "fallback", "custom"];

function ConversationRuleDrawer({
  item, onClose, onSave,
}: { item: ConversationRule | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    key: item?.key ?? "",
    rule_type: item?.rule_type ?? "question_limit",
    label: item?.label ?? "",
    value_json: item ? JSON.stringify(item.value_json, null, 2) : "{}",
    is_active: item?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true); setErr(null);
    try {
      let value_json = {};
      try { value_json = JSON.parse(form.value_json); } catch { setErr("value_json ist kein gültiges JSON"); setSaving(false); return; }
      const body = { ...form, value_json };
      if (item) await updateConversationRule(item.id, body);
      else await createConversationRule(body);
      onSave();
    } catch (e: any) { setErr(e?.message || "Fehler"); }
    setSaving(false);
  }

  return (
    <Drawer title={item ? "Gesprächsregel bearbeiten" : "Neue Gesprächsregel"} onClose={onClose}>
      <Field label="Key"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.key} onChange={e => setForm(p => ({ ...p, key: e.target.value }))} placeholder="max_questions_per_round" /></Field>
      <Field label="Typ">
        <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.rule_type} onChange={e => setForm(p => ({ ...p, rule_type: e.target.value }))}>
          {RULE_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Label"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.label} onChange={e => setForm(p => ({ ...p, label: e.target.value }))} placeholder="Max. Fragen pro Runde" /></Field>
      <Field label="Wert (JSON)">
        <textarea className="w-full border rounded-md px-3 py-2 text-xs font-mono resize-none" rows={5} value={form.value_json}
          onChange={e => setForm(p => ({ ...p, value_json: e.target.value }))} />
        <p className="text-xs text-gray-400 mt-1">Beispiel: {`{ "max": 3 }`}</p>
      </Field>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
        Aktiv
      </label>
      {err && <p className="text-red-600 text-sm">{err}</p>}
      <DrawerActions saving={saving} onSave={save} onClose={onClose} />
    </Drawer>
  );
}

// ── Sizing Rule drawer ────────────────────────────────────────────────────────

const DIMENSIONS = ["user_groups", "functions", "systems", "acceptance_criteria", "risks", "integrations", "custom"];

function SizingRuleDrawer({
  item, onClose, onSave,
}: { item: SizingRule | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    key: item?.key ?? "",
    label: item?.label ?? "",
    dimension: item?.dimension ?? "user_groups",
    weight: String(item?.weight ?? 1.0),
    thresholds_json: item ? JSON.stringify(item.thresholds_json, null, 2) : JSON.stringify({ XS: 1, S: 2, M: 4, L: 7, XL: 10 }, null, 2),
    is_active: item?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true); setErr(null);
    try {
      let thresholds_json = {};
      try { thresholds_json = JSON.parse(form.thresholds_json); } catch { setErr("thresholds_json ist kein gültiges JSON"); setSaving(false); return; }
      const body = { ...form, weight: parseFloat(form.weight) || 1.0, thresholds_json };
      if (item) await updateSizingRule(item.id, body);
      else await createSizingRule(body);
      onSave();
    } catch (e: any) { setErr(e?.message || "Fehler"); }
    setSaving(false);
  }

  return (
    <Drawer title={item ? "Sizing-Regel bearbeiten" : "Neue Sizing-Regel"} onClose={onClose}>
      <Field label="Key"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.key} onChange={e => setForm(p => ({ ...p, key: e.target.value }))} placeholder="size_by_user_groups" /></Field>
      <Field label="Label"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.label} onChange={e => setForm(p => ({ ...p, label: e.target.value }))} placeholder="Nutzergruppen" /></Field>
      <Field label="Dimension">
        <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.dimension} onChange={e => setForm(p => ({ ...p, dimension: e.target.value }))}>
          {DIMENSIONS.map(d => <option key={d}>{d}</option>)}
        </select>
      </Field>
      <Field label="Gewicht">
        <input type="number" step="0.1" min="0" max="3" className="w-full border rounded-md px-3 py-2 text-sm" value={form.weight}
          onChange={e => setForm(p => ({ ...p, weight: e.target.value }))} />
        <p className="text-xs text-gray-400 mt-1">Standard 1.0 · Höhere Werte = stärkerer Einfluss auf Gesamtgröße</p>
      </Field>
      <Field label="Schwellenwerte (JSON)">
        <textarea className="w-full border rounded-md px-3 py-2 text-xs font-mono resize-none" rows={6} value={form.thresholds_json}
          onChange={e => setForm(p => ({ ...p, thresholds_json: e.target.value }))} />
        <p className="text-xs text-gray-400 mt-1">Anzahl je Größe: XS / S / M / L / XL</p>
      </Field>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
        Aktiv
      </label>
      {err && <p className="text-red-600 text-sm">{err}</p>}
      <DrawerActions saving={saving} onSave={save} onClose={onClose} />
    </Drawer>
  );
}

// ── Readiness Rule drawer ─────────────────────────────────────────────────────

const FACT_CATEGORIES = [
  "target_user", "problem", "goal", "benefit", "affected_system",
  "process", "acceptance_criteria", "risks", "stakeholder", "priority", "custom",
];

function ReadinessRuleDrawer({
  item, onClose, onSave,
}: { item: ReadinessRule | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    key: item?.key ?? "",
    label: item?.label ?? "",
    required_category: item?.required_category ?? "target_user",
    min_confidence: String(item?.min_confidence ?? 0.6),
    is_blocking: item?.is_blocking ?? true,
    weight: String(item?.weight ?? 1.0),
    is_active: item?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true); setErr(null);
    try {
      const body = {
        ...form,
        min_confidence: parseFloat(form.min_confidence) || 0.6,
        weight: parseFloat(form.weight) || 1.0,
      };
      if (item) await updateReadinessRule(item.id, body);
      else await createReadinessRule(body);
      onSave();
    } catch (e: any) { setErr(e?.message || "Fehler"); }
    setSaving(false);
  }

  return (
    <Drawer title={item ? "Readiness-Regel bearbeiten" : "Neue Readiness-Regel"} onClose={onClose}>
      <Field label="Key"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.key} onChange={e => setForm(p => ({ ...p, key: e.target.value }))} placeholder="require_target_user" /></Field>
      <Field label="Label"><input className="w-full border rounded-md px-3 py-2 text-sm" value={form.label} onChange={e => setForm(p => ({ ...p, label: e.target.value }))} placeholder="Zielgruppe muss bekannt sein" /></Field>
      <Field label="Faktkategorie (required_category)">
        <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.required_category} onChange={e => setForm(p => ({ ...p, required_category: e.target.value }))}>
          {FACT_CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
        <p className="text-xs text-gray-400 mt-1">Der Fakt dieser Kategorie muss im Protokoll vorhanden sein</p>
      </Field>
      <Field label="Mindest-Konfidenz">
        <input type="number" step="0.05" min="0" max="1" className="w-full border rounded-md px-3 py-2 text-sm" value={form.min_confidence}
          onChange={e => setForm(p => ({ ...p, min_confidence: e.target.value }))} />
        <p className="text-xs text-gray-400 mt-1">0.0 – 1.0 · Wie sicher muss der Fakt sein (Standard 0.6)</p>
      </Field>
      <Field label="Gewicht">
        <input type="number" step="0.1" min="0" max="3" className="w-full border rounded-md px-3 py-2 text-sm" value={form.weight}
          onChange={e => setForm(p => ({ ...p, weight: e.target.value }))} />
      </Field>
      <div className="flex gap-6">
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={form.is_blocking} onChange={e => setForm(p => ({ ...p, is_blocking: e.target.checked }))} />
          <span>Blocking <span className="text-gray-400">(blockiert Abschluss)</span></span>
        </label>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
          Aktiv
        </label>
      </div>
      {err && <p className="text-red-600 text-sm">{err}</p>}
      <DrawerActions saving={saving} onSave={save} onClose={onClose} />
    </Drawer>
  );
}

// ── Generic Drawer wrapper ────────────────────────────────────────────────────

function Drawer({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.45)" }}>
      <div className="ml-auto w-full max-w-lg h-full overflow-y-auto bg-white shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-base">{title}</h2>
          <button onClick={onClose} className="text-2xl text-gray-400 hover:text-gray-700 leading-none">×</button>
        </div>
        <div className="flex-1 px-6 py-5 space-y-4 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}

function DrawerActions({ saving, onSave, onClose }: { saving: boolean; onSave: () => void; onClose: () => void }) {
  return (
    <div className="flex gap-3 pt-2 border-t">
      <button onClick={onSave} disabled={saving}
        className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
        {saving ? "Speichern…" : "Speichern"}
      </button>
      <button onClick={onClose} className="border px-4 py-2 rounded-md text-sm hover:bg-gray-50">Abbrechen</button>
    </div>
  );
}

// ── Help panel ────────────────────────────────────────────────────────────────

function HelpPanel({ tab }: { tab: Tab }) {
  const h = HELP[tab];
  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-4 space-y-3">
      <div className="flex items-start gap-2">
        <span className="text-blue-500 text-lg mt-0.5">ℹ</span>
        <div>
          <p className="font-semibold text-sm text-blue-800">{h.title} – Erläuterung</p>
          <p className="text-sm text-blue-700 mt-1">{h.description}</p>
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold text-blue-700 mb-1">Felder</p>
        <div className="space-y-1">
          {h.fields.map(f => (
            <div key={f.name} className="flex gap-2 text-xs">
              <code className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded font-mono shrink-0">{f.name}</code>
              <span className="text-blue-700">{f.desc}</span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold text-blue-700 mb-1">Beispiele</p>
        <div className="space-y-1">
          {h.examples.map((ex, i) => (
            <pre key={i} className="text-xs bg-white border border-blue-100 rounded px-2 py-1 overflow-x-auto text-blue-900">
              {JSON.stringify(ex, null, 2)}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function RulesPage() {
  const [conversationRules, setConversationRules] = useState<ConversationRule[]>([]);
  const [sizingRules, setSizingRules] = useState<SizingRule[]>([]);
  const [readinessRules, setReadinessRules] = useState<ReadinessRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("conversation");
  const [showHelp, setShowHelp] = useState(false);

  // Drawer state
  const [convDrawer, setConvDrawer] = useState<{ open: boolean; item: ConversationRule | null }>({ open: false, item: null });
  const [sizingDrawer, setSizingDrawer] = useState<{ open: boolean; item: SizingRule | null }>({ open: false, item: null });
  const [readinessDrawer, setReadinessDrawer] = useState<{ open: boolean; item: ReadinessRule | null }>({ open: false, item: null });

  async function load() {
    setLoading(true);
    try {
      setError(null);
      const [conversation, sizing, readiness] = await Promise.all([
        listConversationRules(),
        listSizingRules(),
        listReadinessRules(),
      ]);
      setConversationRules(conversation);
      setSizingRules(sizing);
      setReadinessRules(readiness);
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const tabs: { id: Tab; label: string; count: number }[] = [
    { id: "conversation", label: "Gesprächsregeln", count: conversationRules.length },
    { id: "sizing", label: "Sizing-Regeln", count: sizingRules.length },
    { id: "readiness", label: "Readiness-Regeln", count: readinessRules.length },
  ];

  function openCreate() {
    if (activeTab === "conversation") setConvDrawer({ open: true, item: null });
    if (activeTab === "sizing") setSizingDrawer({ open: true, item: null });
    if (activeTab === "readiness") setReadinessDrawer({ open: true, item: null });
  }

  return (
    <div className="max-w-5xl space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Regelkonfiguration</h1>
          <p className="text-sm text-gray-500 mt-1">Gesprächsregeln · Sizing-Regeln · Readiness-Regeln</p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/conversation/help#rules"
            className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe-Seite
          </Link>
          <button onClick={() => setShowHelp(h => !h)}
            className={`border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50 flex items-center gap-1.5 ${showHelp ? "bg-blue-50 border-blue-200 text-blue-700" : ""}`}>
            ℹ Hilfe
          </button>
          <button onClick={openCreate}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
            + Neue Regel
          </button>
        </div>
      </div>

      {/* Help panel */}
      {showHelp && <HelpPanel tab={activeTab} />}

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {tabs.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              activeTab === tab.id ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {tab.label}
            <span className={`ml-2 text-xs px-1.5 py-0.5 rounded-full ${activeTab === tab.id ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-500"}`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <p className="text-gray-500 py-8 text-center">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
          <button onClick={() => void load()} className="mt-3 text-sm text-yellow-700 underline">Erneut versuchen</button>
        </div>
      ) : activeTab === "conversation" ? (
        <ConversationRuleTable
          rules={conversationRules}
          onEdit={item => setConvDrawer({ open: true, item })}
        />
      ) : activeTab === "sizing" ? (
        <SizingRuleTable
          rules={sizingRules}
          onEdit={item => setSizingDrawer({ open: true, item })}
        />
      ) : (
        <ReadinessRuleTable
          rules={readinessRules}
          onEdit={item => setReadinessDrawer({ open: true, item })}
        />
      )}

      {/* Drawers */}
      {convDrawer.open && (
        <ConversationRuleDrawer
          item={convDrawer.item}
          onClose={() => setConvDrawer({ open: false, item: null })}
          onSave={() => { setConvDrawer({ open: false, item: null }); void load(); }}
        />
      )}
      {sizingDrawer.open && (
        <SizingRuleDrawer
          item={sizingDrawer.item}
          onClose={() => setSizingDrawer({ open: false, item: null })}
          onSave={() => { setSizingDrawer({ open: false, item: null }); void load(); }}
        />
      )}
      {readinessDrawer.open && (
        <ReadinessRuleDrawer
          item={readinessDrawer.item}
          onClose={() => setReadinessDrawer({ open: false, item: null })}
          onSave={() => { setReadinessDrawer({ open: false, item: null }); void load(); }}
        />
      )}
    </div>
  );
}

// ── Table components ──────────────────────────────────────────────────────────

function ConversationRuleTable({ rules, onEdit }: { rules: ConversationRule[]; onEdit: (r: ConversationRule) => void }) {
  if (rules.length === 0) return <EmptyState text="Keine Gesprächsregeln. Erstelle die erste Regel mit + Neue Regel." />;
  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Label</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Key</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Typ</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Wert</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">v</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rules.map(r => (
            <tr key={r.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">{r.label}</td>
              <td className="px-4 py-3 font-mono text-xs text-gray-500">{r.key}</td>
              <td className="px-4 py-3"><span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">{r.rule_type}</span></td>
              <td className="px-4 py-3"><JsonDisplay value={r.value_json} /></td>
              <td className="px-4 py-3"><Badge active={r.is_active} /></td>
              <td className="px-4 py-3 text-xs text-gray-400">v{r.version}</td>
              <td className="px-4 py-3 text-right"><button onClick={() => onEdit(r)} className="text-sm text-blue-600 hover:underline">Bearbeiten</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SizingRuleTable({ rules, onEdit }: { rules: SizingRule[]; onEdit: (r: SizingRule) => void }) {
  if (rules.length === 0) return <EmptyState text="Keine Sizing-Regeln. Erstelle die erste Regel mit + Neue Regel." />;
  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Label</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Dimension</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Gewicht</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Schwellenwerte</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rules.map(r => (
            <tr key={r.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">{r.label}</td>
              <td className="px-4 py-3"><span className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded-full">{r.dimension}</span></td>
              <td className="px-4 py-3 text-center font-mono text-xs">{r.weight}</td>
              <td className="px-4 py-3"><JsonDisplay value={r.thresholds_json} /></td>
              <td className="px-4 py-3"><Badge active={r.is_active} /></td>
              <td className="px-4 py-3 text-right"><button onClick={() => onEdit(r)} className="text-sm text-blue-600 hover:underline">Bearbeiten</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReadinessRuleTable({ rules, onEdit }: { rules: ReadinessRule[]; onEdit: (r: ReadinessRule) => void }) {
  if (rules.length === 0) return <EmptyState text="Keine Readiness-Regeln. Erstelle die erste Regel mit + Neue Regel." />;
  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Label</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Kategorie</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Min. Konfidenz</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Gewicht</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Blocking</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rules.map(r => (
            <tr key={r.id} className="hover:bg-gray-50">
              <td className="px-4 py-3 font-medium">{r.label}</td>
              <td className="px-4 py-3"><span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">{r.required_category}</span></td>
              <td className="px-4 py-3 text-center font-mono text-xs">{r.min_confidence}</td>
              <td className="px-4 py-3 text-center font-mono text-xs">{r.weight}</td>
              <td className="px-4 py-3">
                {r.is_blocking
                  ? <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full">Blocking</span>
                  : <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">Soft</span>}
              </td>
              <td className="px-4 py-3"><Badge active={r.is_active} /></td>
              <td className="px-4 py-3 text-right"><button onClick={() => onEdit(r)} className="text-sm text-blue-600 hover:underline">Bearbeiten</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return <p className="text-gray-400 text-sm py-10 text-center border rounded-lg bg-gray-50">{text}</p>;
}
