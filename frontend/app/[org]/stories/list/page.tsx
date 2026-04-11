"use client";

import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { UserStory, StoryStatus, StoryPriority } from "@/types";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Plus, Trash2, AlertTriangle } from "lucide-react";
import { use, useState } from "react";
import { useT } from "@/lib/i18n/context";

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

const STATUS_COLORS: Record<StoryStatus, string> = {
  draft:       "bg-[var(--paper-warm)] text-[var(--ink-mid)]",
  in_review:   "bg-[rgba(var(--btn-primary-rgb),.08)] text-[var(--btn-primary)]",
  ready:       "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",
  in_progress: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",
  testing:     "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",
  done:        "bg-[rgba(82,107,94,.1)] text-[var(--green)]",
  archived:    "bg-[var(--paper-rule2)] text-[var(--ink-faint)]",
};

const PRIORITY_COLORS: Record<StoryPriority, string> = {
  low:      "text-[var(--ink-faint)]",
  medium:   "text-[var(--navy)]",
  high:     "text-[var(--brown)]",
  critical: "text-[var(--accent-red)]",
};

export default function StoriesListPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const router = useRouter();
  const [deleting, setDeleting] = useState<string | null>(null);
  const { t } = useT();

  const STATUS_LABELS: Record<StoryStatus, string> = {
    draft:       t("story_status_draft"),
    in_review:   t("story_status_in_review"),
    ready:       t("story_status_ready"),
    in_progress: t("story_status_in_progress"),
    testing:     t("story_status_testing"),
    done:        t("story_status_done"),
    archived:    t("story_status_archived"),
  };

  const PRIORITY_LABELS: Record<StoryPriority, string> = {
    low:      t("story_priority_low"),
    medium:   t("story_priority_medium"),
    high:     t("story_priority_high"),
    critical: t("story_priority_critical"),
  };

  const { data: stories, isLoading, error, mutate } = useSWR<UserStory[]>(
    org ? `/api/v1/user-stories?org_id=${org.id}` : null,
    fetcher
  );

  async function handleDelete(e: React.MouseEvent, storyId: string) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t("story_list_delete_confirm"))) return;
    setDeleting(storyId);
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}`, { method: "DELETE" });
      await mutate();
    } catch {
      alert(t("story_list_delete_error"));
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="space-y-6 min-w-0">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink)]">{t("story_list_title")}</h1>
          <p className="text-[var(--ink-faint)] mt-1">
            {stories ? `${stories.length} ${stories.length === 1 ? "Story" : "Stories"}` : ""}
          </p>
        </div>
        <Link
          href={`/${resolvedParams.org}/stories/new`}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          {t("nav_new_story")}
        </Link>
      </div>

      {/* Content */}
      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
        </div>
      )}

      {error && (
        <div className="bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--paper-rule)] rounded-sm p-4 text-[var(--accent-red)] text-sm">
          {t("story_list_error")}
        </div>
      )}

      {stories && stories.length === 0 && (
        <div className="text-center py-16 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
          <div className="text-4xl mb-4">📋</div>
          <h3 className="text-lg font-semibold text-[var(--ink-mid)] mb-2">{t("story_list_empty")}</h3>
          <p className="text-[var(--ink-faint)] mb-6 text-sm">
            {t("story_list_empty_msg")}
          </p>
          <Link
            href={`/${resolvedParams.org}/stories/new`}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--btn-primary)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            {t("story_list_create_first")}
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
                  <span className="text-xs text-[var(--ink-faint)]">{items.length}</span>
                </div>
                <div className="grid gap-2">
                  {items.map((story) => (
                    <Link
                      key={story.id}
                      href={`/${resolvedParams.org}/stories/${story.id}`}
                      className="block bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] p-5 hover:border-[rgba(var(--accent-red-rgb),.3)] transition-all group"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-2 flex-wrap">
                            <span className={`text-xs font-medium ${PRIORITY_COLORS[story.priority]}`}>
                              ● {PRIORITY_LABELS[story.priority]}
                            </span>
                            {story.story_points !== null && (
                              <span className="px-2 py-0.5 rounded-full bg-[var(--paper-warm)] text-[var(--ink-mid)] text-xs font-medium">
                                {story.story_points} SP
                              </span>
                            )}
                            {story.dor_passed && (
                              <span className="px-2 py-0.5 rounded-full bg-[rgba(82,107,94,.1)] text-[var(--green)] text-xs font-medium">
                                ✓ DoR
                              </span>
                            )}
                          </div>
                          <h3 className="font-semibold text-[var(--ink)] truncate group-hover:text-[var(--accent-red)] transition-colors">
                            {story.title}
                          </h3>
                          {story.description && (
                            <p className="text-[var(--ink-faint)] text-sm mt-1 line-clamp-2">{story.description}</p>
                          )}
                        </div>

                        {/* Right side: Quality score badge + delete */}
                        <div className="shrink-0 flex items-center gap-2">
                          {story.quality_score !== null && story.quality_score !== undefined && (
                            <span
                              title={`Quality-Score: ${story.quality_score}/100`}
                              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                                story.quality_score >= 75
                                  ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]"
                                  : story.quality_score >= 50
                                  ? "bg-[rgba(122,100,80,.1)] text-[var(--brown)]"
                                  : "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                              }`}
                            >
                              {story.quality_score < 50 && <AlertTriangle size={11} />}
                              {story.quality_score}
                            </span>
                          )}
                          <button
                            onClick={(e) => void handleDelete(e, story.id)}
                            disabled={deleting === story.id}
                            className="p-2 rounded-sm text-[var(--ink-faintest)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] transition-colors sm:opacity-0 sm:group-hover:opacity-100"
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
