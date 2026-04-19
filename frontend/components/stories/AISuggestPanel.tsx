"use client";

import { useState } from "react";
import { apiRequest } from "@/lib/api/client";
import type { AISuggestion, Source } from "@/types";
import {
  Sparkles, AlertTriangle, GripVertical, CheckCircle,
  ListChecks, CopyPlus, Database, Brain, ChevronRight, Check,
} from "lucide-react";
import { useT } from "@/lib/i18n/context";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface AIDoDSuggestion {
  text: string;
  category?: string;
  sources?: Source[];
}

interface AIFeatureSuggestion {
  title: string;
  description?: string;
  priority?: string;
  sources?: Source[];
}

interface AITestCaseSuggestion {
  title: string;
  steps?: string;
  expected_result?: string;
  sources?: Source[];
}

interface FullAnalysis {
  story: AISuggestion;
  dod: AIDoDSuggestion[];
  features: AIFeatureSuggestion[];
  tests: AITestCaseSuggestion[];
}

interface AISuggestPanelProps {
  title: string;
  description: string;
  acceptanceCriteria: string;
  onApply: (field: "title" | "description" | "acceptance_criteria", value: string, mode?: "replace" | "append") => void;
  storyId?: string;
  persistedScore?: number | null;
  onScorePersisted?: () => void;
  onNavigateToTab?: (tab: "features" | "dod" | "tests") => void;
}

// ---------------------------------------------------------------------------
// Helpers
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

function normalise(s: string) {
  return s.toLowerCase().replace(/\s+/g, " ").trim();
}

function isResolved<T extends { text?: string; title?: string }>(
  prev: T[],
  curr: T[],
  item: T,
): boolean {
  const key = normalise(item.text ?? item.title ?? "");
  if (!key) return false;
  const inCurr = curr.some((c) => normalise(c.text ?? c.title ?? "") === key);
  return !inCurr;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
interface SuggestionCardProps {
  field: "title" | "description" | "acceptance_criteria";
  label: string;
  value: string;
  onApply: AISuggestPanelProps["onApply"];
}

function SuggestionCard({ field, label, value, onApply }: SuggestionCardProps) {
  const { t } = useT();
  const handleDragStart = (e: React.DragEvent) => {
    e.dataTransfer.setData("text/plain", value);
    e.dataTransfer.setData("application/x-story-field", field);
    e.dataTransfer.effectAllowed = "copy";
  };
  return (
    <div
      draggable
      onDragStart={handleDragStart}
      className="border border-[var(--paper-rule)] rounded-lg p-3 bg-[var(--paper-warm)] hover:bg-[var(--card)] hover:border-[var(--accent-red)] transition-all cursor-grab active:cursor-grabbing group"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">{label}</span>
        <GripVertical size={14} className="text-[var(--ink-faintest)] group-hover:text-[var(--ink-faint)] transition-colors" />
      </div>
      <p className="text-sm text-[var(--ink-mid)] whitespace-pre-wrap leading-relaxed">{value}</p>
      <button
        type="button"
        onClick={() => onApply(field, value)}
        className="mt-3 w-full flex items-center justify-center gap-1.5 px-3 py-1.5 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white text-xs font-medium rounded-md transition-colors"
      >
        <CheckCircle size={12} />
        {t("ai_suggest_accept")}
      </button>
    </div>
  );
}

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
      className="flex items-start gap-2 border border-[var(--paper-rule)] rounded-lg px-3 py-2 bg-[var(--paper-warm)] hover:bg-[var(--card)] hover:border-[var(--accent-red)] transition-all cursor-grab active:cursor-grabbing group"
    >
      <span className="shrink-0 mt-0.5 w-5 h-5 flex items-center justify-center rounded-full bg-[var(--paper-warm)] text-[var(--accent-red)] text-xs font-bold">
        {index + 1}
      </span>
      <p className="flex-1 text-sm text-[var(--ink-mid)] leading-relaxed">{text}</p>
      <div className="flex items-center gap-1 shrink-0">
        <GripVertical size={13} className="text-[var(--ink-faintest)] group-hover:text-[var(--ink-faint)] transition-colors" />
        <button
          type="button"
          title="Zu Akzeptanzkriterien hinzufügen"
          onClick={() => onApply("acceptance_criteria", text, "append")}
          className="p-1 rounded text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[var(--paper-warm)] transition-colors"
        >
          <CopyPlus size={13} />
        </button>
      </div>
    </div>
  );
}

interface ACBlockProps {
  raw: string;
  onApply: AISuggestPanelProps["onApply"];
}

function ACBlock({ raw, onApply }: ACBlockProps) {
  const { t } = useT();
  const items = parseACItems(raw);
  if (items.length === 0) {
    return <SuggestionCard field="acceptance_criteria" label="Akzeptanzkriterien" value={raw} onApply={onApply} />;
  }
  return (
    <div className="border border-[var(--paper-rule)] rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--paper-warm)] border-b border-[var(--paper-rule)]">
        <span className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide flex items-center gap-1.5">
          <ListChecks size={13} />
          Akzeptanzkriterien
          <span className="normal-case font-normal text-[var(--ink-faint)]">({items.length})</span>
        </span>
        <button
          type="button"
          onClick={() => onApply("acceptance_criteria", raw, "replace")}
          className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-[var(--accent-red)] hover:bg-[var(--paper-warm)] rounded transition-colors"
        >
          <CheckCircle size={11} />
          {t("ai_suggest_accept")}
        </button>
      </div>
      <div className="divide-y divide-[var(--paper-rule)]">
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
// CategorySection — DoD / Features / Testfälle summary
// ---------------------------------------------------------------------------
interface CategorySectionProps {
  label: string;
  tab: "dod" | "features" | "tests";
  items: { key: string; resolved: boolean }[];
  onNavigate?: (tab: "dod" | "features" | "tests") => void;
  isLoading?: boolean;
  isRefreshing?: boolean;
}

function CategorySection({ label, tab, items, onNavigate, isLoading, isRefreshing }: CategorySectionProps) {
  const pending = items.filter((i) => !i.resolved);
  const resolved = items.filter((i) => i.resolved);

  return (
    <div className={`border rounded-lg overflow-hidden transition-colors ${isRefreshing ? "border-[var(--paper-rule)]" : "border-[var(--paper-rule)]"}`}>
      <div className="flex items-center justify-between px-3 py-2 bg-[var(--paper-warm)] border-b border-[var(--paper-rule)]">
        <span className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide flex items-center gap-1.5">
          {label}
          {isRefreshing && (
            <span className="inline-block w-3 h-3 border-2 border-[var(--accent-red)] border-t-transparent rounded-full animate-spin" />
          )}
        </span>
        <div className="flex items-center gap-2">
          {resolved.length > 0 && (
            <span className="text-[10px] font-medium text-green-600 flex items-center gap-0.5">
              <Check size={10} />
              {resolved.length} erledigt
            </span>
          )}
          {pending.length > 0 && (
            <span className="text-[10px] font-medium text-amber-600">{pending.length} offen</span>
          )}
          {onNavigate && (
            <button
              type="button"
              onClick={() => onNavigate(tab)}
              className="flex items-center gap-0.5 text-[10px] font-medium text-[var(--accent-red)] hover:text-[var(--accent-red)] transition-colors"
            >
              öffnen
              <ChevronRight size={10} />
            </button>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="px-3 py-2 space-y-1.5">
          <div className="h-3 bg-[var(--paper-warm)] rounded w-4/5 animate-pulse" />
          <div className="h-3 bg-[var(--paper-warm)] rounded w-3/5 animate-pulse" />
        </div>
      ) : items.length === 0 ? (
        <div className="px-3 py-2 flex items-center gap-1.5 text-xs text-green-600">
          <Check size={12} />
          Alles in Ordnung
        </div>
      ) : (
        <ul className="divide-y divide-[var(--paper-rule)]">
          {items.map((item) => (
            <li
              key={item.key}
              className={`flex items-start gap-2 px-3 py-2 text-xs ${
                item.resolved ? "opacity-50" : ""
              }`}
            >
              <span
                className={`shrink-0 mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center ${
                  item.resolved
                    ? "border-green-400 bg-green-50 text-green-600"
                    : "border-[var(--paper-rule)] text-transparent"
                }`}
              >
                {item.resolved && <Check size={9} />}
              </span>
              <span className={`leading-relaxed ${item.resolved ? "line-through text-[var(--ink-faint)]" : "text-[var(--ink-mid)]"}`}>
                {item.key}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AISuggestPanel (main export)
// ---------------------------------------------------------------------------
export function AISuggestPanel({
  title,
  description,
  acceptanceCriteria,
  onApply,
  storyId,
  persistedScore,
  onScorePersisted,
  onNavigateToTab,
}: AISuggestPanelProps) {
  const { t } = useT();
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<FullAnalysis | null>(null);
  const [prevAnalysis, setPrevAnalysis] = useState<FullAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  const suggestion = analysis?.story ?? null;
  const displayScore = suggestion?.quality_score ?? persistedScore ?? null;
  const isPersistedScore = suggestion === null && persistedScore !== null;

  // Build item lists with resolved tracking
  function buildDodItems() {
    const curr = analysis?.dod ?? [];
    const prev = prevAnalysis?.dod ?? [];
    return curr.length === 0 && prev.length === 0
      ? []
      : [
          ...curr.map((d) => ({ key: d.text, resolved: false })),
          ...prev
            .filter((p) => isResolved(prev, curr, p))
            .map((p) => ({ key: p.text, resolved: true })),
        ];
  }

  function buildFeatureItems() {
    const curr = analysis?.features ?? [];
    const prev = prevAnalysis?.features ?? [];
    return curr.length === 0 && prev.length === 0
      ? []
      : [
          ...curr.map((f) => ({ key: f.title, resolved: false })),
          ...prev
            .filter((p) => isResolved(prev, curr, p))
            .map((p) => ({ key: p.title, resolved: true })),
        ];
  }

  function buildTestItems() {
    const curr = analysis?.tests ?? [];
    const prev = prevAnalysis?.tests ?? [];
    return curr.length === 0 && prev.length === 0
      ? []
      : [
          ...curr.map((t) => ({ key: t.title, resolved: false })),
          ...prev
            .filter((p) => isResolved(prev, curr, p))
            .map((p) => ({ key: p.title, resolved: true })),
        ];
  }

  async function handleAnalyze() {
    if (!title.trim()) {
      setError(t("story_new_error_title"));
      return;
    }
    setLoading(true);
    setError(null);
    // Save current as previous for resolved tracking
    if (analysis) setPrevAnalysis(analysis);

    try {
      const [storyRes, dodRes, featuresRes, testsRes] = await Promise.all([
        apiRequest<{ suggestions: AISuggestion }>("/api/v1/user-stories/ai-suggest", {
          method: "POST",
          body: JSON.stringify({
            title,
            description: description || null,
            acceptance_criteria: acceptanceCriteria || null,
            story_id: storyId ?? null,
          }),
        }),
        storyId
          ? apiRequest<{ suggestions: AIDoDSuggestion[] }>(
              `/api/v1/user-stories/${storyId}/ai-dod`,
              { method: "POST" },
            ).catch(() => ({ suggestions: [] as AIDoDSuggestion[] }))
          : Promise.resolve({ suggestions: [] as AIDoDSuggestion[] }),
        storyId
          ? apiRequest<{ suggestions: AIFeatureSuggestion[] }>(
              `/api/v1/user-stories/${storyId}/ai-features`,
              { method: "POST" },
            ).catch(() => ({ suggestions: [] as AIFeatureSuggestion[] }))
          : Promise.resolve({ suggestions: [] as AIFeatureSuggestion[] }),
        storyId
          ? apiRequest<{ suggestions: AITestCaseSuggestion[] }>(
              `/api/v1/user-stories/${storyId}/ai-test-case-suggestions`,
              { method: "POST" },
            ).catch(() => ({ suggestions: [] as AITestCaseSuggestion[] }))
          : Promise.resolve({ suggestions: [] as AITestCaseSuggestion[] }),
      ]);

      setAnalysis({
        story: storyRes.suggestions,
        dod: dodRes.suggestions,
        features: featuresRes.suggestions,
        tests: testsRes.suggestions,
      });
      if (storyId) onScorePersisted?.();
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setError(msg ?? t("ai_suggest_error"));
    } finally {
      setLoading(false);
    }
  }

  const dodItems = buildDodItems();
  const featureItems = buildFeatureItems();
  const testItems = buildTestItems();
  const hasResults = analysis !== null;

  return (
    <div className="flex flex-col h-full min-h-0 flex-1">
      <div className="mb-4">
        <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
          <Sparkles size={16} className="text-[var(--accent-red)]" />
          Assistent
        </h2>
      </div>

      <button
        type="button"
        onClick={() => void handleAnalyze()}
        disabled={loading}
        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-lg text-sm font-medium transition-colors"
      >
        {loading ? (
          <>
            <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            {t("ai_suggest_loading")}
          </>
        ) : (
          <>
            <Sparkles size={16} />
            {hasResults ? "Erneut analysieren" : "Analysieren"}
          </>
        )}
      </button>

      {error && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-xs">
          {error}
        </div>
      )}

      <div
        className={`mt-4 space-y-4 flex-1 min-h-0 overflow-y-auto transition-opacity duration-300 ${
          !hasResults && !loading ? "opacity-30 pointer-events-none select-none" : "opacity-100"
        }`}
      >
        {/* Re-analysis loading indicator */}
        {loading && hasResults && (
          <div className="flex items-center gap-2 px-3 py-2 bg-[var(--paper-warm)] border border-[var(--paper-rule)] rounded-lg text-xs text-[var(--accent-red)]">
            <div className="shrink-0 w-3.5 h-3.5 border-2 border-[var(--accent-red)] border-t-transparent rounded-full animate-spin" />
            {t("ai_suggest_loading")}
          </div>
        )}

        {/* Source badges */}
        {suggestion && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border border-[var(--paper-rule)] bg-[var(--paper-warm)] text-[var(--ink-faint)]">
              <Brain size={9} />
              ai
            </span>
            {suggestion.source === "rag_direct" && (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border border-emerald-200 bg-emerald-50 text-emerald-700">
                <Database size={9} />
                direkt
              </span>
            )}
            {(suggestion.sources ?? []).map((s, i) => {
              const isYd = s.type === "confluence" || s.type === "nextcloud" || s.type === "karl_story";
              const isYt = s.type === "jira";
              const isLc = s.type === "user_action";
              const label = isYd ? "yd" : isYt ? "yt" : isLc ? "lc" : s.type;
              const colorCls = isYd
                ? "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100"
                : isYt
                  ? "border-orange-200 bg-orange-50 text-orange-700 hover:bg-orange-100"
                  : isLc
                    ? "border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100"
                    : "border-[var(--paper-rule)] bg-[var(--paper-warm)] text-[var(--ink-faint)]";
              const displayTitle = s.title
                .replace(/^Jira:\s*/i, "")
                .replace(/^Confluence:\s*/i, "")
                .replace(/^Story:\s*/i, "")
                .replace(/^User Action:\s*/i, "");
              const badge = (
                <span className={`inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded border ${colorCls}`}>
                  <span className="font-bold shrink-0">{label}</span>
                  {displayTitle && <span className="font-normal">{displayTitle}</span>}
                </span>
              );
              return s.url ? (
                <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" title={s.title} className="no-underline">
                  {badge}
                </a>
              ) : (
                <span key={i} title={s.title}>{badge}</span>
              );
            })}
          </div>
        )}

        {/* Quality score */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--ink-faint)] font-medium flex items-center gap-1.5">
              Qualitätsscore
              {isPersistedScore && <span className="text-[var(--ink-faint)] font-normal">(gespeichert)</span>}
            </span>
            <span
              className={`font-bold ${
                displayScore === null
                  ? "text-[var(--ink-faint)]"
                  : displayScore >= 75
                    ? "text-green-600"
                    : displayScore >= 50
                      ? "text-amber-600"
                      : "text-red-500"
              }`}
            >
              {displayScore !== null ? `${displayScore}/100` : "—/100"}
            </span>
          </div>
          <div className="h-2 bg-[var(--paper-rule2)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                displayScore !== null
                  ? displayScore >= 75
                    ? "bg-green-500"
                    : displayScore >= 50
                      ? "bg-amber-400"
                      : "bg-red-400"
                  : "bg-[var(--ink-faintest)]"
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
          <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">DoR-Probleme</p>
          {suggestion && suggestion.dor_issues.length > 0 ? (
            suggestion.dor_issues.map((issue, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-2 bg-amber-50 border border-amber-200 rounded-md text-xs text-amber-800"
              >
                <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-500" />
                {issue}
              </div>
            ))
          ) : (
            <div className="h-8 bg-[var(--paper-warm)] rounded-md" />
          )}
        </div>

        {/* Business Value Feedback */}
        {suggestion?.business_value_feedback && (
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">Business Value</p>
            <div className="flex items-start gap-2 p-2.5 bg-orange-50 border border-orange-200 rounded-md text-xs text-orange-800">
              <AlertTriangle size={12} className="mt-0.5 shrink-0 text-orange-500" />
              <span>{suggestion.business_value_feedback}</span>
            </div>
          </div>
        )}

        {/* Story field improvements */}
        <div className="space-y-3">
          <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
            Story-Verbesserungen
            {suggestion && (
              <span className="normal-case font-normal text-[var(--ink-faint)] ml-1">(ziehen oder klicken)</span>
            )}
          </p>
          {suggestion ? (
            <>
              {suggestion.title && <SuggestionCard field="title" label="Titel" value={suggestion.title} onApply={onApply} />}
              {suggestion.description && (
                <SuggestionCard field="description" label="Beschreibung" value={suggestion.description} onApply={onApply} />
              )}
              {suggestion.acceptance_criteria && (
                <ACBlock raw={suggestion.acceptance_criteria} onApply={onApply} />
              )}
              {!suggestion.title && !suggestion.description && !suggestion.acceptance_criteria && (
                <p className="text-xs text-[var(--ink-faint)] italic">
                  Keine Änderungen nötig — die Story ist bereits gut formuliert.
                </p>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <div className="h-16 bg-[var(--paper-warm)] rounded-lg" />
              <div className="h-16 bg-[var(--paper-warm)] rounded-lg" />
              <div className="h-24 bg-[var(--paper-warm)] rounded-lg" />
            </div>
          )}
        </div>

        {/* DoD */}
        <CategorySection
          label="Definition of Done"
          tab="dod"
          items={dodItems}
          onNavigate={onNavigateToTab}
          isLoading={loading && !hasResults}
          isRefreshing={loading && hasResults}
        />

        {/* Features */}
        <CategorySection
          label="Features"
          tab="features"
          items={featureItems}
          onNavigate={onNavigateToTab}
          isLoading={loading && !hasResults}
          isRefreshing={loading && hasResults}
        />

        {/* Testfälle */}
        <CategorySection
          label="Testfälle"
          tab="tests"
          items={testItems}
          onNavigate={onNavigateToTab}
          isLoading={loading && !hasResults}
          isRefreshing={loading && hasResults}
        />

        {/* Explanation */}
        {suggestion?.explanation ? (
          <div
            className={`p-3 rounded-lg border ${
              suggestion.source === "rag_direct"
                ? "bg-emerald-50 border-emerald-100"
                : "bg-blue-50 border-blue-100"
            }`}
          >
            <p
              className={`text-xs font-semibold mb-1 ${
                suggestion.source === "rag_direct" ? "text-emerald-700" : "text-blue-700"
              }`}
            >
              {suggestion.source === "rag_direct" ? "Antwort aus Wissensbank" : "Erklärung"}
            </p>
            <p
              className={`text-xs leading-relaxed ${
                suggestion.source === "rag_direct" ? "text-emerald-800" : "text-blue-800"
              }`}
            >
              {suggestion.explanation}
            </p>
          </div>
        ) : !hasResults ? (
          <div className="p-3 bg-[var(--paper-warm)] border border-[var(--paper-rule)] rounded-lg space-y-1.5">
            <div className="h-3 bg-[var(--paper-rule2)] rounded w-20" />
            <div className="h-3 bg-[var(--paper-rule2)] rounded w-full" />
            <div className="h-3 bg-[var(--paper-rule2)] rounded w-4/5" />
            <p className="text-xs text-[var(--ink-faint)] text-center pt-1">
              Deine Vorschläge findest du hier nach der Analyse.
            </p>
          </div>
        ) : null}

        {/* Sources */}
        {suggestion && (suggestion.sources ?? []).length > 0 && (
          <div className="pt-2 border-t border-[var(--paper-rule)]">
            <p className="text-[10px] font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-1.5">Quellen</p>
            <ul className="space-y-1">
              {(suggestion.sources ?? []).slice(0, 5).map((s, i) => {
                const isYd = s.type === "confluence" || s.type === "nextcloud" || s.type === "karl_story";
                const isYt = s.type === "jira";
                const isLc = s.type === "user_action";
                const label = isYd ? "yd" : isYt ? "yt" : isLc ? "lc" : s.type;
                const displayTitle = s.title
                  .replace(/^Jira:\s*/i, "")
                  .replace(/^Confluence:\s*/i, "")
                  .replace(/^Story:\s*/i, "")
                  .replace(/^User Action:\s*/i, "");
                const labelCls = isYd
                  ? "text-blue-600"
                  : isYt
                    ? "text-orange-600"
                    : isLc
                      ? "text-violet-600"
                      : "text-[var(--ink-faint)]";
                const inner = (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-[var(--ink-mid)]">
                    <span className={`text-[10px] font-bold shrink-0 ${labelCls}`}>{label}</span>
                    <span className="truncate">{displayTitle}</span>
                  </li>
                );
                return s.url ? (
                  <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" className="hover:text-[var(--accent-red)] no-underline block">
                    {inner}
                  </a>
                ) : (
                  inner
                );
              })}
            </ul>
          </div>
        )}

        {/* Sticky re-analyse button at bottom of results */}
        {hasResults && (
          <div className="pt-3 border-t border-[var(--paper-rule)]">
            <button
              type="button"
              onClick={() => void handleAnalyze()}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-3 py-2 border border-[var(--paper-rule)] text-[var(--accent-red)] hover:bg-[var(--paper-warm)] disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
            >
              {loading ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-[var(--accent-red)] border-t-transparent rounded-full animate-spin" />
                  {t("ai_suggest_loading")}
                </>
              ) : (
                <>
                  <Sparkles size={13} />
                  Erneut analysieren
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
