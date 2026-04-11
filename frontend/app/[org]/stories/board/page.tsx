"use client";

import { use, useState, useRef } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus } from "@/types";
import Link from "next/link";
import { Plus, AlertTriangle } from "lucide-react";
import { StoryCard } from "@/components/stories/StoryCard";
import { ProjectSelector } from "@/components/stories/ProjectSelector";
import { useSearchParams } from "next/navigation";
import { useT } from "@/lib/i18n/context";

type ColumnDef = { status: StoryStatus; label: string; color: string; dot: string; dropHighlight: string };

function getQualityScore(story: UserStory): number | null {
  return story.quality_score ?? null;
}

export default function StoriesBoardPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const searchParams = useSearchParams();
  const [dragId, setDragId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<StoryStatus | null>(null);
  const [blockedMsg, setBlockedMsg] = useState<string | null>(null);
  const [projectFilter, setProjectFilter] = useState<string | null>(
    searchParams.get("project_id") ?? null
  );
  const dragCounters = useRef<Record<string, number>>({});
  const { t } = useT();

  const COLUMNS: ColumnDef[] = [
    { status: "draft",       label: t("story_status_draft"),       color: "bg-[var(--paper-warm)] text-[var(--ink-mid)] border-[var(--paper-rule)]",                        dot: "bg-[var(--ink-faintest)]",   dropHighlight: "ring-2 ring-[var(--ink-faint)] bg-[var(--paper-warm)]" },
    { status: "in_review",   label: t("story_status_in_review"),   color: "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)] border-[rgba(var(--accent-red-rgb),.3)]", dot: "bg-[var(--btn-primary)]",  dropHighlight: "ring-2 ring-[var(--btn-primary)] bg-[rgba(var(--btn-primary-rgb),.08)]" },
    { status: "ready",       label: t("story_status_ready"),       color: "bg-[rgba(74,85,104,.06)] text-[var(--navy)] border-[var(--paper-rule)]",            dot: "bg-[var(--navy)]",   dropHighlight: "ring-2 ring-[var(--navy)] bg-[rgba(74,85,104,.06)]" },
    { status: "in_progress", label: t("story_status_in_progress"), color: "bg-[rgba(122,100,80,.1)] text-[var(--brown)] border-[var(--paper-rule)]",            dot: "bg-[var(--brown)]",   dropHighlight: "ring-2 ring-[var(--brown)] bg-[rgba(122,100,80,.1)]" },
    { status: "testing",     label: t("story_status_testing"),     color: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] border-[var(--paper-rule)]",           dot: "bg-[var(--accent-red)]",   dropHighlight: "ring-2 ring-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)]" },
    { status: "done",        label: t("story_status_done"),        color: "bg-[rgba(82,107,94,.1)] text-[var(--green)] border-[var(--paper-rule)]",            dot: "bg-[var(--green)]",   dropHighlight: "ring-2 ring-[var(--green)] bg-[rgba(82,107,94,.1)]" },
    { status: "archived",    label: t("story_status_archived"),    color: "bg-[var(--paper-warm)] text-[var(--ink-faint)] border-[var(--paper-rule)]",                       dot: "bg-[var(--ink-faintest)]",   dropHighlight: "ring-2 ring-[var(--ink-faintest)] bg-[var(--paper-warm)]" },
  ];

  const { data: stories, isLoading, error, mutate } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}${projectFilter ? `&project_id=${projectFilter}` : ""}` : null,
    fetcher
  );

  async function handleValidate(storyId: string) {
    try {
      const updated = await apiRequest<UserStory>(
        `/api/v1/user-stories/${storyId}/validate`,
        { method: "POST" }
      );
      mutate((prev) => prev?.map((s) => s.id === storyId ? { ...s, quality_score: updated.quality_score } : s), false);
    } finally {
      await mutate();
    }
  }

  async function handleStatusChange(storyId: string, newStatus: StoryStatus) {
    const story = stories?.find((s) => s.id === storyId);

    // Quality gate: block advancement to ready/in_progress/testing/done if score < 80
    const GATED = new Set(["ready", "in_progress", "testing", "done"]);
    if (GATED.has(newStatus) && story) {
      const score = getQualityScore(story);
      if (score !== null && score < 80) {
        setBlockedMsg(t("story_board_quality_blocked"));
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
          <h1 className="text-2xl font-bold text-[var(--ink)]">{t("story_board_title")}</h1>
          {total > 0 && (
            <p className="text-[var(--ink-faint)] mt-0.5 text-sm">{total} {total === 1 ? "Story" : "Stories"}</p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {org && (
            <div className="w-44">
              <ProjectSelector orgId={org.id} value={projectFilter} onChange={setProjectFilter} label="" />
            </div>
          )}
          <Link
            href={`/${resolvedParams.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            {t("nav_new_story")}
          </Link>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
        </div>
      )}

      {error && (
        <div className="bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--paper-rule)] rounded-sm p-4 text-[var(--accent-red)] text-sm">
          {t("error_load")}
        </div>
      )}

      {!isLoading && !error && stories && stories.length === 0 && (
        <div className="text-center py-16 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-[var(--ink-mid)] mb-2">{t("story_board_empty")}</h3>
          <p className="text-[var(--ink-faint)] mb-6 text-sm">Erstelle deine erste User Story.</p>
          <Link
            href={`/${resolvedParams.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            {t("nav_new_story")}
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
                  className={`flex-1 rounded-b-sm border border-[var(--paper-rule)] p-2 space-y-2 min-h-[120px] transition-all ${
                    isOver ? col.dropHighlight : "bg-[var(--card)]"
                  }`}
                >
                  {isOver && dragId && (
                    <div className="border-2 border-dashed border-current rounded-sm h-12 opacity-40" />
                  )}
                  {colStories.length === 0 && !isOver && (
                    <p className="text-xs text-[var(--ink-faint)] text-center py-8">{t("story_board_empty")}</p>
                  )}
                  {colStories.map((story) => (
                    <StoryCard
                      key={story.id}
                      story={story}
                      org={resolvedParams.org}
                      dragging={dragId === story.id}
                      onDragStart={(id) => { setDragId(id); dragCounters.current = {}; }}
                      onDragEnd={() => { setDragId(null); setDragOverStatus(null); dragCounters.current = {}; }}
                      onValidate={handleValidate}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {dragId && !blockedMsg && (
        <p className="fixed bottom-4 left-1/2 -translate-x-1/2 text-xs bg-[var(--ink)] text-white px-3 py-1.5 rounded-full pointer-events-none z-50">
          Story in eine andere Spalte ziehen
        </p>
      )}

      {blockedMsg && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 text-xs bg-[var(--accent-red)] text-white px-4 py-2 rounded-full pointer-events-none z-50">
          <AlertTriangle size={13} />
          {blockedMsg}
        </div>
      )}
    </div>
  );
}
