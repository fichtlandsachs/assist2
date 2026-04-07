"use client";

import { use, useState, useCallback } from "react";
import useSWR from "swr";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Project, ProjectStatus } from "@/types";
import Link from "next/link";
import { Plus, X, Folder } from "lucide-react";

const COLUMNS: { status: ProjectStatus; label: string; dot: string }[] = [
  { status: "planning",  label: "Planung",    dot: "bg-slate-400" },
  { status: "active",    label: "Aktiv",      dot: "bg-teal-500" },
  { status: "done",      label: "Fertig",     dot: "bg-emerald-500" },
  { status: "archived",  label: "Archiviert", dot: "bg-slate-300" },
];

const STATUS_COLORS: Record<ProjectStatus, string> = {
  planning: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  active:   "bg-teal-100 text-teal-700",
  done:     "bg-emerald-100 text-emerald-700",
  archived: "bg-[var(--paper-warm)] text-[var(--ink-faint)]",
};

const EFFORT_LABELS: Record<string, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", xl: "XL",
};

const COLOR_OPTIONS = [
  "#E11D48", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899", "#6B7280",
];

function ProjectCard({
  project,
  orgSlug,
  onDragStart,
}: {
  project: Project;
  orgSlug: string;
  onDragStart: (id: string) => void;
}) {
  return (
    <div
      draggable
      onDragStart={() => onDragStart(project.id)}
      className="bg-[var(--card)] border border-[var(--ink)]/10 rounded-xl p-4 hover:border-[var(--ink)]/25 hover:shadow-[2px_2px_0_rgba(0,0,0,.06)] transition-all cursor-grab active:cursor-grabbing"
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          {project.color ? (
            <span className="w-3 h-3 rounded-full flex-shrink-0 border border-white shadow" style={{ background: project.color }} />
          ) : (
            <Folder size={13} className="text-[var(--ink-faint)] flex-shrink-0" />
          )}
          <Link
            href={`/${orgSlug}/project/${project.id}`}
            className="font-bold text-[var(--ink)] text-[13px] hover:text-teal-600 transition-colors leading-snug truncate"
            onClick={e => e.stopPropagation()}
          >
            {project.name}
          </Link>
        </div>
        <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 ${STATUS_COLORS[project.status]}`}>
          {COLUMNS.find(c => c.status === project.status)?.label}
        </span>
      </div>
      {project.description && (
        <p className="text-[11px] text-[var(--ink-faint)] line-clamp-2 leading-relaxed mb-2">{project.description}</p>
      )}
      <div className="flex items-center gap-2 flex-wrap">
        {project.deadline && (
          <span className="text-[9px] text-[var(--ink-faint)]">
            ⏰ {new Date(project.deadline).toLocaleDateString("de-DE")}
          </span>
        )}
        {project.effort && (
          <span className="text-[9px] bg-[var(--paper-warm)] text-[var(--ink-mid)] px-1.5 py-0.5 rounded">
            {EFFORT_LABELS[project.effort]}
          </span>
        )}
      </div>
    </div>
  );
}

export default function ProjectListPage({ params }: { params: Promise<{ org: string }> }) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<ProjectStatus | null>(null);

  const { data: projects, isLoading, mutate } = useSWR<Project[]>(
    org ? `/api/v1/projects?org_id=${org.id}` : null,
    fetcher
  );

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !org) return;
    setSaving(true);
    try {
      const project = await apiRequest<Project>(`/api/v1/projects?org_id=${org.id}`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), description: description.trim() || null, color, status: "planning" }),
      });
      mutate(prev => [project, ...(prev ?? [])], false);
      setShowForm(false);
      setName("");
      setDescription("");
      setColor(null);
    } finally {
      setSaving(false);
    }
  }

  const handleDrop = useCallback(async (status: ProjectStatus) => {
    if (!draggingId) return;
    setDropTarget(null);
    setDraggingId(null);
    const project = projects?.find(p => p.id === draggingId);
    if (!project || project.status === status) return;
    // Optimistic update
    mutate(prev => prev?.map(p => p.id === draggingId ? { ...p, status } : p), false);
    try {
      await apiRequest(`/api/v1/projects/${draggingId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      mutate();
    } catch {
      mutate(); // revert on error
    }
  }, [draggingId, projects, mutate]);

  const byStatus = (status: ProjectStatus) =>
    (projects ?? []).filter(p => p.status === status);

  return (
    <div className="relative h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6 flex-shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink)]">Projekte</h1>
          <p className="text-[12px] text-[var(--ink-faint)] mt-0.5">
            {projects?.length ?? 0} Projekt{(projects?.length ?? 0) !== 1 ? "e" : ""}
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-xl text-[12px] font-bold hover:bg-teal-600 transition-colors border-2 border-[var(--ink)] shadow-[2px_2px_0_rgba(0,0,0,1)]"
        >
          <Plus size={14} />
          Neues Projekt
        </button>
      </div>

      {/* Create modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={e => void handleCreate(e)}
            className="bg-white border-2 border-[var(--ink)] rounded-2xl p-6 shadow-[6px_6px_0_rgba(0,0,0,1)] w-full max-w-md flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-[var(--ink)] text-xl">Neues Projekt</h2>
              <button type="button" onClick={() => setShowForm(false)} className="p-1 text-[var(--ink-faint)] hover:text-[var(--ink-mid)]">
                <X size={18} />
              </button>
            </div>
            <input
              autoFocus
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Projektname"
              className="px-3 py-2 border-2 border-[var(--paper-rule)] rounded-xl text-sm outline-none focus:border-teal-400"
            />
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Beschreibung (optional)"
              rows={2}
              className="px-3 py-2 border-2 border-[var(--paper-rule)] rounded-xl text-sm outline-none focus:border-teal-400 resize-none"
            />
            <div>
              <p className="text-[11px] font-bold text-[var(--ink-faint)] mb-2">Farbe</p>
              <div className="flex gap-2 flex-wrap">
                <button type="button" onClick={() => setColor(null)}
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${!color ? "border-[var(--ink)]" : "border-[var(--paper-rule)]"}`}>
                  <span className="text-[9px] text-[var(--ink-faint)]">—</span>
                </button>
                {COLOR_OPTIONS.map(c => (
                  <button key={c} type="button" onClick={() => setColor(c)}
                    className={`w-6 h-6 rounded-full border-2 ${color === c ? "border-[var(--ink)] shadow" : "border-transparent"}`}
                    style={{ background: c }} />
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 border-2 border-[var(--paper-rule)] rounded-xl text-sm text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]">
                Abbrechen
              </button>
              <button type="submit" disabled={saving || !name.trim()}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-teal-600 transition-colors disabled:opacity-50">
                {saving ? "Speichern..." : "Erstellen"}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--ink)]" />
        </div>
      )}

      {/* Kanban board */}
      {!isLoading && (
        <div className="flex gap-4 flex-1 overflow-x-auto pb-4">
          {COLUMNS.map(col => (
            <div
              key={col.status}
              className={`flex flex-col flex-shrink-0 rounded-2xl transition-colors ${dropTarget === col.status ? "bg-teal-50 border-2 border-teal-300" : "bg-[var(--paper-warm)] border-2 border-[var(--ink)]/5"}`}
              style={{ width: 280, minHeight: 200 }}
              onDragOver={e => { e.preventDefault(); setDropTarget(col.status); }}
              onDragLeave={() => setDropTarget(null)}
              onDrop={() => void handleDrop(col.status)}
            >
              {/* Column header */}
              <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--ink)]/5">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${col.dot}`} />
                <span className="font-bold text-[var(--ink-mid)] text-[12px] uppercase tracking-wider flex-1">
                  {col.label}
                </span>
                <span className="text-[10px] font-bold text-[var(--ink-faint)] bg-[var(--card)] rounded-full px-1.5 py-0.5 border border-[var(--paper-rule)]">
                  {byStatus(col.status).length}
                </span>
              </div>

              {/* Cards */}
              <div className="flex flex-col gap-2.5 p-3 flex-1">
                {byStatus(col.status).map(project => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    orgSlug={orgSlug}
                    onDragStart={setDraggingId}
                  />
                ))}
                {byStatus(col.status).length === 0 && (
                  <div className="flex flex-col items-center justify-center py-8 text-center">
                    <Folder size={20} className="text-[var(--ink-faintest)] mb-2" />
                    <p className="text-[10px] text-[var(--ink-faintest)]">Leer</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
