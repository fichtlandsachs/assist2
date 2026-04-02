"use client";

import { use, useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority, TestCase, TestResult, DoDItem, Feature, FeatureStatus, Epic } from "@/types";
import { AISuggestPanel } from "@/components/stories/AISuggestPanel";
import { EpicSelector } from "@/components/stories/EpicSelector";
import { ProjectSelector } from "@/components/stories/ProjectSelector";
import { DoDItem as DoDItemComponent } from "@/components/stories/DoDItem";
import { AISuggestionItem } from "@/components/stories/AISuggestionItem";
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
  draft: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_review: "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",
  ready: "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const PRIORITY_OPTIONS: { value: StoryPriority; label: string }[] = [
  { value: "low", label: "Niedrig" },
  { value: "medium", label: "Mittel" },
  { value: "high", label: "Hoch" },
  { value: "critical", label: "Kritisch" },
];

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low: "text-[var(--ink-faint)]",
  medium: "text-[var(--navy)]",
  high: "text-[var(--brown)]",
  critical: "text-[var(--accent-red)]",
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
  return <p className="mt-1 text-xs text-[var(--accent-red)]">{msg}</p>;
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

  const baseClass = `w-full px-3 py-2 text-sm border rounded-sm outline-none transition-colors ${
    isDragOver
      ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] ring-2 ring-[var(--accent-red)]"
      : error
      ? "border-red-400 bg-[rgba(var(--accent-red-rgb),.08)] focus:border-red-400 focus:ring-2 focus:ring-red-100"
      : "border-[var(--ink-faintest)] bg-[var(--card)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)]"
  }`;

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
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
        <div className="px-3 py-2 text-sm text-[var(--ink-mid)] bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm min-h-[2.5rem] whitespace-pre-wrap">
          {value || <span className="text-[var(--ink-faint)]">{placeholder}</span>}
        </div>
      )}
      <FieldError msg={error} />
    </div>
  );
}

const TEST_RESULT_COLORS: Record<TestResult, string> = {
  pending: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  passed: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  failed: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  skipped: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
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
      className="border border-[rgba(var(--btn-primary-rgb),.3)] rounded-sm bg-[rgba(var(--btn-primary-rgb),.08)] hover:bg-[var(--card)] hover:border-[var(--btn-primary)] transition-all cursor-grab active:cursor-grabbing group"
    >
      <div className="flex items-center gap-2 px-3 py-2.5">
        <GripVertical size={13} className="shrink-0 text-[var(--btn-primary)] group-hover:text-[var(--btn-primary)] transition-colors" />
        <span className="flex-1 min-w-0 text-sm font-medium text-[var(--ink)] leading-tight break-words">{suggestion.title}</span>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="shrink-0 text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] px-1"
        >
          {expanded ? "▲" : "▼"}
        </button>
        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={adding}
          title="Direkt als Testfall hinzufügen"
          className="shrink-0 flex items-center gap-1 px-2 py-1 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--btn-primary)] text-white rounded-sm text-xs font-medium transition-colors"
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
        <div className="px-3 pb-3 space-y-2 border-t border-[rgba(var(--btn-primary-rgb),.3)] pt-2">
          {suggestion.steps && (
            <div>
              <p className="text-xs font-medium text-[var(--ink-faint)] mb-0.5">Schritte:</p>
              <p className="text-xs text-[var(--ink-mid)] whitespace-pre-wrap">{suggestion.steps}</p>
            </div>
          )}
          {suggestion.expected_result && (
            <div>
              <p className="text-xs font-medium text-[var(--ink-faint)] mb-0.5">Erwartetes Ergebnis:</p>
              <p className="text-xs text-[var(--ink-mid)] whitespace-pre-wrap">{suggestion.expected_result}</p>
            </div>
          )}
          <button
            type="button"
            onClick={() => onDragToForm(suggestion)}
            className="text-xs text-[var(--btn-primary)] hover:text-[var(--btn-primary)] underline"
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={16} className="text-[var(--ink-faint)]" />
            <h2 className="text-base font-semibold text-[var(--ink)]">Definition of Done</h2>
            {items.length > 0 && (
              <span className="px-1.5 py-0.5 bg-[var(--paper-warm)] text-[var(--ink-mid)] rounded-sm text-xs font-medium">
                {doneCount}/{items.length}
              </span>
            )}
          </div>
          <button
            onClick={() => setShowInput((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors"
          >
            <Plus size={14} />
            Kriterium
          </button>
        </div>

        <div className="p-4 space-y-3">
          {items.length > 0 && (
            <div className="space-y-1">
              <div className="flex items-center justify-between text-xs text-[var(--ink-faint)]">
                <span>{doneCount} von {items.length} erledigt</span>
                <span className={`font-semibold ${progress === 100 ? "text-[var(--green)]" : "text-[var(--ink-mid)]"}`}>{progress}%</span>
              </div>
              <div className="h-1.5 bg-[var(--paper-warm)] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${progress === 100 ? "bg-[var(--green)]" : "bg-[var(--accent-red)]"}`}
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
                className="flex-1 min-w-0 px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)]"
              />
              <button
                onClick={() => { addItem(newText); setNewText(""); setShowInput(false); }}
                disabled={!newText.trim() || saving}
                className="shrink-0 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-xs font-medium transition-colors"
              >
                Hinzufügen
              </button>
              <button
                onClick={() => { setNewText(""); setShowInput(false); }}
                className="shrink-0 px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors"
              >
                Abbrechen
              </button>
            </div>
          )}

          {items.length === 0 && !showInput && (
            <p className="text-sm text-[var(--ink-faint)] text-center py-8">
              Noch keine DoD-Kriterien definiert. Füge eigene hinzu oder lass dir Vorschläge generieren.
            </p>
          )}

          {items.length > 0 && (
            <div className="space-y-1.5">
              {items.map((item, i) => (
                <DoDItemComponent
                  key={i}
                  text={item.text}
                  done={item.done}
                  onToggle={() => void toggleItem(i)}
                  onDelete={() => void removeItem(i)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* RIGHT: Assistent */}
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--accent-red)]" />
            Assistent
          </h2>
          <p className="text-xs text-[var(--ink-faint)] mt-1">
            Schlägt DoD-Kriterien basierend auf der Story vor.
          </p>
        </div>

        <button
          onClick={() => void handleLoadSuggestions()}
          disabled={aiLoading}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
        >
          {aiLoading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
              Analysiert…
            </>
          ) : (
            <>
              <Sparkles size={16} />
              Vorschläge
            </>
          )}
        </button>

        {aiError && (
          <div className="mt-3 p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-xs">{aiError}</div>
        )}

        <div className={`mt-4 space-y-2 transition-opacity duration-300 ${!aiSuggestions && !aiLoading ? "opacity-30 pointer-events-none select-none" : "opacity-100"}`}>
          {!aiSuggestions && (
            <div className="space-y-2">
              <div className="h-10 bg-[var(--paper-warm)] rounded-sm" />
              <div className="h-10 bg-[var(--paper-warm)] rounded-sm" />
              <div className="h-10 bg-[var(--paper-warm)] rounded-sm" />
              <p className="text-xs text-[var(--ink-faint)] text-center pt-1">Kriterien erscheinen nach der Analyse hier.</p>
            </div>
          )}

          {aiSuggestions?.length === 0 && (
            <p className="text-xs text-[var(--ink-faint)] text-center py-4">Alle Vorschläge wurden übernommen.</p>
          )}

          {aiSuggestions && aiSuggestions.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide flex items-center gap-1.5">
                  <Sparkles size={12} />
                  Vorschläge
                  <span className="normal-case font-normal text-[var(--ink-faint)]">({aiSuggestions.length})</span>
                </p>
                <button
                  onClick={() => setAiSuggestions(null)}
                  className="text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
                >
                  Schließen
                </button>
              </div>
              {aiSuggestions.map((s, i) => (
                <AISuggestionItem
                  key={i}
                  text={s.text}
                  category={s.category}
                  onAdd={() => void addFromSuggestion(s)}
                />
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
          <div className="flex items-center gap-2">
            <ClipboardCheck size={16} className="text-[var(--ink-faint)]" />
            <h2 className="text-base font-semibold text-[var(--ink)]">Testfälle</h2>
            {testCases && testCases.length > 0 && (
              <span className="px-1.5 py-0.5 bg-[var(--paper-warm)] text-[var(--ink-mid)] rounded-sm text-xs font-medium">
                {testCases.length}
              </span>
            )}
          </div>
          {isLocked ? (
            <span className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--paper-warm)] text-[var(--ink-faint)] rounded-sm text-xs font-medium">
              <Lock size={13} />
              Gesperrt
            </span>
          ) : (
            <button
              onClick={() => setShowForm(!showForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors"
            >
              <Plus size={14} />
              Hinzufügen
            </button>
          )}
        </div>

        {isLocked && (
          <div className="mx-4 mt-3 mb-1 flex items-center gap-2 px-3 py-2 bg-[rgba(122,100,80,.1)] border border-[rgba(122,100,80,.3)] rounded-sm text-xs text-[var(--brown)]">
            <Lock size={12} />
            Testfälle sind ab Status „Test" schreibgeschützt. Testergebnisse können weiterhin eingetragen werden.
          </div>
        )}

        <div className="p-4 space-y-3">
          {!isLocked && showForm && (
            <form onSubmit={(e) => void handleAddTestCase(e)} className="border border-[var(--paper-rule)] bg-[var(--paper-warm)] rounded-sm p-4 space-y-3">
              <div>
                <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">Titel <span className="text-[var(--accent-red)]">*</span></label>
                <input type="text" value={formTitle} onChange={e => setFormTitle(e.target.value)}
                  placeholder="Testfall Titel"
                  className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)]" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">Schritte</label>
                <textarea value={formSteps} onChange={e => setFormSteps(e.target.value)}
                  placeholder={"1. Schritt\n2. Schritt"} rows={3}
                  className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)] resize-none" />
              </div>
              <div>
                <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">Erwartetes Ergebnis</label>
                <textarea value={formExpected} onChange={e => setFormExpected(e.target.value)}
                  placeholder="Das erwartete Ergebnis..." rows={2}
                  className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-1 focus:ring-[var(--accent-red)] bg-[var(--card)] resize-none" />
              </div>
              <div className="flex gap-2">
                <button type="submit" disabled={saving || !formTitle.trim()}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-xs font-medium transition-colors">
                  {saving ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" /> : <Plus size={12} />}
                  Hinzufügen
                </button>
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors">
                  Abbrechen
                </button>
              </div>
            </form>
          )}

          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--accent-red)]" />
            </div>
          )}

          {!isLoading && testCases && testCases.length === 0 && !showForm && (
            <p className="text-sm text-[var(--ink-faint)] text-center py-8">Noch keine Testfälle definiert.</p>
          )}

          {testCases && testCases.length > 0 && (
            <div className="space-y-3">
              {testCases.map((tc) => (
                <div key={tc.id} className={`border rounded-sm p-4 space-y-2 ${tc.is_ai_generated ? "border-[rgba(var(--btn-primary-rgb),.3)] bg-[rgba(var(--btn-primary-rgb),.08)]" : "border-[var(--paper-rule)]"}`}>
                  {editingId === tc.id ? (
                    <div className="space-y-2">
                      <input type="text" value={editTitle} onChange={e => setEditTitle(e.target.value)}
                        className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]" />
                      <textarea value={editSteps} onChange={e => setEditSteps(e.target.value)} rows={3}
                        placeholder="Schritte..."
                        className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)] resize-none" />
                      <textarea value={editExpected} onChange={e => setEditExpected(e.target.value)} rows={2}
                        placeholder="Erwartetes Ergebnis..."
                        className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)] resize-none" />
                      <div className="flex gap-2">
                        <button onClick={() => void handleSaveEdit(tc.id)} disabled={editSaving}
                          className="flex items-center gap-1 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors">
                          {editSaving ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-white border-t-transparent" /> : <CheckCircle size={12} />}
                          Speichern
                        </button>
                        <button onClick={() => setEditingId(null)}
                          className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors">
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
                              <span className="flex items-center gap-1 px-1.5 py-0.5 bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)] rounded-sm text-xs font-medium">
                                <Sparkles size={10} />Auto
                              </span>
                            )}
                          </div>
                          <h4 className="text-sm font-semibold text-[var(--ink)] break-words">{tc.title}</h4>
                        </div>
                        <div className="flex items-center gap-1 sm:shrink-0 flex-wrap">
                          <button onClick={() => void handleMark(tc.id, "passed")}
                            disabled={markingId === tc.id || tc.result === "passed"}
                            className="flex items-center gap-1 px-2 py-1 bg-[rgba(82,107,94,.1)] hover:bg-[rgba(82,107,94,.15)] text-[var(--green)] disabled:opacity-50 rounded-sm text-xs font-medium transition-colors">
                            <CheckCircle size={12} />Bestanden
                          </button>
                          <button onClick={() => void handleMark(tc.id, "failed")}
                            disabled={markingId === tc.id || tc.result === "failed"}
                            className="flex items-center gap-1 px-2 py-1 bg-[rgba(var(--accent-red-rgb),.08)] hover:bg-[rgba(var(--accent-red-rgb),.12)] text-[var(--accent-red)] disabled:opacity-50 rounded-sm text-xs font-medium transition-colors">
                            <XCircle size={12} />Fehlgeschlagen
                          </button>
                          {!isLocked && (
                            <>
                              <button onClick={() => startEdit(tc)}
                                className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm transition-colors">
                                <Pencil size={13} />
                              </button>
                              <button onClick={() => void handleDelete(tc.id)}
                                className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm transition-colors">
                                <Trash2 size={13} />
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      {tc.steps && (
                        <div>
                          <p className="text-xs font-medium text-[var(--ink-faint)] mb-0.5">Schritte:</p>
                          <p className="text-xs text-[var(--ink-mid)] whitespace-pre-wrap bg-[var(--card)] rounded-sm p-2 border border-[var(--paper-rule)]">{tc.steps}</p>
                        </div>
                      )}
                      {tc.expected_result && (
                        <div>
                          <p className="text-xs font-medium text-[var(--ink-faint)] mb-0.5">Erwartetes Ergebnis:</p>
                          <p className="text-xs text-[var(--ink-mid)] whitespace-pre-wrap bg-[var(--card)] rounded-sm p-2 border border-[var(--paper-rule)]">{tc.expected_result}</p>
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--accent-red)]" />
            Assistent
          </h2>
          <p className="text-xs text-[var(--ink-faint)] mt-1">
            Generiert Testfall-Vorschläge aus den Akzeptanzkriterien und speichert sie direkt an der Story.
            Beim erneuten Generieren werden bestehende Testfälle ersetzt.
          </p>
        </div>

        {isLocked ? (
          <div className="flex items-center gap-2 px-4 py-3 bg-[var(--paper-warm)] text-[var(--ink-faint)] rounded-sm text-sm">
            <Lock size={15} />
            Generierung gesperrt (Status: {storyStatus})
          </div>
        ) : (
          <button
            onClick={() => void generateAndSave()}
            disabled={aiLoading}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
          >
            {aiLoading ? (
              <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />Analysiert…</>
            ) : (
              <><Sparkles size={16} />Testfälle generieren &amp; speichern</>
            )}
          </button>
        )}

        {aiError && (
          <div className="mt-3 p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-xs">{aiError}</div>
        )}

        {lastAiCount !== null && !aiError && (
          <div className="mt-3 flex items-center gap-2 px-3 py-2 bg-[rgba(82,107,94,.1)] border border-[rgba(82,107,94,.3)] rounded-sm text-[var(--green)] text-xs">
            <CheckCircle size={13} />
            {lastAiCount} Testfall{lastAiCount !== 1 ? "fälle" : ""} generiert und gespeichert.
          </div>
        )}

        <div className="mt-5 space-y-2 text-xs text-[var(--ink-faint)]">
          <p className="font-medium text-[var(--ink-mid)]">Regeln:</p>
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
// StoryPromptSection — KI-Implementierungsprompt aus Story-Daten
// ---------------------------------------------------------------------------

function StoryPromptSection({ story, orgId }: { story: UserStory; orgId: string }) {
  const { data: features } = useSWR<Feature[]>(
    `/api/v1/features?org_id=${orgId}&story_id=${story.id}`,
    fetcher
  );
  const { data: testCases } = useSWR<TestCase[]>(
    `/api/v1/user-stories/${story.id}/test-cases`,
    fetcher
  );
  const [copied, setCopied] = useState(false);

  let dod: { text: string; done: boolean }[] = [];
  try {
    if (story.definition_of_done) {
      const parsed = JSON.parse(story.definition_of_done as string);
      if (Array.isArray(parsed)) dod = parsed;
    }
  } catch { /* ignore */ }

  const lines: string[] = [];
  lines.push(`# Implementierungsauftrag: ${story.title}`);
  lines.push("");

  if (story.description) {
    lines.push("## User Story");
    lines.push(story.description);
    lines.push("");
  }

  if (story.acceptance_criteria) {
    lines.push("## Akzeptanzkriterien");
    lines.push(story.acceptance_criteria);
    lines.push("");
  }

  if (features && features.length > 0) {
    lines.push("## Zu implementierende Features");
    features.forEach(f => {
      lines.push(`- **${f.title}**${f.description ? `: ${f.description}` : ""}`);
    });
    lines.push("");
  }

  if (testCases && testCases.length > 0) {
    lines.push("## Testfälle");
    testCases.forEach(tc => {
      lines.push(`- ${tc.title}`);
      if (tc.steps) lines.push(`  Schritte: ${tc.steps}`);
      if (tc.expected_result) lines.push(`  Erwartetes Ergebnis: ${tc.expected_result}`);
    });
    lines.push("");
  }

  if (dod.length > 0) {
    lines.push("## Definition of Done");
    dod.forEach(item => {
      lines.push(`- [${item.done ? "x" : " "}] ${item.text}`);
    });
    lines.push("");
  }

  lines.push("## Hinweise");
  lines.push("- Implementiere alle Features vollständig und teste sie gegen die Akzeptanzkriterien.");
  lines.push("- Stelle sicher, dass alle Testfälle erfolgreich durchlaufen.");
  lines.push("- Beachte die Definition of Done vor dem Abschluss.");

  const prompt = lines.join("\n");

  function handleCopy() {
    void navigator.clipboard.writeText(prompt).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
        <div className="flex items-center gap-2">
          <Sparkles size={15} className="text-[var(--ink-faint)]" />
          <h2 className="text-base font-semibold text-[var(--ink)]">KI-Implementierungsprompt</h2>
        </div>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-xs font-medium transition-colors"
        >
          {copied ? <CheckCircle size={12} className="text-[var(--green)]" /> : <ClipboardCheck size={12} />}
          {copied ? "Kopiert!" : "Kopieren"}
        </button>
      </div>
      <div className="p-4 sm:p-6">
        <p className="text-xs text-[var(--ink-faint)] mb-3">
          Dieser Prompt fasst alle relevanten Story-Informationen zusammen und kann direkt in einem KI-Assistenten (z.B. Claude, ChatGPT, Copilot) verwendet werden.
        </p>
        <textarea
          readOnly
          value={prompt}
          rows={20}
          className="w-full px-3 py-2 text-sm font-mono border border-[var(--paper-rule)] rounded-sm bg-white text-[var(--ink-mid)] resize-y outline-none focus:border-[rgba(var(--accent-red-rgb),.3)]"
        />
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
        <h3 className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">{label}</h3>
        {!editing && (
          <button
            onClick={() => setEditing(true)}
            className="flex items-center gap-1 px-2 py-0.5 text-xs text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm transition-colors"
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
            className="w-full px-3 py-2 text-sm border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm outline-none focus:ring-2 focus:ring-[var(--accent-red)] resize-y"
          />
          <div className="flex gap-2">
            <button
              onClick={() => void handleSave()}
              disabled={saving}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-xs font-medium transition-colors"
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
              className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors"
            >
              Abbrechen
            </button>
          </div>
        </div>
      ) : (
        <div
          onClick={() => setEditing(true)}
          className={`px-3 py-2.5 text-sm rounded-sm border cursor-text min-h-[3rem] whitespace-pre-wrap leading-relaxed transition-colors ${
            value
              ? "text-[var(--ink-mid)] bg-[var(--card)] border-[var(--paper-rule)] hover:border-[rgba(var(--accent-red-rgb),.3)]"
              : "text-[var(--ink-faint)] bg-[var(--card)] border-dashed border-[var(--ink-faintest)] hover:border-[rgba(var(--accent-red-rgb),.3)]"
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
        <div className="flex items-center gap-2 px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
          <FileText size={15} className="text-[var(--ink-faint)]" />
          <h2 className="text-base font-semibold text-[var(--ink)]">Dokumentation</h2>
          {docs && <span className="text-xs text-[var(--ink-faint)] ml-1">Automatisch generiert, wird bei Änderungen aktualisiert</span>}
        </div>

        <div className="p-4 sm:p-6 space-y-6">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--accent-red)]" />
            </div>
          )}

          {!isLoading && !docs && !regenerating && (
            <div className="text-center py-6">
              <p className="text-sm text-[var(--ink-faint)]">
                Noch keine Dokumentation vorhanden. Starte die Generierung oder speichere die Story.
              </p>
            </div>
          )}

          {docs && (
            <div className="space-y-5">
              <div>
                <h3 className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-2">Zusammenfassung</h3>
                <p className="text-sm text-[var(--ink-mid)] leading-relaxed bg-[var(--card)] rounded-sm p-3">{docs.summary}</p>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-2">Changelog-Eintrag</h3>
                <pre className="text-xs text-[var(--ink-mid)] bg-[var(--card)] rounded-sm p-3 whitespace-pre-wrap font-mono overflow-x-auto">{docs.changelog_entry}</pre>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-2">Dokumenten-Gliederung</h3>
                <ol className="space-y-1.5">
                  {docs.pdf_outline.map((item, i) => (
                    <li key={i} className="flex items-start gap-2.5 text-sm text-[var(--ink-mid)]">
                      <span className="shrink-0 w-5 h-5 rounded-full bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] text-xs flex items-center justify-center font-semibold mt-0.5">{i + 1}</span>
                      {item}
                    </li>
                  ))}
                </ol>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-2">Technische Hinweise</h3>
                <p className="text-sm text-[var(--ink-mid)] leading-relaxed bg-[var(--card)] rounded-sm p-3 whitespace-pre-wrap">{docs.technical_notes}</p>
              </div>

              {docs.confluence_page_url && (
                <a
                  href={docs.confluence_page_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-1.5 bg-[rgba(74,85,104,.06)] border border-[rgba(74,85,104,.2)] text-[var(--navy)] hover:bg-[rgba(74,85,104,.1)] rounded-sm text-xs font-medium transition-colors"
                >
                  In Confluence öffnen →
                </a>
              )}
            </div>
          )}

          {/* Divider for user-editable sections — always visible */}
          <div className="border-t border-[var(--paper-rule)] pt-5 space-y-5">
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
            <Sparkles size={16} className="text-[var(--accent-red)]" />
            Assistent
          </h2>
          <p className="text-xs text-[var(--ink-faint)] mt-1">
            Generiert Zusammenfassung, Changelog-Eintrag, Dokumenten-Gliederung und technische Hinweise aus der Story.
          </p>
        </div>

        <button
          onClick={() => void handleRegenerate()}
          disabled={regenerating}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
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
          <div className="mt-3 p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-xs">{regenError}</div>
        )}

        <div className="mt-5 space-y-2">
          <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-3">Generierte Abschnitte</p>
          {[
            { label: "Zusammenfassung" },
            { label: "Changelog-Eintrag" },
            { label: "Dokumenten-Gliederung" },
            { label: "Technische Hinweise" },
          ].map(({ label }) => (
            <div key={label} className="flex items-center gap-2 p-3 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
              <div className={`w-2 h-2 rounded-full shrink-0 ${docs ? "bg-[var(--green)]" : "bg-[var(--paper-rule)]"}`} />
              <span className="text-xs text-[var(--ink-mid)]">{label}</span>
            </div>
          ))}
          {!docs && (
            <p className="text-xs text-[var(--ink-faint)] text-center pt-1">Wird nach dem Generieren befüllt.</p>
          )}

          <div className="border-t border-[var(--paper-rule)] pt-4 mt-4 space-y-2">
            <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-3">Manuell gepflegt</p>
            <div className="flex items-center gap-2 p-3 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
              <div className={`w-2 h-2 rounded-full shrink-0 ${additionalInfo ? "bg-[var(--accent-red)]" : "bg-[var(--paper-rule)]"}`} />
              <span className="text-xs text-[var(--ink-mid)]">Zusatzinformationen</span>
            </div>
            <div className="flex items-center gap-2 p-3 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
              <div className={`w-2 h-2 rounded-full shrink-0 ${workarounds ? "bg-[var(--accent-red)]" : "bg-[var(--paper-rule)]"}`} />
              <span className="text-xs text-[var(--ink-mid)]">Bekannte Workarounds</span>
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
  draft: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived: "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
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
    <div className="border border-[var(--paper-rule)] rounded-sm bg-[var(--card)] hover:border-[var(--ink-faintest)] transition-colors">
      <div className="flex items-start gap-2 p-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className={`px-1.5 py-0.5 rounded-sm text-xs font-medium ${FEATURE_STATUS_COLORS[feature.status]}`}>
              {FEATURE_STATUS_LABELS[feature.status]}
            </span>
            <span className={`text-xs font-medium ${PRIORITY_COLORS[feature.priority]}`}>
              ● {PRIORITY_OPTIONS.find((p) => p.value === feature.priority)?.label}
            </span>
            {feature.story_points !== null && (
              <span className="px-1.5 py-0.5 rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] text-xs">{feature.story_points} SP</span>
            )}
          </div>
          <p className="text-sm font-medium text-[var(--ink)] leading-snug">{feature.title}</p>
          {feature.description && (
            <>
              {!expanded && (
                <button onClick={() => setExpanded(true)} className="text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] mt-0.5">
                  Beschreibung anzeigen ▼
                </button>
              )}
              {expanded && (
                <>
                  <p className="text-xs text-[var(--ink-faint)] mt-1 whitespace-pre-wrap">{feature.description}</p>
                  <button onClick={() => setExpanded(false)} className="text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] mt-0.5">
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
            className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm transition-colors"
            title="Bearbeiten"
          >
            <Pencil size={13} />
          </button>
          <button
            type="button"
            onClick={() => void onDelete(feature.id)}
            disabled={deletingId === feature.id}
            className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm transition-colors"
            title="Löschen"
          >
            {deletingId === feature.id
              ? <div className="animate-spin rounded-full h-3 w-3 border-2 border-[var(--accent-red)] border-t-transparent" />
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
    <div className="border border-emerald-200 rounded-sm bg-emerald-50 hover:border-emerald-300 transition-colors">
      <div className="flex items-start gap-2 px-3 py-2.5">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 mb-0.5">
            <span className={`text-xs font-medium ${PRIORITY_COLORS[suggestion.priority ?? "medium"]}`}>
              ● {PRIORITY_OPTIONS.find((p) => p.value === (suggestion.priority ?? "medium"))?.label}
            </span>
            {suggestion.story_points !== null && suggestion.story_points !== undefined && (
              <span className="px-1.5 py-0.5 rounded-sm bg-emerald-100 text-emerald-600 text-xs">{suggestion.story_points} SP</span>
            )}
          </div>
          <p className="text-sm font-medium text-[var(--ink)] leading-snug">{suggestion.title}</p>
          {suggestion.description && (
            <>
              {!expanded && (
                <button onClick={() => setExpanded(true)} className="text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] mt-0.5">
                  Details ▼
                </button>
              )}
              {expanded && (
                <>
                  <p className="text-xs text-[var(--ink-mid)] mt-1 whitespace-pre-wrap">{suggestion.description}</p>
                  <button onClick={() => setExpanded(false)} className="text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)]">▲</button>
                </>
              )}
            </>
          )}
        </div>
        <button
          type="button"
          onClick={() => void handleAdd()}
          disabled={adding}
          className="shrink-0 flex items-center gap-1 px-2.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-400 text-white rounded-sm text-xs font-medium transition-colors"
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

  const inputCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Package size={16} className="text-[var(--accent-red)]" />
            <h3 className="font-semibold text-[var(--ink)]">Features</h3>
            <span className="text-xs text-[var(--ink-faint)] bg-[var(--paper-warm)] px-2 py-0.5 rounded-full">{features?.length ?? 0}</span>
          </div>
          {!showAddForm && (
            <button
              onClick={() => setShowAddForm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors"
            >
              <Plus size={12} /> Feature hinzufügen
            </button>
          )}
        </div>

        {/* Add form */}
        {showAddForm && (
          <div className="border border-[var(--paper-rule)] rounded-sm p-3 bg-[var(--paper-warm)] space-y-3">
            <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">Neues Feature</p>
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
                className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
              >
                {addSaving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
                Speichern
              </button>
              <button
                onClick={() => { setShowAddForm(false); setAddTitle(""); setAddDesc(""); }}
                className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm transition-colors"
              >
                Abbrechen
              </button>
            </div>
          </div>
        )}

        {/* Feature list */}
        {!features ? (
          <div className="flex justify-center py-8"><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[var(--accent-red)]" /></div>
        ) : features.length === 0 && !showAddForm ? (
          <div className="text-center py-10 text-[var(--ink-faint)]">
            <Package size={32} className="mx-auto mb-2 opacity-30" />
            <p className="text-sm">Noch keine Features.</p>
            <p className="text-xs mt-1">Features manuell hinzufügen oder Vorschläge generieren.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {features.map((f) =>
              editingId === f.id ? (
                <div key={f.id} className="border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm p-3 bg-[rgba(var(--accent-red-rgb),.08)] space-y-3">
                  <p className="text-xs font-semibold text-[var(--accent-red)] uppercase tracking-wide">Feature bearbeiten</p>
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
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium"
                    >
                      {editSaving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
                      Speichern
                    </button>
                    <button onClick={() => setEditingId(null)} className="px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm">
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
      <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-[var(--accent-red)]" />
          <h3 className="font-semibold text-[var(--ink)]">Feature-Vorschläge</h3>
        </div>
        <p className="text-sm text-[var(--ink-faint)]">
          Analysiert die User Story und schlägt konkrete, implementierbare Features (Teilfunktionen) vor.
        </p>

        <button
          onClick={() => void handleAiSuggest()}
          disabled={aiLoading}
          className="flex items-center justify-center gap-2 w-full px-4 py-2.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
        >
          {aiLoading
            ? <><div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" /> Wird analysiert…</>
            : <><Sparkles size={14} /> Features vorschlagen</>
          }
        </button>

        {aiError && (
          <p className="text-sm text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] px-3 py-2 rounded-sm">{aiError}</p>
        )}

        {aiSuggestions.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
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

type ActiveTab = "story" | "dod" | "tests" | "features" | "docs" | "prompt";

type DemoRole = "user" | "ba" | "architect" | "developer" | "tester" | "release";

const DEMO_ROLES: { id: DemoRole; label: string; description: string; color: string }[] = [
  { id: "user",      label: "User",              description: "Gesamtüberblick",                         color: "bg-[var(--paper-warm)] text-[var(--ink-mid)] border-[var(--ink-faintest)]" },
  { id: "ba",        label: "Business Analyst",  description: "Story, DoD & Akzeptanzkriterien",         color: "bg-[rgba(74,85,104,.06)] text-[var(--navy)] border-[rgba(74,85,104,.3)]" },
  { id: "architect", label: "Senior Architekt",  description: "Story, DoD, Features & Dokumentation",    color: "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)] border-[rgba(var(--btn-primary-rgb),.3)]" },
  { id: "developer", label: "Developer",         description: "Story, DoD, Testfälle & Features",         color: "bg-[rgba(122,100,80,.1)] text-[var(--brown)] border-[rgba(122,100,80,.3)]" },
  { id: "tester",    label: "Tester",            description: "Story, Akzeptanzkriterien & Testfälle",   color: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] border-[rgba(var(--accent-red-rgb),.3)]" },
  { id: "release",   label: "Releasemanager",    description: "Story, Testfälle & Dokumentation",        color: "bg-[rgba(82,107,94,.1)] text-[var(--green)] border-[rgba(82,107,94,.3)]" },
];

const ROLE_TABS: Record<DemoRole, ActiveTab[]> = {
  user:      ["story", "dod", "tests", "features", "docs"],
  ba:        ["story", "dod", "tests", "features", "docs"],
  architect: ["story", "dod", "features", "docs", "prompt"],
  developer: ["story", "dod", "tests", "features", "prompt"],
  tester:    ["story", "tests"],
  release:   ["story", "tests", "features", "docs"],
};

export default function StoryDetailPage({
  params,
}: {
  params: Promise<{ org: string; id: string }>;
}) {
  const resolvedParams = use(params);
  const router = useRouter();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; general?: string }>({});
  const [docsRefreshTrigger, setDocsRefreshTrigger] = useState(0);
  const [showSplitPanel, setShowSplitPanel] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("story");
  const [demoRole, setDemoRole] = useState<DemoRole>("user");
  const [showRolePicker, setShowRolePicker] = useState(false);
  const [score, setScore] = useState<{ level: "low" | "medium" | "high"; confidence: number; clarity: number; complexity: number; risk: number; domain: string } | null>(null);
  const [isScoring, setIsScoring] = useState(false);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [status, setStatus] = useState<StoryStatus>("draft");
  const [priority, setPriority] = useState<StoryPriority>("medium");
  const [storyPoints, setStoryPoints] = useState("");
  const [dorPassed, setDorPassed] = useState(false);
  const [epicId, setEpicId] = useState<string | null>(null);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [initialized, setInitialized] = useState(false);

  const { data: story, isLoading, mutate } = useSWR<UserStory>(
    `/api/v1/user-stories/${resolvedParams.id}`,
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
          setProjectId(data.project_id);
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
      if (projectId !== story.project_id) patch.project_id = projectId;

      const saved = await apiRequest<UserStory>(`/api/v1/user-stories/${resolvedParams.id}`, {
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

  async function handleDelete() {
    if (!confirm("User Story wirklich löschen? Alle Testfälle und Features werden ebenfalls gelöscht.")) return;
    setDeleting(true);
    try {
      await apiRequest(`/api/v1/user-stories/${resolvedParams.id}`, { method: "DELETE" });
      router.push(`/${resolvedParams.org}/stories`);
    } catch {
      setFieldErrors({ general: "Fehler beim Löschen." });
    } finally {
      setDeleting(false);
    }
  }

  async function handleScore() {
    setIsScoring(true);
    setScore(null);
    try {
      const result = await apiRequest<{ level: "low" | "medium" | "high"; confidence: number; clarity: number; complexity: number; risk: number; domain: string }>(
        `/api/v1/user-stories/${resolvedParams.id}/score`,
        { method: "POST" }
      );
      setScore(result);
    } catch {
      setFieldErrors({ general: "Scoring fehlgeschlagen." });
    } finally {
      setIsScoring(false);
    }
  }

  if (isLoading || !story) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  const ALL_TABS: { id: ActiveTab; label: string }[] = [
    { id: "story",    label: "Story" },
    { id: "features", label: "Features" },
    { id: "tests",    label: "Testfälle" },
    { id: "dod",      label: "Definition of Done" },
    { id: "docs",     label: "Dokumentation" },
    { id: "prompt",   label: "KI-Prompt" },
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
            href={`/${resolvedParams.org}/stories`}
            className="p-2 rounded-sm text-[var(--ink-faint)] hover:text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] transition-colors"
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
                <span className="px-2 py-0.5 rounded-full bg-[var(--paper-warm)] text-[var(--ink-mid)] text-xs font-medium">
                  {story.story_points} SP
                </span>
              )}
              {story.dor_passed && (
                <span className="px-2 py-0.5 rounded-full bg-[rgba(82,107,94,.1)] text-[var(--green)] text-xs font-medium">
                  ✓ DoR
                </span>
              )}
              {story.epic_id && (
                <EpicBadge epicId={story.epic_id} orgId={story.organization_id} />
              )}
            </div>
            <h1 className="text-xl font-bold text-[var(--ink)] break-words">
              {story.title}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {!editing && !showSplitPanel && (
            <button
              onClick={() => setShowSplitPanel(true)}
              className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm font-medium transition-colors"
            >
              <GitBranch size={16} />
              Aufteilen
            </button>
          )}
          {editing ? (
            <>
              <button
                onClick={() => void handleScore()}
                disabled={isScoring}
                className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] disabled:opacity-50 rounded-sm text-sm font-medium transition-colors"
              >
                {isScoring ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-[var(--ink-mid)] border-t-transparent" />
                ) : (
                  <ClipboardCheck size={16} />
                )}
                Prüfen
              </button>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium transition-colors"
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
                className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm font-medium transition-colors"
              >
                <X size={16} />
                Abbrechen
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => void handleScore()}
                disabled={isScoring}
                className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] disabled:opacity-50 rounded-sm text-sm font-medium transition-colors"
              >
                {isScoring ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-[var(--ink-mid)] border-t-transparent" />
                ) : (
                  <ClipboardCheck size={16} />
                )}
                Prüfen
              </button>
              <button
                onClick={() => setEditing(true)}
                className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm font-medium transition-colors"
              >
                <Pencil size={16} />
                Bearbeiten
              </button>
              <button
                onClick={() => void handleDelete()}
                disabled={deleting}
                className="flex items-center gap-2 px-4 py-2 border border-[rgba(var(--accent-red-rgb),.3)] text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] disabled:opacity-50 rounded-sm text-sm font-medium transition-colors"
              >
                {deleting ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-[var(--accent-red)] border-t-transparent" />
                ) : (
                  <Trash2 size={16} />
                )}
                Löschen
              </button>
            </>
          )}
        </div>
      </div>

      {/* Split badge */}
      {story.is_split && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-[rgba(122,100,80,.1)] border border-[rgba(122,100,80,.3)] rounded-sm text-[var(--brown)] text-sm">
          <GitBranch size={15} className="shrink-0" />
          Diese Story wurde aufgeteilt. Die Sub-Stories findest du in der Story-Liste.
        </div>
      )}

      {/* Split panel */}
      {showSplitPanel && (
        <SplitStoryPanel
          storyId={resolvedParams.id}
          orgId={story.organization_id}
          orgSlug={resolvedParams.org}
          onClose={() => setShowSplitPanel(false)}
        />
      )}

      {/* Score panel */}
      {score && (
        <div className="px-4 py-3 bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-[var(--ink-faint)] uppercase tracking-wide">Story Scoring</span>
              <span className={`inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-semibold ${
                score.level === "low"
                  ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]"
                  : score.level === "medium"
                  ? "bg-[rgba(122,100,80,.1)] text-[var(--brown)]"
                  : "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
              }`}>
                {score.level === "low" ? "Niedrig" : score.level === "medium" ? "Mittel" : "Hoch"}
              </span>
              <span className="text-xs text-[var(--ink-faint)] capitalize">{score.domain}</span>
            </div>
            <button onClick={() => setScore(null)} className="text-[var(--ink-faint)] hover:text-[var(--ink-mid)] text-sm leading-none">×</button>
          </div>
          <div className="space-y-2">
            {([
              { label: "Klarheit", value: score.clarity },
              { label: "Komplexität", value: score.complexity },
              { label: "Risiko", value: score.risk },
            ] as { label: string; value: number }[]).map(({ label, value }) => (
              <div key={label} className="flex items-center gap-3">
                <span className="text-xs text-[var(--ink-faint)] w-20 shrink-0">{label}</span>
                <div className="flex-1 h-1.5 bg-[var(--paper-rule)] rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-[var(--accent-red)]" style={{ width: `${Math.round(value * 100)}%` }} />
                </div>
                <span className="text-xs text-[var(--ink-faint)] w-8 text-right">{Math.round(value * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Demo role switcher */}
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm">
        <div className="flex items-center gap-2 min-w-0">
          <Users size={14} className="text-[var(--ink-faint)] shrink-0" />
          <span className="text-xs text-[var(--ink-faint)] font-medium shrink-0">Demo-Ansicht:</span>
          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold border ${currentRole.color}`}>
            {currentRole.label}
          </span>
          <span className="text-xs text-[var(--ink-faint)] hidden sm:inline truncate">{currentRole.description}</span>
        </div>
        <div className="relative shrink-0">
          <button
            onClick={() => setShowRolePicker((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-xs font-medium transition-colors"
          >
            Rolle wechseln
          </button>
          {showRolePicker && (
            <div className="absolute right-0 top-full mt-1 w-72 bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm z-50 overflow-hidden">
              <div className="px-3 py-2 border-b border-[var(--paper-rule)] bg-[var(--paper-warm)]">
                <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">Perspektive wählen</p>
              </div>
              {DEMO_ROLES.map((role) => (
                <button
                  key={role.id}
                  onClick={() => handleRoleChange(role.id)}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-[var(--paper-warm)] transition-colors border-b border-[var(--paper-rule)] last:border-0 ${
                    demoRole === role.id ? "bg-[rgba(var(--accent-red-rgb),.08)]" : ""
                  }`}
                >
                  <span className={`mt-0.5 shrink-0 px-1.5 py-0.5 rounded-sm text-xs font-semibold border ${role.color}`}>
                    {role.label.split(" ")[0]}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)]">{role.label}</p>
                    <p className="text-xs text-[var(--ink-faint)]">{role.description}</p>
                  </div>
                  {demoRole === role.id && (
                    <CheckCircle size={14} className="shrink-0 mt-0.5 text-[var(--accent-red)]" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex gap-1 border-b border-[var(--paper-rule)] overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
              activeTab === tab.id
                ? "border-[var(--accent-red)] text-[var(--accent-red)]"
                : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"
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
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 space-y-5">
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
                  <label htmlFor="status" className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                    Status
                  </label>
                  <select
                    id="status"
                    value={status}
                    onChange={(e) => setStatus(e.target.value as StoryStatus)}
                    className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
                  >
                    {STATUS_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="priority" className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                    Priorität
                  </label>
                  <select
                    id="priority"
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as StoryPriority)}
                    className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
                  >
                    {PRIORITY_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label htmlFor="story_points" className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
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
                    className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
                  />
                </div>

                <div className="flex items-end pb-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={dorPassed}
                      onChange={(e) => setDorPassed(e.target.checked)}
                      className="w-4 h-4 rounded border-[var(--ink-faintest)] text-[var(--accent-red)]"
                    />
                    <span className="text-sm font-medium text-[var(--ink-mid)]">DoR bestanden</span>
                  </label>
                </div>
              </div>

              <EpicSelector
                orgId={story.organization_id}
                value={epicId}
                onChange={setEpicId}
              />

              <ProjectSelector
                orgId={story.organization_id}
                value={projectId}
                onChange={setProjectId}
              />
              </>
            )}

            {fieldErrors.general && (
              <div className="p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[rgba(var(--accent-red-rgb),.3)] rounded-sm text-[var(--accent-red)] text-sm">
                {fieldErrors.general}
              </div>
            )}

            <div className="text-xs text-[var(--ink-faint)] pt-2 border-t border-[var(--paper-rule)]">
              Erstellt: {new Date(story.created_at).toLocaleDateString("de-DE")} &middot; Aktualisiert:{" "}
              {new Date(story.updated_at).toLocaleDateString("de-DE")}
            </div>
          </div>

          {/* RIGHT: AI Suggestions */}
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
            <AISuggestPanel
              title={title}
              description={description}
              acceptanceCriteria={acceptanceCriteria}
              onApply={handleApplySuggestion}
              storyId={resolvedParams.id}
              persistedScore={story.quality_score}
              onScorePersisted={() => void mutate()}
            />
          </div>
        </div>
      )}

      {/* DoD tab */}
      {activeTab === "dod" && (
        <DefinitionOfDoneSection storyId={resolvedParams.id} initialDod={story.definition_of_done} />
      )}

      {/* Tests tab */}
      {activeTab === "tests" && (
        <TestCasesSection storyId={resolvedParams.id} storyStatus={story.status} />
      )}

      {/* Features tab */}
      {activeTab === "features" && (
        <FeaturesSection storyId={resolvedParams.id} orgId={story.organization_id} />
      )}

      {/* Docs tab */}
      {activeTab === "docs" && (
        <StoryDocsSection storyId={resolvedParams.id} refreshTrigger={docsRefreshTrigger} />
      )}

      {/* KI-Prompt tab */}
      {activeTab === "prompt" && (
        <StoryPromptSection story={story} orgId={story.organization_id} />
      )}
    </div>
  );
}
