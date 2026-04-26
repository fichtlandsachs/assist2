"use client";

import { use, useState, useRef, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { mutate as swrMutate } from "swr";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest } from "@/lib/api/client";
import type { UserStory, StoryPriority } from "@/types";
import { StoryRefinementPanel } from "@/components/stories/StoryRefinementPanel";
import { StoryDoDChatPanel } from "@/components/stories/StoryDoDChatPanel";
import { StoryFeaturesChatPanel } from "@/components/stories/StoryFeaturesChatPanel";
import { EpicSelector } from "@/components/stories/EpicSelector";
import { ProjectSelector } from "@/components/stories/ProjectSelector";
import { VoiceRecorder } from "@/components/voice/VoiceRecorder";
import { ArrowLeft, Save, Sparkles, ListChecks, Layers } from "lucide-react";
import { useT } from "@/lib/i18n/context";

type RightTab = "suggest" | "dod" | "features";

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="mt-1 text-xs text-[var(--accent-red)]">{msg}</p>;
}

function DroppableTextarea({
  id,
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  fieldName,
  error,
  dragHint,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  rows?: number;
  fieldName: "title" | "description" | "acceptance_criteria";
  error?: string;
  dragHint: string;
}) {
  const [isDragOver, setIsDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value]);

  const handleDragOver = (e: React.DragEvent) => {
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

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
        {label}
      </label>
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
        className={`w-full px-3 py-2 text-sm border rounded-sm resize-y overflow-hidden outline-none transition-colors ${
          isDragOver
            ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] ring-2 ring-[rgba(var(--accent-red-rgb),.3)]"
            : error
            ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)]"
            : "border-[var(--ink-faintest)] bg-[var(--card)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)]"
        }`}
      />
      {isDragOver && (
        <p className="text-xs text-[var(--accent-red)] mt-1">{dragHint}</p>
      )}
      <FieldError msg={error} />
    </div>
  );
}

function DroppableInput({
  id,
  label,
  value,
  onChange,
  placeholder,
  fieldName,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  fieldName: "title" | "description" | "acceptance_criteria";
  error?: string;
}) {
  const [isDragOver, setIsDragOver] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    const field = e.dataTransfer.types.includes("application/x-story-field");
    if (field) {
      e.preventDefault();
      setIsDragOver(true);
    }
  };

  const handleDragLeave = () => setIsDragOver(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedField = e.dataTransfer.getData("application/x-story-field");
    if (droppedField === fieldName) {
      const text = e.dataTransfer.getData("text/plain");
      if (text) onChange(text);
    }
  };

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
        {label}
        <span className="text-[var(--accent-red)] ml-0.5">*</span>
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        placeholder={placeholder}
        className={`w-full px-3 py-2 text-sm border rounded-sm outline-none transition-colors ${
          isDragOver
            ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] ring-2 ring-[rgba(var(--accent-red-rgb),.3)]"
            : error
            ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)]"
            : "border-[var(--ink-faintest)] bg-[var(--card)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)]"
        }`}
      />
      <FieldError msg={error} />
    </div>
  );
}


// ── Voice transcription parser ────────────────────────────────────────────────
const VOICE_KEYWORD_MAP: Record<string, "title" | "description" | "acceptance_criteria"> = {
  titel: "title", title: "title",
  beschreibung: "description", description: "description",
  akzeptanzkriterien: "acceptance_criteria",
  akzeptanzkriterium: "acceptance_criteria",
  kriterien: "acceptance_criteria",
  criteria: "acceptance_criteria",
  ac: "acceptance_criteria",
};

function parseTranscription(raw: string): Partial<Record<"title" | "description" | "acceptance_criteria", string>> {
  const keys = Object.keys(VOICE_KEYWORD_MAP).join("|");
  const regex = new RegExp("\\b(" + keys + ")\\s*[:\\-,.]?\\s*", "gi");
  const segments: { field: "title" | "description" | "acceptance_criteria"; contentStart: number; segmentStart: number }[] = [];
  let m: RegExpExecArray | null;
  while ((m = regex.exec(raw)) !== null) {
    segments.push({ field: VOICE_KEYWORD_MAP[m[1].toLowerCase()], segmentStart: m.index, contentStart: m.index + m[0].length });
  }
  if (segments.length === 0) return { description: raw.trim() };
  const result: Partial<Record<"title" | "description" | "acceptance_criteria", string>> = {};
  for (let i = 0; i < segments.length; i++) {
    const { field, contentStart } = segments[i];
    const end = i + 1 < segments.length ? segments[i + 1].segmentStart : raw.length;
    const content = raw.slice(contentStart, end).trim();
    if (content) result[field] = content;
  }
  const prefix = raw.slice(0, segments[0].segmentStart).trim();
  if (prefix) result.description = result.description ? result.description + "\n" + prefix : prefix;
  return result;
}

export default function NewStoryPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useT();

  const PRIORITY_OPTIONS: { value: StoryPriority; label: string }[] = [
    { value: "low",      label: t("story_priority_low") },
    { value: "medium",   label: t("story_priority_medium") },
    { value: "high",     label: t("story_priority_high") },
    { value: "critical", label: t("story_priority_critical") },
  ];

  // ── Form state ─────────────────────────────────────────────────────────────
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [priority, setPriority] = useState<StoryPriority>("medium");
  const [storyPoints, setStoryPoints] = useState("");
  const [epicId, setEpicId] = useState<string | null>(searchParams.get("epic_id"));
  const [projectId, setProjectId] = useState<string | null>(searchParams.get("project_id"));
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; general?: string }>({});
  const [rightTab, setRightTab] = useState<RightTab>("suggest");

  // ── Draft story ────────────────────────────────────────────────────────────
  const [draftStory, setDraftStory] = useState<UserStory | null>(null);
  const draftIdRef = useRef<string | null>(null);
  const savedRef = useRef(false);
  const draftCreatedRef = useRef(false);
  const syncTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Create a draft story as soon as the org is available
  useEffect(() => {
    if (!org || draftCreatedRef.current) return;
    draftCreatedRef.current = true;

    void apiRequest<UserStory>(`/api/v1/user-stories?org_id=${org.id}`, {
      method: "POST",
      body: JSON.stringify({ title: "(Entwurf)", priority: "medium" }),
    })
      .then((story) => {
        draftIdRef.current = story.id;
        setDraftStory(story);
      })
      .catch(() => {
        // silently fail — save will fall back to POST
      });
  }, [org?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Delete the draft when the user navigates away without saving
  useEffect(() => {
    return () => {
      if (!savedRef.current && draftIdRef.current) {
        void apiRequest(`/api/v1/user-stories/${draftIdRef.current}`, {
          method: "DELETE",
        }).catch(() => {});
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Debounced sync: push form changes to the draft so the chat has current content
  useEffect(() => {
    if (!draftIdRef.current) return;
    if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    syncTimerRef.current = setTimeout(() => {
      void apiRequest<UserStory>(`/api/v1/user-stories/${draftIdRef.current}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: title.trim() || "(Entwurf)",
          description: description || null,
          acceptance_criteria: acceptanceCriteria || null,
        }),
      })
        .then((updated) => setDraftStory(updated as UserStory))
        .catch(() => {});
    }, 800);
    return () => {
      if (syncTimerRef.current) clearTimeout(syncTimerRef.current);
    };
  }, [title, description, acceptanceCriteria]); // eslint-disable-line react-hooks/exhaustive-deps

  // Merged story for chat panels — form fields take precedence over last synced state
  const storyForChat: UserStory | null = draftStory
    ? {
        ...draftStory,
        title: title.trim() || draftStory.title,
        description: description || null,
        acceptance_criteria: acceptanceCriteria || null,
        priority,
        story_points: storyPoints ? parseInt(storyPoints, 10) : null,
        epic_id: epicId ?? draftStory.epic_id,
        project_id: projectId ?? draftStory.project_id,
      }
    : null;

  // ── Handlers ───────────────────────────────────────────────────────────────

  function handleApplySuggestion(
    field: "title" | "description" | "acceptance_criteria",
    value: string,
    mode: "replace" | "append" = "replace"
  ) {
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

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    if (!title.trim()) {
      setFieldErrors({ title: t("story_new_error_title") });
      return;
    }
    setSaving(true);
    setFieldErrors({});
    try {
      let story: UserStory;
      if (draftIdRef.current) {
        // Update the existing draft with the final form values
        story = await apiRequest<UserStory>(`/api/v1/user-stories/${draftIdRef.current}`, {
          method: "PATCH",
          body: JSON.stringify({
            title,
            description: description || null,
            acceptance_criteria: acceptanceCriteria || null,
            priority,
            story_points: storyPoints ? parseInt(storyPoints, 10) : null,
            epic_id: epicId || null,
            project_id: projectId || null,
          }),
        });
      } else {
        // Fallback: draft creation failed, create a fresh story
        story = await apiRequest<UserStory>(`/api/v1/user-stories?org_id=${org.id}`, {
          method: "POST",
          body: JSON.stringify({
            title,
            description: description || null,
            acceptance_criteria: acceptanceCriteria || null,
            priority,
            story_points: storyPoints ? parseInt(storyPoints, 10) : null,
            epic_id: epicId || null,
            project_id: projectId || null,
          }),
        });
      }
      savedRef.current = true;
      await swrMutate(`/api/v1/user-stories/${story.id}`, story, false);
      router.push(`/${resolvedParams.org}/stories/${story.id}`);
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setFieldErrors({ general: msg ?? t("story_new_error_save") });
    } finally {
      setSaving(false);
    }
  }

  async function handleCancel() {
    savedRef.current = true; // prevent cleanup from firing a second DELETE
    if (draftIdRef.current) {
      await apiRequest(`/api/v1/user-stories/${draftIdRef.current}`, {
        method: "DELETE",
      }).catch(() => {});
    }
    router.push(`/${resolvedParams.org}/stories`);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => void handleCancel()}
          className="p-2 rounded-sm text-[var(--ink-faint)] hover:text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] transition-colors"
        >
          <ArrowLeft size={18} />
        </button>
        <div>
          <h1 className="text-xl font-bold text-[var(--ink)]">{t("story_new_title")}</h1>
          <p className="text-[var(--ink-faint)] text-sm">{t("story_new_subtitle")}</p>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
        {/* LEFT: Form */}
        <form onSubmit={(e) => void handleSave(e)} className="space-y-4">
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 space-y-5">
            <DroppableInput
              id="title"
              label={t("story_new_field_title")}
              value={title}
              onChange={(v) => { setTitle(v); setFieldErrors((e) => ({ ...e, title: undefined })); }}
              placeholder={t("story_new_title_placeholder")}
              fieldName="title"
              error={fieldErrors.title}
            />

            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--ink-faint)]">{t("story_new_voice")}</span>
              <VoiceRecorder
                onTranscription={(text) => {
                  const parsed = parseTranscription(text);
                  if (parsed.title) setTitle(parsed.title);
                  if (parsed.description) setDescription((prev) => prev ? `${prev}\n${parsed.description!}` : parsed.description!);
                  if (parsed.acceptance_criteria) setAcceptanceCriteria((prev) => prev ? `${prev}\n${parsed.acceptance_criteria!}` : parsed.acceptance_criteria!);
                }}
              />
            </div>

            <DroppableTextarea
              id="description"
              label={t("story_new_field_desc")}
              value={description}
              onChange={setDescription}
              placeholder={t("story_new_desc_placeholder")}
              rows={5}
              fieldName="description"
              dragHint={t("story_new_drag_hint")}
            />

            <DroppableTextarea
              id="acceptance_criteria"
              label={t("story_new_field_criteria")}
              value={acceptanceCriteria}
              onChange={setAcceptanceCriteria}
              placeholder={t("story_new_criteria_placeholder")}
              rows={5}
              fieldName="acceptance_criteria"
              dragHint={t("story_new_drag_hint")}
            />

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="priority" className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                  {t("story_new_field_priority")}
                </label>
                <select
                  id="priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as StoryPriority)}
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)] bg-[var(--card)]"
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
                  {t("story_new_field_points")}
                </label>
                <input
                  id="story_points"
                  type="number"
                  min={0}
                  max={100}
                  value={storyPoints}
                  onChange={(e) => setStoryPoints(e.target.value)}
                  placeholder={t("story_new_points_placeholder")}
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)] bg-[var(--card)]"
                />
              </div>
            </div>

            {org && (
              <EpicSelector
                orgId={org.id}
                value={epicId}
                onChange={setEpicId}
              />
            )}

            {org && (
              <ProjectSelector
                orgId={org.id}
                value={projectId}
                onChange={setProjectId}
              />
            )}
          </div>

          {fieldErrors.general && (
            <div className="p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--paper-rule)] rounded-sm text-[var(--accent-red)] text-sm">
              {fieldErrors.general}
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving || !org}
              className="flex items-center gap-2 px-5 py-2.5 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faintest)] text-white rounded-sm text-sm font-medium transition-colors"
            >
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  {t("common_saving")}
                </>
              ) : (
                <>
                  <Save size={16} />
                  {t("story_new_save")}
                </>
              )}
            </button>
            <button
              type="button"
              onClick={() => void handleCancel()}
              className="px-5 py-2.5 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm font-medium transition-colors"
            >
              {t("common_cancel")}
            </button>
          </div>
        </form>

        {/* RIGHT: AI Assistant */}
        <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] flex flex-col overflow-hidden">
          {/* Tab bar */}
          <div className="flex border-b border-[var(--paper-rule)] shrink-0">
            {(
              [
                { id: "suggest" as RightTab, icon: <Sparkles size={13} />, label: "Assistent" },
                { id: "dod"     as RightTab, icon: <ListChecks size={13} />, label: "DoD" },
                { id: "features" as RightTab, icon: <Layers size={13} />, label: "Features" },
              ] as { id: RightTab; icon: React.ReactNode; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setRightTab(tab.id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 text-xs font-medium transition-colors border-b-2 ${
                  rightTab === tab.id
                    ? "border-[var(--accent-red)] text-[var(--accent-red)]"
                    : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"
                } ${!draftStory && tab.id !== "suggest" ? "opacity-40 cursor-not-allowed" : ""}`}
                disabled={!draftStory && tab.id !== "suggest"}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4 sm:p-6">
            {rightTab === "suggest" && org && (
              <StoryRefinementPanel
                storyId={draftStory?.id ?? ""}
                orgId={org.id}
                story={storyForChat ?? { id: "", title: title || "(Entwurf)", description, acceptance_criteria: acceptanceCriteria } as UserStory}
                onApply={handleApplySuggestion}
              />
            )}

            {rightTab === "dod" && storyForChat && org && (
              <StoryDoDChatPanel
                storyId={storyForChat.id}
                orgId={org.id}
                story={storyForChat}
                onAddItem={() => {}}
              />
            )}

            {rightTab === "features" && storyForChat && org && (
              <StoryFeaturesChatPanel
                storyId={storyForChat.id}
                orgId={org.id}
                story={storyForChat}
                onAddFeature={() => {}}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
