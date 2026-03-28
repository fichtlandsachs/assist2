"use client";

import { use, useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority } from "@/types";
import Link from "next/link";
import { LayoutList, Columns, Plus, GitBranch, AlertTriangle, Layers } from "lucide-react";

const COLUMNS: { status: StoryStatus; label: string; color: string; dot: string; dropHighlight: string }[] = [
  { status: "draft",       label: "Entwurf",        color: "bg-[#f7f4ee] text-[#5a5040] border-[#e2ddd4]",                        dot: "bg-[#cec8bc]",   dropHighlight: "ring-2 ring-[#a09080] bg-[#f7f4ee]" },
  { status: "in_review",   label: "Überarbeitung",   color: "bg-[rgba(90,58,122,.08)] text-[#5a3a7a] border-[rgba(192,57,43,.3)]", dot: "bg-[#5a3a7a]",  dropHighlight: "ring-2 ring-[#5a3a7a] bg-[rgba(90,58,122,.08)]" },
  { status: "ready",       label: "Bereit",          color: "bg-[rgba(30,58,95,.06)] text-[#1e3a5f] border-[#e2ddd4]",            dot: "bg-[#1e3a5f]",   dropHighlight: "ring-2 ring-[#1e3a5f] bg-[rgba(30,58,95,.06)]" },
  { status: "in_progress", label: "In Arbeit",       color: "bg-[rgba(139,69,19,.1)] text-[#8b4513] border-[#e2ddd4]",            dot: "bg-[#8b4513]",   dropHighlight: "ring-2 ring-[#8b4513] bg-[rgba(139,69,19,.1)]" },
  { status: "testing",     label: "Test",            color: "bg-[rgba(192,57,43,.08)] text-[#c0392b] border-[#e2ddd4]",           dot: "bg-[#c0392b]",   dropHighlight: "ring-2 ring-[#c0392b] bg-[rgba(192,57,43,.08)]" },
  { status: "done",        label: "Fertig",          color: "bg-[rgba(45,106,79,.1)] text-[#2d6a4f] border-[#e2ddd4]",            dot: "bg-[#2d6a4f]",   dropHighlight: "ring-2 ring-[#2d6a4f] bg-[rgba(45,106,79,.1)]" },
  { status: "archived",    label: "Archiviert",      color: "bg-[#f7f4ee] text-[#a09080] border-[#e2ddd4]",                       dot: "bg-[#cec8bc]",   dropHighlight: "ring-2 ring-[#cec8bc] bg-[#f7f4ee]" },
];

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low:      "bg-[#f7f4ee] text-[#a09080]",
  medium:   "bg-[rgba(30,58,95,.06)] text-[#1e3a5f]",
  high:     "bg-[rgba(139,69,19,.1)] text-[#8b4513]",
  critical: "bg-[rgba(192,57,43,.08)] text-[#c0392b]",
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
      className={`bg-[#faf9f6] rounded-sm border p-3.5 transition-all cursor-grab active:cursor-grabbing select-none ${
        dragging ? "opacity-40 scale-95" : ""
      } ${lowScore ? "border-[#8b4513] hover:border-[#8b4513]" : "border-[#e2ddd4] hover:border-[rgba(192,57,43,.3)]"}`}
    >
      <Link
        href={`/${org}/stories/${story.id}`}
        className="block text-sm font-semibold text-[#1c1810] hover:text-[#c0392b] transition-colors line-clamp-2 mb-2.5 leading-snug"
        onClick={(e) => e.stopPropagation()}
        draggable={false}
      >
        {story.title}
      </Link>

      {story.description && (
        <p className="text-xs text-[#a09080] line-clamp-2 mb-2.5 leading-relaxed">{story.description}</p>
      )}

      <div className="flex flex-wrap items-center gap-1">
        <span className={`px-1.5 py-0.5 rounded-sm text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
          {PRIORITY_LABELS[story.priority]}
        </span>
        {story.story_points !== null && (
          <span className="px-1.5 py-0.5 rounded-sm bg-[#f7f4ee] text-[#a09080] text-xs font-medium">
            {story.story_points} SP
          </span>
        )}
        {score !== null && (
          <span className={`px-1.5 py-0.5 rounded-sm text-xs font-medium flex items-center gap-0.5 ${
            score >= 80 ? "bg-[rgba(45,106,79,.1)] text-[#2d6a4f]" :
            score >= 50 ? "bg-[rgba(139,69,19,.1)] text-[#8b4513]" :
            "bg-[rgba(192,57,43,.08)] text-[#c0392b]"
          }`}>
            {score < 80 && <AlertTriangle size={9} />}
            {score}
          </span>
        )}
        {story.dor_passed && (
          <span className="px-1.5 py-0.5 rounded-sm bg-[rgba(45,106,79,.1)] text-[#2d6a4f] text-xs font-medium">✓ DoR</span>
        )}
        {story.is_split && (
          <span className="px-1.5 py-0.5 rounded-sm bg-[rgba(139,69,19,.1)] text-[#8b4513] text-xs font-medium flex items-center gap-0.5">
            <GitBranch size={10} />
            Aufgeteilt
          </span>
        )}
      </div>
    </div>
  );
}

export default function StoriesBoardPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
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
          <h1 className="text-2xl font-bold text-[#1c1810]">User Stories</h1>
          {total > 0 && (
            <p className="text-[#a09080] mt-0.5 text-sm">{total} {total === 1 ? "Story" : "Stories"}</p>
          )}
        </div>
        <Link
          href={`/${resolvedParams.org}/stories/new`}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#5a3a7a] hover:bg-[#a93226] text-white rounded-sm text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Neue Story
        </Link>
      </div>

      {/* View tabs */}
      <div className="flex gap-1 border-b border-[#e2ddd4] shrink-0 overflow-x-auto">
        <Link
          href={`/${resolvedParams.org}/stories/list`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"
        >
          <LayoutList size={15} />
          Liste
        </Link>
        <span className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-[#c0392b] text-[#c0392b] whitespace-nowrap">
          <Columns size={15} />
          Board
        </span>
        <Link
          href={`/${resolvedParams.org}/stories/features/board`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"
        >
          <Layers size={15} />
          Features
        </Link>
        <Link
          href={`/${resolvedParams.org}/stories/epics/board`}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 border-transparent text-[#a09080] hover:text-[#5a5040] transition-colors whitespace-nowrap"
        >
          <GitBranch size={15} />
          Epics
        </Link>
      </div>

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

      {!isLoading && !error && stories && stories.length === 0 && (
        <div className="text-center py-16 bg-[#faf9f6] rounded-sm border border-[#e2ddd4]">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-[#5a5040] mb-2">Noch keine User Stories</h3>
          <p className="text-[#a09080] mb-6 text-sm">Erstelle deine erste User Story.</p>
          <Link
            href={`/${resolvedParams.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#5a3a7a] hover:bg-[#a93226] text-white rounded-sm text-sm font-medium transition-colors"
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
                <div className={`flex items-center justify-between px-3 py-2.5 rounded-t-sm border-x border-t ${col.color}`}>
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
                  className={`flex-1 rounded-b-sm border border-[#e2ddd4] p-2 space-y-2 min-h-[120px] transition-all ${
                    isOver ? col.dropHighlight : "bg-[#faf9f6]"
                  }`}
                >
                  {isOver && dragId && (
                    <div className="border-2 border-dashed border-current rounded-sm h-12 opacity-40" />
                  )}
                  {colStories.length === 0 && !isOver && (
                    <p className="text-xs text-[#a09080] text-center py-8">Keine Stories</p>
                  )}
                  {colStories.map((story) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      org={resolvedParams.org}
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
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-[#1c1810] text-white px-3 py-1.5 rounded-full pointer-events-none z-50">
          Story in eine andere Spalte ziehen
        </p>
      )}

      {blockedMsg && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 text-xs bg-[#c0392b] text-white px-4 py-2 rounded-full pointer-events-none z-50">
          <AlertTriangle size={13} />
          {blockedMsg}
        </div>
      )}
    </div>
  );
}
