"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Save } from "lucide-react";
import { createControl, useCategories, useScoringSchemes } from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string }>;
}

const GATE_OPTIONS = ["G1", "G2", "G3", "G4"];

export default function NewControlPage({ params }: PageProps) {
  const { org } = use(params);
  const router = useRouter();
  const { data: categories } = useCategories();
  const { data: scoringSchemes } = useScoringSchemes();

  const [form, setForm] = useState({
    slug: "",
    name: "",
    short_description: "",
    why_relevant: "",
    what_to_check: "",
    what_to_do: "",
    guiding_questions: [] as string[],
    help_text: "",
    category_id: "",
    control_objective: "",
    risk_rationale: "",
    gate_phases: [] as string[],
    default_weight: 1.0,
    hard_stop: false,
    hard_stop_threshold: 1,
    requires_trigger: false,
    responsible_role: "",
    review_interval_days: 365,
    is_visible_in_frontend: true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (key: string, value: unknown) =>
    setForm(f => ({ ...f, [key]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.slug) {
      setError("Name und Slug sind Pflichtfelder.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const ctrl = await createControl({
        ...form,
        category_id: form.category_id || undefined,
        scoring_scheme_id: undefined,
        guiding_questions: form.guiding_questions,
      });
      router.push(`/${org}/admin/governance/controls/${ctrl.id}`);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const cls = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400";

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href={`/${org}/admin/governance/controls`} className="text-[var(--ink-muted)] hover:text-[var(--ink-mid)]">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)]">Neues Control anlegen</h1>
          <p className="text-sm text-[var(--ink-muted)]">Zusätzliches (dynamisches) Control erstellen</p>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Grunddaten (Pflicht)</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Name *</label>
              <input className={cls} placeholder="z.B. Cybersecurity Assessment" required
                value={form.name} onChange={e => set("name", e.target.value)} />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Slug / ID *</label>
              <input className={cls} placeholder="z.B. cybersecurity-assessment" required
                value={form.slug} onChange={e => set("slug", e.target.value.toLowerCase().replace(/\s+/g, "-"))} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Kontrollziel *</label>
            <textarea className={cls + " resize-y"} rows={2} required
              placeholder="Was soll dieses Control sicherstellen?"
              value={form.control_objective}
              onChange={e => set("control_objective", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Kurzbeschreibung</label>
            <textarea className={cls + " resize-y"} rows={2}
              placeholder="Kurze, verständliche Erklärung"
              value={form.short_description}
              onChange={e => set("short_description", e.target.value)} />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Kategorie</label>
              <select className={cls} value={form.category_id} onChange={e => set("category_id", e.target.value)}>
                <option value="">Keine Kategorie</option>
                {categories?.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Verantwortliche Rolle</label>
              <input className={cls} placeholder="z.B. Quality Manager"
                value={form.responsible_role} onChange={e => set("responsible_role", e.target.value)} />
            </div>
          </div>
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Gate-Zuordnung & Scoring</h2>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-2">Gates *</label>
            <div className="flex gap-2">
              {GATE_OPTIONS.map(g => (
                <button key={g} type="button"
                  onClick={() => {
                    const current = form.gate_phases;
                    set("gate_phases", current.includes(g) ? current.filter(x => x !== g) : [...current, g]);
                  }}
                  className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                    form.gate_phases.includes(g)
                      ? "bg-violet-600 text-white"
                      : "bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--ink-mid)]"
                  }`}
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div>
              <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Gewichtung</label>
              <input type="number" min={0} max={10} step={0.5} className={cls}
                value={form.default_weight} onChange={e => set("default_weight", parseFloat(e.target.value))} />
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input type="checkbox" id="hard_stop" className="w-4 h-4 accent-red-600"
                checked={form.hard_stop} onChange={e => set("hard_stop", e.target.checked)} />
              <label htmlFor="hard_stop" className="text-sm text-[var(--ink-mid)]">Hard Stop</label>
            </div>
            <div className="flex items-center gap-2 pb-2">
              <input type="checkbox" id="requires_trigger" className="w-4 h-4 accent-amber-600"
                checked={form.requires_trigger} onChange={e => set("requires_trigger", e.target.checked)} />
              <label htmlFor="requires_trigger" className="text-sm text-[var(--ink-mid)]">Nur per Trigger aktiv</label>
            </div>
          </div>
        </div>

        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Nutzertext</h2>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Warum relevant?</label>
            <textarea className={cls + " resize-y"} rows={2}
              value={form.why_relevant} onChange={e => set("why_relevant", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Was prüfen?</label>
            <textarea className={cls + " resize-y"} rows={2}
              value={form.what_to_check} onChange={e => set("what_to_check", e.target.value)} />
          </div>
          <div>
            <label className="block text-sm font-medium text-[var(--ink-strong)] mb-1">Leitfragen (eine pro Zeile)</label>
            <textarea className={cls + " resize-y"} rows={3}
              value={form.guiding_questions.join("\n")}
              onChange={e => set("guiding_questions", e.target.value.split("\n").filter(Boolean))} />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <Link href={`/${org}/admin/governance/controls`}
            className="px-4 py-2 text-sm text-[var(--ink-mid)] hover:text-[var(--ink-strong)]">
            Abbrechen
          </Link>
          <button type="submit" disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 transition-colors disabled:opacity-60">
            <Save className="h-4 w-4" />
            {saving ? "Speichern…" : "Control anlegen"}
          </button>
        </div>
      </form>
    </div>
  );
}
