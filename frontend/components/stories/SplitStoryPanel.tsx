"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest } from "@/lib/api/client";
import { Sparkles, Plus, Trash2, ChevronDown, ChevronUp, GitBranch, ArrowRight, Layers } from "lucide-react";

interface SplitItem {
  title: string;
  description: string;
  acceptance_criteria: string;
  story_points: number | "";
}

interface SplitStoryPanelProps {
  storyId: string;
  orgId: string;
  orgSlug: string;
  onClose: () => void;
}

const BLANK_ITEM = (): SplitItem => ({
  title: "",
  description: "",
  acceptance_criteria: "",
  story_points: "",
});

function StoryCard({
  index,
  item,
  onChange,
  onRemove,
  isSelected,
  onSelect,
  canRemove,
}: {
  index: number;
  item: SplitItem;
  onChange: (updated: SplitItem) => void;
  onRemove: () => void;
  isSelected: boolean;
  onSelect: () => void;
  canRemove: boolean;
}) {
  const [expanded, setExpanded] = useState(index < 2);

  return (
    <div
      className={`border rounded-xl transition-all ${
        isSelected
          ? "border-brand-400 ring-2 ring-brand-100 bg-brand-50"
          : "border-[var(--paper-rule)] bg-[var(--card)]"
      }`}
    >
      {/* Card header */}
      <div className="flex items-center gap-3 p-3">
        {/* "Continue with" radio */}
        <button
          type="button"
          onClick={onSelect}
          title="Mit dieser Story weiterarbeiten"
          className={`shrink-0 w-5 h-5 rounded-full border-2 transition-colors flex items-center justify-center ${
            isSelected
              ? "border-brand-600 bg-brand-600"
              : "border-slate-300 hover:border-brand-400"
          }`}
        >
          {isSelected && <div className="w-2 h-2 rounded-full bg-[var(--card)]" />}
        </button>

        <span className={`shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${isSelected ? "bg-brand-600 text-white" : "bg-[var(--paper-warm)] text-[var(--ink-faint)]"}`}>
          {index + 1}
        </span>

        <input
          type="text"
          value={item.title}
          onChange={(e) => onChange({ ...item, title: e.target.value })}
          placeholder="Story-Titel…"
          className="flex-1 min-w-0 text-sm font-medium bg-transparent border-none outline-none text-[var(--ink)] placeholder:text-[var(--ink-faint)]"
        />

        <input
          type="number"
          min={1}
          max={13}
          value={item.story_points}
          onChange={(e) => onChange({ ...item, story_points: e.target.value ? parseInt(e.target.value) : "" })}
          placeholder="SP"
          className="w-14 px-2 py-1 text-xs text-center border border-[var(--paper-rule)] rounded-lg outline-none focus:border-brand-400 bg-[var(--card)]"
        />

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="p-1 text-[var(--ink-faint)] hover:text-[var(--ink-mid)] rounded transition-colors"
        >
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>

        {canRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="p-1 text-[var(--ink-faintest)] hover:text-red-500 rounded transition-colors"
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>

      {/* Expandable body */}
      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-[var(--paper-rule)] pt-3">
          <div>
            <label className="block text-xs font-medium text-[var(--ink-faint)] mb-1">Beschreibung</label>
            <textarea
              value={item.description}
              onChange={(e) => onChange({ ...item, description: e.target.value })}
              placeholder="Als [Rolle] möchte ich [Funktion], damit [Nutzen]"
              rows={2}
              className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 resize-none bg-[var(--card)]"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[var(--ink-faint)] mb-1">Akzeptanzkriterien</label>
            <textarea
              value={item.acceptance_criteria}
              onChange={(e) => onChange({ ...item, acceptance_criteria: e.target.value })}
              placeholder={"1. Kriterium\n2. Kriterium"}
              rows={3}
              className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100 resize-none bg-[var(--card)]"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export function SplitStoryPanel({ storyId, orgId, orgSlug, onClose }: SplitStoryPanelProps) {
  const router = useRouter();
  const [stories, setStories] = useState<SplitItem[]>([BLANK_ITEM(), BLANK_ITEM()]);
  const [epicTitle, setEpicTitle] = useState("");
  const [continueWithIndex, setContinueWithIndex] = useState(0);
  const [aiLoading, setAiLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAISuggest() {
    setAiLoading(true);
    setError(null);
    try {
      const res = await apiRequest<{ stories: SplitItem[] }>(
        `/api/v1/user-stories/${storyId}/ai-split`,
        { method: "POST" }
      );
      setStories(res.stories.map((s) => ({
        title: s.title ?? "",
        description: s.description ?? "",
        acceptance_criteria: s.acceptance_criteria ?? "",
        story_points: s.story_points ?? "",
      })));
      setContinueWithIndex(0);
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? "Fehler beim Generieren der Vorschläge.");
    } finally {
      setAiLoading(false);
    }
  }

  async function handleSave() {
    const valid = stories.filter((s) => s.title.trim());
    if (valid.length < 2) {
      setError("Mindestens 2 Stories mit Titel erforderlich.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const res = await apiRequest<{ epic: { id: string } | null; stories: { id: string }[]; continue_with_id: string }>(
        `/api/v1/user-stories/${storyId}/split/save?org_id=${orgId}`,
        {
          method: "POST",
          body: JSON.stringify({
            stories: valid.map((s) => ({
              title: s.title,
              description: s.description || null,
              acceptance_criteria: s.acceptance_criteria || null,
              story_points: s.story_points || null,
            })),
            epic_title: epicTitle.trim() || null,
            continue_with_index: continueWithIndex,
          }),
        }
      );
      router.push(`/${orgSlug}/stories/${res.continue_with_id}`);
    } catch (err: unknown) {
      setError((err as { error?: string })?.error ?? "Fehler beim Speichern.");
      setSaving(false);
    }
  }

  function updateStory(index: number, updated: SplitItem) {
    setStories((prev) => prev.map((s, i) => (i === index ? updated : s)));
  }

  function addStory() {
    setStories((prev) => [...prev, BLANK_ITEM()]);
  }

  function removeStory(index: number) {
    setStories((prev) => prev.filter((_, i) => i !== index));
    if (continueWithIndex >= index && continueWithIndex > 0) {
      setContinueWithIndex((v) => v - 1);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-[var(--paper-rule)] overflow-hidden">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)] bg-[var(--paper-warm)]">
        <div className="flex items-center gap-3">
          <div className="p-1.5 bg-brand-100 rounded-lg shrink-0">
            <GitBranch size={16} className="text-brand-700" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-[var(--ink)]">Story aufteilen</h2>
            <p className="text-xs text-[var(--ink-faint)]">Teile diese Story in unabhängige Sub-Stories auf und gruppiere sie optional unter einem Epic.</p>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => void handleAISuggest()}
            disabled={aiLoading}
            className="flex items-center gap-1.5 px-3 py-1.5 border border-brand-300 text-brand-700 hover:bg-brand-50 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors"
          >
            {aiLoading ? (
              <div className="animate-spin rounded-full h-3 w-3 border-2 border-brand-500 border-t-transparent" />
            ) : (
              <Sparkles size={13} />
            )}
            Aufteilung vorschlagen
          </button>
          <button type="button" onClick={onClose}
            className="px-3 py-1.5 text-[var(--ink-faint)] hover:text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-lg text-xs transition-colors">
            Abbrechen
          </button>
        </div>
      </div>

      <div className="p-4 sm:p-6 space-y-5">
        {/* Epic grouping */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 shrink-0">
            <Layers size={15} className="text-[var(--ink-faint)]" />
            <label className="text-sm font-medium text-[var(--ink-mid)]">Epic</label>
            <span className="text-xs text-[var(--ink-faint)] font-normal">(optional)</span>
          </div>
          <input
            type="text"
            value={epicTitle}
            onChange={(e) => setEpicTitle(e.target.value)}
            placeholder="z.B. Nutzerauthentifizierung"
            className="flex-1 px-3 py-1.5 text-sm border border-slate-300 rounded-lg outline-none focus:border-brand-400 focus:ring-1 focus:ring-brand-100"
          />
        </div>

        {/* Story cards */}
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-1">
            <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide flex items-center gap-1.5">
              Sub-Stories
              <span className="px-1.5 py-0.5 bg-[var(--paper-warm)] rounded text-[var(--ink-mid)] normal-case font-normal tracking-normal">
                {stories.length}
              </span>
            </p>
            <p className="text-xs text-[var(--ink-faint)] flex items-center gap-1">
              <span className="hidden sm:inline">Wähle aus, womit du weitermachen möchtest</span>
              <span className="sm:hidden">Story wählen</span>
              <span className="inline-block w-3 h-3 rounded-full border-2 border-slate-300" />
            </p>
          </div>

          {stories.map((story, i) => (
            <StoryCard
              key={i}
              index={i}
              item={story}
              onChange={(updated) => updateStory(i, updated)}
              onRemove={() => removeStory(i)}
              isSelected={continueWithIndex === i}
              onSelect={() => setContinueWithIndex(i)}
              canRemove={stories.length > 2}
            />
          ))}

          <button
            type="button"
            onClick={addStory}
            className="w-full flex items-center justify-center gap-2 py-2 border border-dashed border-slate-300 text-[var(--ink-faint)] hover:border-brand-400 hover:text-brand-600 rounded-lg text-sm transition-colors"
          >
            <Plus size={14} />
            Story hinzufügen
          </button>
        </div>

        {/* Continue-with hint */}
        {stories[continueWithIndex]?.title && (
          <div className="flex items-center gap-2 px-4 py-3 bg-brand-50 border border-brand-100 rounded-lg text-sm text-brand-700">
            <ArrowRight size={14} className="shrink-0" />
            <span>
              Du wirst nach dem Speichern zu{" "}
              <strong>„{stories[continueWithIndex].title}"</strong> weitergeleitet.
            </span>
          </div>
        )}

        {error && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving || stories.filter((s) => s.title.trim()).length < 2}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-600 hover:bg-brand-700 disabled:bg-brand-400 text-white rounded-lg text-sm font-medium transition-colors"
          >
            {saving ? (
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            ) : (
              <GitBranch size={15} />
            )}
            {saving ? "Speichern…" : `${stories.filter((s) => s.title.trim()).length} Stories speichern & weiter`}
          </button>
          <button type="button" onClick={onClose}
            className="px-5 py-2.5 border border-slate-300 text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-lg text-sm font-medium transition-colors">
            Abbrechen
          </button>
        </div>
      </div>
    </div>
  );
}
