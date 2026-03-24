"use client";

import { useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority } from "@/types";
import Link from "next/link";
import { LayoutList, Columns, Plus, GitBranch, AlertTriangle, Layers } from "lucide-react";

const COLUMNS: { status: StoryStatus; label: string; color: string; dot: string; dropHighlight: string }[] = [
  { status: "draft",       label: "Entwurf",        color: "bg-slate-100 text-slate-700 border-slate-200",   dot: "bg-slate-400",   dropHighlight: "ring-2 ring-slate-400 bg-slate-100" },
  { status: "in_review",   label: "Überarbeitung",   color: "bg-violet-50 text-violet-800 border-violet-200", dot: "bg-violet-500",  dropHighlight: "ring-2 ring-violet-400 bg-violet-50" },
  { status: "ready",       label: "Bereit",          color: "bg-blue-50 text-blue-800 border-blue-200",       dot: "bg-blue-500",    dropHighlight: "ring-2 ring-blue-400 bg-blue-50" },
  { status: "in_progress", label: "In Arbeit",       color: "bg-amber-50 text-amber-800 border-amber-200",    dot: "bg-amber-500",   dropHighlight: "ring-2 ring-amber-400 bg-amber-50" },
  { status: "testing",     label: "Test",            color: "bg-orange-50 text-orange-800 border-orange-200", dot: "bg-orange-500",  dropHighlight: "ring-2 ring-orange-400 bg-orange-50" },
  { status: "done",        label: "Fertig",          color: "bg-green-50 text-green-800 border-green-200",    dot: "bg-green-500",   dropHighlight: "ring-2 ring-green-400 bg-green-50" },
  { status: "archived",    label: "Archiviert",      color: "bg-gray-100 text-gray-500 border-gray-200",      dot: "bg-gray-400",    dropHighlight: "ring-2 ring-gray-400 bg-gray-100" },
];

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low:      "bg-slate-100 text-slate-500",
  medium:   "bg-blue-100  text-blue-600",
  high:     "bg-amber-100 text-amber-700",
  critical: "bg-red-100   text-red-600",
};

const PRIORITY_LABELS: Record<StoryPriority, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", critical: "Kritisch",
};

function getQualityScore(story: UserStory): number | null {
  return story.quality_score ?? null;
}

function StoryCard({
  story,
  org,
  dragging,
  onDragStart,
  onDragEnd,
}: {
  story: UserStory;
  org: string;
  dragging: boolean;
  onDragStart: (id: string) => void;
  onDragEnd: () => void;
}) {
  const score = getQualityScore(story);
  const lowScore = score !== null && score < 80;

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", story.id);
        onDragStart(story.id);
      }}
      onDragEnd={onDragEnd}
      className={`bg-white rounded-xl border p-3.5 shadow-sm hover:shadow-md transition-all cursor-grab active:cursor-grabbing select-none ${
        dragging ? "opacity-40 scale-95" : ""
      } ${lowScore ? "border-amber-300 hover:border-amber-400" : "border-slate-200 hover:border-brand-300"}`}
    >
      <Link
        href={`/${org}/stories/${story.id}`}
        className="block text-sm font-semibold text-slate-800 hover:text-brand-600 transition-colors line-clamp-2 mb-2.5 leading-snug"
        onClick={(e) => e.stopPropagation()}
        draggable={false}
      >
        {story.title}
      </Link>

      {story.description && (
        <p className="text-xs text-slate-400 line-clamp-2 mb-2.5 leading-relaxed">{story.description}</p>
      )}

      <div className="flex flex-wrap items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
          {PRIORITY_LABELS[story.priority]}
        </span>
        {story.story_points !== null && (
          <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-500 text-xs font-medium">
            {story.story_points} SP
          </span>
        )}
        {score !== null && (
          <span className={`px-1.5 py-0.5 rounded text-xs font-medium flex items-center gap-0.5 ${
            score >= 80 ? "bg-green-50 text-green-600" :
            score >= 50 ? "bg-amber-50 text-amber-600" :
            "bg-red-50 text-red-500"
          }`}>
            {score < 80 && <AlertTriangle size={9} />}
            {score}
          </span>
        )}
        {story.dor_passed && (
          <span className="px-1.5 py-0.5 rounded bg-green-50 text-green-600 text-xs font-medium">✓ DoR</span>
        )}
        {story.is_split && (
          <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-600 text-xs font-medium flex items-center gap-0.5">
            <GitBranch size={10} />
            Aufgeteilt
          </span>
        )}
      </div>
    </div>
  );
}

export default function StoriesBoardPage({ params }: { params: { org: string } }) {
  const { org } = useOrg(params.org);
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<StoryStatus | null>(null);
  const [blockedMsg, setBlockedMsg] = useState<string | null>(null);
  const dragCounters = useRef<Record<string, number>>({});

  const { data: stories, isLoading, error, mutate } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}` : null,
    fetcher
  );

  async function handleStatusChange(storyId: string, newStatus: StoryStatus) {
    const story = stories?.find((s) => s.id === storyId);

    // Quality gate: block advancement to ready/in_progress/testing/done if score < 80
    const GATED = new Set(["ready", "in_progress", "testing", "done"]);
    if (GATED.has(newStatus) && story) {
      const score = getQualityScore(story);
      if (score !== null && score < 80) {
        setBlockedMsg(`Quality-Score ${score}/100 zu niedrig (Min. 80). Story zuerst verbessern.`);
        setTimeout(() => setBlockedMsg(null), 4000);
        return;
      }
    }

    mutate(
      (prev) => prev?.map((s) => s.id === storyId ? { ...s, status: newStatus } : s),
      false
    );
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: newStatus }),
      });
    } catch (err: unknown) {
      const msg = (err as { error?: string })?.error;
      if (msg) { setBlockedMsg(msg); setTimeout(() => setBlockedMsg(null), 4000); }
    } finally {
      await mutate();
    }
  }

  function handleDragOver(e: React.DragEvent, colStatus: StoryStatus) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverStatus(colStatus);
  }

  function handleDragEnter(e: React.DragEvent, colStatus: StoryStatus) {
    e.preventDefault();
    dragCounters.current[colStatus] = (dragCounters.current[colStatus] ?? 0) + 1;
    setDragOverStatus(colStatus);
  }

  function handleDragLeave(e: React.DragEvent, colStatus: StoryStatus) {
    dragCounters.current[colStatus] = (dragCounters.current[colStatus] ?? 1) - 1;
    if (dragCounters.current[colStatus] <= 0) {
      dragCounters.current[colStatus] = 0;
      if (dragOverStatus === colStatus) setDragOverStatus(null);
    }
  }

  async function handleDrop(e: React.DragEvent, colStatus: StoryStatus) {
    e.preventDefault();
    dragCounters.current = {};
    setDragOverStatus(null);
    const storyId = e.dataTransfer.getData("text/plain");
    if (!storyId) return;
    const story = stories?.find((s) => s.id === storyId);
    if (!story || story.status === colStatus) return;
    await handleStatusChange(storyId, colStatus);
  }

  const byStatus = (status: StoryStatus) =>
    (stories ?? []).filter((s) => s.status === status);

  const total = stories?.length ?? 0;

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">User Stories</h1>
          {total > 0 && (
            <p className="text-slate-500 mt-0.5 text-sm">{total} {total === 1 ? "Story" : "Stories"}</p>
          )}
        </div>
        <Link
          href={`/${params.org}/stories/new`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neue Story
        </Link>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-slate-200 shrink-0 overflow-x-auto">
        <Link
          href={`/${params.org}/stories/list`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap"
        >
          <LayoutList size={15} />
          Liste
        </Link>
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-brand-600 text-brand-600 whitespace-nowrap">
          <Columns size={15} />
          Board
        </span>
        <Link
          href={`/${params.org}/stories/features/board`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap"
        >
          <Layers size={15} />
          Features
        </Link>
        <Link
          href={`/${params.org}/stories/epics/board`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-slate-500 hover:text-slate-700 transition-colors whitespace-nowrap"
        >
          <GitBranch size={15} />
          Epics
        </Link>
      </div>

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

      {!isLoading && !error && stories && stories.length === 0 && (
        <div className="text-center py-16 bg-white rounded-xl border border-slate-200">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-slate-700 mb-2">Noch keine User Stories</h3>
          <p className="text-slate-400 mb-6 text-sm">Erstelle deine erste User Story.</p>
          <Link
            href={`/${params.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            Erste Story erstellen
          </Link>
        </div>
      )}

      {!isLoading && !error && stories && stories.length > 0 && (
        <div className="flex gap-3 overflow-x-auto pb-4 flex-1">
          {COLUMNS.map((col) => {
            const colStories = byStatus(col.status);
            const isOver = dragOverStatus === col.status;
            return (
              <div key={col.status} className="flex flex-col min-w-[240px] w-[240px] shrink-0">
                <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-xl border-x border-t ${col.color}`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${col.dot}`} />
                    <span className="text-xs font-semibold uppercase tracking-wide">{col.label}</span>
                  </div>
                  <span className="text-xs font-bold opacity-70">{colStories.length}</span>
                </div>

                <div
                  onDragOver={(e) => handleDragOver(e, col.status)}
                  onDragEnter={(e) => handleDragEnter(e, col.status)}
                  onDragLeave={(e) => handleDragLeave(e, col.status)}
                  onDrop={(e) => void handleDrop(e, col.status)}
                  className={`flex-1 rounded-b-xl border border-slate-200 p-2 space-y-2 min-h-[120px] transition-all ${
                    isOver ? col.dropHighlight : "bg-slate-50/60"
                  }`}
                >
                  {isOver && dragId && (
                    <div className="border-2 border-dashed border-current rounded-xl h-12 opacity-40" />
                  )}
                  {colStories.length === 0 && !isOver && (
                    <p className="text-xs text-slate-400 text-center py-8">Keine Stories</p>
                  )}
                  {colStories.map((story) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      org={params.org}
                      dragging={dragId === story.id}
                      onDragStart={(id) => { setDragId(id); dragCounters.current = {}; }}
                      onDragEnd={() => { setDragId(null); setDragOverStatus(null); dragCounters.current = {}; }}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {dragId && !blockedMsg && (
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-slate-800 text-white px-3 py-1.5 rounded-full shadow-lg pointer-events-none z-50">
          Story in eine andere Spalte ziehen
        </p>
      )}

      {blockedMsg && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 text-xs bg-red-700 text-white px-4 py-2 rounded-full shadow-lg pointer-events-none z-50">
          <AlertTriangle size={13} />
          {blockedMsg}
        </div>
      )}
    </div>
  );
}
