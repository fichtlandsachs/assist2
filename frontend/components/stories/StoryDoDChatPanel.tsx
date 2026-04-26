"use client";

import type { UserStory, DoDProposalItem } from "@/types";
import { useT } from "@/lib/i18n/context";
import { StoryAssistantPanel } from "./StoryAssistantPanel";

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  onAddItem: (text: string) => void;
}

export function StoryDoDChatPanel({ storyId, orgId, story, onAddItem }: Props) {
  const { t } = useT();

  return (
    <StoryAssistantPanel
      storyId={storyId}
      orgId={orgId}
      story={story}
      sessionType="dod"
      panelTitle={t("assistant_dod_title")}
      emptyTitle={t("assistant_dod_empty_title")}
      emptyDesc={t("assistant_dod_empty_desc")}
      startButtonLabel={t("refinement_start_button")}
      consolidateMessage="Erstelle bitte jetzt eine vollständige Liste von DoD-Kriterien für diese Story basierend auf unserem Gespräch."
      proposalRenderer={{
        renderItem: (item) => {
          const i = item as DoDProposalItem;
          return <span className="whitespace-pre-wrap">{i.text}</span>;
        },
        emptyLabel: "",
      }}
      onProposalItemAdd={async (item) => onAddItem((item as DoDProposalItem).text)}
    />
  );
}
