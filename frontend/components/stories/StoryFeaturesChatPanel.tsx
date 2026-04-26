"use client";

import type { UserStory, FeaturesProposalItem } from "@/types";
import { useT } from "@/lib/i18n/context";
import { StoryAssistantPanel } from "./StoryAssistantPanel";

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  onAddFeature: (feature: FeaturesProposalItem) => void;
}

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-100 text-red-700",
  high: "bg-orange-100 text-orange-700",
  medium: "bg-yellow-100 text-yellow-700",
  low: "bg-gray-100 text-gray-600",
};

export function StoryFeaturesChatPanel({ storyId, orgId, story, onAddFeature }: Props) {
  const { t } = useT();

  return (
    <StoryAssistantPanel
      storyId={storyId}
      orgId={orgId}
      story={story}
      sessionType="features"
      panelTitle={t("assistant_features_title")}
      emptyTitle={t("assistant_features_empty_title")}
      emptyDesc={t("assistant_features_empty_desc")}
      startButtonLabel={t("refinement_start_button")}
      consolidateMessage="Erstelle bitte jetzt eine vollständige strukturierte Feature-Liste für diese Story basierend auf unserem Gespräch."
      proposalRenderer={{
        renderItem: (item) => {
          const f = item as FeaturesProposalItem;
          const priorityColor = PRIORITY_COLORS[f.priority] ?? PRIORITY_COLORS.medium;
          return (
            <div className="space-y-0.5">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="font-medium">{f.title}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${priorityColor}`}>
                  {f.priority}
                </span>
                {f.story_points != null && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-blue-100 text-blue-700 font-medium">
                    {f.story_points} SP
                  </span>
                )}
              </div>
              {f.description && (
                <p className="text-[var(--ink-faint)] line-clamp-2">{f.description}</p>
              )}
            </div>
          );
        },
        emptyLabel: "",
      }}
      onProposalItemAdd={async (item) => onAddFeature(item as FeaturesProposalItem)}
    />
  );
}
