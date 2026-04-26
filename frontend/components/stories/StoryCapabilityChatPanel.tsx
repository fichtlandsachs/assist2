"use client";

import { MapPin } from "lucide-react";
import { apiRequest } from "@/lib/api/client";
import { StoryAssistantPanel } from "./StoryAssistantPanel";
import type { UserStory } from "@/types";

interface CapabilityProposalItem {
  node_id: string;
  path: string;
}

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
  onAssigned: () => void;
}

export function StoryCapabilityChatPanel({ storyId, orgId, story, onAssigned }: Props) {
  const handleAccept = async (item: unknown) => {
    const proposal = item as CapabilityProposalItem;
    await apiRequest(`/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`, {
      method: "PATCH",
      body: JSON.stringify({ node_id: proposal.node_id }),
    });
    // Clear the proposal from the DB session so it doesn't reappear when the chat is reopened.
    // (The local setSession call in StoryAssistantPanel may not run if onAssigned() closes the
    // chat panel before the Promise chain completes.)
    await apiRequest(`/api/v1/stories/${storyId}/assistant/capability/dismiss`, {
      method: "POST",
      body: JSON.stringify({ org_id: orgId }),
    }).catch(() => {});
    onAssigned();
  };

  return (
    <StoryAssistantPanel
      storyId={storyId}
      orgId={orgId}
      story={story}
      sessionType="capability"
      panelTitle="BCM-Assistent"
      emptyTitle="Capability via Chat ermitteln"
      emptyDesc="Beschreibe kurz, was diese Story macht — der Assistent schlägt die passende Capability vor."
      startButtonLabel="Chat starten"
      consolidateMessage="Bitte mach jetzt einen konkreten Vorschlag für die passende Capability und schließe mit dem Vorschlagsblock ab."
      proposalRenderer={{
        renderItem: (item) => {
          const p = item as CapabilityProposalItem;
          return (
            <div className="flex items-center gap-1.5">
              <MapPin size={12} className="text-[var(--accent-orange)] shrink-0" />
              <span className="font-medium">{p.path}</span>
            </div>
          );
        },
        emptyLabel: "",
      }}
      onProposalItemAdd={handleAccept}
    />
  );
}
