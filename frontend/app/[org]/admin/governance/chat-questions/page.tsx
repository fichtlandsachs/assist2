"use client";

import { useState } from "react";
import { use } from "react";
import useSWR, { mutate as globalMutate } from "swr";
import { fetcher, authFetch } from "@/lib/api/client";
import {
  MessageSquare, Search, Save, Wand2, Plus, Trash2,
  ChevronDown, ChevronUp, AlertCircle, CheckCircle2,
  RefreshCw, Info,
} from "lucide-react";

interface Props {
  params: Promise<{ org: string }>;
}

interface ChatQuestion {
  id: string;
  control_id: string;
  control_name: string;
  control_slug: string;
  primary_question: string;
  answer_type: string;
  hint_text: string | null;
  question_priority: number;
  always_ask: boolean;
  skippable: boolean;
  gap_label_template: string | null;
  risk_label_template: string | null;
  is_active: boolean;
  alternative_questions: AlternativeQuestion[];
  followup_questions: FollowupQuestion[];
  score_mapping_rules: ScoreMappingRule[];
  forbidden_terms: string[];
  updated_at: string;
}

interface AlternativeQuestion {
  condition_type: string;
  condition_value: string;
  question: string;
}

interface FollowupQuestion {
  trigger_condition: Record<string, unknown>;
  question: string;
  answer_type: string;
}

interface ScoreMappingRule {
  match_type: string;
  match_value: string;
  score: number;
}

const ANSWER_TYPE_LABELS: Record<string, string> = {
  free_text:    "Freitext",
  choice:       "Einfachauswahl",
  multi_choice: "Mehrfachauswahl",
  scale:        "Skala",
  yes_no:       "Ja/Nein",
  evidence:     "Nachweis vorhanden?",
};

const FORBIDDEN_DEFAULT = [
  "ISO 9001", "Normkapitel", "Audit", "regulatorische Anforderung",
  "Kontrollziel", "Gate-Blocking", "Hard-Stop-Control",
  "Assessment-Item", "Compliance-Score", "Konformität",
];

export default function ChatQuestionsAdminPage({ params }: Props) {
  const { org: orgSlug } = use(params);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<ChatQuestion> | null>(null);
  const [saving, setSaving] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const { data, isLoading, mutate } = useSWR<{ total: number; items: ChatQuestion[] }>(
    `/api/v1/compliance/chat/questions?page=${page}&page_size=30`,
    fetcher
  );

  const filtered = (data?.items ?? []).filter(q =>
    !search ||
    q.control_name.toLowerCase().includes(search.toLowerCase()) ||
    q.primary_question.toLowerCase().includes(search.toLowerCase())
  );

  const handleSeed = async () => {
    setSeeding(true);
    try {
      const res = await authFetch("/api/v1/compliance/chat/seed-questions", { method: "POST" });
      const json = await res.json();
      setSeedResult(`${json.created} neue Chat-Fragen erstellt.`);
      mutate();
    } catch (e) {
      setSeedResult("Fehler beim Seeden.");
    } finally {
      setSeeding(false);
    }
  };

  const handleEdit = (q: ChatQuestion) => {
    setEditingId(q.control_id);
    setEditDraft({ ...q });
    setExpandedId(q.id);
  };

  const handleSave = async () => {
    if (!editDraft || !editingId) return;
    setSaving(true);
    try {
      await authFetch(`/api/v1/compliance/chat/questions/${editingId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          primary_question: editDraft.primary_question,
          answer_type: editDraft.answer_type,
          hint_text: editDraft.hint_text,
          question_priority: editDraft.question_priority,
          always_ask: editDraft.always_ask,
          skippable: editDraft.skippable,
          gap_label_template: editDraft.gap_label_template,
          risk_label_template: editDraft.risk_label_template,
          is_active: editDraft.is_active,
          alternative_questions: editDraft.alternative_questions,
          followup_questions: editDraft.followup_questions,
          score_mapping_rules: editDraft.score_mapping_rules,
          forbidden_terms: editDraft.forbidden_terms,
        }),
      });
      setEditingId(null);
      setEditDraft(null);
      mutate();
    } catch (e) {
      alert("Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  };

  const ta = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400 resize-y";
  const inp = "w-full px-3 py-1.5 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400";

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-violet-500" />
            Chat-Fragen konfigurieren
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-1">
            Lege fest, wie Controls im Chat für Fachanwender formuliert werden — ohne ISO- oder Audit-Sprache.
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleSeed} disabled={seeding}
            className="flex items-center gap-2 px-3 py-2 text-sm bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-60">
            <Wand2 className="h-4 w-4" />
            {seeding ? "Wird erstellt…" : "Standard-Fragen generieren"}
          </button>
        </div>
      </div>

      {seedResult && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 border border-green-200 text-sm text-green-800">
          <CheckCircle2 className="h-4 w-4" />
          {seedResult}
          <button onClick={() => setSeedResult(null)} className="ml-auto text-green-600">×</button>
        </div>
      )}

      {/* Language guardrail reminder */}
      <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200">
        <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
        <div className="text-xs text-amber-800">
          <strong>Sprachregeln für Chat-Fragen:</strong> Keine ISO-, Norm- oder Audit-Begriffe.
          Schreibe so wie ein erfahrener Kollege aus Produktmanagement oder Qualität fragen würde.
          Verwende Sprache wie: <em>„Für den Markteintritt…"</em>, <em>„Wie kritisch wäre ein Ausfall…"</em>,
          <em>„Welche Tests liegen schon vor…"</em>
        </div>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[var(--ink-muted)]" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Control oder Frage suchen…"
          className="w-full pl-8 pr-3 py-1.5 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400" />
      </div>

      {/* Question list */}
      {isLoading ? (
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-violet-500" />
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(q => {
            const isExpanded = expandedId === q.id;
            const isEditing = editingId === q.control_id;
            const draft = isEditing ? editDraft : null;

            return (
              <div key={q.id}
                className={`bg-[var(--bg-card)] rounded-xl border ${
                  q.is_active ? "border-[var(--border-subtle)]" : "border-dashed border-slate-200 opacity-60"
                }`}>
                {/* Row header */}
                <div className="flex items-center gap-3 px-4 py-3 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : q.id)}>
                  <div className={`w-2 h-2 rounded-full shrink-0 ${q.is_active ? "bg-green-500" : "bg-slate-300"}`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-mono text-violet-600 bg-violet-50 px-1.5 py-0.5 rounded">
                        {q.control_slug}
                      </span>
                      <span className="text-sm font-medium text-[var(--ink-strong)] truncate">{q.control_name}</span>
                      <span className="text-xs text-[var(--ink-muted)] bg-slate-100 px-1.5 py-0.5 rounded">
                        {ANSWER_TYPE_LABELS[q.answer_type] ?? q.answer_type}
                      </span>
                      {q.always_ask && (
                        <span className="text-xs text-violet-700 bg-violet-50 px-1.5 py-0.5 rounded">Immer fragen</span>
                      )}
                      <span className="text-xs text-[var(--ink-muted)]">Priorität {q.question_priority}</span>
                    </div>
                    <p className="text-xs text-[var(--ink-muted)] mt-0.5 truncate italic">
                      „{q.primary_question}"
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {!isEditing && (
                      <button onClick={e => { e.stopPropagation(); handleEdit(q); }}
                        className="px-2.5 py-1 text-xs bg-violet-50 text-violet-600 rounded hover:bg-violet-100">
                        Bearbeiten
                      </button>
                    )}
                    {isExpanded ? <ChevronUp className="h-4 w-4 text-[var(--ink-muted)]" /> : <ChevronDown className="h-4 w-4 text-[var(--ink-muted)]" />}
                  </div>
                </div>

                {/* Expanded / edit area */}
                {isExpanded && (
                  <div className="border-t border-[var(--border-subtle)] px-4 py-4 space-y-4">
                    {isEditing && draft ? (
                      <>
                        {/* Primary question */}
                        <div>
                          <label className="block text-xs font-semibold text-[var(--ink-strong)] mb-1.5">
                            Primärfrage (Fachanwender-Sprache)
                          </label>
                          <textarea rows={3} className={ta} value={draft.primary_question ?? ""}
                            onChange={e => setEditDraft(d => ({ ...d, primary_question: e.target.value }))} />
                          <p className="text-xs text-[var(--ink-muted)] mt-1">
                            Kein ISO-/Audit-Jargon. Formuliere wie ein erfahrener Produktmanager.
                          </p>
                        </div>

                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                          {/* Answer type */}
                          <div>
                            <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Antworttyp</label>
                            <select className="w-full px-2.5 py-1.5 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none"
                              value={draft.answer_type ?? "free_text"}
                              onChange={e => setEditDraft(d => ({ ...d, answer_type: e.target.value }))}>
                              {Object.entries(ANSWER_TYPE_LABELS).map(([k, v]) => (
                                <option key={k} value={k}>{v}</option>
                              ))}
                            </select>
                          </div>

                          {/* Priority */}
                          <div>
                            <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Priorität (1=hoch, 99=niedrig)</label>
                            <input type="number" min={1} max={99} className={inp}
                              value={draft.question_priority ?? 50}
                              onChange={e => setEditDraft(d => ({ ...d, question_priority: parseInt(e.target.value) }))} />
                          </div>

                          {/* Toggles */}
                          <div className="flex flex-col gap-2 justify-end">
                            {[
                              { key: "always_ask", label: "Immer fragen" },
                              { key: "skippable", label: "Überspringbar" },
                              { key: "is_active", label: "Aktiv" },
                            ].map(({ key, label }) => (
                              <label key={key} className="flex items-center gap-2 text-xs cursor-pointer">
                                <input type="checkbox"
                                  checked={Boolean((draft as Record<string, unknown>)[key])}
                                  onChange={e => setEditDraft(d => ({ ...d, [key]: e.target.checked }))} />
                                {label}
                              </label>
                            ))}
                          </div>
                        </div>

                        {/* Hint */}
                        <div>
                          <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Hinweistext (optional, unter der Frage)</label>
                          <input className={inp} value={draft.hint_text ?? ""}
                            onChange={e => setEditDraft(d => ({ ...d, hint_text: e.target.value }))}
                            placeholder="z.B. 'Denke an CE-Zeichen, WEEE, RoHS…'" />
                        </div>

                        {/* Gap label */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          <div>
                            <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">
                              Lücken-Hinweis (Fachanwender-sichtbar)
                            </label>
                            <textarea rows={2} className={ta}
                              value={draft.gap_label_template ?? ""}
                              onChange={e => setEditDraft(d => ({ ...d, gap_label_template: e.target.value }))}
                              placeholder="z.B. 'Für den Markteintritt fehlen noch belastbare Angaben…'" />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">
                              Risiko-Hinweis (Fachanwender-sichtbar)
                            </label>
                            <textarea rows={2} className={ta}
                              value={draft.risk_label_template ?? ""}
                              onChange={e => setEditDraft(d => ({ ...d, risk_label_template: e.target.value }))}
                              placeholder="z.B. 'Hier ist noch Risiko offen: Marktanforderungen nicht bekannt.'" />
                          </div>
                        </div>

                        {/* Forbidden terms */}
                        <div>
                          <label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">
                            Verbotene Begriffe (werden nicht in Chat-Fragen verwendet)
                          </label>
                          <div className="flex flex-wrap gap-1.5 p-2 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)] min-h-10">
                            {(draft.forbidden_terms ?? []).map((term, i) => (
                              <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-red-50 text-red-700 text-xs rounded">
                                {term}
                                <button onClick={() => setEditDraft(d => ({
                                  ...d,
                                  forbidden_terms: (d?.forbidden_terms ?? []).filter((_, idx) => idx !== i),
                                }))}>×</button>
                              </span>
                            ))}
                            <input
                              className="text-xs bg-transparent outline-none min-w-24 flex-1"
                              placeholder="Begriff hinzufügen…"
                              onKeyDown={e => {
                                if (e.key === "Enter" || e.key === ",") {
                                  e.preventDefault();
                                  const val = (e.target as HTMLInputElement).value.trim();
                                  if (val) {
                                    setEditDraft(d => ({
                                      ...d,
                                      forbidden_terms: [...(d?.forbidden_terms ?? []), val],
                                    }));
                                    (e.target as HTMLInputElement).value = "";
                                  }
                                }
                              }} />
                          </div>
                        </div>

                        {/* Save/Cancel */}
                        <div className="flex gap-2 pt-2">
                          <button onClick={handleSave} disabled={saving}
                            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 disabled:opacity-60">
                            <Save className="h-4 w-4" />
                            {saving ? "Speichern…" : "Speichern"}
                          </button>
                          <button onClick={() => { setEditingId(null); setEditDraft(null); }}
                            className="px-4 py-2 text-sm text-[var(--ink-muted)] hover:text-[var(--ink-mid)]">
                            Abbrechen
                          </button>
                        </div>
                      </>
                    ) : (
                      // Read-only view
                      <div className="space-y-3">
                        <div className="p-3 rounded-lg bg-violet-50 border border-violet-100">
                          <p className="text-xs font-medium text-violet-700 mb-1">Primärfrage:</p>
                          <p className="text-sm text-[var(--ink-strong)] italic">„{q.primary_question}"</p>
                        </div>
                        <div className="grid grid-cols-2 gap-3 text-xs">
                          <div>
                            <p className="text-[var(--ink-muted)]">Lücken-Hinweis:</p>
                            <p className="text-[var(--ink-mid)]">{q.gap_label_template || "–"}</p>
                          </div>
                          <div>
                            <p className="text-[var(--ink-muted)]">Risiko-Hinweis:</p>
                            <p className="text-[var(--ink-mid)]">{q.risk_label_template || "–"}</p>
                          </div>
                        </div>
                        {q.forbidden_terms.length > 0 && (
                          <div>
                            <p className="text-xs text-[var(--ink-muted)] mb-1">Verbotene Begriffe:</p>
                            <div className="flex flex-wrap gap-1">
                              {q.forbidden_terms.map((t, i) => (
                                <span key={i} className="px-1.5 py-0.5 bg-red-50 text-red-700 text-xs rounded">{t}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}

          {filtered.length === 0 && !isLoading && (
            <div className="text-center py-12 text-[var(--ink-muted)] text-sm">
              {search ? "Keine Treffer." : "Noch keine Chat-Fragen konfiguriert. Klicke auf 'Standard-Fragen generieren'."}
            </div>
          )}
        </div>
      )}

      {/* Pagination */}
      {data && data.total > 30 && (
        <div className="flex items-center justify-between">
          <p className="text-xs text-[var(--ink-muted)]">{data.total} Einträge</p>
          <div className="flex gap-2">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
              className="px-2.5 py-1 text-xs rounded border border-[var(--border-subtle)] disabled:opacity-40">←</button>
            <span className="px-2 py-1 text-xs text-[var(--ink-muted)]">
              {page} / {Math.ceil(data.total / 30)}
            </span>
            <button disabled={page >= Math.ceil(data.total / 30)} onClick={() => setPage(p => p + 1)}
              className="px-2.5 py-1 text-xs rounded border border-[var(--border-subtle)] disabled:opacity-40">→</button>
          </div>
        </div>
      )}
    </div>
  );
}
