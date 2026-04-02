"use client";

import { use, useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { useOrg } from "@/lib/hooks/useOrg";
import { fetcher } from "@/lib/api/client";
import type { Project, Epic, UserStory } from "@/types";
import { ArrowLeft, Layers, BookOpen } from "lucide-react";

const STATUS_LABELS: Record<string, string> = {
  planning:    "Planung",
  active:      "Aktiv",
  done:        "Fertig",
  archived:    "Archiviert",
  in_progress: "In Arbeit",
  draft:       "Entwurf",
  in_review:   "Überarbeitung",
  ready:       "Bereit",
  testing:     "Test",
};

const STATUS_COLORS: Record<string, string> = {
  planning:    "bg-slate-100 text-slate-600",
  active:      "bg-teal-100 text-teal-700",
  done:        "bg-emerald-100 text-emerald-700",
  archived:    "bg-slate-50 text-slate-400",
  in_progress: "bg-amber-100 text-amber-700",
  draft:       "bg-slate-100 text-slate-500",
  in_review:   "bg-purple-100 text-purple-600",
  ready:       "bg-blue-100 text-blue-600",
  testing:     "bg-rose-100 text-rose-600",
};

type TabId = "epics" | "stories";

export default function ProjectDetailPage({ params }: { params: Promise<{ org: string; id: string }> }) {
  const { org: orgSlug, id: projectId } = use(params);
  const { org } = useOrg(orgSlug);
  const [tab, setTab] = useState<TabId>("epics");

  const { data: project, isLoading: loadingProject } = useSWR<Project>(
    `/api/v1/projects/${projectId}`,
    fetcher
  );

  const { data: epics } = useSWR<Epic[]>(
    `/api/v1/projects/${projectId}/epics`,
    fetcher
  );

  const { data: stories } = useSWR<UserStory[]>(
    `/api/v1/projects/${projectId}/stories`,
    fetcher
  );

  if (loadingProject) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20">
        <p className="text-slate-400 font-['Architects_Daughter']">Projekt nicht gefunden</p>
        <Link href={`/${orgSlug}/project`} className="mt-3 inline-block text-teal-600 text-sm font-bold font-['Architects_Daughter'] hover:underline">
          ← Zurück
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div>
        <Link href={`/${orgSlug}/project`}
          className="flex items-center gap-1.5 text-[11px] text-slate-400 font-['Architects_Daughter'] hover:text-teal-600 mb-3 transition-colors">
          <ArrowLeft size={12} />
          Alle Projekte
        </Link>

        <div className="bg-[var(--card)] border-2 border-slate-900/10 rounded-2xl p-5 flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-3">
              {project.color && (
                <span className="w-5 h-5 rounded-full flex-shrink-0 border-2 border-white shadow-[2px_2px_0_rgba(0,0,0,.15)]"
                  style={{ background: project.color }} />
              )}
              <h1 className="text-2xl font-bold text-slate-900 font-['Architects_Daughter']">{project.name}</h1>
            </div>
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[project.status] ?? "bg-slate-100 text-slate-500"}`}>
              {STATUS_LABELS[project.status] ?? project.status}
            </span>
          </div>
          {project.description && (
            <p className="text-sm text-slate-500 leading-relaxed">{project.description}</p>
          )}
          <div className="flex items-center gap-4 flex-wrap text-[11px] text-slate-400 font-['Architects_Daughter']">
            {project.deadline && <span>⏰ {new Date(project.deadline).toLocaleDateString("de-DE")}</span>}
            {project.effort && <span>Aufwand: {project.effort.toUpperCase()}</span>}
            {project.complexity && <span>Komplexität: {project.complexity.toUpperCase()}</span>}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b-2 border-slate-900/5 pb-0">
        {([
          { id: "epics" as TabId,   label: "Epics",             icon: Layers,   count: epics?.length ?? 0 },
          { id: "stories" as TabId, label: "Standalone Stories", icon: BookOpen, count: stories?.length ?? 0 },
        ] as const).map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-[12px] font-bold font-['Architects_Daughter'] tracking-wide transition-colors border-b-2 -mb-[2px] ${
              tab === t.id
                ? "text-slate-900 border-slate-900"
                : "text-slate-400 border-transparent hover:text-slate-600"
            }`}>
            <t.icon size={13} />
            {t.label}
            <span className="ml-1 px-1.5 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[9px]">{t.count}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "epics" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(epics ?? []).length === 0 && (
            <p className="text-slate-400 text-sm font-['Architects_Daughter'] col-span-3">Keine Epics zugewiesen.</p>
          )}
          {(epics ?? []).map(epic => (
            <div key={epic.id} className="bg-[var(--card)] border-2 border-slate-900/10 rounded-xl p-4 flex flex-col gap-2 hover:border-slate-900/20 transition-all">
              <div className="flex items-start justify-between gap-2">
                <p className="font-bold text-slate-900 font-['Architects_Daughter'] text-[13px] leading-snug line-clamp-2">{epic.title}</p>
                <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[epic.status] ?? "bg-slate-100 text-slate-500"}`}>
                  {STATUS_LABELS[epic.status] ?? epic.status}
                </span>
              </div>
              {epic.description && (
                <p className="text-[11px] text-slate-400 line-clamp-2">{epic.description}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === "stories" && (
        <div className="flex flex-col gap-2">
          {(stories ?? []).length === 0 && (
            <p className="text-slate-400 text-sm font-['Architects_Daughter']">Keine direkten Stories (ohne Epic) zugewiesen.</p>
          )}
          {(stories ?? []).map(story => (
            <Link key={story.id} href={`/${orgSlug}/stories/${story.id}`}
              className="bg-[var(--card)] border-2 border-slate-900/10 rounded-xl p-4 flex items-center justify-between gap-3 hover:border-slate-900/20 transition-all">
              <p className="font-bold text-slate-900 font-['Architects_Daughter'] text-[13px] truncate">{story.title}</p>
              <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full flex-shrink-0 font-['Architects_Daughter'] ${STATUS_COLORS[story.status] ?? "bg-slate-100 text-slate-500"}`}>
                {STATUS_LABELS[story.status] ?? story.status}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
