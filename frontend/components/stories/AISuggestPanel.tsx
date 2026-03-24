"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api/client";
import type { AISuggestion } from "@/types";
import { Sparkles, AlertTriangle, GripVertical, CheckCircle, ListChecks, CopyPlus } from "lucide-react";

interface AISuggestPanelProps {
  title: string;
  description: string;
  acceptanceCriteria: string;
  onApply: (field: "title" | "description" | "acceptance_criteria", value: string, mode?: "replace" | "append") => void;
  storyId?: string;
  persistedScore?: number | null;
  onScorePersisted?: () => void;
}

// ---------------------------------------------------------------------------
// Parse AC string into individual numbered items
// ---------------------------------------------------------------------------
function parseACItems(text: string): string[] {
  if (!text?.trim()) return [];
  const lines = text.split(/\n/).map((l) => l.trim()).filter(Boolean);
  const items: string[] = [];
  for (const line of lines) {
    if (/^\d+[\.\)]/.test(line)) {
      items.push(line.replace(/^\d+[\.\)]\s*/, "").trim());
    } else if (items.length > 0) {
      items[items.length - 1] += " " + line;
    } else {
      items.push(line);
    }
  }
  return items.filter(Boolean);
}

// ---------------------------------------------------------------------------
// SuggestionCard — for title and description (single-value fields)
// ---------------------------------------------------------------------------
interface SuggestionCardProps {
  field: "title" | "description" | "acceptance_criteria";
  label: string;
  value: string;
  onApply: AISuggestPanelProps["onApply"];
}

function SuggestionCard({ field, label, value, onApply }: SuggestionCardProps) {
  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData("text/plain", value);
    e.dataTransfer.setData("application/x-story-field", field);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="border border-slate-200 rounded-lg p-3 bg-slate-50 hover:bg-white hover:border-brand-300 transition-all cursor-grab active:cursor-grabbing group"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {label}
        </span>
        <GripVertical size={14} className="text-slate-300 group-hover:text-slate-400 transition-colors" />
      </div>
      <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">{value}</p>
      <button
        type="button"
        onClick={() => onApply(field, value)}
        className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-medium rounded-md transition-colors"
      >
        <CheckCircle size={12} />
        Übernehmen
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// CriterionCard — single AC item, appends to the AC field
// ---------------------------------------------------------------------------
interface CriterionCardProps {
  index: number;
  text: string;
  onApply: AISuggestPanelProps["onApply"];
}

function CriterionCard({ index, text, onApply }: CriterionCardProps) {
  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData("text/plain", text);
    e.dataTransfer.setData("application/x-story-criterion", text);
    e.dataTransfer.effectAllowed = "copy";
  };

  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="flex items-start gap-2 border border-slate-200 rounded-lg px-3 py-2 bg-slate-50 hover:bg-white hover:border-brand-300 transition-all cursor-grab active:cursor-grabbing group"
    >
      <span className="shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center rounded-full bg-brand-100 text-brand-700 text-xs font-bold">
        {index + 1}
      </span>
      <p className="flex-1 text-sm text-slate-700 leading-relaxed">{text}</p>
      <div className="flex items-center gap-1 shrink-0">
        <GripVertical size={13} className="text-slate-300 group-hover:text-slate-400 transition-colors" />
        <button
          type="button"
          title="Zu Akzeptanzkriterien hinzufügen"
          onClick={() => onApply("acceptance_criteria", text, "append")}
          className="p-1 rounded text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-colors"
        >
          <CopyPlus size={13} />
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ACBlock — header + individual items + "alle übernehmen"
// ---------------------------------------------------------------------------
interface ACBlockProps {
  raw: string;
  onApply: AISuggestPanelProps["onApply"];
}

function ACBlock({ raw, onApply }: ACBlockProps) {
  const items = parseACItems(raw);

  // Fallback: if parsing yields nothing, treat as single card
  if (items.length === 0) {
    return (
      <SuggestionCard
        field="acceptance_criteria"
        label="Akzeptanzkriterien"
        value={raw}
        onApply={onApply}
      />
    );
  }

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-slate-50 border-b border-slate-200">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1.5">
          <ListChecks size={13} />
          Akzeptanzkriterien
          <span className="normal-case font-normal text-slate-400">({items.length})</span>
        </span>
        <button
          type="button"
          onClick={() => onApply("acceptance_criteria", raw, "replace")}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50 rounded transition-colors"
        >
          <CheckCircle size={11} />
          Alle übernehmen
        </button>
      </div>

      {/* Individual items */}
      <div className="divide-y divide-slate-100">
        {items.map((item, i) => (
          <div key={i} className="px-2 py-1.5">
            <CriterionCard index={i} text={item} onApply={onApply} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AISuggestPanel (main export)
// ---------------------------------------------------------------------------
export function AISuggestPanel({ title, description, acceptanceCriteria, onApply, storyId, persistedScore, onScorePersisted }: AISuggestPanelProps) {
  const [loading, setLoading] = useState(false);
  const [suggestion, setSuggestion] = useState<AISuggestion | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Displayed score: fresh analysis > persisted DB value
  const displayScore = suggestion?.quality_score ?? persistedScore ?? null;
  const isPersistedScore = suggestion === null && persistedScore !== null;

  async function handleAnalyze() {
    if (!title.trim()) {
      setError("Bitte gib zuerst einen Titel ein.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await apiRequest<{ suggestions: AISuggestion }>(
        "/api/v1/user-stories/ai-suggest",
        {
          method: "POST",
          body: JSON.stringify({
            title,
            description: description || null,
            acceptance_criteria: acceptanceCriteria || null,
            story_id: storyId ?? null,
          }),
        }
      );
      setSuggestion(response.suggestions);
      if (storyId) onScorePersisted?.();
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setError(msg ?? "Fehler bei der Analyse. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
          <Sparkles size={16} className="text-brand-500" />
          Assistent
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Analysiert deine Story gegen die Definition of Ready und schlägt Verbesserungen vor.
        </p>
      </div>

      <button
        type="button"
        onClick={() => void handleAnalyze()}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
      >
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            Analysiert…
          </>
        ) : (
          <>
            <Sparkles size={16} />
            Analysieren
          </>
        )}
      </button>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* Results — real when available, ghost skeleton when not yet analysed */}
      <div className={`mt-4 space-y-4 flex-1 overflow-y-auto transition-opacity duration-300 ${!suggestion && !loading ? "opacity-30 pointer-events-none select-none" : "opacity-100"}`}>

        {/* Quality score */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-500 font-medium flex items-center gap-1.5">
              Qualitätsscore
              {isPersistedScore && <span className="text-slate-400 font-normal">(gespeichert)</span>}
            </span>
            <span className={`font-bold ${
              displayScore === null ? "text-slate-400" :
              displayScore >= 75 ? "text-green-600" :
              displayScore >= 50 ? "text-amber-600" : "text-red-500"
            }`}>
              {displayScore !== null ? `${displayScore}/100` : "—/100"}
            </span>
          </div>
          <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                displayScore !== null
                  ? displayScore >= 75 ? "bg-green-500" : displayScore >= 50 ? "bg-amber-400" : "bg-red-400"
                  : "bg-slate-300"
              }`}
              style={{ width: displayScore !== null ? `${displayScore}%` : "40%" }}
            />
          </div>
          {displayScore !== null && displayScore < 50 && (
            <p className="text-xs text-red-500 flex items-center gap-1">
              <AlertTriangle size={11} />
              Score unter 50 — Story kann nicht auf &quot;Bereit&quot; gesetzt werden.
            </p>
          )}
        </div>

        {/* DoR issues */}
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">DoR-Probleme</p>
          {suggestion && suggestion.dor_issues.length > 0 ? (
            suggestion.dor_issues.map((issue, i) => (
              <div key={i} className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800">
                <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500" />
                {issue}
              </div>
            ))
          ) : (
            <div className="h-8 bg-slate-100 rounded-md" />
          )}
        </div>

        {/* Suggestions */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
            Vorschläge
            {suggestion && (
              <span className="normal-case font-normal text-slate-400 ml-1">(ziehen oder klicken zum Übernehmen)</span>
            )}
          </p>

          {suggestion ? (
            <>
              {suggestion.title && <SuggestionCard field="title" label="Titel" value={suggestion.title} onApply={onApply} />}
              {suggestion.description && <SuggestionCard field="description" label="Beschreibung" value={suggestion.description} onApply={onApply} />}
              {suggestion.acceptance_criteria && <ACBlock raw={suggestion.acceptance_criteria} onApply={onApply} />}
              {!suggestion.title && !suggestion.description && !suggestion.acceptance_criteria && (
                <p className="text-xs text-slate-400 italic">Keine Änderungen nötig — die Story ist bereits gut formuliert.</p>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <div className="h-16 bg-slate-100 rounded-lg" />
              <div className="h-16 bg-slate-100 rounded-lg" />
              <div className="h-24 bg-slate-100 rounded-lg" />
            </div>
          )}
        </div>

        {/* Explanation */}
        {suggestion?.explanation ? (
          <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
            <p className="text-xs font-semibold text-blue-700 mb-1">Erklärung</p>
            <p className="text-xs text-blue-800 leading-relaxed">{suggestion.explanation}</p>
          </div>
        ) : (
          <div className="p-3 bg-slate-50 border border-slate-100 rounded-lg space-y-1.5">
            <div className="h-3 bg-slate-200 rounded w-20" />
            <div className="h-3 bg-slate-200 rounded w-full" />
            <div className="h-3 bg-slate-200 rounded w-4/5" />
            <p className="text-xs text-slate-400 text-center pt-1">Deine Vorschläge findest du hier nach der Analyse.</p>
          </div>
        )}
      </div>
    </div>
  );
}
