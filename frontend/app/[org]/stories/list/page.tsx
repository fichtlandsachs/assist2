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
  draft:       "bg-[#f7f4ee] text-[#5a5040]",
  in_review:   "bg-[rgba(90,58,122,.08)] text-[#5a3a7a]",
  ready:       "bg-[rgba(30,58,95,.06)] text-[#1e3a5f]",
  in_progress: "bg-[rgba(139,69,19,.1)] text-[#8b4513]",
  testing:     "bg-[rgba(192,57,43,.08)] text-[#c0392b]",
  done:        "bg-[rgba(45,106,79,.1)] text-[#2d6a4f]",
  archived:    "bg-[#ece8e0] text-[#a09080]",
};

const PRIORITY_LABELS: Record<StoryPriority, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low:      "text-[#a09080]",
  medium:   "text-[#1e3a5f]",
  high:     "text-[#8b4513]",
  critical: "text-[#c0392b]",
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
          <h1 className="text-2xl font-bold text-[#1c1810]">User Stories</h1>
          <p className="text-[#a09080] mt-1">
            {stories ? `${stories.length} ${stories.length === 1 ? "Story" : "Stories"}` : ""}
          </p>
        </div>
        <Link
          href={`/${params.org}/stories/new`}
          className="flex items-center gap-2 px-4 py-2 bg-[#5a3a7a] hover:bg-[#a93226] text-white rounded-sm text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neue Story
        </Link>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-[#e2ddd4] overflow-x-auto">
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-[#c0392b] text-[#c0392b] whitespace-nowrap">
          <LayoutList size={15} /> Liste
        </span>
        <Link href={`/${params.org}/stories/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap">
          <Columns size={15} /> Board
        </Link>
        <Link href={`/${params.org}/stories/features/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap">
          <Layers size={15} /> Features
        </Link>
        <Link href={`/${params.org}/stories/epics/board`} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap">
          <GitBranch size={15} /> Epics
        </Link>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#c0392b]" />
        </div>
      )}

      {error && (
        <div className="bg-[rgba(192,57,43,.08)] border border-[#e2ddd4] rounded-sm p-4 text-[#c0392b] text-sm">
          Fehler beim Laden der Stories.
        </div>
      )}

      {stories && stories.length === 0 && (
        <div className="text-center py-16 bg-[#faf9f6] rounded-sm border border-[#e2ddd4]">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-[#5a5040] mb-2">Noch keine User Stories</h3>
          <p className="text-[#a09080] mb-6 text-sm">
            Erstelle deine erste User Story.
          </p>
          <Link
            href={`/${params.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#5a3a7a] hover:bg-[#a93226] text-white rounded-sm text-sm font-medium transition-colors"
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
                  <span className="text-xs text-[#a09080]">{items.length}</span>
                </div>
                <div className="grid gap-2">
                  {items.map((story) => (
                    <Link
                      key={story.id}
                      href={`/${params.org}/stories/${story.id}`}
                      className="block bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-5 hover:border-[rgba(192,57,43,.3)] transition-all group"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <span className={`text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
                              ● {PRIORITY_LABELS[story.priority]}
                            </span>
                            {story.story_points !== null && (
                              <span className="px-2 py-0.5 rounded-full bg-[#f7f4ee] text-[#5a5040] text-xs font-medium">
                                {story.story_points} SP
                              </span>
                            )}
                            {story.dor_passed && (
                              <span className="px-2 py-0.5 rounded-full bg-[rgba(45,106,79,.1)] text-[#2d6a4f] text-xs font-medium">
                                ✓ DoR
                              </span>
                            )}
                          </div>
                          <h3 className="font-semibold text-[#1c1810] truncate group-hover:text-[#c0392b] transition-colors">
                            {story.title}
                          </h3>
                          {story.description && (
                            <p className="text-[#a09080] text-sm mt-1 line-clamp-2">{story.description}</p>
                          )}
                        </div>

                        {/* Right side: Quality score badge + delete */}
                        <div className="shrink-0 flex items-center gap-2">
                          {story.quality_score !== null && story.quality_score !== undefined && (
                            <span
                              title={`Quality-Score: ${story.quality_score}/100`}
                              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                                story.quality_score >= 75
                                  ? "bg-[rgba(45,106,79,.1)] text-[#2d6a4f]"
                                  : story.quality_score >= 50
                                  ? "bg-[rgba(139,69,19,.1)] text-[#8b4513]"
                                  : "bg-[rgba(192,57,43,.08)] text-[#c0392b]"
                              }`}
                            >
                              {story.quality_score < 50 && <AlertTriangle size={11} />}
                              {story.quality_score}
                            </span>
                          )}
                          <button
                            onClick={(e) => void handleDelete(e, story.id)}
                            disabled={deleting === story.id}
                            className="p-2 rounded-sm text-[#cec8bc] hover:text-[#c0392b] hover:bg-[rgba(192,57,43,.08)] transition-colors sm:opacity-0 sm:group-hover:opacity-100"
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
