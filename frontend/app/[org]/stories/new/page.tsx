"use client";

import { use, useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { mutate as swrMutate } from "swr";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest } from "@/lib/api/client";
import type { UserStory, StoryPriority } from "@/types";
import { AISuggestPanel } from "@/components/stories/AISuggestPanel";
import { EpicSelector } from "@/components/stories/EpicSelector";
import { VoiceRecorder } from "@/components/voice/VoiceRecorder";
import { ArrowLeft, Save } from "lucide-react";
import Link from "next/link";

const PRIORITY_OPTIONS: { value: StoryPriority; label: string }[] = [
  { value: "low", label: "Niedrig" },
  { value: "medium", label: "Mittel" },
  { value: "high", label: "Hoch" },
  { value: "critical", label: "Kritisch" },
];

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="mt-1 text-xs text-[#8b5e52]">{msg}</p>;
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
}: {
  id: string;
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
  rows?: number;
  fieldName: "title" | "description" | "acceptance_criteria";
  error?: string;
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
    // Individual criterion drop → append
    if (fieldName === "acceptance_criteria" && e.dataTransfer.types.includes("application/x-story-criterion")) {
      const text = e.dataTransfer.getData("application/x-story-criterion");
      if (text) onChange(value ? `${value}\n${text}` : text);
      return;
    }
    // Whole-field drop → replace
    const droppedField = e.dataTransfer.getData("application/x-story-field");
    if (droppedField === fieldName) {
      const text = e.dataTransfer.getData("text/plain");
      if (text) onChange(text);
    }
  };

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[#5a5040] mb-1.5">
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
            ? "border-[#8b5e52] bg-[rgba(139,94,82,.08)] ring-2 ring-[rgba(139,94,82,.3)]"
            : error
            ? "border-[#8b5e52] bg-[rgba(139,94,82,.08)] focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)]"
            : "border-[#cec8bc] bg-[#faf9f6] focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)]"
        }`}
      />
      {isDragOver && (
        <p className="text-xs text-[#8b5e52] mt-1">Loslassen zum Übernehmen</p>
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
      <label htmlFor={id} className="block text-sm font-medium text-[#5a5040] mb-1.5">
        {label}
        <span className="text-[#8b5e52] ml-0.5">*</span>
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
            ? "border-[#8b5e52] bg-[rgba(139,94,82,.08)] ring-2 ring-[rgba(139,94,82,.3)]"
            : error
            ? "border-[#8b5e52] bg-[rgba(139,94,82,.08)] focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)]"
            : "border-[#cec8bc] bg-[#faf9f6] focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)]"
        }`}
      />
      <FieldError msg={error} />
    </div>
  );
}

export default function NewStoryPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const router = useRouter();

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [acceptanceCriteria, setAcceptanceCriteria] = useState("");
  const [priority, setPriority] = useState<StoryPriority>("medium");
  const [storyPoints, setStoryPoints] = useState("");
  const [epicId, setEpicId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; general?: string }>({});

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
      setFieldErrors({ title: "Bitte gib einen Titel ein." });
      return;
    }
    setSaving(true);
    setFieldErrors({});
    try {
      const story = await apiRequest<UserStory>(
        `/api/v1/user-stories?org_id=${org.id}`,
        {
          method: "POST",
          body: JSON.stringify({
            title,
            description: description || null,
            acceptance_criteria: acceptanceCriteria || null,
            priority,
            story_points: storyPoints ? parseInt(storyPoints, 10) : null,
            epic_id: epicId || null,
          }),
        }
      );
      // Pre-seed SWR cache so detail page renders instantly without a loading spinner
      await swrMutate(`/api/v1/user-stories/${story.id}`, story, false);
      router.push(`/${resolvedParams.org}/stories/${story.id}`);
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setFieldErrors({ general: msg ?? "Fehler beim Speichern." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href={`/${resolvedParams.org}/stories`}
          className="p-2 rounded-sm text-[#a09080] hover:text-[#5a5040] hover:bg-[#f7f4ee] transition-colors"
        >
          <ArrowLeft size={18} />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-[#1c1810]">Neue User Story</h1>
          <p className="text-[#a09080] text-sm">Erstelle eine neue Story mit Assistent-Unterstützung</p>
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">
        {/* LEFT: Form */}
        <form onSubmit={(e) => void handleSave(e)} className="space-y-4">
          <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-4 sm:p-6 space-y-5">
            <DroppableInput
              id="title"
              label="Titel"
              value={title}
              onChange={(v) => { setTitle(v); setFieldErrors((e) => ({ ...e, title: undefined })); }}
              placeholder="z.B. Als Nutzer möchte ich mein Passwort zurücksetzen"
              fieldName="title"
              error={fieldErrors.title}
            />

            <div className="flex items-center gap-2">
              <span className="text-xs text-[#a09080]">Sprachaufnahme:</span>
              <VoiceRecorder
                onTranscription={(text) => setDescription((prev) => prev ? `${prev}\n${text}` : text)}
              />
            </div>

            <DroppableTextarea
              id="description"
              label="Beschreibung"
              value={description}
              onChange={setDescription}
              placeholder="Als [Rolle] möchte ich [Funktion], damit [Nutzen]"
              rows={5}
              fieldName="description"
            />

            <DroppableTextarea
              id="acceptance_criteria"
              label="Akzeptanzkriterien"
              value={acceptanceCriteria}
              onChange={setAcceptanceCriteria}
              placeholder={"1. Gegeben...\n2. Wenn...\n3. Dann..."}
              rows={5}
              fieldName="acceptance_criteria"
            />

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="priority" className="block text-sm font-medium text-[#5a5040] mb-1.5">
                  Priorität
                </label>
                <select
                  id="priority"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value as StoryPriority)}
                  className="w-full px-3 py-2 text-sm border border-[#cec8bc] rounded-sm outline-none focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)] bg-[#faf9f6]"
                >
                  {PRIORITY_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="story_points" className="block text-sm font-medium text-[#5a5040] mb-1.5">
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
                  className="w-full px-3 py-2 text-sm border border-[#cec8bc] rounded-sm outline-none focus:border-[#8b5e52] focus:ring-2 focus:ring-[rgba(139,94,82,.08)] bg-[#faf9f6]"
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
          </div>

          {fieldErrors.general && (
            <div className="p-3 bg-[rgba(139,94,82,.08)] border border-[#e2ddd4] rounded-sm text-[#8b5e52] text-sm">
              {fieldErrors.general}
            </div>
          )}

          <div className="flex gap-3">
            <button
              type="submit"
              disabled={saving || !org}
              className="flex items-center gap-2 px-5 py-2.5 bg-[#5a5068] hover:bg-[#7a5248] disabled:bg-[#cec8bc] text-white rounded-sm text-sm font-medium transition-colors"
            >
              {saving ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  Speichern…
                </>
              ) : (
                <>
                  <Save size={16} />
                  Story speichern
                </>
              )}
            </button>
            <Link
              href={`/${resolvedParams.org}/stories`}
              className="px-5 py-2.5 border border-[#cec8bc] text-[#5a5040] hover:bg-[#faf9f6] rounded-sm text-sm font-medium transition-colors"
            >
              Abbrechen
            </Link>
          </div>
        </form>

        {/* RIGHT: AI Suggestions */}
        <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-4 sm:p-6 xl:sticky xl:top-6 xl:max-h-[calc(100vh-8rem)] xl:overflow-y-auto">
          <AISuggestPanel
            title={title}
            description={description}
            acceptanceCriteria={acceptanceCriteria}
            onApply={handleApplySuggestion}
          />
        </div>
      </div>
    </div>
  );
}
