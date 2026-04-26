"use client";

import { use, useState } from "react";
import { FileCheck, Plus, Shield } from "lucide-react";
import { useEvidenceTypes, type EvidenceType } from "@/lib/hooks/useGovernance";
import { authFetch } from "@/lib/api/client";
import { mutate as globalMutate } from "swr";

interface PageProps {
  params: Promise<{ org: string }>;
}

function EvidenceRow({ et }: { et: EvidenceType }) {
  return (
    <div className="flex items-start gap-3 p-4 rounded-lg bg-[var(--bg-card)] border border-[var(--border-subtle)] hover:border-violet-200 transition-colors">
      <div className={`w-8 h-8 rounded flex items-center justify-center shrink-0 ${
        et.is_system ? "bg-violet-100 text-violet-600" : "bg-slate-100 text-slate-500"
      }`}>
        <FileCheck className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <p className="text-sm font-medium text-[var(--ink-strong)]">{et.name}</p>
          {et.is_system && (
            <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-violet-100 text-violet-700">
              <Shield className="h-3 w-3" /> System
            </span>
          )}
          <span className={`px-1.5 py-0.5 rounded text-xs ${et.is_active ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
            {et.is_active ? "Aktiv" : "Inaktiv"}
          </span>
        </div>
        <p className="text-xs font-mono text-[var(--ink-muted)]">{et.slug}</p>
        {et.description && <p className="text-xs text-[var(--ink-muted)] mt-1">{et.description}</p>}
        {et.format_guidance && (
          <p className="text-xs text-[var(--ink-muted)] mt-0.5">
            <span className="font-medium">Format:</span> {et.format_guidance}
          </p>
        )}
      </div>
    </div>
  );
}

export default function EvidencePage({ params }: PageProps) {
  const { org } = use(params);
  const { data: types, mutate } = useEvidenceTypes();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ slug: "", name: "", description: "", format_guidance: "" });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!form.slug || !form.name) { setError("Slug und Name erforderlich"); return; }
    setSaving(true);
    try {
      await authFetch("/api/v1/governance/evidence-types", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      await mutate();
      setCreating(false);
      setForm({ slug: "", name: "", description: "", format_guidance: "" });
      setError(null);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const cls = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400";

  const systemTypes = types?.filter(t => t.is_system) ?? [];
  const customTypes = types?.filter(t => !t.is_system) ?? [];

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <FileCheck className="h-5 w-5 text-violet-500" />
            Nachweis-Katalog
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            Zentrale Verwaltung aller Nachweis- und Evidence-Typen
          </p>
        </div>
        <button
          onClick={() => setCreating(c => !c)}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Neuer Nachweis-Typ
        </button>
      </div>

      {creating && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-violet-200 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Neuen Nachweis-Typ anlegen</h2>
          {error && <div className="p-2 rounded bg-red-50 text-red-700 text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1">Name *</label>
              <input className={cls} value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Slug *</label>
              <input className={cls} value={form.slug} onChange={e => setForm(f => ({ ...f, slug: e.target.value.toLowerCase().replace(/\s+/g, "-") }))} />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Beschreibung</label>
            <input className={cls} value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1">Format-Vorgaben</label>
            <input className={cls} placeholder="z.B. PDF, versioniert, mit Datum" value={form.format_guidance} onChange={e => setForm(f => ({ ...f, format_guidance: e.target.value }))} />
          </div>
          <div className="flex gap-3">
            <button onClick={handleCreate} disabled={saving}
              className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm disabled:opacity-60">
              {saving ? "Speichern…" : "Erstellen"}
            </button>
            <button onClick={() => setCreating(false)} className="px-4 py-2 text-sm text-[var(--ink-muted)]">Abbrechen</button>
          </div>
        </div>
      )}

      {systemTypes.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-3">
            System-Nachweise ({systemTypes.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {systemTypes.map(et => <EvidenceRow key={et.id} et={et} />)}
          </div>
        </div>
      )}

      {customTypes.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-3">
            Admin-definierte Nachweise ({customTypes.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {customTypes.map(et => <EvidenceRow key={et.id} et={et} />)}
          </div>
        </div>
      )}

      {!types || types.length === 0 && (
        <div className="text-center py-12 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
          <FileCheck className="h-10 w-10 text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-[var(--ink-muted)]">Keine Nachweis-Typen. Seed-Daten laden.</p>
        </div>
      )}
    </div>
  );
}
