"use client";

import { BookOpen } from "lucide-react";
import { PriorityBadge, StoryPointsBadge } from "@/components/ui/badge";
import type { Feature } from "@/types";

export interface FeatureCardProps {
  feature: Feature;
  dragging?: boolean;
  onDragStart?: (id: string) => void;
  onDragEnd?: () => void;
}

/**
 * Feature card for Kanban board view.
 *
 * Extracted from features/board/page.tsx. Shares the same card anatomy as
 * StoryCard — identical base styling, different data fields (story_title
 * instead of quality_score / DoR).
 */
export function FeatureCard({
  feature,
  dragging = false,
  onDragStart,
  onDragEnd,
}: FeatureCardProps) {
  return (
    <div
      draggable
      onDragStart={(e) => {
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData("text/plain", feature.id);
        onDragStart?.(feature.id);
      }}
      onDragEnd={onDragEnd}
      className={`bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-3.5 hover:border-[rgba(var(--accent-red-rgb),.3)] transition-all cursor-grab active:cursor-grabbing select-none ${
        dragging ? "opacity-40 scale-95" : ""
      }`}
    >
      <p className="text-sm font-semibold text-[var(--ink)] line-clamp-2 mb-2.5 leading-snug">
        {feature.title}
      </p>

      {feature.description && (
        <p className="text-xs text-[var(--ink-faint)] line-clamp-2 mb-2.5 leading-relaxed">
          {feature.description}
        </p>
      )}

      <div className="flex items-center justify-between gap-2 mt-1 pt-2 border-t border-[var(--paper-rule)]">
        {feature.story_title ? (
          <span className="flex items-center gap-1 text-[var(--ink-faint)] [font-family:var(--font-mono)] text-[7px] uppercase tracking-[.06em] truncate min-w-0">
            <BookOpen size={9} className="shrink-0" />
            {feature.story_title}
          </span>
        ) : (
          <span />
        )}
        <div className="flex items-center gap-1 shrink-0">
          <PriorityBadge priority={feature.priority} />
          {feature.story_points !== null && (
            <StoryPointsBadge points={feature.story_points} />
          )}
        </div>
      </div>
    </div>
  );
}
