"use client";

import { use, useState } from "react";
import useSWR from "swr";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import type { Project, ProjectStatus } from "@/types";
import Link from "next/link";
import { Plus, X, Folder } from "lucide-react";

const STATUS_LABELS: Record<ProjectStatus, string> = {
  planning: "Planung",
  active:   "Aktiv",
  done:     "Fertig",
  archived: "Archiviert",
};

const STATUS_COLORS: Record<ProjectStatus, string> = {
  planning: "bg-slate-100 text-slate-600",
  active:   "bg-teal-100 text-teal-700",
  done:     "bg-emerald-100 text-emerald-700",
  archived: "bg-slate-50 text-slate-400",
};

const EFFORT_LABELS: Record<string, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", xl: "XL",
};

const COLOR_OPTIONS = [
  "#E11D48", "#F59E0B", "#10B981", "#3B82F6", "#8B5CF6", "#EC4899", "#6B7280",
];

function ProjectCard({ project, orgSlug }: { project: Project; orgSlug: string }) {
  return (
    <Link href={`/${orgSlug}/project/${project.id}`}
      className="bg-[var(--card)] border-2 border-slate-900/10 rounded-2xl p-5 hover:border-slate-900/30 hover:shadow-[4px_4px_0_rgba(0,0,0,.08)] transition-all flex flex-col gap-3 group">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {project.color ? (
            <span className="w-4 h-4 rounded-full flex-shrink-0 border-2 border-white shadow" style={{ background: project.color }} />
          ) : (
            <Folder size={16} className="text-slate-400 flex-shrink-0" />
          )}
          <span className="font-bold text-slate-900 font-['Architects_Daughter'] text-[15px] group-hover:text-teal-600 transition-colors leading-snug">
            {project.name}
          </span>
        </div>
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[project.status]}`}>
          {STATUS_LABELS[project.status]}
        </span>
      </div>
      {project.description && (
        <p className="text-[12px] text-slate-500 line-clamp-2 leading-relaxed">{project.description}</p>
      )}
      <div className="flex items-center gap-3 flex-wrap">
        {project.deadline && (
          <span className="text-[10px] text-slate-400 font-['Architects_Daughter']">
            ⏰ {new Date(project.deadline).toLocaleDateString("de-DE")}
          </span>
        )}
        {project.effort && (
          <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-['Architects_Daughter']">
            Aufwand: {EFFORT_LABELS[project.effort]}
          </span>
        )}
        {project.complexity && (
          <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-['Architects_Daughter']">
            Kompl.: {project.complexity.toUpperCase()}
          </span>
        )}
      </div>
    </Link>
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

  return (
    <div className="relative">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 font-['Architects_Daughter']">Projekte</h1>
          <p className="text-[12px] text-slate-400 font-['Architects_Daughter'] mt-0.5">
            {projects?.length ?? 0} Projekt{(projects?.length ?? 0) !== 1 ? "e" : ""}
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 text-white rounded-xl text-[12px] font-bold font-['Architects_Daughter'] hover:bg-teal-600 transition-colors border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)]"
        >
          <Plus size={14} />
          Neues Projekt
        </button>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <form onSubmit={e => void handleCreate(e)}
            className="bg-white border-2 border-slate-900 rounded-2xl p-6 shadow-[6px_6px_0_rgba(0,0,0,1)] w-full max-w-md flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 className="font-bold text-slate-900 font-['Architects_Daughter'] text-xl">Neues Projekt</h2>
              <button type="button" onClick={() => setShowForm(false)} className="p-1 text-slate-400 hover:text-slate-700">
                <X size={18} />
              </button>
            </div>
            <input
              autoFocus
              required
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="Projektname"
              className="px-3 py-2 border-2 border-slate-200 rounded-xl text-sm outline-none focus:border-teal-400 font-['Architects_Daughter']"
            />
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Beschreibung (optional)"
              rows={2}
              className="px-3 py-2 border-2 border-slate-200 rounded-xl text-sm outline-none focus:border-teal-400 resize-none font-['Architects_Daughter']"
            />
            <div>
              <p className="text-[11px] font-bold text-slate-500 font-['Architects_Daughter'] mb-2">Farbe</p>
              <div className="flex gap-2 flex-wrap">
                <button type="button" onClick={() => setColor(null)}
                  className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${!color ? "border-slate-900" : "border-slate-200"}`}>
                  <span className="text-[9px] text-slate-400">—</span>
                </button>
                {COLOR_OPTIONS.map(c => (
                  <button key={c} type="button" onClick={() => setColor(c)}
                    className={`w-6 h-6 rounded-full border-2 ${color === c ? "border-slate-900 shadow" : "border-transparent"}`}
                    style={{ background: c }} />
                ))}
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 border-2 border-slate-200 rounded-xl text-sm text-slate-600 font-['Architects_Daughter'] hover:bg-slate-50">
                Abbrechen
              </button>
              <button type="submit" disabled={saving || !name.trim()}
                className="px-4 py-2 bg-slate-900 text-white rounded-xl text-sm font-bold font-['Architects_Daughter'] hover:bg-teal-600 transition-colors disabled:opacity-50">
                {saving ? "Speichern..." : "Erstellen"}
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading && (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
        </div>
      )}

      {!isLoading && (projects ?? []).length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Folder size={40} className="text-slate-300 mb-3" />
          <p className="text-slate-400 font-['Architects_Daughter'] text-sm">Noch keine Projekte</p>
          <button onClick={() => setShowForm(true)} className="mt-3 text-teal-600 text-sm font-bold font-['Architects_Daughter'] hover:underline">
            Erstes Projekt anlegen →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(projects ?? []).map(project => (
          <ProjectCard key={project.id} project={project} orgSlug={orgSlug} />
        ))}
      </div>
    </div>
  );
}
