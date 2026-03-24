"use client";

import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority } from "@/types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2, LayoutList, Columns, Layers, GitBranch, AlertTriangle } from "lucide-react";
import { useState } from "react";

// Order matches the board lane sequence (left → right)
const LANE_ORDER: StoryStatus[] = [
  "draft",
  "in_review",
  "ready",
  "in_progress",
  "testing",
  "done",
  "archived",
];

const STATUS_LABELS: Record<StoryStatus, string> = {
  draft: "Entwurf",
  in_review: "Überarbeitung",
  ready: "Bereit",
  in_progress: "In Arbeit",
  testing: "Test",
  done: "Fertig",
  archived: "Archiviert",
};

const STATUS_COLORS: Record<StoryStatus, string> = {
  draft: "bg-slate-100 text-slate-600",
  in_review: "bg-violet-100 text-violet-700",
  ready: "bg-blue-100 text-blue-700",
  in_progress: "bg-amber-100 text-amber-700",
  testing: "bg-orange-100 text-orange-700",
  done: "bg-green-100 text-green-700",
  archived: "bg-slate-200 text-slate-500",
};

const PRIORITY_LABELS: Record<StoryPriority, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low: "text-slate-400",
  medium: "text-blue-500",
  high: "text-amber-500",
  critical: "text-red-500",
};

export default function StoriesListPage({ params }: { params: { org: string } }) {
  const { org } = useOrg(params.org);
  const router = useRouter();
  const [deleting, setDeleting] = useState<string | null>(null);

  const { data: stories, isLoading, error, mutate } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}` : null,
    fetcher
  );

  async function handleDelete(e: React.MouseEvent, storyId: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm("Story wirklich löschen?")) return;
    setDeleting(storyId);
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}`, { method: "DELETE" });
      await mutate();
    } catch {
      alert("Fehler beim Löschen.");
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6 min-w-0">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">User Stories</h1>
          <p className="text-slate-500 mt-1">
            {stories ? `${stories.length} ${stories.length === 1 ? "Story" : "Stories"}` : ""}
          </p>
        </div>
        <Link
          href={`/${params.org}/stories/new`}
          className="flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neue Story
        </Link>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-slate-200 overflow-x-auto">
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-brand-600 text-brand-600 whitespace-nowrap">
          <LayoutList size={15} /> Liste
        </span>
        <Link href={`/${params.org}/stories/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <Columns size={15} /> Board
        </Link>
        <Link href={`/${params.org}/stories/features/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <Layers size={15} /> Features
        </Link>
        <Link href={`/${params.org}/stories/epics/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap">
          <GitBranch size={15} /> Epics
        </Link>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Fehler beim Laden der Stories.
        </div>
      )}

      {stories && stories.length === 0 && (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">Noch keine User Stories</h3>
          <p className="text-slate-400 mb-6 text-sm">
            Erstelle deine erste User Story.
          </p>
          <Link
            href={`/${params.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            Erste Story erstellen
          </Link>
        </div>
      )}

      {stories && stories.length > 0 && (() => {
        const grouped = LANE_ORDER
          .map((status) => ({ status, items: stories.filter((s) => s.status === status) }))
          .filter((g) => g.items.length > 0);

        return (
          <div className="space-y-6">
            {grouped.map(({ status, items }) => (
              <div key={status}>
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[status]}`}>
                    {STATUS_LABELS[status]}
                  </span>
                  <span className="text-xs text-slate-400">{items.length}</span>
                </div>
                <div className="grid gap-2">
                  {items.map((story) => (
                    <Link
                      key={story.id}
                      href={`/${params.org}/stories/${story.id}`}
                      className="block bg-white rounded-xl border border-slate-200 p-5 hover:border-brand-300 hover:shadow-sm transition-all group"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <span className={`text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
                              ● {PRIORITY_LABELS[story.priority]}
                            </span>
                            {story.story_points !== null && (
                              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-medium">
                                {story.story_points} SP
                              </span>
                            )}
                            {story.dor_passed && (
                              <span className="px-2 py-0.5 rounded-full bg-green-50 text-green-600 text-xs font-medium">
                                ✓ DoR
                              </span>
                            )}
                          </div>
                          <h3 className="font-semibold text-slate-900 truncate group-hover:text-brand-600 transition-colors">
                            {story.title}
                          </h3>
                          {story.description && (
                            <p className="text-slate-500 text-sm mt-1 line-clamp-2">{story.description}</p>
                          )}
                        </div>

                        {/* Right side: Quality score badge + delete */}
                        <div className="shrink-0 flex items-center gap-2">
                          {story.quality_score !== null && story.quality_score !== undefined && (
                            <span
                              title={`Quality-Score: ${story.quality_score}/100`}
                              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                                story.quality_score >= 75
                                  ? "bg-green-100 text-green-700"
                                  : story.quality_score >= 50
                                  ? "bg-amber-100 text-amber-700"
                                  : "bg-red-100 text-red-600"
                              }`}
                            >
                              {story.quality_score < 50 && <AlertTriangle size={11} />}
                              {story.quality_score}
                            </span>
                          )}
                          <button
                            onClick={(e) => void handleDelete(e, story.id)}
                            disabled={deleting === story.id}
                            className="p-2 rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors sm:opacity-0 sm:group-hover:opacity-100"
                            aria-label="Story löschen"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        );
      })()}
    </div>
  );
}
