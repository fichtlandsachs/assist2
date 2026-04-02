"use client";

import { useState } from "react";
import Link from "next/link";
import { GitBranch, Star } from "lucide-react";
import { PriorityBadge, StoryPointsBadge, QualityScoreBadge, DoRBadge } from "@/components/ui/badge";
import type { UserStory } from "@/types";

export interface StoryCardProps {
  story: UserStory;
  org: string;
  dragging?: boolean;
  onDragStart?: (id: string) => void;
  onDragEnd?: () => void;
  /**
   * Called when the user triggers quality re-validation.
   * The board page is responsible for the API call + SWR mutate.
   * Receives the story id; should resolve once the score is refreshed.
   */
  onValidate?: (id: string) => Promise<void>;
}

/**
 * Story card for Kanban board view.
 *
 * Extracted from stories/board/page.tsx. Uses shared badge components
 * (PriorityBadge, QualityScoreBadge, StoryPointsBadge, DoRBadge) instead
 * of inline Tailwind colour strings.
 */
export function StoryCard({
  story,
  org,
  dragging = false,
  onDragStart,
  onDragEnd,
  onValidate,
}: StoryCardProps) {
  const score = story.quality_score ?? null;
  const lowScore = score !== null && score < 80;
  const [validating, setValidating] = useState(false);

  async function handleValidate(e: React.MouseEvent) {
    e.stopPropagation();
    if (!onValidate || validating) return;
    setValidating(true);
    try {
      await onValidate(story.id);
    } finally {
      setValidating(false);
    }
  }

  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", story.id);
        onDragStart?.(story.id);
      }}
      onDragEnd={onDragEnd}
      className={`relative bg-[var(--paper)] rounded-sm border p-3.5 transition-all cursor-grab active:cursor-grabbing select-none group/card ${
        dragging ? "opacity-40 scale-95" : ""
      } ${
        lowScore
          ? "border-[var(--brown)] hover:border-[var(--brown)]"
          : "border-[var(--paper-rule)] hover:border-[rgba(var(--accent-red-rgb),.3)]"
      }`}
    >
      {/* Validate button — top right, visible on hover */}
      {onValidate && (
        <button
          type="button"
          onClick={handleValidate}
          disabled={validating}
          className="absolute top-[7px] right-[7px] flex items-center gap-[3px] px-1.5 py-[3px] bg-[rgba(82,107,94,.08)] border-[0.5px] border-[rgba(82,107,94,.3)] text-[var(--green)] rounded-sm [font-family:var(--font-mono)] text-[7px] uppercase tracking-[.06em] opacity-0 group-hover/card:opacity-100 transition-all hover:bg-[var(--green)] hover:text-white disabled:pointer-events-none"
        >
          {validating ? (
            <span className="inline-block animate-spin w-[9px] h-[9px] rounded-full border border-current border-t-transparent" />
          ) : (
            <Star size={9} />
          )}
          {validating ? "Prüfe…" : "Prüfen"}
        </button>
      )}

      <Link
        href={`/${org}/stories/${story.id}`}
        className="block text-sm font-semibold text-[var(--ink)] hover:text-[var(--accent-red)] transition-colors line-clamp-2 mb-2.5 leading-snug"
        onClick={(e) => e.stopPropagation()}
        draggable={false}
      >
        {story.title}
      </Link>

      {story.description && (
        <p className="text-xs text-[var(--ink-faint)] line-clamp-2 mb-2.5 leading-relaxed">
          {story.description}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-1 mt-1 pt-2 border-t border-[var(--paper-rule)]">
        <PriorityBadge priority={story.priority} />
        {story.story_points !== null && (
          <StoryPointsBadge points={story.story_points} />
        )}
        {score !== null && <QualityScoreBadge score={score} />}
        {story.dor_passed && <DoRBadge />}
        {story.is_split && (
          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-[10px] border-[0.5px] bg-[rgba(122,100,80,.08)] text-[var(--brown)] border-[rgba(122,100,80,.3)] [font-family:var(--font-mono)] text-[7px] uppercase tracking-[.06em]">
            <GitBranch size={8} />
            Aufgeteilt
          </span>
        )}
      </div>
    </div>
  );
}
