"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { Epic, EpicStatus, UserStory, StoryStatus } from "@/types";
import { ProjectSelector } from "@/components/stories/ProjectSelector";
import { useOrg } from "@/lib/hooks/useOrg";
import Link from "next/link";
import {
  ArrowLeft,
  Save,
  Pencil,
  X,
  Trash2,
  GitBranch,
  Plus,
} from "lucide-react";

const STATUS_OPTIONS: { value: EpicStatus; label: string }[] = [
  { value: "planning",    label: "Planung" },
  { value: "in_progress", label: "In Arbeit" },
  { value: "done",        label: "Fertig" },
  { value: "archived",    label: "Archiviert" },
];

const STATUS_COLORS: Record<EpicStatus, string> = {
  planning:    "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const STORY_STATUS_COLORS: Record<StoryStatus, string> = {
  draft:       "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_review:   "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",
  ready:       "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing:     "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const STORY_STATUS_LABELS: Record<StoryStatus, string> = {
  draft:       "Entwurf",
  in_review:   "Überarbeitung",
  ready:       "Bereit",
  in_progress: "In Arbeit",
  testing:     "Test",
  done:        "Fertig",
  archived:    "Archiviert",
};

function FieldError({ msg }: { msg?: string }) {
  if (!msg) return null;
  return <p className="mt-1 text-xs text-[var(--accent-red)]">{msg}</p>;
}

function EditableField({
  id,
  label,
  value,
  onChange,
  placeholder,
  multiline = false,
  editing,
  error,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  multiline?: boolean;
  editing: boolean;
  error?: string;
}) {
  const cls =
    "w-full px-3 py-2 text-sm border rounded-sm outline-none transition-colors border-[var(--ink-faintest)] bg-[var(--card)] focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)]";
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
        {label}
      </label>
      {editing ? (
        multiline ? (
          <textarea
            id={id}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            rows={5}
            className={`${cls} resize-y`}
          />
        ) : (
          <input
            id={id}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            className={cls}
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

export default function EpicDetailPage({
  params,
}: {
  params: Promise<{ org: string; id: string }>;
}) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const router = useRouter();

  const { data: epic, mutate } = useSWR<Epic>(
    `/api/v1/epics/${resolvedParams.id}`,
    fetcher,
    {
      onSuccess: (data) => {
        if (!initialized) {
          setTitle(data.title);
          setDescription(data.description ?? "");
          setStatus(data.status as EpicStatus);
          setProjectId(data.project_id ?? null);
          setInitialized(true);
        }
      },
    }
  );

  const { data: stories } = useSWR<UserStory[]>(
    org
      ? `/api/v1/user-stories?org_id=${org.id}&epic_id=${resolvedParams.id}`
      : null,
    fetcher
  );

  const [initialized, setInitialized] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<EpicStatus>("planning");
  const [projectId, setProjectId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; general?: string }>({});

  function handleEdit() {
    setEditing(true);
    setFieldErrors({});
  }

  function handleCancel() {
    if (epic) {
      setTitle(epic.title);
      setDescription(epic.description ?? "");
      setStatus(epic.status as EpicStatus);
      setProjectId(epic.project_id ?? null);
    }
    setEditing(false);
    setFieldErrors({});
  }

  async function handleSave() {
    if (!title.trim()) {
      setFieldErrors({ title: "Bitte gib einen Titel ein." });
      return;
    }
    setSaving(true);
    setFieldErrors({});
    try {
      const updated = await apiRequest<Epic>(
        `/api/v1/epics/${resolvedParams.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title,
            description: description || null,
            status,
            project_id: projectId || null,
          }),
        }
      );
      await mutate(updated, false);
      setEditing(false);
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      setFieldErrors({ general: msg ?? "Fehler beim Speichern." });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setDeleting(true);
    try {
      await apiRequest(`/api/v1/epics/${resolvedParams.id}`, { method: "DELETE" });
      router.push(`/${resolvedParams.org}/stories/epics/board`);
    } catch {
      setDeleting(false);
      setConfirmDelete(false);
    }
  }

  if (!epic) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href={`/${resolvedParams.org}/stories/epics/board`}
          className="p-2 rounded-sm text-[var(--ink-faint)] hover:text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] transition-colors"
        >
          <ArrowLeft size={18} />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <GitBranch size={14} className="text-[var(--ink-faint)] shrink-0" />
            <span className="text-xs text-[var(--ink-faint)] uppercase tracking-wide font-medium">Epic</span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[epic.status as EpicStatus]}`}
            >
              {STATUS_OPTIONS.find((o) => o.value === epic.status)?.label ?? epic.status}
            </span>
          </div>
          <h1 className="text-xl font-bold text-[var(--ink)] truncate">{epic.title}</h1>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {editing ? (
            <>
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faintest)] text-white rounded-sm text-sm font-medium transition-colors"
              >
                {saving ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                ) : (
                  <Save size={15} />
                )}
                Speichern
              </button>
              <button
                onClick={handleCancel}
                className="p-2 rounded-sm text-[var(--ink-faint)] hover:text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] transition-colors"
              >
                <X size={18} />
              </button>
            </>
          ) : (
            <button
              onClick={handleEdit}
              className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--card)] rounded-sm text-sm font-medium transition-colors"
            >
              <Pencil size={15} />
              Bearbeiten
            </button>
          )}
        </div>
      </div>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 md:gap-6">

        {/* LEFT: Edit form */}
        <div className="space-y-4">
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6 space-y-5">
            <EditableField
              id="epic-title"
              label="Titel"
              value={title}
              onChange={(v) => { setTitle(v); setFieldErrors((e) => ({ ...e, title: undefined })); }}
              placeholder="Epic-Titel"
              editing={editing}
              error={fieldErrors.title}
            />

            <EditableField
              id="epic-description"
              label="Beschreibung"
              value={description}
              onChange={setDescription}
              placeholder="Beschreibung des Epics…"
              multiline
              editing={editing}
            />

            <div>
              <label htmlFor="epic-status" className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                Status
              </label>
              {editing ? (
                <select
                  id="epic-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as EpicStatus)}
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)] bg-[var(--card)]"
                >
                  {STATUS_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              ) : (
                <div className="px-3 py-2">
                  <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[status]}`}>
                    {STATUS_OPTIONS.find((o) => o.value === status)?.label}
                  </span>
                </div>
              )}
            </div>

            {org && (
              <div>
                <ProjectSelector
                  orgId={org.id}
                  value={projectId}
                  onChange={setProjectId}
                  disabled={!editing}
                />
              </div>
            )}
          </div>

          {fieldErrors.general && (
            <div className="p-3 bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--paper-rule)] rounded-sm text-[var(--accent-red)] text-sm">
              {fieldErrors.general}
            </div>
          )}

          {/* Delete */}
          <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-4 sm:p-6">
            <h3 className="text-sm font-semibold text-[var(--ink-mid)] mb-3">Gefahrenzone</h3>
            {confirmDelete ? (
              <div className="space-y-3">
                <p className="text-sm text-[var(--ink-mid)]">
                  Dieses Epic wirklich löschen? Die verknüpften User Stories bleiben erhalten.
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => void handleDelete()}
                    disabled={deleting}
                    className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--accent-red)] disabled:bg-[var(--ink-faintest)] text-white rounded-sm text-sm font-medium transition-colors"
                  >
                    {deleting ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                    ) : (
                      <Trash2 size={15} />
                    )}
                    Ja, löschen
                  </button>
                  <button
                    onClick={() => setConfirmDelete(false)}
                    className="px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors"
                  >
                    Abbrechen
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setConfirmDelete(true)}
                className="flex items-center gap-2 px-4 py-2 border border-[rgba(var(--accent-red-rgb),.3)] text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded-sm text-sm font-medium transition-colors"
              >
                <Trash2 size={15} />
                Epic löschen
              </button>
            )}
          </div>
        </div>

        {/* RIGHT: Linked stories */}
        <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
          <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
            <h2 className="text-base font-semibold text-[var(--ink)] flex items-center gap-2">
              User Stories
              {stories && (
                <span className="px-1.5 py-0.5 bg-[var(--paper-warm)] text-[var(--ink-mid)] rounded-sm text-xs font-medium">
                  {stories.length}
                </span>
              )}
            </h2>
            <Link
              href={`/${resolvedParams.org}/stories/new`}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors"
            >
              <Plus size={13} />
              Neue Story
            </Link>
          </div>

          {!stories && (
            <div className="flex items-center justify-center py-10">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
            </div>
          )}

          {stories && stories.length === 0 && (
            <div className="text-center py-12">
              <p className="text-sm text-[var(--ink-faint)] mb-4">
                Noch keine User Stories in diesem Epic.
              </p>
              <Link
                href={`/${resolvedParams.org}/stories/new`}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
              >
                <Plus size={15} />
                Erste Story erstellen
              </Link>
            </div>
          )}

          {stories && stories.length > 0 && (
            <div className="divide-y divide-[var(--paper-rule)]">
              {stories.map((story) => (
                <Link
                  key={story.id}
                  href={`/${resolvedParams.org}/stories/${story.id}`}
                  className="flex items-center gap-3 px-4 sm:px-6 py-3.5 hover:bg-[var(--paper-warm)] transition-colors group"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] group-hover:text-[var(--accent-red)] transition-colors truncate">
                      {story.title}
                    </p>
                    {story.description && (
                      <p className="text-xs text-[var(--ink-faint)] truncate mt-0.5">
                        {story.description}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {story.story_points !== null && (
                      <span className="text-xs font-medium text-[var(--ink-faint)] bg-[var(--paper-warm)] px-1.5 py-0.5 rounded-sm">
                        {story.story_points} SP
                      </span>
                    )}
                    {story.quality_score !== null && (
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded-sm ${
                        story.quality_score >= 80 ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" :
                        story.quality_score >= 50 ? "bg-[rgba(122,100,80,.1)] text-[var(--brown)]" :
                        "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                      }`}>
                        {story.quality_score}%
                      </span>
                    )}
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        STORY_STATUS_COLORS[story.status]
                      }`}
                    >
                      {STORY_STATUS_LABELS[story.status]}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
