"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority, TestCase, TestResult, DoDItem, Feature, FeatureStatus, Epic } from "@/types";
import { AISuggestPanel } from "@/components/stories/AISuggestPanel";
import { EpicSelector } from "@/components/stories/EpicSelector";
import { ArrowLeft, Save, Pencil, X, Plus, CheckCircle, XCircle, Sparkles, GripVertical, GitBranch, ClipboardCheck, Trash2, FileText, RefreshCw, Users, Package, Lock } from "lucide-react";
import { SplitStoryPanel } from "@/components/stories/SplitStoryPanel";
import Link from "next/link";

interface StoryDocsData {
  changelog_entry: string;
  pdf_outline: string[];
  summary: string;
  technical_notes: string;
  confluence_page_url?: string | null;
  additional_info?: string | null;
  workarounds?: string | null;
}

const STATUS_OPTIONS: { value: StoryStatus; label: string }[] = [
  { value: "draft", label: "Entwurf" },
  { value: "in_review", label: "Überarbeitung" },
  { value: "ready", label: "Bereit" },
  { value: "in_progress", label: "In Arbeit" },
  { value: "testing", label: "Test" },
  { value: "done", label: "Fertig" },
  { value: "archived", label: "Archiviert" },
];

const STATUS_COLORS: Record<StoryStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  in_review: "bg-violet-100 text-violet-700",
  ready: "bg-blue-100 text-blue-700",
  in_progress: "bg-amber-100 text-amber-700",
  testing: "bg-orange-100 text-orange-700",
  done: "bg-green-100 text-green-700",
  archived: "bg-slate-200 text-slate-500",
};

const PRIORITY_OPTIONS: { value: StoryPriority; label: string }[] = [
  { value: "low", label: "Niedrig" },
  { value: "medium", label: "Mittel" },
  { value: "high", label: "Hoch" },
  { value: "critical", label: "Kritisch" },
];

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low: "text-slate-400",
  medium: "text-blue-500",
  high: "text-amber-500",
  critical: "text-red-500",
};

function EpicBadge({ epicId, orgId }: { epicId: string; orgId: string }) {
  const { data: epics } = useSWR<Epic[]>(
    `/api/v1/epics?org_id=${orgId}`,
    fetcher
  );
  const title = epics?.find((e) => e.id === epicId)?.title;
  if (!title) return null;
  return (
    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 text-xs font-medium">
      <GitBranch size={10} />
      {title}
    </span>
  );
}

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="mt-1 text-xs text-red-600">{msg}</p>;
}

function DroppableField({
  id,
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
  rows = 4,
  fieldName,
  editing,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  multiline?: boolean;
  rows?: number;
  fieldName: "title" | "description" | "acceptance_criteria";
  editing: boolean;
  error?: string;
}) {
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (multiline && textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value, multiline]);

  const handleDragOver = (e: React.DragEvent) => {
    if (!editing) return;
    const hasField = e.dataTransfer.types.includes("application/x-story-field");
    const hasCriterion = fieldName === "acceptance_criteria" && e.dataTransfer.types.includes("application/x-story-criterion");
    if (hasField || hasCriterion) {
      e.preventDefault();
      setIsDragOver(true);
    }
  };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (!editing) return;
    if (fieldName === "acceptance_criteria" && e.dataTransfer.types.includes("application/x-story-criterion")) {
      const text = e.dataTransfer.getData("application/x-story-criterion");
      if (text) onChange(value ? `${value}\n${text}` : text);
      return;
    }
    const droppedField = e.dataTransfer.getData("application/x-story-field");
    if (droppedField === fieldName) {
      const text = e.dataTransfer.getData("text/plain");
      if (text) onChange(text);
    }
  };

  const baseClass = `w-full px-3 py-2 text-sm border rounded-lg outline-none transition-colors ${
    isDragOver
      ? "border-brand-400 bg-brand-50 ring-2 ring-brand-200"
      : error
      ? "border-red-400 bg-red-50 focus:border-red-400 focus:ring-2 focus:ring-red-100"
      : "border-slate-300 bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
  }`;

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700 mb-1.5">
        {label}
      </label>
      {editing ? (
        multiline ? (
          <textarea
            ref={textareaRef}
            id={id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            placeholder={placeholder}
            rows={rows}
            className={`${baseClass} resize-y overflow-hidden`}
          />
        ) : (
          <input
            id={id}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            placeholder={placeholder}
            className={baseClass}
          />
        )
      ) : (
        <div className="px-3 py-2 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-lg min-h-[2.5rem] whitespace-pre-wrap">
          {value || <span className="text-slate-400">{placeholder}</span>}
        </div>
      )}
      <FieldError msg={error} />
    </div>
  );
}

const TEST_RESULT_COLORS: Record<TestResult, string> = {
  pending: "bg-slate-100 text-slate-600",
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  skipped: "bg-amber-100 text-amber-700",
};

const TEST_RESULT_LABELS: Record<TestResult, string> = {
  pending: "Ausstehend",
  passed: "Bestanden",
  failed: "Fehlgeschlagen",
  skipped: "Übersprungen",
};

interface AITestCaseSuggestionData {
  title: string;
  steps: string | null;
  expected_result: string | null;
}

function SuggestedTestCaseCard({
  suggestion,
  onAdd,
  onDragToForm,
}: {
  suggestion: AITestCaseSuggestionData;
  onAdd: (s: AITestCaseSuggestionData) => Promise<void>;
  onDragToForm: (s: AITestCaseSuggestionData) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData(
      "application/x-test-case-suggestion",
      JSON.stringify(suggestion)
    );
    e.dataTransfer.setData("text/plain", suggestion.title);
    e.dataTransfer.effectAllowed = "copy";
  };

  async function handleAdd() {
    setAdding(true);
    try {
      await onAdd(suggestion);
    } finally {
      setAdding(false);
    }
  }

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="border border-violet-200 rounded-lg bg-violet-50 hover:bg-white hover:border-violet-300 transition-all cursor-grab active:cursor-grabbing group"
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <GripVertical size={13} className="shrink-0 text-violet-300 group-hover:text-violet-400 transition-colors" />
        <span className="flex-1 min-w-0 text-sm font-medium text-slate-800 leading-tight break-words">{suggestion.title}</span>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 text-xs text-slate-400 hover:text-slate-600 px-1"
        >
          {expanded ? "▲" : "▼"}
        </button>
        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={adding}
          title="Direkt als Testfall hinzufügen"
          className="shrink-0 flex items-center gap-1 px-2 py-1 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 text-white rounded text-xs font-medium transition-colors"
        >
          {adding ? (
            <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" />
          ) : (
            <Plus size={12} />
          )}
          Hinzufügen
        </button>
      </div>
      {expanded && (suggestion.steps || suggestion.expected_result) && (
        <div className="px-3 pb-3 space-y-2 border-t border-violet-100 pt-2">
          {suggestion.steps && (
            <div>
              <p className="text-xs font-medium text-slate-500 mb-0.5">Schritte:</p>
              <p className="text-xs text-slate-700 whitespace-pre-wrap">{suggestion.steps}</p>
            </div>
          )}
          {suggestion.expected_result && (
            <div>
              <p className="text-xs font-medium text-slate-500 mb-0.5">Erwartetes Ergebnis:</p>
              <p className="text-xs text-slate-700 whitespace-pre-wrap">{suggestion.expected_result}</p>
            </div>
          )}
          <button
            type="button"
            onClick={() => onDragToForm(suggestion)}
            className="text-xs text-violet-600 hover:text-violet-800 underline"
          >
            In Formular laden zum Bearbeiten
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DefinitionOfDoneSection — links: Checkliste, rechts: Assistent
// ---------------------------------------------------------------------------

interface AIDoDSuggestionData {
  text: string;
  category: string | null;
}

function DefinitionOfDoneSection({ storyId, initialDod }: { storyId: string; initialDod: string | null }) {
  function parseDod(raw: string | null): DoDItem[] {
    if (!raw) return [];
    try { return JSON.parse(raw) as DoDItem[]; } catch { return []; }
  }

  const [items, setItems] = useState<DoDItem[]>(() => parseDod(initialDod));
  const [newText, setNewText] = useState("");
  const [showInput, setShowInput] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<AIDoDSuggestionData[] | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);

  async function persist(updated: DoDItem[]) {
    setSaving(true);
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}`, {
        method: "PATCH",
        body: JSON.stringify({ definition_of_done: JSON.stringify(updated) }),
      });
    } finally {
      setSaving(false);
    }
  }

  function toggleItem(index: number) {
    const updated = items.map((it, i) => i === index ? { ...it, done: !it.done } : it);
    setItems(updated);
    void persist(updated);
  }

  function removeItem(index: number) {
    const updated = items.filter((_, i) => i !== index);
    setItems(updated);
    void persist(updated);
  }

  function addItem(text: string) {
    if (!text.trim()) return;
    const updated = [...items, { text: text.trim(), done: false }];
    setItems(updated);
    void persist(updated);
  }

  function addFromSuggestion(s: AIDoDSuggestionData) {
    setAiSuggestions((prev) => prev?.filter((x) => x.text !== s.text) ?? prev);
    addItem(s.text);
  }

  async function handleLoadSuggestions() {
    setAiLoading(true);
    setAiError(null);
    try {
      const res = await apiRequest<{ suggestions: AIDoDSuggestionData[] }>(
        `/api/v1/user-stories/${storyId}/ai-dod`,
        { method: "POST" }
      );
      setAiSuggestions(res.suggestions);
    } catch (err: unknown) {
      setAiError((err as { error?: string })?.error ?? "Fehler beim Laden der Vorschläge.");
    } finally {
      setAiLoading(false);
    }
  }

  const doneCount = items.filter((i) => i.done).length;
  const progress = items.length > 0 ? Math.round((doneCount / items.length) * 100) : 0;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
      {/* LEFT: Checkliste */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={16} className="text-slate-500" />
            <h2 className="text-base font-semibold text-slate-900">Definition of Done</h2>
            {items.length > 0 && (
              <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium">
                {doneCount}/{items.length}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowInput((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium transition-colors"
          >
            <Plus size={14} />
            Kriterium
          </button>
        </div>

        <div className="p-4 space-y-3">
          {items.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{doneCount} von {items.length} erledigt</span>
                <span className={`font-semibold ${progress === 100 ? "text-green-600" : "text-slate-600"}`}>{progress}%</span>
              </div>
              <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${progress === 100 ? "bg-green-500" : "bg-brand-500"}`}
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {showInput && (
            <div className="flex gap-2">
              <input
                type="text"
                value={newText}
                onChange={(e) => setNewText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addItem(newText);
                    setNewText("");
                  }
                }}
                placeholder="Kriterium eingeben…"
                autoFocus
                className="flex-1 min-w-0 px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100"
              />
              <button
                onClick={() => { addItem(newText); setNewText(""); setShowInput(false); }}
                disabled={!newText.trim() || saving}
                className="shrink-0 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-xs font-medium transition-colors"
              >
                Hinzufügen
              </button>
              <button
                onClick={() => { setNewText(""); setShowInput(false); }}
                className="shrink-0 px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-colors"
              >
                Abbrechen
              </button>
            </div>
          )}

          {items.length === 0 && !showInput && (
            <p className="text-sm text-slate-400 text-center py-8">
              Noch keine DoD-Kriterien definiert. Füge eigene hinzu oder lass dir Vorschläge generieren.
            </p>
          )}

          {items.length > 0 && (
            <div className="space-y-1.5">
              {items.map((item, i) => (
                <div key={i} className={`flex items-start gap-3 px-3 py-2.5 rounded-lg border transition-colors group ${item.done ? "bg-green-50 border-green-200" : "bg-white border-slate-200"}`}>
                  <button
                    onClick={() => void toggleItem(i)}
                    className={`shrink-0 mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${item.done ? "bg-green-500 border-green-500" : "border-slate-300 hover:border-green-400"}`}
                  >
                    {item.done && <CheckCircle size={10} className="text-white" />}
                  </button>
                  <span className={`flex-1 min-w-0 text-sm break-words ${item.done ? "line-through text-slate-400" : "text-slate-700"}`}>
                    {item.text}
                  </span>
                  <button
                    onClick={() => void removeItem(i)}
                    className="shrink-0 p-0.5 text-slate-200 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all rounded"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Assistent */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles size={16} className="text-brand-500" />
            Assistent
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Schlägt DoD-Kriterien basierend auf der Story vor.
          </p>
        </div>

        <button
          onClick={() => void handleLoadSuggestions()}
          disabled={aiLoading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {aiLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Analysiert…
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Vorschläge generieren
            </>
          )}
        </button>

        {aiError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">{aiError}</div>
        )}

        <div className={`mt-4 space-y-2 transition-opacity duration-300 ${!aiSuggestions && !aiLoading ? "opacity-30 pointer-events-none select-none" : "opacity-100"}`}>
          {!aiSuggestions && (
            <div className="space-y-2">
              <div className="h-10 bg-slate-100 rounded-lg" />
              <div className="h-10 bg-slate-100 rounded-lg" />
              <div className="h-10 bg-slate-100 rounded-lg" />
              <p className="text-xs text-slate-400 text-center pt-1">Kriterien erscheinen nach der Analyse hier.</p>
            </div>
          )}

          {aiSuggestions?.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-4">Alle Vorschläge wurden übernommen.</p>
          )}

          {aiSuggestions && aiSuggestions.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
                  <Sparkles size={12} />
                  Vorschläge
                  <span className="normal-case font-normal text-slate-400">({aiSuggestions.length})</span>
                </p>
                <button
                  onClick={() => setAiSuggestions(null)}
                  className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                >
                  Schließen
                </button>
              </div>
              {aiSuggestions.map((s, i) => (
                <div key={i} className="flex items-start gap-2 px-3 py-2.5 border border-slate-200 rounded-lg bg-white hover:border-brand-200 transition-colors">
                  {s.category && (
                    <span className="shrink-0 px-1.5 py-0.5 bg-brand-50 text-brand-600 rounded text-xs font-medium">
                      {s.category}
                    </span>
                  )}
                  <span className="flex-1 min-w-0 text-sm text-slate-700 break-words">{s.text}</span>
                  <button
                    onClick={() => void addFromSuggestion(s)}
                    className="shrink-0 flex items-center gap-1 px-2 py-1 bg-brand-600 hover:bg-brand-700 text-white rounded text-xs font-medium transition-colors"
                  >
                    <Plus size={11} />
                    Hinzufügen
                  </button>
                </div>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TestCasesSection — persistent test cases with AI generation + status lock
// ---------------------------------------------------------------------------

const LOCKED_STORY_STATUSES = new Set(["testing", "done", "archived"]);

function TestCasesSection({ storyId, storyStatus }: { storyId: string; storyStatus: string }) {
  const isLocked = LOCKED_STORY_STATUSES.has(storyStatus);

  const { data: testCases, isLoading, mutate } = useSWR<TestCase[]>(
    `/api/v1/user-stories/${storyId}/test-cases`,
    fetcher
  );
  const [showForm, setShowForm] = useState(false);
  const [formTitle, setFormTitle] = useState("");
  const [formSteps, setFormSteps] = useState("");
  const [formExpected, setFormExpected] = useState("");
  const [saving, setSaving] = useState(false);
  const [markingId, setMarkingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSteps, setEditSteps] = useState("");
  const [editExpected, setEditExpected] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);
  const [lastAiCount, setLastAiCount] = useState<number | null>(null);

  async function generateAndSave() {
    setAiLoading(true);
    setAiError(null);
    setLastAiCount(null);
    try {
      const saved = await apiRequest<TestCase[]>(
        `/api/v1/user-stories/${storyId}/ai-test-cases`,
        { method: "POST" }
      );
      setLastAiCount(saved.length);
      // Replace AI-generated entries in cache without refetch
      mutate(
        (current) => {
          const manual = (current ?? []).filter((tc) => !tc.is_ai_generated);
          return [...saved, ...manual];
        },
        false
      );
    } catch (err: unknown) {
      setAiError((err as { error?: string })?.error ?? "Fehler beim Generieren der Testfälle.");
    } finally {
      setAiLoading(false);
    }
  }

  async function handleAddTestCase(e: React.FormEvent) {
    e.preventDefault();
    if (!formTitle.trim()) return;
    setSaving(true);
    try {
      const created = await apiRequest<TestCase>(`/api/v1/user-stories/${storyId}/test-cases`, {
        method: "POST",
        body: JSON.stringify({
          title: formTitle,
          steps: formSteps || null,
          expected_result: formExpected || null,
        }),
      });
      mutate((current) => [...(current ?? []), created], false);
      setFormTitle(""); setFormSteps(""); setFormExpected(""); setShowForm(false);
    } catch { /* ignore */ } finally { setSaving(false); }
  }

  async function handleMark(tcId: string, result: TestResult) {
    // Optimistic update
    mutate((current) => (current ?? []).map((tc) => tc.id === tcId ? { ...tc, result } : tc), false);
    setMarkingId(tcId);
    try {
      const updated = await apiRequest<TestCase>(`/api/v1/test-cases/${tcId}`, {
        method: "PATCH",
        body: JSON.stringify({ result }),
      });
      mutate((current) => (current ?? []).map((tc) => tc.id === tcId ? updated : tc), false);
    } catch {
      mutate(); // revert on error
    } finally { setMarkingId(null); }
  }

  function startEdit(tc: TestCase) {
    setEditingId(tc.id);
    setEditTitle(tc.title);
    setEditSteps(tc.steps ?? "");
    setEditExpected(tc.expected_result ?? "");
  }

  async function handleSaveEdit(tcId: string) {
    setEditSaving(true);
    try {
      const updated = await apiRequest<TestCase>(`/api/v1/test-cases/${tcId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle,
          steps: editSteps || null,
          expected_result: editExpected || null,
        }),
      });
      mutate((current) => (current ?? []).map((tc) => tc.id === tcId ? updated : tc), false);
      setEditingId(null);
    } catch { /* ignore */ } finally { setEditSaving(false); }
  }

  async function handleDelete(tcId: string) {
    if (!confirm("Testfall wirklich löschen?")) return;
    mutate((current) => (current ?? []).filter((tc) => tc.id !== tcId), false);
    try {
      await apiRequest(`/api/v1/test-cases/${tcId}`, { method: "DELETE" });
    } catch {
      mutate(); // revert on error
    }
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
      {/* LEFT: Testfall-Liste */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={16} className="text-slate-500" />
            <h2 className="text-base font-semibold text-slate-900">Testfälle</h2>
            {testCases && testCases.length > 0 && (
              <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded text-xs font-medium">
                {testCases.length}
              </span>
            )}
          </div>
          {isLocked ? (
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 text-slate-500 rounded-lg text-xs font-medium">
              <Lock size={13} />
              Gesperrt
            </span>
          ) : (
            <button
              onClick={() => setShowForm(!showForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium transition-colors"
            >
              <Plus size={14} />
              Hinzufügen
            </button>
          )}
        </div>

        {isLocked && (
          <div className="mx-4 mt-3 mb-1 flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-700">
            <Lock size={12} />
            Testfälle sind ab Status „Test" schreibgeschützt. Testergebnisse können weiterhin eingetragen werden.
          </div>
        )}

        <div className="p-4 space-y-3">
          {!isLocked && showForm && (
            <form onSubmit={(e) => void handleAddTestCase(e)} className="border border-slate-200 bg-slate-50 rounded-lg p-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Titel <span className="text-red-500">*</span></label>
                <input type="text" value={formTitle} onChange={e => setFormTitle(e.target.value)}
                  placeholder="Testfall Titel"
                  className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 bg-white" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Schritte</label>
                <textarea value={formSteps} onChange={e => setFormSteps(e.target.value)}
                  placeholder={"1. Schritt\n2. Schritt"} rows={3}
                  className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 bg-white resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Erwartetes Ergebnis</label>
                <textarea value={formExpected} onChange={e => setFormExpected(e.target.value)}
                  placeholder="Das erwartete Ergebnis..." rows={2}
                  className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 bg-white resize-none" />
              </div>
              <div className="flex gap-2">
                <button type="submit" disabled={saving || !formTitle.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-xs font-medium transition-colors">
                  {saving ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" /> : <Plus size={12} />}
                  Hinzufügen
                </button>
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-colors">
                  Abbrechen
                </button>
              </div>
            </form>
          )}

          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
            </div>
          )}

          {!isLoading && testCases && testCases.length === 0 && !showForm && (
            <p className="text-sm text-slate-400 text-center py-8">Noch keine Testfälle definiert.</p>
          )}

          {testCases && testCases.length > 0 && (
            <div className="space-y-3">
              {testCases.map((tc) => (
                <div key={tc.id} className={`border rounded-lg p-4 space-y-2 ${tc.is_ai_generated ? "border-violet-200 bg-violet-50/30" : "border-slate-200"}`}>
                  {editingId === tc.id ? (
                    <div className="space-y-2">
                      <input type="text" value={editTitle} onChange={e => setEditTitle(e.target.value)}
                        className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 bg-white" />
                      <textarea value={editSteps} onChange={e => setEditSteps(e.target.value)} rows={3}
                        placeholder="Schritte..."
                        className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 bg-white resize-none" />
                      <textarea value={editExpected} onChange={e => setEditExpected(e.target.value)} rows={2}
                        placeholder="Erwartetes Ergebnis..."
                        className="w-full px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 bg-white resize-none" />
                      <div className="flex gap-2">
                        <button onClick={() => void handleSaveEdit(tc.id)} disabled={editSaving}
                          className="flex items-center gap-1 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium transition-colors">
                          {editSaving ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" /> : <CheckCircle size={12} />}
                          Speichern
                        </button>
                        <button onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-colors">
                          Abbrechen
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex flex-wrap items-center gap-1.5 mb-1">
                            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TEST_RESULT_COLORS[tc.result]}`}>
                              {TEST_RESULT_LABELS[tc.result]}
                            </span>
                            {tc.is_ai_generated && (
                              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-violet-100 text-violet-600 rounded text-xs font-medium">
                                <Sparkles size={10} />Auto
                              </span>
                            )}
                          </div>
                          <h4 className="text-sm font-semibold text-slate-800 break-words">{tc.title}</h4>
                        </div>
                        <div className="flex items-center gap-1 sm:shrink-0 flex-wrap">
                          <button onClick={() => void handleMark(tc.id, "passed")}
                            disabled={markingId === tc.id || tc.result === "passed"}
                            className="flex items-center gap-1 px-2 py-1 bg-green-50 hover:bg-green-100 text-green-700 disabled:opacity-50 rounded text-xs font-medium transition-colors">
                            <CheckCircle size={12} />Bestanden
                          </button>
                          <button onClick={() => void handleMark(tc.id, "failed")}
                            disabled={markingId === tc.id || tc.result === "failed"}
                            className="flex items-center gap-1 px-2 py-1 bg-red-50 hover:bg-red-100 text-red-700 disabled:opacity-50 rounded text-xs font-medium transition-colors">
                            <XCircle size={12} />Fehlgeschlagen
                          </button>
                          {!isLocked && (
                            <>
                              <button onClick={() => startEdit(tc)}
                                className="p-1.5 text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors">
                                <Pencil size={13} />
                              </button>
                              <button onClick={() => void handleDelete(tc.id)}
                                className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors">
                                <Trash2 size={13} />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {tc.steps && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 mb-0.5">Schritte:</p>
                          <p className="text-xs text-slate-700 whitespace-pre-wrap bg-white rounded p-2 border border-slate-100">{tc.steps}</p>
                        </div>
                      )}
                      {tc.expected_result && (
                        <div>
                          <p className="text-xs font-medium text-slate-500 mb-0.5">Erwartetes Ergebnis:</p>
                          <p className="text-xs text-slate-700 whitespace-pre-wrap bg-white rounded p-2 border border-slate-100">{tc.expected_result}</p>
                        </div>
                      )}
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Assistent */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles size={16} className="text-brand-500" />
            Assistent
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Generiert Testfall-Vorschläge aus den Akzeptanzkriterien und speichert sie direkt an der Story.
            Beim erneuten Generieren werden bestehende Testfälle ersetzt.
          </p>
        </div>

        {isLocked ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-slate-100 text-slate-500 rounded-lg text-sm">
            <Lock size={15} />
            Generierung gesperrt (Status: {storyStatus})
          </div>
        ) : (
          <button
            onClick={() => void generateAndSave()}
            disabled={aiLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {aiLoading ? (
              <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />Analysiert…</>
            ) : (
              <><Sparkles size={16} />Testfälle generieren &amp; speichern</>
            )}
          </button>
        )}

        {aiError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">{aiError}</div>
        )}

        {lastAiCount !== null && !aiError && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-green-50 border border-green-200 rounded-lg text-green-700 text-xs">
            <CheckCircle size={13} />
            {lastAiCount} Testfall{lastAiCount !== 1 ? "fälle" : ""} generiert und gespeichert.
          </div>
        )}

        <div className="mt-5 space-y-2 text-xs text-slate-500">
          <p className="font-medium text-slate-600">Regeln:</p>
          <ul className="space-y-1 list-disc list-inside">
            <li>Testfälle werden sofort gespeichert</li>
            <li>Erneutes Generieren ersetzt bestehende Testfälle</li>
            <li>Manuell hinzugefügte Testfälle bleiben erhalten</li>
            <li>Ab Status <strong>Test</strong> sind Hinzufügen und Bearbeiten gesperrt</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StoryDocsSection — links: Dokumentation, rechts: Regenerieren-Panel
// ---------------------------------------------------------------------------

function EditableNotesField({
  label,
  value,
  placeholder,
  onSave,
}: {
  label: string;
  value: string;
  placeholder: string;
  onSave: (v: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(value);
  }, [value, editing]);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide">{label}</h3>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1 px-2 py-0.5 text-xs text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors"
          >
            <Pencil size={11} />
            Bearbeiten
          </button>
        )}
      </div>
      {editing ? (
        <div className="space-y-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={placeholder}
            rows={4}
            autoFocus
            className="w-full px-3 py-2 text-sm border border-brand-300 rounded-lg outline-none focus:ring-2 focus:ring-brand-100 resize-y"
          />
          <div className="flex gap-2">
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-xs font-medium transition-colors"
            >
              {saving ? (
                <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" />
              ) : (
                <Save size={12} />
              )}
              Speichern
            </button>
            <button
              onClick={() => { setEditing(false); setDraft(value); }}
              className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-xs font-medium transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </div>
      ) : (
        <div
          onClick={() => setEditing(true)}
          className={`px-3 py-2.5 text-sm rounded-lg border cursor-text min-h-[3rem] whitespace-pre-wrap leading-relaxed transition-colors ${
            value
              ? "text-slate-700 bg-white border-slate-200 hover:border-brand-300"
              : "text-slate-400 bg-slate-50 border-dashed border-slate-300 hover:border-brand-300"
          }`}
        >
          {value || placeholder}
        </div>
      )}
    </div>
  );
}

function StoryDocsSection({ storyId, refreshTrigger }: { storyId: string; refreshTrigger: number }) {
  const { data: docs, isLoading, mutate } = useSWR<StoryDocsData | null>(
    `/api/v1/user-stories/${storyId}/docs`,
    fetcher
  );
  const [regenerating, setRegenerating] = useState(false);
  const [regenError, setRegenError] = useState<string | null>(null);

  // Local state for user-editable notes (initialised from docs/story)
  const [additionalInfo, setAdditionalInfo] = useState("");
  const [workarounds, setWorkarounds] = useState("");

  useEffect(() => {
    if (refreshTrigger > 0) void mutate();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger]);

  // Sync editable fields when docs load
  useEffect(() => {
    setAdditionalInfo(docs?.additional_info ?? "");
    setWorkarounds(docs?.workarounds ?? "");
  }, [docs?.additional_info, docs?.workarounds]);

  async function handleRegenerate() {
    setRegenerating(true);
    setRegenError(null);
    try {
      const freshDocs = await apiRequest<StoryDocsData>(`/api/v1/user-stories/${storyId}/docs/regenerate`, { method: "POST" });
      mutate(freshDocs, false);
    } catch (err: unknown) {
      setRegenError((err as { error?: string })?.error ?? "Fehler beim Generieren.");
    } finally {
      setRegenerating(false);
    }
  }

  async function saveNotes(field: "doc_additional_info" | "doc_workarounds", value: string) {
    await apiRequest(`/api/v1/user-stories/${storyId}`, {
      method: "PATCH",
      body: JSON.stringify({ [field]: value || null }),
    });
    if (field === "doc_additional_info") setAdditionalInfo(value);
    else setWorkarounds(value);
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
      {/* LEFT: Dokumentationsinhalt + Zusatzfelder */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="flex items-center gap-2 px-4 sm:px-6 py-4 border-b border-slate-100">
          <FileText size={15} className="text-slate-500" />
          <h2 className="text-base font-semibold text-slate-900">Dokumentation</h2>
          {docs && <span className="text-xs text-slate-400 ml-1">Automatisch generiert, wird bei Änderungen aktualisiert</span>}
        </div>

        <div className="p-4 sm:p-6 space-y-6">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" />
            </div>
          )}

          {!isLoading && !docs && !regenerating && (
            <div className="text-center py-6">
              <p className="text-sm text-slate-400">
                Noch keine Dokumentation vorhanden. Starte die Generierung oder speichere die Story.
              </p>
            </div>
          )}

          {docs && (
            <div className="space-y-5">
              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Zusammenfassung</h3>
                <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3">{docs.summary}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Changelog-Eintrag</h3>
                <pre className="text-xs text-slate-700 bg-slate-50 rounded-lg p-3 whitespace-pre-wrap font-mono overflow-x-auto">{docs.changelog_entry}</pre>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Dokumenten-Gliederung</h3>
                <ol className="space-y-1.5">
                  {docs.pdf_outline.map((item, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-slate-700">
                      <span className="shrink-0 w-5 h-5 rounded-full bg-brand-100 text-brand-700 text-xs flex items-center justify-center font-semibold mt-0.5">{i + 1}</span>
                      {item}
                    </li>
                  ))}
                </ol>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Technische Hinweise</h3>
                <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-lg p-3 whitespace-pre-wrap">{docs.technical_notes}</p>
              </div>

              {docs.confluence_page_url && (
                <a
                  href={docs.confluence_page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 text-blue-700 hover:bg-blue-100 rounded-lg text-xs font-medium transition-colors"
                >
                  In Confluence öffnen →
                </a>
              )}
            </div>
          )}

          {/* Divider for user-editable sections — always visible */}
          <div className="border-t border-slate-100 pt-5 space-y-5">
            <EditableNotesField
              label="Zusatzinformationen"
              value={additionalInfo}
              placeholder="Zusätzliche Hinweise, Kontext oder Anmerkungen eintragen…"
              onSave={(v) => saveNotes("doc_additional_info", v)}
            />
            <EditableNotesField
              label="Bekannte Workarounds"
              value={workarounds}
              placeholder="Bekannte Einschränkungen, Umgehungslösungen oder temporäre Fixes eintragen…"
              onSave={(v) => saveNotes("doc_workarounds", v)}
            />
          </div>
        </div>
      </div>

      {/* RIGHT: Assistent / Regenerieren */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
            <Sparkles size={16} className="text-brand-500" />
            Assistent
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Generiert Zusammenfassung, Changelog-Eintrag, Dokumenten-Gliederung und technische Hinweise aus der Story.
          </p>
        </div>

        <button
          onClick={() => void handleRegenerate()}
          disabled={regenerating}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {regenerating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Generiert…
            </>
          ) : (
            <>
              <RefreshCw size={16} />
              {docs ? "Regenerieren" : "Jetzt generieren"}
            </>
          )}
        </button>

        {regenError && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">{regenError}</div>
        )}

        <div className="mt-5 space-y-2">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Generierte Abschnitte</p>
          {[
            { label: "Zusammenfassung" },
            { label: "Changelog-Eintrag" },
            { label: "Dokumenten-Gliederung" },
            { label: "Technische Hinweise" },
          ].map(({ label }) => (
            <div key={label} className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className={`w-2 h-2 rounded-full shrink-0 ${docs ? "bg-green-400" : "bg-slate-300"}`} />
              <span className="text-xs text-slate-600">{label}</span>
            </div>
          ))}
          {!docs && (
            <p className="text-xs text-slate-400 text-center pt-1">Wird nach dem Generieren befüllt.</p>
          )}

          <div className="border-t border-slate-100 pt-4 mt-4 space-y-2">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Manuell gepflegt</p>
            <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className={`w-2 h-2 rounded-full shrink-0 ${additionalInfo ? "bg-brand-400" : "bg-slate-300"}`} />
              <span className="text-xs text-slate-600">Zusatzinformationen</span>
            </div>
            <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg border border-slate-200">
              <div className={`w-2 h-2 rounded-full shrink-0 ${workarounds ? "bg-brand-400" : "bg-slate-300"}`} />
              <span className="text-xs text-slate-600">Bekannte Workarounds</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Features Section
// ---------------------------------------------------------------------------

const FEATURE_STATUS_LABELS: Record<FeatureStatus, string> = {
  draft: "Entwurf",
  in_progress: "In Arbeit",
  testing: "Test",
  done: "Fertig",
  archived: "Archiviert",
};

const FEATURE_STATUS_COLORS: Record<FeatureStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  in_progress: "bg-amber-100 text-amber-700",
  testing: "bg-orange-100 text-orange-700",
  done: "bg-green-100 text-green-700",
  archived: "bg-slate-200 text-slate-500",
};

const FEATURE_STATUS_OPTIONS: { value: FeatureStatus; label: string }[] = [
  { value: "draft", label: "Entwurf" },
  { value: "in_progress", label: "In Arbeit" },
  { value: "testing", label: "Test" },
  { value: "done", label: "Fertig" },
  { value: "archived", label: "Archiviert" },
];

interface AIFeatureSuggestion {
  title: string;
  description: string | null;
  priority: StoryPriority;
  story_points: number | null;
}

function FeatureCard({
  feature,
  onEdit,
  onDelete,
  deletingId,
}: {
  feature: Feature;
  onEdit: (f: Feature) => void;
  onDelete: (id: string) => Promise<void>;
  deletingId: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border border-slate-200 rounded-lg bg-white hover:border-slate-300 transition-colors">
      <div className="flex items-start gap-2 p-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${FEATURE_STATUS_COLORS[feature.status]}`}>
              {FEATURE_STATUS_LABELS[feature.status]}
            </span>
            <span className={`text-xs font-medium ${PRIORITY_COLORS[feature.priority]}`}>
              ● {PRIORITY_OPTIONS.find((p) => p.value === feature.priority)?.label}
            </span>
            {feature.story_points !== null && (
              <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-xs">{feature.story_points} SP</span>
            )}
          </div>
          <p className="text-sm font-medium text-slate-800 leading-snug">{feature.title}</p>
          {feature.description && (
            <>
              {!expanded && (
                <button onClick={() => setExpanded(true)} className="text-xs text-slate-400 hover:text-slate-600 mt-0.5">
                  Beschreibung anzeigen ▼
                </button>
              )}
              {expanded && (
                <>
                  <p className="text-xs text-slate-500 mt-1 whitespace-pre-wrap">{feature.description}</p>
                  <button onClick={() => setExpanded(false)} className="text-xs text-slate-400 hover:text-slate-600 mt-0.5">
                    ▲ Einklappen
                  </button>
                </>
              )}
            </>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => onEdit(feature)}
            className="p-1.5 text-slate-400 hover:text-brand-600 hover:bg-brand-50 rounded transition-colors"
            title="Bearbeiten"
          >
            <Pencil size={13} />
          </button>
          <button
            type="button"
            onClick={() => void onDelete(feature.id)}
            disabled={deletingId === feature.id}
            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
            title="Löschen"
          >
            {deletingId === feature.id
              ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-red-400 border-t-transparent" />
              : <Trash2 size={13} />
            }
          </button>
        </div>
      </div>
    </div>
  );
}

function SuggestedFeatureCard({
  suggestion,
  onAdd,
}: {
  suggestion: AIFeatureSuggestion;
  onAdd: (s: AIFeatureSuggestion) => Promise<void>;
}) {
  const [adding, setAdding] = useState(false);
  const [expanded, setExpanded] = useState(false);

  async function handleAdd() {
    setAdding(true);
    try { await onAdd(suggestion); }
    finally { setAdding(false); }
  }

  return (
    <div className="border border-emerald-200 rounded-lg bg-emerald-50 hover:border-emerald-300 transition-colors">
      <div className="flex items-start gap-2 px-3 py-2.5">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
            <span className={`text-xs font-medium ${PRIORITY_COLORS[suggestion.priority ?? "medium"]}`}>
              ● {PRIORITY_OPTIONS.find((p) => p.value === (suggestion.priority ?? "medium"))?.label}
            </span>
            {suggestion.story_points !== null && suggestion.story_points !== undefined && (
              <span className="px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-600 text-xs">{suggestion.story_points} SP</span>
            )}
          </div>
          <p className="text-sm font-medium text-slate-800 leading-snug">{suggestion.title}</p>
          {suggestion.description && (
            <>
              {!expanded && (
                <button onClick={() => setExpanded(true)} className="text-xs text-slate-400 hover:text-slate-600 mt-0.5">
                  Details ▼
                </button>
              )}
              {expanded && (
                <>
                  <p className="text-xs text-slate-600 mt-1 whitespace-pre-wrap">{suggestion.description}</p>
                  <button onClick={() => setExpanded(false)} className="text-xs text-slate-400 hover:text-slate-600">▲</button>
                </>
              )}
            </>
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={adding}
          className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-lg text-xs font-medium transition-colors"
        >
          {adding
            ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" />
            : <Plus size={11} />
          }
          Übernehmen
        </button>
      </div>
    </div>
  );
}

function FeaturesSection({ storyId, orgId }: { storyId: string; orgId: string }) {
  const { data: features, mutate } = useSWR<Feature[]>(
    `/api/v1/features?org_id=${orgId}&story_id=${storyId}`,
    fetcher
  );

  // Add form
  const [showAddForm, setShowAddForm] = useState(false);
  const [addTitle, setAddTitle] = useState("");
  const [addDesc, setAddDesc] = useState("");
  const [addPriority, setAddPriority] = useState<StoryPriority>("medium");
  const [addPoints, setAddPoints] = useState("");
  const [addSaving, setAddSaving] = useState(false);

  // Edit form
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editStatus, setEditStatus] = useState<FeatureStatus>("draft");
  const [editPriority, setEditPriority] = useState<StoryPriority>("medium");
  const [editPoints, setEditPoints] = useState("");
  const [editSaving, setEditSaving] = useState(false);

  const [deletingId, setDeletingId] = useState<string | null>(null);

  // AI
  const [aiSuggestions, setAiSuggestions] = useState<AIFeatureSuggestion[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  const inputCls = "w-full px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 bg-white";

  function startEdit(f: Feature) {
    setEditingId(f.id);
    setEditTitle(f.title);
    setEditDesc(f.description ?? "");
    setEditStatus(f.status);
    setEditPriority(f.priority);
    setEditPoints(f.story_points?.toString() ?? "");
  }

  async function handleAdd() {
    if (!addTitle.trim()) return;
    setAddSaving(true);
    try {
      const created = await apiRequest<Feature>(`/api/v1/features?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({
          story_id: storyId,
          title: addTitle.trim(),
          description: addDesc || null,
          priority: addPriority,
          story_points: addPoints ? parseInt(addPoints, 10) : null,
        }),
      });
      mutate((current) => [...(current ?? []), created], false);
      setAddTitle(""); setAddDesc(""); setAddPriority("medium"); setAddPoints(""); setShowAddForm(false);
    } finally { setAddSaving(false); }
  }

  async function handleSaveEdit(id: string) {
    setEditSaving(true);
    try {
      const updated = await apiRequest<Feature>(`/api/v1/features/${id}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle,
          description: editDesc || null,
          status: editStatus,
          priority: editPriority,
          story_points: editPoints ? parseInt(editPoints, 10) : null,
        }),
      });
      mutate((current) => (current ?? []).map((f) => f.id === id ? updated : f), false);
      setEditingId(null);
    } finally { setEditSaving(false); }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    mutate((current) => (current ?? []).filter((f) => f.id !== id), false);
    try {
      await apiRequest(`/api/v1/features/${id}`, { method: "DELETE" });
    } catch {
      mutate(); // revert on error
    } finally { setDeletingId(null); }
  }

  async function handleAiSuggest() {
    setAiLoading(true); setAiError(null);
    try {
      const data = await apiRequest<{ suggestions: AIFeatureSuggestion[] }>(
        `/api/v1/user-stories/${storyId}/ai-features`,
        { method: "POST" }
      );
      setAiSuggestions(data.suggestions ?? []);
    } catch {
      setAiError("Vorschläge konnten nicht generiert werden.");
    } finally { setAiLoading(false); }
  }

  async function handleAddSuggestion(s: AIFeatureSuggestion) {
    const created = await apiRequest<Feature>(`/api/v1/features?org_id=${orgId}`, {
      method: "POST",
      body: JSON.stringify({
        story_id: storyId,
        title: s.title,
        description: s.description || null,
        priority: s.priority ?? "medium",
        story_points: s.story_points ?? null,
      }),
    });
    mutate((current) => [...(current ?? []), created], false);
  }

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
      {/* LEFT: Feature list */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Package size={16} className="text-brand-500" />
            <h3 className="font-semibold text-slate-900">Features</h3>
            <span className="text-xs text-slate-400 bg-slate-100 px-2 py-0.5 rounded-full">{features?.length ?? 0}</span>
          </div>
          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs font-medium transition-colors"
            >
              <Plus size={12} /> Feature hinzufügen
            </button>
          )}
        </div>

        {/* Add form */}
        {showAddForm && (
          <div className="border border-slate-200 rounded-xl p-3 bg-slate-50 space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Neues Feature</p>
            <input
              autoFocus
              value={addTitle}
              onChange={(e) => setAddTitle(e.target.value)}
              placeholder="Feature-Titel"
              className={inputCls}
            />
            <textarea
              value={addDesc}
              onChange={(e) => setAddDesc(e.target.value)}
              placeholder="Beschreibung (optional)"
              rows={2}
              className={`${inputCls} resize-none`}
            />
            <div className="grid grid-cols-2 gap-2">
              <select value={addPriority} onChange={(e) => setAddPriority(e.target.value as StoryPriority)} className={inputCls}>
                {PRIORITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <input
                type="number" min={0} max={100}
                value={addPoints} onChange={(e) => setAddPoints(e.target.value)}
                placeholder="Story Points"
                className={inputCls}
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => void handleAdd()}
                disabled={!addTitle.trim() || addSaving}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {addSaving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
                Speichern
              </button>
              <button
                onClick={() => { setShowAddForm(false); setAddTitle(""); setAddDesc(""); }}
                className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm transition-colors"
              >
                Abbrechen
              </button>
            </div>
          </div>
        )}

        {/* Feature list */}
        {!features ? (
          <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-brand-500" /></div>
        ) : features.length === 0 && !showAddForm ? (
          <div className="text-center py-10 text-slate-400">
            <Package size={32} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Noch keine Features.</p>
            <p className="text-xs mt-1">Features manuell hinzufügen oder Vorschläge generieren.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {features.map((f) =>
              editingId === f.id ? (
                <div key={f.id} className="border border-brand-300 rounded-xl p-3 bg-brand-50 space-y-3">
                  <p className="text-xs font-semibold text-brand-600 uppercase tracking-wide">Feature bearbeiten</p>
                  <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className={inputCls} placeholder="Titel" />
                  <textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} rows={2} className={`${inputCls} resize-none`} placeholder="Beschreibung" />
                  <div className="grid grid-cols-3 gap-2">
                    <select value={editStatus} onChange={(e) => setEditStatus(e.target.value as FeatureStatus)} className={inputCls}>
                      {FEATURE_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                    <select value={editPriority} onChange={(e) => setEditPriority(e.target.value as StoryPriority)} className={inputCls}>
                      {PRIORITY_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                    <input type="number" min={0} max={100} value={editPoints} onChange={(e) => setEditPoints(e.target.value)} className={inputCls} placeholder="SP" />
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => void handleSaveEdit(f.id)}
                      disabled={!editTitle.trim() || editSaving}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium"
                    >
                      {editSaving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
                      Speichern
                    </button>
                    <button onClick={() => setEditingId(null)} className="px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm">
                      Abbrechen
                    </button>
                  </div>
                </div>
              ) : (
                <FeatureCard key={f.id} feature={f} onEdit={startEdit} onDelete={handleDelete} deletingId={deletingId} />
              )
            )}
          </div>
        )}
      </div>

      {/* RIGHT: AI Panel */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-brand-500" />
          <h3 className="font-semibold text-slate-900">Feature-Vorschläge</h3>
        </div>
        <p className="text-sm text-slate-500">
          Analysiert die User Story und schlägt konkrete, implementierbare Features (Teilfunktionen) vor.
        </p>

        <button
          onClick={() => void handleAiSuggest()}
          disabled={aiLoading}
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
        >
          {aiLoading
            ? <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> Wird analysiert…</>
            : <><Sparkles size={14} /> Features vorschlagen</>
          }
        </button>

        {aiError && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-lg">{aiError}</p>
        )}

        {aiSuggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
              {aiSuggestions.length} Vorschläge — mit „Übernehmen" zur Feature-Liste hinzufügen
            </p>
            {aiSuggestions.map((s, i) => (
              <SuggestedFeatureCard key={i} suggestion={s} onAdd={handleAddSuggestion} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

type ActiveTab = "story" | "dod" | "tests" | "features" | "docs";

type DemoRole = "user" | "ba" | "architect" | "developer" | "tester" | "release";

const DEMO_ROLES: { id: DemoRole; label: string; description: string; color: string }[] = [
  { id: "user",      label: "User",              description: "Gesamtüberblick",                         color: "bg-slate-100 text-slate-700 border-slate-300" },
  { id: "ba",        label: "Business Analyst",  description: "Story, DoD & Akzeptanzkriterien",         color: "bg-blue-100 text-blue-700 border-blue-300" },
  { id: "architect", label: "Senior Architekt",  description: "Story, DoD, Features & Dokumentation",    color: "bg-violet-100 text-violet-700 border-violet-300" },
  { id: "developer", label: "Developer",         description: "Story, DoD, Testfälle & Features",         color: "bg-amber-100 text-amber-700 border-amber-300" },
  { id: "tester",    label: "Tester",            description: "Story, Akzeptanzkriterien & Testfälle",   color: "bg-orange-100 text-orange-700 border-orange-300" },
  { id: "release",   label: "Releasemanager",    description: "Story, Testfälle & Dokumentation",        color: "bg-green-100 text-green-700 border-green-300" },
];

const ROLE_TABS: Record<DemoRole, ActiveTab[]> = {
  user:      ["story", "dod", "tests", "features", "docs"],
  ba:        ["story", "dod", "tests", "features", "docs"],
  architect: ["story", "dod", "features", "docs"],
  developer: ["story", "dod", "tests", "features"],
  tester:    ["story", "tests"],
  release:   ["story", "tests", "features", "docs"],
};

export default function StoryDetailPage({
  params,
}: {
  params: { org: string; id: string };
}) {
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; general?: string }>({});
  const [docsRefreshTrigger, setDocsRefreshTrigger] = useState(0);
  const [showSplitPanel, setShowSplitPanel] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("story");
  const [demoRole, setDemoRole] = useState<DemoRole>("user");
  const [showRolePicker, setShowRolePicker] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [status, setStatus] = useState<StoryStatus>("draft");
  const [priority, setPriority] = useState<StoryPriority>("medium");
  const [storyPoints, setStoryPoints] = useState("");
  const [dorPassed, setDorPassed] = useState(false);
  const [epicId, setEpicId] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const { data: story, isLoading, mutate } = useSWR<UserStory>(
    `/api/v1/user-stories/${params.id}`,
    fetcher,
    {
      onSuccess: (data) => {
        if (!initialized) {
          setTitle(data.title);
          setDescription(data.description ?? "");
          setAcceptanceCriteria(data.acceptance_criteria ?? "");
          setStatus(data.status);
          setPriority(data.priority);
          setStoryPoints(data.story_points?.toString() ?? "");
          setDorPassed(data.dor_passed);
          setEpicId(data.epic_id);
          setInitialized(true);
        }
      },
    }
  );

  function handleApplySuggestion(
    field: "title" | "description" | "acceptance_criteria",
    value: string,
    mode: "replace" | "append" = "replace"
  ) {
    if (!editing) setEditing(true);
    if (field === "title") setTitle(value);
    else if (field === "description") setDescription(value);
    else if (field === "acceptance_criteria") {
      if (mode === "append") {
        setAcceptanceCriteria((prev) => (prev ? `${prev}\n${value}` : value));
      } else {
        setAcceptanceCriteria(value);
      }
    }
  }

  function handleCancelEdit() {
    if (story) {
      setTitle(story.title);
      setDescription(story.description ?? "");
      setAcceptanceCriteria(story.acceptance_criteria ?? "");
      setStatus(story.status);
      setPriority(story.priority);
      setStoryPoints(story.story_points?.toString() ?? "");
      setDorPassed(story.dor_passed);
      setEpicId(story.epic_id);
    }
    setEditing(false);
    setFieldErrors({});
  }

  async function handleSave() {
    if (!story) return;
    if (!title.trim()) {
      setFieldErrors({ title: "Bitte gib einen Titel ein." });
      return;
    }
    setSaving(true);
    setFieldErrors({});
    try {
      // Only send fields that actually changed — avoids unnecessary doc regeneration
      const patch: Record<string, unknown> = {};
      if (title !== story.title) patch.title = title;
      if (description !== (story.description ?? "")) patch.description = description || null;
      if (acceptanceCriteria !== (story.acceptance_criteria ?? "")) patch.acceptance_criteria = acceptanceCriteria || null;
      if (status !== story.status) patch.status = status;
      if (priority !== story.priority) patch.priority = priority;
      const sp = storyPoints ? parseInt(storyPoints, 10) : null;
      if (sp !== story.story_points) patch.story_points = sp;
      if (dorPassed !== story.dor_passed) patch.dor_passed = dorPassed;
      if (epicId !== story.epic_id) patch.epic_id = epicId;

      const saved = await apiRequest<UserStory>(`/api/v1/user-stories/${params.id}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });
      mutate(saved, false);
      setEditing(false);
      setTimeout(() => setDocsRefreshTrigger((t) => t + 1), 2000);
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setFieldErrors({ general: msg ?? "Fehler beim Speichern." });
    } finally {
      setSaving(false);
    }
  }

  if (isLoading || !story) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
      </div>
    );
  }

  const ALL_TABS: { id: ActiveTab; label: string }[] = [
    { id: "story",    label: "Story" },
    { id: "features", label: "Features" },
    { id: "tests",    label: "Testfälle" },
    { id: "dod",      label: "Definition of Done" },
    { id: "docs",     label: "Dokumentation" },
  ];

  const visibleTabIds = ROLE_TABS[demoRole];
  const tabs = ALL_TABS.filter((t) => visibleTabIds.includes(t.id));

  function handleRoleChange(role: DemoRole) {
    setDemoRole(role);
    setShowRolePicker(false);
    if (!ROLE_TABS[role].includes(activeTab)) {
      setActiveTab(ROLE_TABS[role][0]);
    }
  }

  const currentRole = DEMO_ROLES.find((r) => r.id === demoRole)!;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center gap-4">
          <Link
            href={`/${params.org}/stories`}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
          >
            <ArrowLeft size={18} />
          </Link>
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[story.status]}`}>
                {STATUS_OPTIONS.find((s) => s.value === story.status)?.label}
              </span>
              <span className={`text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
                ● {PRIORITY_OPTIONS.find((p) => p.value === story.priority)?.label}
              </span>
              {story.story_points !== null && (
                <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">
                  {story.story_points} SP
                </span>
              )}
              {story.dor_passed && (
                <span className="px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-xs font-medium">
                  ✓ DoR
                </span>
              )}
              {story.epic_id && (
                <EpicBadge epicId={story.epic_id} orgId={story.organization_id} />
              )}
            </div>
            <h1 className="text-xl font-bold text-slate-900 break-words">
              {story.title}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {!editing && !showSplitPanel && (
            <button
              onClick={() => setShowSplitPanel(true)}
              className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
            >
              <GitBranch size={16} />
              Aufteilen
            </button>
          )}
          {editing ? (
            <>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {saving ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                ) : (
                  <Save size={16} />
                )}
                Speichern
              </button>
              <button
                onClick={handleCancelEdit}
                className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
              >
                <X size={16} />
                Abbrechen
              </button>
            </>
          ) : (
            <button
              onClick={() => setEditing(true)}
              className="flex items-center gap-2 px-4 py-2 border border-slate-300 text-slate-600 hover:bg-slate-50 rounded-lg text-sm font-medium transition-colors"
            >
              <Pencil size={16} />
              Bearbeiten
            </button>
          )}
        </div>
      </div>

      {/* Split badge */}
      {story.is_split && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-amber-700 text-sm">
          <GitBranch size={15} className="shrink-0" />
          Diese Story wurde aufgeteilt. Die Sub-Stories findest du in der Story-Liste.
        </div>
      )}

      {/* Split panel */}
      {showSplitPanel && (
        <SplitStoryPanel
          storyId={params.id}
          orgId={story.organization_id}
          orgSlug={params.org}
          onClose={() => setShowSplitPanel(false)}
        />
      )}

      {/* Demo role switcher */}
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl">
        <div className="flex items-center gap-2 min-w-0">
          <Users size={14} className="text-slate-400 shrink-0" />
          <span className="text-xs text-slate-400 font-medium shrink-0">Demo-Ansicht:</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${currentRole.color}`}>
            {currentRole.label}
          </span>
          <span className="text-xs text-slate-400 hidden sm:inline truncate">{currentRole.description}</span>
        </div>
        <div className="relative shrink-0">
          <button
            onClick={() => setShowRolePicker((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 text-slate-600 hover:bg-white rounded-lg text-xs font-medium transition-colors"
          >
            Rolle wechseln
          </button>
          {showRolePicker && (
            <div className="absolute right-0 top-full mt-1 w-72 bg-white border border-slate-200 rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="px-3 py-2 border-b border-slate-100 bg-slate-50">
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Perspektive wählen</p>
              </div>
              {DEMO_ROLES.map((role) => (
                <button
                  key={role.id}
                  onClick={() => handleRoleChange(role.id)}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-slate-50 transition-colors border-b border-slate-100 last:border-0 ${
                    demoRole === role.id ? "bg-brand-50" : ""
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 px-1.5 py-0.5 rounded text-xs font-semibold border ${role.color}`}>
                    {role.label.split(" ")[0]}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-800">{role.label}</p>
                    <p className="text-xs text-slate-400">{role.description}</p>
                  </div>
                  {demoRole === role.id && (
                    <CheckCircle size={14} className="shrink-0 mt-0.5 text-brand-600" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-slate-200 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "border-brand-600 text-brand-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Story tab */}
      {activeTab === "story" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
          {/* LEFT: Story fields */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 space-y-5">
            <DroppableField
              id="title"
              label="Titel"
              value={title}
              onChange={(v) => { setTitle(v); setFieldErrors((e) => ({ ...e, title: undefined })); }}
              placeholder="Titel der User Story"
              fieldName="title"
              editing={editing}
              error={fieldErrors.title}
            />

            <DroppableField
              id="description"
              label="Beschreibung"
              value={description}
              onChange={setDescription}
              placeholder="Als [Rolle] möchte ich [Funktion], damit [Nutzen]"
              multiline
              rows={5}
              fieldName="description"
              editing={editing}
            />

            <DroppableField
              id="acceptance_criteria"
              label="Akzeptanzkriterien"
              value={acceptanceCriteria}
              onChange={setAcceptanceCriteria}
              placeholder={"1. Gegeben...\n2. Wenn...\n3. Dann..."}
              multiline
              rows={5}
              fieldName="acceptance_criteria"
              editing={editing}
            />

            {editing && (
              <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label htmlFor="status" className="block text-sm font-medium text-slate-700 mb-1.5">
                    Status
                  </label>
                  <select
                    id="status"
                    value={status}
                    onChange={(e) => setStatus(e.target.value as StoryStatus)}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 bg-white"
                  >
                    {STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="priority" className="block text-sm font-medium text-slate-700 mb-1.5">
                    Priorität
                  </label>
                  <select
                    id="priority"
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as StoryPriority)}
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 bg-white"
                  >
                    {PRIORITY_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="story_points" className="block text-sm font-medium text-slate-700 mb-1.5">
                    Story Points
                  </label>
                  <input
                    id="story_points"
                    type="number"
                    min={0}
                    max={100}
                    value={storyPoints}
                    onChange={(e) => setStoryPoints(e.target.value)}
                    placeholder="z.B. 5"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100 bg-white"
                  />
                </div>

                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={dorPassed}
                      onChange={(e) => setDorPassed(e.target.checked)}
                      className="w-4 h-4 rounded border-slate-300 text-brand-600"
                    />
                    <span className="text-sm font-medium text-slate-700">DoR bestanden</span>
                  </label>
                </div>
              </div>

              <EpicSelector
                orgId={story.organization_id}
                value={epicId}
                onChange={setEpicId}
              />
              </>
            )}

            {fieldErrors.general && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
                {fieldErrors.general}
              </div>
            )}

            <div className="text-xs text-slate-400 pt-2 border-t border-slate-100">
              Erstellt: {new Date(story.created_at).toLocaleDateString("de-DE")} &middot; Aktualisiert:{" "}
              {new Date(story.updated_at).toLocaleDateString("de-DE")}
            </div>
          </div>

          {/* RIGHT: AI Suggestions */}
          <div className="bg-white rounded-xl border border-slate-200 p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
            <AISuggestPanel
              title={title}
              description={description}
              acceptanceCriteria={acceptanceCriteria}
              onApply={handleApplySuggestion}
              storyId={params.id}
              persistedScore={story.quality_score}
              onScorePersisted={() => void mutate()}
            />
          </div>
        </div>
      )}

      {/* DoD tab */}
      {activeTab === "dod" && (
        <DefinitionOfDoneSection storyId={params.id} initialDod={story.definition_of_done} />
      )}

      {/* Tests tab */}
      {activeTab === "tests" && (
        <TestCasesSection storyId={params.id} storyStatus={story.status} />
      )}

      {/* Features tab */}
      {activeTab === "features" && (
        <FeaturesSection storyId={params.id} orgId={story.organization_id} />
      )}

      {/* Docs tab */}
      {activeTab === "docs" && (
        <StoryDocsSection storyId={params.id} refreshTrigger={docsRefreshTrigger} />
      )}
    </div>
  );
}
