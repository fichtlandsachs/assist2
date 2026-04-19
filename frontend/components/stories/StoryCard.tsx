"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, GitBranch, Star } from "lucide-react";
import { PriorityBadge, StoryPointsBadge, QualityScoreBadge, DoRBadge } from "@/components/ui/badge";
import type { UserStory } from "@/types";

const JIRA_STATUS_COLORS: Record<string, string> = {
  "To Do": "bg-gray-100 text-gray-600",
  "In Progress": "bg-blue-100 text-blue-700",
  "In Review": "bg-yellow-100 text-yellow-700",
  "Done": "bg-green-100 text-green-700",
  "Blocked": "bg-red-100 text-red-700",
};

function JiraBadge({
  ticketKey,
  title,
  jiraStatus,
  jiraTicketUrl,
}: {
  ticketKey: string;
  title: string;
  jiraStatus: string | null;
  jiraTicketUrl: string | null;
}) {
  const colorClass = jiraStatus
    ? (JIRA_STATUS_COLORS[jiraStatus] ?? "bg-gray-100 text-gray-500")
    : "bg-gray-100 text-gray-500";

  const label = `${title} (${ticketKey})`;

  return (
    <div className="flex items-center gap-1.5 mt-1">
      {jiraTicketUrl ? (
        <a
          href={jiraTicketUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-blue-600 hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          {label}
        </a>
      ) : (
        <span className="text-xs text-gray-500">{label}</span>
      )}
      {jiraStatus && (
        <span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${colorClass}`}>
          {jiraStatus}
        </span>
      )}
    </div>
  );
}

function LinkedIssueChips({ linkedKeys }: { linkedKeys: string[] }) {
  if (linkedKeys.length === 0) return null;
  const visible = linkedKeys.slice(0, 3);
  const rest = linkedKeys.length - visible.length;
  return (
    <div className="flex items-center gap-1 mt-1 flex-wrap">
      <span className="text-xs text-gray-400">↔</span>
      {visible.map((key) => (
        <span
          key={key}
          className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono"
        >
          {key}
        </span>
      ))}
      {rest > 0 && <span className="text-xs text-gray-400">+{rest}</span>}
    </div>
  );
}

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
      className={`relative bg-[var(--card)] rounded-sm border p-3.5 transition-all cursor-grab active:cursor-grabbing select-none group/card ${
        dragging ? "opacity-40 scale-95" : ""
      } ${
        lowScore
          ? "border-[var(--brown)] hover:border-[var(--brown)]"
          : "border-[var(--paper-rule)] hover:border-[rgba(var(--accent-red-rgb),.3)]"
      }`}
    >
      {/* Validate button — top right, always visible */}
      {onValidate && (
        <button
          type="button"
          onClick={handleValidate}
          disabled={validating}
          className="absolute top-[7px] right-[7px] flex items-center gap-[3px] px-1.5 py-[3px] bg-[rgba(82,107,94,.08)] border-[0.5px] border-[rgba(82,107,94,.3)] text-[var(--green)] rounded-sm [font-family:var(--font-mono)] text-[7px] uppercase tracking-[.06em] transition-all hover:bg-[var(--green)] hover:text-white disabled:pointer-events-none"
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

      {story.jira_ticket_key && (
        <JiraBadge
          ticketKey={story.jira_ticket_key}
          title={story.title}
          jiraStatus={story.jira_status ?? null}
          jiraTicketUrl={story.jira_ticket_url ?? null}
        />
      )}
      {story.jira_linked_issue_keys &&
        (() => {
          try {
            const parsed = JSON.parse(story.jira_linked_issue_keys);
            if (!Array.isArray(parsed)) return null;
            const keys = parsed.filter((k): k is string => typeof k === "string");
            return <LinkedIssueChips linkedKeys={keys} />;
          } catch {
            return null;
          }
        })()}
      {story.jira_ticket_key && story.jira_status && story.status &&
        (() => {
          const jiraDone = story.jira_status.toLowerCase() === "done";
          const localDone = story.status === "done" || story.status === "archived";
          if (jiraDone && !localDone) {
            return (
              <div
                className="flex items-center gap-1 mt-1 text-xs text-amber-600"
                title={`In Jira als "${story.jira_status}" — im Workspace noch "${story.status}"`}
              >
                <AlertTriangle className="w-3 h-3" />
                <span>Jira: {story.jira_status}</span>
              </div>
            );
          }
          return null;
        })()}

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
        <QualityScoreBadge score={score} />
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
