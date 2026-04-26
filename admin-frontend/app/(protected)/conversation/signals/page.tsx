"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listAnswerSignals,
  createAnswerSignal,
  updateAnswerSignal,
  type AnswerSignal,
} from "@/lib/api";

const FACT_CATEGORIES = [
  "target_user", "problem", "goal", "benefit", "affected_system",
  "process", "acceptance_criteria", "risks", "stakeholder", "priority", "custom",
];
const PATTERN_TYPES = ["keyword", "regex", "llm"];

function Badge({ active }: { active: boolean }) {
  return active
    ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Aktiv</span>
    : <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">Inaktiv</span>;
}

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

function SignalDrawer({
  item, onClose, onSave,
}: { item: AnswerSignal | null; onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    key: item?.key ?? "",
    fact_category: item?.fact_category ?? "target_user",
    pattern_type: item?.pattern_type ?? "keyword",
    pattern: item?.pattern ?? "",
    confidence_boost: String(item?.confidence_boost ?? 0.5),
    is_active: item?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true); setErr(null);
    try {
      const body = { ...form, confidence_boost: parseFloat(form.confidence_boost) || 0.5 };
      if (item) await updateAnswerSignal(item.id, body);
      else await createAnswerSignal(body);
      onSave();
    } catch (e: any) { setErr(e?.message || "Fehler"); }
    setSaving(false);
  }

  return (
    <Drawer title={item ? "Antwortsignal bearbeiten" : "Neues Antwortsignal"} onClose={onClose}>
      <Field label="Key">
        <input className="w-full border rounded-md px-3 py-2 text-sm" value={form.key}
          onChange={e => setForm(p => ({ ...p, key: e.target.value }))} placeholder="signal_zielgruppe" />
        <p className="text-xs text-gray-400 mt-1">Eindeutiger technischer Bezeichner</p>
      </Field>
      <Field label="Faktkategorie">
        <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.fact_category}
          onChange={e => setForm(p => ({ ...p, fact_category: e.target.value }))}>
          {FACT_CATEGORIES.map(c => <option key={c}>{c}</option>)}
        </select>
        <p className="text-xs text-gray-400 mt-1">Welchem Faktyp wird ein Treffer zugeordnet</p>
      </Field>
      <Field label="Mustertyp">
        <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.pattern_type}
          onChange={e => setForm(p => ({ ...p, pattern_type: e.target.value }))}>
          {PATTERN_TYPES.map(t => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Muster (Pattern)">
        <textarea className="w-full border rounded-md px-3 py-2 text-sm font-mono text-xs resize-none" rows={4}
          value={form.pattern} onChange={e => setForm(p => ({ ...p, pattern: e.target.value }))}
          placeholder="keyword: als Nutzer|Rolle|Persona&#10;regex: ^(wenn|dann|gegeben)" />
        <p className="text-xs text-gray-400 mt-1">
          keyword: durch | getrennte Begriffe · regex: regulärer Ausdruck
        </p>
      </Field>
      <Field label="Confidence Boost">
        <input type="number" step="0.05" min="0" max="1" className="w-full border rounded-md px-3 py-2 text-sm"
          value={form.confidence_boost} onChange={e => setForm(p => ({ ...p, confidence_boost: e.target.value }))} />
        <p className="text-xs text-gray-400 mt-1">Wert 0.0–1.0 · wie stark erhöht ein Treffer die Konfidenz</p>
      </Field>
      <label className="flex items-center gap-2 text-sm cursor-pointer">
        <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
        Aktiv
      </label>
      {err && <p className="text-red-600 text-sm">{err}</p>}
      <div className="flex gap-3 pt-2 border-t">
        <button onClick={save} disabled={saving}
          className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
          {saving ? "Speichern…" : "Speichern"}
        </button>
        <button onClick={onClose} className="border px-4 py-2 rounded-md text-sm hover:bg-gray-50">Abbrechen</button>
      </div>
    </Drawer>
  );
}

export default function SignalsPage() {
  const [items, setItems] = useState<AnswerSignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<{ open: boolean; item: AnswerSignal | null }>({ open: false, item: null });

  async function load() {
    setLoading(true);
    try {
      setError(null);
      setItems(await listAnswerSignals());
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Antwortsignale</h1>
          <p className="text-sm text-gray-500 mt-1">
            Keyword- und Regex-Muster, die Nutzertext einer Faktkategorie zuordnen
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/conversation/help#signals"
            className="border px-3 py-2 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe
          </Link>
          <button onClick={() => setDrawer({ open: true, item: null })}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
            + Neues Signal
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500 py-8 text-center">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
          <button onClick={() => void load()} className="mt-3 text-sm text-yellow-700 underline">Erneut versuchen</button>
        </div>
      ) : items.length === 0 ? (
        <p className="text-gray-400 text-sm py-10 text-center border rounded-lg bg-gray-50">
          Keine Antwortsignale vorhanden.
        </p>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Key</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Faktkategorie</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Typ</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Muster</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Boost</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Status</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {items.map(item => (
                <tr key={item.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-700">{item.key}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-teal-50 text-teal-700 px-2 py-0.5 rounded-full">
                      {item.fact_category}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-purple-50 text-purple-700 px-2 py-0.5 rounded-full">
                      {item.pattern_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 max-w-xs">
                    <span className="text-xs font-mono text-gray-600 line-clamp-2 break-all">
                      {item.pattern}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center font-mono text-xs">{item.confidence_boost}</td>
                  <td className="px-4 py-3"><Badge active={item.is_active} /></td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => setDrawer({ open: true, item })}
                      className="text-sm text-blue-600 hover:underline">
                      Bearbeiten
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {drawer.open && (
        <SignalDrawer
          item={drawer.item}
          onClose={() => setDrawer({ open: false, item: null })}
          onSave={() => { setDrawer({ open: false, item: null }); void load(); }}
        />
      )}
    </div>
  );
}
