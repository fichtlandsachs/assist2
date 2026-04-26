"use client";

import { useState } from "react";
import {
  X, AlertTriangle, Lock, Zap, GitMerge,
  CheckCircle2, Clock, FileCheck, ListTodo, History,
  Info, Save, Plus, Trash2, ExternalLink, TrendingUp,
  TrendingDown, Minus,
} from "lucide-react";
import {
  useAssessmentItem,
  submitScore, addEvidence, removeEvidence,
  createAction, updateAction,
  type AssessmentItemDetail,
  type ComplianceAction,
} from "@/lib/hooks/useCompliance";

interface Props {
  assessmentId: string;
  itemId: string;
  canScore: boolean;
  canEdit: boolean;
  onClose: () => void;
  onScored: () => void;
}

// ── Score button helper ───────────────────────────────────────────────────────

const SCORE_CONFIG = [
  { value: 0, label: "–",  desc: "Nicht bewertet", color: "bg-slate-100 text-slate-500 border-slate-200" },
  { value: 1, label: "1",  desc: "Kritisch",        color: "bg-red-100 text-red-700 border-red-300" },
  { value: 2, label: "2",  desc: "Teilweise",       color: "bg-amber-100 text-amber-700 border-amber-300" },
  { value: 3, label: "3",  desc: "Beherrscht",      color: "bg-green-100 text-green-700 border-green-300" },
];

const STATUS_LABEL: Record<string, string> = {
  open: "Offen", in_progress: "In Bearbeitung", fulfilled: "Erfüllt",
  deviation: "Abweichung", not_fulfilled: "Nicht erfüllt", not_assessable: "Nicht bewertbar",
};

const ACTION_STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  open:        { label: "Offen",        color: "bg-slate-100 text-slate-600" },
  in_progress: { label: "In Bearbeitung", color: "bg-blue-100 text-blue-700" },
  done:        { label: "Erledigt",     color: "bg-green-100 text-green-700" },
  escalated:   { label: "Eskaliert",    color: "bg-red-100 text-red-700"     },
  overdue:     { label: "Überfällig",   color: "bg-red-100 text-red-700"     },
};

// ── Tabs ──────────────────────────────────────────────────────────────────────

const TABS = [
  { key: "general",   label: "Allgemein", icon: Info },
  { key: "score",     label: "Bewertung", icon: CheckCircle2 },
  { key: "evidence",  label: "Nachweise", icon: FileCheck },
  { key: "actions",   label: "Maßnahmen", icon: ListTodo },
  { key: "origin",    label: "Herkunft",  icon: Zap },
  { key: "history",   label: "Historie",  icon: History },
];

// ── Main panel ────────────────────────────────────────────────────────────────

export function ComplianceItemPanel({ assessmentId, itemId, canScore, canEdit, onClose, onScored }: Props) {
  const { data: item, isLoading, mutate } = useAssessmentItem(assessmentId, itemId);
  const [tab, setTab] = useState("general");

  if (isLoading || !item) {
    return (
      <div className="fixed inset-y-0 right-0 w-full md:w-[520px] bg-[var(--bg-card)] shadow-2xl border-l border-[var(--border-subtle)] flex items-center justify-center z-40">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
      </div>
    );
  }

  const scoreConf = SCORE_CONFIG[item.score] ?? SCORE_CONFIG[0];
  const hasCritical = item.hard_stop && item.blocks_gate;

  return (
    <div className="fixed inset-y-0 right-0 w-full md:w-[540px] bg-[var(--bg-card)] shadow-2xl border-l border-[var(--border-subtle)] flex flex-col z-40">
      {/* Header */}
      <div className={`px-5 py-4 border-b border-[var(--border-subtle)] ${hasCritical ? "bg-red-50" : "bg-[var(--bg-card)]"}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {item.hard_stop && (
                <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700">
                  <AlertTriangle className="h-3 w-3" /> Hard Stop
                </span>
              )}
              {item.blocks_gate && (
                <span className="px-1.5 py-0.5 rounded text-xs font-bold bg-red-600 text-white">GATE BLOCKIERT</span>
              )}
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${scoreConf.color} border`}>
                Score {scoreConf.value} — {scoreConf.desc}
              </span>
            </div>
            <h2 className="text-sm font-semibold text-[var(--ink-strong)] mt-1.5 line-clamp-2">{item.control_name}</h2>
            <p className="text-xs text-[var(--ink-muted)] font-mono mt-0.5">{item.control_slug}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-[var(--bg-hover)] shrink-0">
            <X className="h-4 w-4 text-[var(--ink-muted)]" />
          </button>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 border-b border-[var(--border-subtle)] overflow-x-auto shrink-0">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => setTab(key)}
            className={`flex items-center gap-1.5 px-3.5 py-2.5 text-xs whitespace-nowrap border-b-2 transition-colors ${
              tab === key
                ? "border-violet-500 text-violet-700 font-medium"
                : "border-transparent text-[var(--ink-muted)] hover:text-[var(--ink-mid)]"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-5">
        {tab === "general" && <GeneralTab item={item} />}
        {tab === "score" && (
          <ScoreTab
            item={item}
            assessmentId={assessmentId}
            canScore={canScore}
            onScored={() => { mutate(); onScored(); }}
          />
        )}
        {tab === "evidence" && (
          <EvidenceTab
            item={item}
            assessmentId={assessmentId}
            canEdit={canEdit}
            onChanged={() => mutate()}
          />
        )}
        {tab === "actions" && (
          <ActionsTab
            item={item}
            assessmentId={assessmentId}
            canEdit={canEdit}
            onChanged={() => mutate()}
          />
        )}
        {tab === "origin" && <OriginTab item={item} />}
        {tab === "history" && <HistoryTab item={item} />}
      </div>
    </div>
  );
}

// ── Tab: Allgemein ────────────────────────────────────────────────────────────

function GeneralTab({ item }: { item: AssessmentItemDetail }) {
  return (
    <div className="space-y-4">
      {item.control_objective && (
        <Field label="Kontrollziel">{item.control_objective}</Field>
      )}
      {item.why_relevant && (
        <Field label="Warum relevant?">{item.why_relevant}</Field>
      )}
      {item.what_to_check && (
        <Field label="Was prüfen?">{item.what_to_check}</Field>
      )}
      {item.guiding_questions.length > 0 && (
        <Field label="Leitfragen">
          <ul className="list-disc list-inside space-y-1">
            {item.guiding_questions.map((q, i) => (
              <li key={i} className="text-sm text-[var(--ink-mid)]">{q}</li>
            ))}
          </ul>
        </Field>
      )}
      <div className="grid grid-cols-2 gap-3">
        <MetaItem label="Kategorie" value={item.category_name ?? "–"} />
        <MetaItem label="Verantwortliche Rolle" value={item.responsible_role ?? "–"} />
        <MetaItem label="Gates" value={item.gate_phases.join(", ") || "–"} />
        <MetaItem label="Gewichtung" value={`${item.default_weight}×`} />
        <MetaItem label="Control-Version" value={`v${item.control_version}`} />
        <MetaItem label="Aktivierungsquelle" value={item.activation_source} />
      </div>
      {item.hard_stop && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-sm font-medium text-red-800">Hard-Stop-Control</span>
          </div>
          <p className="text-xs text-red-700">
            Ein Score ≤ {item.hard_stop_threshold} blockiert alle zugehörigen Gates.
            Aktueller Status: {item.blocks_gate ? "🔴 BLOCKIERT" : "✅ Nicht blockierend"}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Tab: Bewertung ────────────────────────────────────────────────────────────

function ScoreTab({ item, assessmentId, canScore, onScored }: {
  item: AssessmentItemDetail; assessmentId: string; canScore: boolean; onScored: () => void;
}) {
  const [selectedScore, setSelectedScore] = useState(item.score);
  const [rationale, setRationale] = useState(item.rationale ?? "");
  const [residualRisk, setResidualRisk] = useState(item.residual_risk ?? "");
  const [saving, setSaving] = useState(false);

  const changed = selectedScore !== item.score || rationale !== (item.rationale ?? "") || residualRisk !== (item.residual_risk ?? "");

  const handleSave = async () => {
    setSaving(true);
    try {
      await submitScore(assessmentId, item.id, selectedScore, rationale || undefined, residualRisk || undefined);
      onScored();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const previousScore = item.score_history.length > 1
    ? item.score_history[item.score_history.length - 2]?.to_score
    : null;

  const cls = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400 resize-y";

  return (
    <div className="space-y-4">
      {/* Score selector */}
      <div>
        <p className="text-xs font-medium text-[var(--ink-muted)] mb-2">Bewertung wählen</p>
        <div className="grid grid-cols-4 gap-2">
          {SCORE_CONFIG.map(cfg => (
            <button
              key={cfg.value}
              disabled={!canScore}
              onClick={() => setSelectedScore(cfg.value)}
              className={`flex flex-col items-center gap-1 p-3 rounded-xl border-2 transition-all ${
                selectedScore === cfg.value
                  ? `${cfg.color} border-current shadow-sm scale-105`
                  : "border-[var(--border-subtle)] hover:border-violet-300 bg-[var(--bg-card)]"
              } disabled:opacity-50 disabled:cursor-not-allowed`}
            >
              <span className="text-2xl font-bold">{cfg.label}</span>
              <span className="text-xs text-center leading-tight">{cfg.desc}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Trend indicator */}
      {previousScore !== null && previousScore !== item.score && (
        <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)]">
          {previousScore < item.score
            ? <TrendingUp className="h-3.5 w-3.5 text-green-500" />
            : <TrendingDown className="h-3.5 w-3.5 text-red-500" />
          }
          Vorherige Bewertung: {previousScore}
        </div>
      )}

      {/* Rationale */}
      <div>
        <label className="block text-xs font-medium text-[var(--ink-strong)] mb-1">Bewertungsbegründung</label>
        <textarea disabled={!canScore} value={rationale} onChange={e => setRationale(e.target.value)}
          className={cls} rows={3}
          placeholder="Kurze Begründung der Bewertung, Evidenzgrundlage…" />
      </div>

      {/* Residual risk */}
      <div>
        <label className="block text-xs font-medium text-[var(--ink-strong)] mb-1">Rest-Risiko</label>
        <textarea disabled={!canScore} value={residualRisk} onChange={e => setResidualRisk(e.target.value)}
          className={cls} rows={2}
          placeholder="Offene Risiken nach Maßnahmen…" />
      </div>

      {/* Gate impact preview */}
      {selectedScore <= item.hard_stop_threshold && item.hard_stop && (
        <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-xs text-red-700">
          <strong>Gate-Auswirkung:</strong> Bei Score {selectedScore} wird dieses Hard-Stop-Control
          Gate {item.gate_phases.join(", ")} blockieren.
        </div>
      )}
      {selectedScore === 2 && item.hard_stop && (
        <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-700">
          <strong>Gate-Auswirkung:</strong> Score 2 bei Hard-Stop → maximal Conditional Go.
        </div>
      )}

      {/* Meta */}
      {item.assessed_by_name && (
        <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)]">
          <CheckCircle2 className="h-3.5 w-3.5" />
          Bewertet von {item.assessed_by_name}
          {item.assessed_at && ` am ${new Date(item.assessed_at).toLocaleDateString("de-DE")}`}
        </div>
      )}

      {canScore && changed && (
        <button onClick={handleSave} disabled={saving}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 transition-colors disabled:opacity-60">
          <Save className="h-4 w-4" />
          {saving ? "Speichern…" : "Bewertung speichern"}
        </button>
      )}
    </div>
  );
}

// ── Tab: Nachweise ────────────────────────────────────────────────────────────

function EvidenceTab({ item, assessmentId, canEdit, onChanged }: {
  item: AssessmentItemDetail; assessmentId: string; canEdit: boolean; onChanged: () => void;
}) {
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ evidence_type_name: "", file_name: "", external_ref: "", description: "" });
  const [saving, setSaving] = useState(false);

  const handleAdd = async () => {
    setSaving(true);
    try {
      await addEvidence(assessmentId, item.id, form);
      setAdding(false);
      setForm({ evidence_type_name: "", file_name: "", external_ref: "", description: "" });
      onChanged();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (evId: string) => {
    if (!confirm("Nachweis entfernen?")) return;
    try {
      await removeEvidence(assessmentId, item.id, evId);
      onChanged();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const evidenceStatus = item.evidence_status;

  return (
    <div className="space-y-4">
      {/* Status banner */}
      <div className={`flex items-center gap-2 p-3 rounded-lg text-sm ${
        evidenceStatus === "complete" ? "bg-green-50 border border-green-200 text-green-800" :
        evidenceStatus === "partial"  ? "bg-amber-50 border border-amber-200 text-amber-800" :
        "bg-slate-50 border border-slate-200 text-slate-600"
      }`}>
        <FileCheck className="h-4 w-4 shrink-0" />
        Nachweisstand: {evidenceStatus === "complete" ? "Vollständig" : evidenceStatus === "partial" ? "Teilweise" : "Fehlt"}
      </div>

      {/* Required evidence */}
      {item.required_evidence_types.length > 0 && (
        <div>
          <p className="text-xs font-medium text-[var(--ink-muted)] mb-2">Erforderliche Nachweise</p>
          <div className="space-y-1">
            {item.required_evidence_types.map((ev: unknown, i) => {
              const evObj = ev as Record<string, string>;
              return (
                <div key={i} className="flex items-center gap-2 text-xs p-2 rounded bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                  <span className={`px-1.5 py-0.5 rounded ${evObj.requirement === "mandatory" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"}`}>
                    {evObj.requirement === "mandatory" ? "Pflicht" : "Optional"}
                  </span>
                  <span className="text-[var(--ink-mid)] font-mono">{evObj.evidence_type_id || "–"}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Linked evidence */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-medium text-[var(--ink-muted)]">Verknüpfte Nachweise ({item.evidence_links.length})</p>
          {canEdit && (
            <button onClick={() => setAdding(a => !a)}
              className="flex items-center gap-1 px-2 py-1 text-xs bg-violet-50 text-violet-600 rounded hover:bg-violet-100">
              <Plus className="h-3 w-3" /> Hinzufügen
            </button>
          )}
        </div>

        {adding && (
          <div className="p-3 rounded-lg bg-violet-50 border border-violet-200 space-y-2 mb-3">
            {[
              { key: "evidence_type_name", label: "Nachweis-Typ" },
              { key: "file_name", label: "Dateiname" },
              { key: "external_ref", label: "Externe Referenz / URL" },
              { key: "description", label: "Beschreibung" },
            ].map(({ key, label }) => (
              <div key={key}>
                <label className="block text-xs mb-0.5 text-[var(--ink-muted)]">{label}</label>
                <input className="w-full px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded"
                  value={(form as Record<string, string>)[key]}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
              </div>
            ))}
            <div className="flex gap-2">
              <button onClick={handleAdd} disabled={saving}
                className="px-3 py-1.5 text-xs bg-violet-600 text-white rounded disabled:opacity-60">
                {saving ? "…" : "Speichern"}
              </button>
              <button onClick={() => setAdding(false)} className="px-3 py-1.5 text-xs text-[var(--ink-muted)]">Abbrechen</button>
            </div>
          </div>
        )}

        {item.evidence_links.length === 0 ? (
          <p className="text-xs text-[var(--ink-muted)] py-4 text-center">Noch keine Nachweise verknüpft.</p>
        ) : (
          <div className="space-y-2">
            {item.evidence_links.map(ev => (
              <div key={ev.id} className="flex items-start gap-2 p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
                <FileCheck className="h-4 w-4 text-violet-400 mt-0.5 shrink-0" />
                <div className="flex-1 min-w-0">
                  {ev.evidence_type_name && <p className="text-xs font-medium text-[var(--ink-strong)]">{ev.evidence_type_name}</p>}
                  {ev.file_name && <p className="text-xs text-[var(--ink-mid)]">{ev.file_name}</p>}
                  {ev.external_ref && (
                    <a href={ev.external_ref} target="_blank" rel="noopener noreferrer"
                      className="text-xs text-violet-600 hover:underline flex items-center gap-0.5">
                      <ExternalLink className="h-3 w-3" /> {ev.external_ref.slice(0, 50)}…
                    </a>
                  )}
                  {ev.description && <p className="text-xs text-[var(--ink-muted)] mt-0.5">{ev.description}</p>}
                </div>
                {canEdit && (
                  <button onClick={() => handleRemove(ev.id)} className="p-1 rounded hover:bg-red-50 shrink-0">
                    <Trash2 className="h-3.5 w-3.5 text-red-400" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: Maßnahmen ────────────────────────────────────────────────────────────

function ActionsTab({ item, assessmentId, canEdit, onChanged }: {
  item: AssessmentItemDetail; assessmentId: string; canEdit: boolean; onChanged: () => void;
}) {
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ title: "", description: "", priority: "medium", owner_name: "" });
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!form.title) return;
    setSaving(true);
    try {
      await createAction(assessmentId, item.id, form);
      setCreating(false);
      setForm({ title: "", description: "", priority: "medium", owner_name: "" });
      onChanged();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const handleStatusUpdate = async (action: ComplianceAction, newStatus: string) => {
    try {
      await updateAction(assessmentId, item.id, action.id, { status: newStatus });
      onChanged();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const openCount = item.actions.filter(a => a.status !== "done").length;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-[var(--ink-muted)]">
          {openCount > 0
            ? <span className="text-amber-600">{openCount} offene Maßnahme{openCount !== 1 ? "n" : ""}</span>
            : <span className="text-green-600">Alle Maßnahmen erledigt</span>
          }
        </p>
        {canEdit && (
          <button onClick={() => setCreating(c => !c)}
            className="flex items-center gap-1 px-2 py-1 text-xs bg-violet-50 text-violet-600 rounded hover:bg-violet-100">
            <Plus className="h-3 w-3" /> Maßnahme
          </button>
        )}
      </div>

      {creating && (
        <div className="p-3 rounded-lg bg-violet-50 border border-violet-200 space-y-2">
          <input className="w-full px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded"
            placeholder="Maßnahmen-Titel *" value={form.title}
            onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
          <textarea className="w-full px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded resize-y" rows={2}
            placeholder="Beschreibung" value={form.description}
            onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
          <div className="grid grid-cols-2 gap-2">
            <select className="px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded"
              value={form.priority} onChange={e => setForm(f => ({ ...f, priority: e.target.value }))}>
              <option value="low">Niedrig</option>
              <option value="medium">Mittel</option>
              <option value="high">Hoch</option>
            </select>
            <input className="px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded"
              placeholder="Zuständig" value={form.owner_name}
              onChange={e => setForm(f => ({ ...f, owner_name: e.target.value }))} />
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} disabled={saving || !form.title}
              className="px-3 py-1.5 text-xs bg-violet-600 text-white rounded disabled:opacity-60">
              {saving ? "…" : "Erstellen"}
            </button>
            <button onClick={() => setCreating(false)} className="px-3 py-1.5 text-xs text-[var(--ink-muted)]">Abbrechen</button>
          </div>
        </div>
      )}

      {item.actions.length === 0 ? (
        <p className="text-xs text-[var(--ink-muted)] py-4 text-center">Keine Maßnahmen definiert.</p>
      ) : (
        <div className="space-y-2">
          {item.actions.map(action => {
            const cfg = ACTION_STATUS_CONFIG[action.status] ?? ACTION_STATUS_CONFIG.open;
            const isOverdue = action.due_date && action.status !== "done" && new Date(action.due_date) < new Date();
            return (
              <div key={action.id} className={`p-3 rounded-lg border ${isOverdue ? "border-red-200 bg-red-50/40" : "border-[var(--border-subtle)] bg-[var(--bg-base)]"}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--ink-strong)]">{action.title}</p>
                    {action.description && <p className="text-xs text-[var(--ink-muted)] mt-0.5">{action.description}</p>}
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                      <span className={`px-1.5 py-0.5 rounded text-xs ${action.priority === "high" ? "bg-red-100 text-red-700" : action.priority === "medium" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-600"}`}>
                        {action.priority === "high" ? "Hoch" : action.priority === "medium" ? "Mittel" : "Niedrig"}
                      </span>
                      {action.owner_name && <span className="text-xs text-[var(--ink-muted)]">👤 {action.owner_name}</span>}
                      {action.due_date && (
                        <span className={`text-xs ${isOverdue ? "text-red-600 font-medium" : "text-[var(--ink-muted)]"}`}>
                          📅 {new Date(action.due_date).toLocaleDateString("de-DE")}
                          {isOverdue && " (ÜBERFÄLLIG)"}
                        </span>
                      )}
                    </div>
                  </div>
                  {canEdit && action.status !== "done" && (
                    <button onClick={() => handleStatusUpdate(action, "done")}
                      className="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 shrink-0">
                      ✓ Erledigt
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Tab: Herkunft ─────────────────────────────────────────────────────────────

function OriginTab({ item }: { item: AssessmentItemDetail }) {
  type LucideEl = React.ElementType;
  const sourceIconMap: Record<string, LucideEl> = {
    fixed: Lock, trigger: Zap, gate: GitMerge, manual: Lock,
  };
  const SourceIcon: LucideEl = sourceIconMap[item.activation_source] ?? Lock;

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl bg-[var(--bg-base)] border border-[var(--border-subtle)]">
        <div className="flex items-center gap-3 mb-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            item.activation_source === "fixed"   ? "bg-slate-100 text-slate-600" :
            item.activation_source === "trigger" ? "bg-amber-100 text-amber-600" :
            item.activation_source === "gate"    ? "bg-violet-100 text-violet-600" : "bg-blue-100 text-blue-600"
          }`}>
            <SourceIcon className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--ink-strong)]">
              {{
                fixed: "Festes System-Control",
                trigger: "Trigger-aktiviert",
                gate: "Gate-spezifisch",
                manual: "Manuell ergänzt",
              }[item.activation_source] ?? item.activation_source}
            </p>
            <p className="text-xs text-[var(--ink-muted)]">Aktivierungsquelle</p>
          </div>
        </div>

        {item.activating_trigger_name && (
          <div className="p-2 rounded bg-amber-50 border border-amber-200">
            <p className="text-xs text-[var(--ink-muted)]">Auslösende Trigger-Regel:</p>
            <p className="text-sm font-medium text-amber-800">{item.activating_trigger_name}</p>
            {item.activating_trigger_id && (
              <p className="text-xs text-[var(--ink-muted)] font-mono mt-0.5">{item.activating_trigger_id}</p>
            )}
          </div>
        )}

        {item.activating_gate && (
          <div className="p-2 rounded bg-violet-50 border border-violet-200 mt-2">
            <p className="text-xs text-[var(--ink-muted)]">Gate:</p>
            <p className="text-sm font-medium text-violet-800">{item.activating_gate}</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <MetaItem label="Control-Typ" value={item.control_kind === "fixed" ? "Fest (System)" : "Dynamisch"} />
        <MetaItem label="Control-Version" value={`v${item.control_version}`} />
      </div>

      <div>
        <p className="text-xs font-medium text-[var(--ink-muted)] mb-2">Gate-Zuordnung dieses Controls</p>
        <div className="flex gap-2">
          {item.gate_phases.map(g => (
            <span key={g} className="px-3 py-1 rounded text-sm font-semibold bg-violet-100 text-violet-700">{g}</span>
          ))}
          {item.gate_phases.length === 0 && <span className="text-xs text-[var(--ink-muted)]">Keinem Gate zugeordnet</span>}
        </div>
      </div>
    </div>
  );
}

// ── Tab: Historie ─────────────────────────────────────────────────────────────

function HistoryTab({ item }: { item: AssessmentItemDetail }) {
  return (
    <div className="space-y-3">
      {item.score_history.length === 0 ? (
        <p className="text-xs text-[var(--ink-muted)] py-6 text-center">Noch keine Bewertungen vorgenommen.</p>
      ) : (
        <div className="relative">
          <div className="absolute left-4 top-0 bottom-0 w-px bg-[var(--border-subtle)]" />
          <div className="space-y-4">
            {[...item.score_history].reverse().map((entry, i) => {
              const isImprovement = entry.to_score > entry.from_score;
              const TrendIcon = entry.to_score > entry.from_score ? TrendingUp :
                                entry.to_score < entry.from_score ? TrendingDown : Minus;
              const trendColor = isImprovement ? "text-green-500" : entry.to_score < entry.from_score ? "text-red-500" : "text-slate-400";

              return (
                <div key={entry.id} className="flex gap-4 pl-8 relative">
                  <div className="absolute left-2.5 top-1.5 w-3 h-3 rounded-full bg-violet-500 border-2 border-white" />
                  <div className="flex-1 min-w-0 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[var(--ink-strong)]">
                        {entry.from_score} → {entry.to_score}
                      </span>
                      <TrendIcon className={`h-3.5 w-3.5 ${trendColor}`} />
                      {entry.gate_impact && (
                        <span className="text-xs text-amber-600">⚠ Gate-Auswirkung</span>
                      )}
                    </div>
                    {entry.rationale && (
                      <p className="text-xs text-[var(--ink-mid)] mt-0.5 italic">"{entry.rationale}"</p>
                    )}
                    {entry.gate_impact && (
                      <p className="text-xs text-amber-700 mt-0.5 bg-amber-50 px-2 py-1 rounded">{entry.gate_impact}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1 text-xs text-[var(--ink-muted)]">
                      {entry.changed_by_name && <span>von {entry.changed_by_name}</span>}
                      <span>{new Date(entry.created_at).toLocaleDateString("de-DE", {
                        day: "2-digit", month: "2-digit", year: "numeric",
                        hour: "2-digit", minute: "2-digit",
                      })}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">{label}</p>
      <div className="text-sm text-[var(--ink-mid)]">{children}</div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-2.5 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
      <p className="text-xs text-[var(--ink-muted)]">{label}</p>
      <p className="text-sm font-medium text-[var(--ink-strong)] mt-0.5">{value}</p>
    </div>
  );
}

