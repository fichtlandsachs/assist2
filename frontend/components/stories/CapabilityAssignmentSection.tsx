"use client";

import { useState } from "react";
import useSWR from "swr";
import { MapPin, X, MessageSquare } from "lucide-react";
import { fetcher, apiRequest } from "@/lib/api/client";
import { StoryCapabilityChatPanel } from "./StoryCapabilityChatPanel";
import type { UserStory } from "@/types";

interface CapabilityAssignment {
  assignment_id: string;
  node_id: string;
  node_path: string;
}

interface Props {
  storyId: string;
  orgId: string;
  story: UserStory;
}

export function CapabilityAssignmentSection({ storyId, orgId, story }: Props) {
  const [chatOpen, setChatOpen] = useState(false);

  const { data: assignment, mutate, isLoading } = useSWR<CapabilityAssignment | null>(
    `/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  const handleRemove = async () => {
    try {
      await apiRequest(`/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`, {
        method: "DELETE",
      });
      await mutate(null, false);
    } catch { /* ignore */ }
  };

  const handleAssigned = async () => {
    await mutate();
    setChatOpen(false);
  };

  return (
    <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-[var(--paper-rule)]">
        <div className="flex items-center gap-2">
          <MapPin size={15} className="text-[var(--ink-mid)]" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--ink)]">Business Capability</h3>
            <p className="text-xs text-[var(--ink-faint)] mt-0.5">
              Zuordnung zur Business Capability Map
            </p>
          </div>
        </div>
        {!chatOpen && (
          <button
            onClick={() => setChatOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:border-[var(--btn-primary)] hover:text-[var(--btn-primary)] transition-colors"
          >
            <MessageSquare size={12} />
            {assignment ? "Ändern" : "Via Chat zuweisen"}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="px-4 sm:px-6 py-4 space-y-4">
        {/* Current assignment */}
        {isLoading ? (
          <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)]">
            <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            Lade…
          </div>
        ) : assignment ? (
          <div className="flex items-center justify-between gap-2 p-3 rounded-lg bg-[var(--paper-warm)] border border-[var(--paper-rule2)]">
            <div className="flex items-center gap-2 min-w-0">
              <MapPin size={13} className="text-[var(--accent-orange)] shrink-0" />
              <span className="text-sm font-medium text-[var(--ink)] truncate">
                {assignment.node_path}
              </span>
            </div>
            <button
              onClick={handleRemove}
              className="shrink-0 text-[var(--ink-faint)] hover:text-rose-500 transition-colors"
              aria-label="Zuweisung entfernen"
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-faint)]">
            Noch keine Capability zugewiesen. Nutze den Chat, um die passende Capability zu ermitteln.
          </p>
        )}

        {/* Chat panel */}
        {chatOpen && (
          <div className="mt-2">
            <StoryCapabilityChatPanel
              storyId={storyId}
              orgId={orgId}
              story={story}
              onAssigned={handleAssigned}
              onClose={() => setChatOpen(false)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
