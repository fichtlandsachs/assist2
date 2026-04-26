"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Lock, ArrowLeft, Save, Send, AlertTriangle,
  History, Info, Settings, FileCheck, BarChart3, Zap,
} from "lucide-react";
import {
  useControl, useControlVersions, useCategories, useScoringSchemes,
  updateControl, publishControl, type ControlDetail,
} from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string; controlId: string }>;
}

const TABS = [
  { key: "general",    label: "Allgemein",  icon: Info },
  { key: "user",       label: "Nutzertext", icon: Settings },
  { key: "governance", label: "Governance", icon: Shield },
  { key: "scoring",    label: "Scoring",    icon: BarChart3 },
  { key: "evidence",   label: "Nachweise",  icon: FileCheck },
  { key: "history",    label: "Historie",   icon: History },
];

import { Shield } from "lucide-react";

const GATE_OPTIONS = ["G1", "G2", "G3", "G4"];
const RISK_LEVELS = ["", "low", "medium", "high", "critical"];

function TabNav({ active, onChange }: { active: string; onChange: (t: string) => void }) {
  return (
    <div className="flex gap-0 border-b border-[var(--border-subtle)] overflow-x-auto">
      {TABS.map(({ key, label, icon: Icon }) => (
        <button
          key={key}
          onClick={() => onChange(key)}
          className={`flex items-center gap-1.5 px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors ${
            active === key
              ? "border-violet-500 text-violet-700 font-medium"
              : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink-mid)]"
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
          {label}
        </button>
      ))}
    </div>
  );
}

function FieldGroup({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-[var(--ink-strong)]">{label}</label>
      {hint && <p className="text-xs text-[var(--ink-muted)]">{hint}</p>}
      {children}
    </div>
  );
}

function TextInput({ value, onChange, disabled, placeholder, multiline }: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  placeholder?: string;
  multiline?: boolean;
}) {
  const cls = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400 disabled:opacity-60 disabled:bg-[var(--bg-card)]";
  if (multiline) {
    return (
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        placeholder={placeholder}
        rows={3}
        className={cls + " resize-y"}
      />
    );
  }
  return (
    <input
      type="text"
      value={value}
      onChange={e => onChange(e.target.value)}
      disabled={disabled}
      placeholder={placeholder}
      className={cls}
    />
  );
}

export default function ControlDetailPage({ params }: PageProps) {
  const { org, controlId } = use(params);
  const router = useRouter();
  const { data: ctrl, isLoading, mutate } = useControl(controlId);
  const { data: versions } = useControlVersions(controlId);
  const { data: categories } = useCategories();
  const { data: scoringSchemes } = useScoringSchemes();

  const [tab, setTab] = useState("general");
  const [form, setForm] = useState<Partial<ControlDetail>>({});
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [saved, setSaved] = useState(false);

  const isFixed = ctrl?.kind === "fixed";
  const FIXED_EDITABLE = new Set([
    "name", "short_description", "why_relevant", "what_to_check",
    "what_to_do", "guiding_questions", "help_text", "gate_phases",
    "default_weight", "responsible_role", "evidence_requirements",
    "is_visible_in_frontend", "review_interval_days", "audit_notes",
  ]);

  const val = (key: keyof ControlDetail): unknown =>
    form[key] !== undefined ? form[key] : ctrl?.[key];

  const set = (key: keyof ControlDetail, value: unknown) => {
    if (isFixed && !FIXED_EDITABLE.has(key)) return;
    setForm(f => ({ ...f, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    if (!ctrl) return;
    setSaving(true);
    try {
      await updateControl(ctrl.id, { ...form });
      setSaved(true);
      mutate();
      setForm({});
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handlePublish = async () => {
    if (!ctrl) return;
    const reason = prompt("Änderungsgrund (für Versionshistorie):");
    setPublishing(true);
    try {
      await publishControl(ctrl.id, reason ?? undefined);
      mutate();
    } catch (e: unknown) {
      alert((e as Error).message);
    } finally {
      setPublishing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
      </div>
    );
  }

  if (!ctrl) return <div className="p-6 text-sm text-[var(--ink-muted)]">Control nicht gefunden.</div>;

  const hasChanges = Object.keys(form).length > 0;

  return (
    <div className="flex flex-col h-full">
      {/* Topbar */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-subtle)] bg-[var(--bg-card)]">
        <div className="flex items-center gap-3">
          <Link href={`/${org}/admin/governance/controls`} className="text-[var(--ink-muted)] hover:text-[var(--ink-mid)]">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <div className="flex items-center gap-2">
              {isFixed && <Lock className="h-4 w-4 text-slate-400 shrink-0" />}
              <h1 className="text-base font-semibold text-[var(--ink-strong)]">{ctrl.name}</h1>
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                ctrl.status === "approved" ? "bg-green-100 text-green-700" :
                ctrl.status === "draft" ? "bg-sky-100 text-sky-700" :
                "bg-amber-100 text-amber-700"
              }`}>
                {ctrl.status === "approved" ? "Freigegeben" : ctrl.status === "draft" ? "Entwurf" : "In Prüfung"}
              </span>
              {ctrl.hard_stop && (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                  <AlertTriangle className="h-3 w-3" /> Hard Stop
                </span>
              )}
            </div>
            <p className="text-xs text-[var(--ink-muted)] font-mono">{ctrl.slug} · v{ctrl.version}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <button
              onClick={handleSave}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-60"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? "Speichern…" : "Speichern"}
            </button>
          )}
          {saved && !hasChanges && (
            <span className="text-xs text-green-600">✓ Gespeichert</span>
          )}
          {ctrl.kind === "dynamic" && ctrl.status === "draft" && !hasChanges && (
            <button
              onClick={handlePublish}
              disabled={publishing}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-60"
            >
              <Send className="h-3.5 w-3.5" />
              {publishing ? "Veröffentlichen…" : "Veröffentlichen"}
            </button>
          )}
        </div>
      </div>

      {/* Warning for fixed controls */}
      {isFixed && (
        <div className="mx-6 mt-4 flex items-start gap-2 p-3 rounded-lg bg-slate-50 border border-slate-200 text-sm">
          <Lock className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
          <p className="text-slate-700">
            <strong>System-Control</strong> — Einige Felder sind schreibgeschützt.
            Nur: Name, Erklärungstext, Leitfragen, Nachweise, Gewicht, Gate-Zuordnung, Verantwortlichkeit.
          </p>
        </div>
      )}

      {/* Tabs */}
      <div className="px-6 pt-4 bg-[var(--bg-card)]">
        <TabNav active={tab} onChange={setTab} />
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="max-w-3xl space-y-5">

          {/* ── Tab: Allgemein ───────────────────────── */}
          {tab === "general" && (
            <>
              <FieldGroup label="Name (sichtbar)" hint="Wird im Workspace angezeigt">
                <TextInput value={val("name") as string ?? ""} onChange={v => set("name", v)} />
              </FieldGroup>
              <FieldGroup label="Slug / Interne ID" hint="Eindeutig, nicht änderbar nach Erstellen">
                <TextInput value={ctrl.slug} onChange={() => {}} disabled />
              </FieldGroup>
              {ctrl.system_id && (
                <FieldGroup label="System-ID">
                  <TextInput value={ctrl.system_id} onChange={() => {}} disabled />
                </FieldGroup>
              )}
              <FieldGroup label="Verantwortliche Rolle">
                <TextInput
                  value={val("responsible_role") as string ?? ""}
                  onChange={v => set("responsible_role", v)}
                  placeholder="z.B. Quality Manager, Product Owner"
                />
              </FieldGroup>
              <FieldGroup label="Review-Intervall (Tage)">
                <input
                  type="number"
                  value={val("review_interval_days") as number ?? 365}
                  onChange={e => set("review_interval_days", parseInt(e.target.value))}
                  className="w-32 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
                />
              </FieldGroup>
              <FieldGroup label="Gate-Zuordnung" hint="Welche Gates dieses Control betrifft">
                <div className="flex gap-2 flex-wrap">
                  {GATE_OPTIONS.map(g => {
                    const gatePhases = val("gate_phases") as string[] ?? [];
                    const active = gatePhases.includes(g);
                    return (
                      <button
                        key={g}
                        onClick={() => {
                          const current = gatePhases;
                          set("gate_phases", active ? current.filter(x => x !== g) : [...current, g]);
                        }}
                        className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                          active
                            ? "bg-violet-600 text-white"
                            : "bg-[var(--bg-base)] border border-[var(--border-subtle)] text-[var(--ink-mid)] hover:border-violet-400"
                        }`}
                      >
                        {g}
                      </button>
                    );
                  })}
                </div>
              </FieldGroup>
              <FieldGroup label="Im Frontend sichtbar">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={val("is_visible_in_frontend") as boolean ?? true}
                    onChange={e => set("is_visible_in_frontend", e.target.checked)}
                    className="w-4 h-4 accent-violet-600"
                  />
                  <span className="text-sm text-[var(--ink-mid)]">Für Nutzer sichtbar</span>
                </label>
              </FieldGroup>
            </>
          )}

          {/* ── Tab: Nutzertext ──────────────────────── */}
          {tab === "user" && (
            <>
              <FieldGroup label="Kurzbeschreibung" hint="Kurze, verständliche Erklärung für Nutzer">
                <TextInput multiline value={val("short_description") as string ?? ""} onChange={v => set("short_description", v)} />
              </FieldGroup>
              <FieldGroup label="Warum relevant?">
                <TextInput multiline value={val("why_relevant") as string ?? ""} onChange={v => set("why_relevant", v)} />
              </FieldGroup>
              <FieldGroup label="Was prüfen?">
                <TextInput multiline value={val("what_to_check") as string ?? ""} onChange={v => set("what_to_check", v)} />
              </FieldGroup>
              <FieldGroup label="Was tun?">
                <TextInput multiline value={val("what_to_do") as string ?? ""} onChange={v => set("what_to_do", v)} />
              </FieldGroup>
              <FieldGroup label="Leitfragen" hint="Eine pro Zeile">
                <textarea
                  value={(val("guiding_questions") as string[] ?? []).join("\n")}
                  onChange={e => set("guiding_questions", e.target.value.split("\n").filter(Boolean))}
                  rows={4}
                  className="w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400 resize-y"
                  placeholder={"Frage 1\nFrage 2\nFrage 3"}
                />
              </FieldGroup>
              <FieldGroup label="Hilfetext">
                <TextInput multiline value={val("help_text") as string ?? ""} onChange={v => set("help_text", v)} />
              </FieldGroup>
            </>
          )}

          {/* ── Tab: Governance ──────────────────────── */}
          {tab === "governance" && (
            <>
              <FieldGroup label="Kontrollziel">
                <TextInput
                  multiline
                  value={val("control_objective") as string ?? ""}
                  onChange={v => set("control_objective", v)}
                  disabled={isFixed}
                  placeholder="Was soll durch dieses Control sichergestellt werden?"
                />
              </FieldGroup>
              <FieldGroup label="Risikobegründung">
                <TextInput
                  multiline
                  value={val("risk_rationale") as string ?? ""}
                  onChange={v => set("risk_rationale", v)}
                  disabled={isFixed}
                  placeholder="Welches Risiko wird durch dieses Control adressiert?"
                />
              </FieldGroup>
              <FieldGroup label="Eskalationslogik">
                <TextInput
                  multiline
                  value={val("escalation_logic") as string ?? ""}
                  onChange={v => set("escalation_logic", v)}
                  disabled={isFixed}
                  placeholder="Bei welchem Score-Wert / Status eskalieren?"
                />
              </FieldGroup>
              <FieldGroup label="Hard Stop">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={val("hard_stop") as boolean ?? false}
                    onChange={e => set("hard_stop", e.target.checked)}
                    disabled={isFixed}
                    className="w-4 h-4 accent-red-600"
                  />
                  <span className="text-sm text-[var(--ink-mid)]">
                    Wenn aktiv: Control blockiert Gate-Freigabe bei Score ≤ {val("hard_stop_threshold") as number}
                  </span>
                </label>
              </FieldGroup>
              {val("hard_stop") && (
                <FieldGroup label="Hard-Stop-Schwellwert">
                  <input
                    type="number"
                    min={0} max={3}
                    value={val("hard_stop_threshold") as number ?? 1}
                    onChange={e => set("hard_stop_threshold", parseInt(e.target.value))}
                    disabled={isFixed}
                    className="w-24 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
                  />
                </FieldGroup>
              )}
              <FieldGroup label="Trigger erforderlich?">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={val("requires_trigger") as boolean ?? false}
                    onChange={e => set("requires_trigger", e.target.checked)}
                    disabled={isFixed}
                    className="w-4 h-4 accent-amber-600"
                  />
                  <span className="text-sm text-[var(--ink-mid)]">Control wird nur durch Trigger aktiviert</span>
                </label>
              </FieldGroup>
              <FieldGroup label="Audit-Notizen (intern)">
                <TextInput
                  multiline
                  value={val("audit_notes") as string ?? ""}
                  onChange={v => set("audit_notes", v)}
                  placeholder="Interne Notizen für Prüfer und Admin"
                />
              </FieldGroup>
            </>
          )}

          {/* ── Tab: Scoring ─────────────────────────── */}
          {tab === "scoring" && (
            <>
              <FieldGroup label="Gewichtung" hint="Faktor für Gesamtscore-Berechnung (0.0–10.0)">
                <input
                  type="number"
                  min={0} max={10} step={0.5}
                  value={val("default_weight") as number ?? 1.0}
                  onChange={e => set("default_weight", parseFloat(e.target.value))}
                  className="w-28 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
                />
              </FieldGroup>
              <FieldGroup label="Scoring-Schema">
                <select
                  value={val("scoring_scheme_id") as string ?? ""}
                  onChange={e => set("scoring_scheme_id", e.target.value || null)}
                  disabled={isFixed}
                  className="w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none"
                >
                  <option value="">Standard (0–3)</option>
                  {scoringSchemes?.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </FieldGroup>
              <div className="p-4 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                <p className="text-xs font-medium text-[var(--ink-muted)] mb-3 uppercase tracking-wider">Standard Bewertungsskala</p>
                <div className="space-y-2">
                  {[
                    { v: 0, label: "Nicht bewertet", color: "bg-gray-100 text-gray-600" },
                    { v: 1, label: "Kritisch unzureichend", color: "bg-red-100 text-red-700" },
                    { v: 2, label: "Teilweise beherrscht", color: "bg-amber-100 text-amber-700" },
                    { v: 3, label: "Beherrscht", color: "bg-green-100 text-green-700" },
                  ].map(({ v, label, color }) => (
                    <div key={v} className="flex items-center gap-3">
                      <span className={`w-7 h-7 rounded flex items-center justify-center text-sm font-bold ${color}`}>{v}</span>
                      <span className="text-sm text-[var(--ink-mid)]">{label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ── Tab: Nachweise ───────────────────────── */}
          {tab === "evidence" && (
            <div className="space-y-3">
              <p className="text-sm text-[var(--ink-muted)]">
                Definierte Nachweis-Anforderungen für dieses Control.
                Direkte Zuordnung über den{" "}
                <Link href={`/${org}/admin/governance/evidence`} className="text-violet-600 hover:underline">
                  Nachweis-Katalog
                </Link>.
              </p>
              {(ctrl.evidence_requirements ?? []).length === 0 ? (
                <div className="text-center py-8 bg-[var(--bg-base)] rounded-lg border border-[var(--border-subtle)]">
                  <p className="text-sm text-[var(--ink-muted)]">Keine Nachweise definiert</p>
                  <p className="text-xs text-[var(--ink-muted)] mt-1">
                    Fehlende Nachweisdefinitionen werden im Dashboard als Warnung angezeigt.
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  {ctrl.evidence_requirements.map((ev, i) => (
                    <div key={i} className="flex items-center gap-3 p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        ev.requirement === "mandatory"
                          ? "bg-red-100 text-red-700"
                          : "bg-slate-100 text-slate-600"
                      }`}>
                        {ev.requirement === "mandatory" ? "Pflicht" : "Optional"}
                      </span>
                      <span className="text-sm text-[var(--ink-mid)] font-mono">{ev.evidence_type_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── Tab: Historie ────────────────────────── */}
          {tab === "history" && (
            <div className="space-y-3">
              {!versions || versions.length === 0 ? (
                <div className="text-center py-8 text-sm text-[var(--ink-muted)]">
                  Noch keine veröffentlichten Versionen.
                </div>
              ) : (
                versions.map(v => (
                  <div key={v.id} className="flex items-center gap-4 p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                    <span className="text-xs font-bold text-violet-700 bg-violet-50 px-2 py-1 rounded">v{v.version}</span>
                    <div className="flex-1">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                        v.status === "approved" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600"
                      }`}>
                        {v.status}
                      </span>
                      {v.change_reason && (
                        <p className="text-xs text-[var(--ink-muted)] mt-0.5">{v.change_reason}</p>
                      )}
                    </div>
                    <span className="text-xs text-[var(--ink-muted)]">
                      {new Date(v.created_at).toLocaleDateString("de-DE")}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
