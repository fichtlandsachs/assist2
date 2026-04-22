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

const LEVEL_STYLES = [
  { label: "Capability",  border: "border-[var(--navy,#2d3a8c)]",           bg: "bg-[rgba(45,58,140,.04)]",  text: "text-[var(--navy,#2d3a8c)]"  },
  { label: "Level 1",    border: "border-[var(--accent-orange,#f97316)]",   bg: "bg-[rgba(249,115,22,.04)]", text: "text-[var(--accent-orange,#f97316)]" },
  { label: "Level 2",    border: "border-[var(--green,#527b5e)]",           bg: "bg-[rgba(82,123,94,.04)]",  text: "text-[var(--green,#527b5e)]"  },
  { label: "Level 3",    border: "border-[var(--accent-orange,#f97316)]",   bg: "bg-[rgba(249,115,22,.10)]", text: "text-[var(--accent-orange,#f97316)]" },
];

function CapabilityHierarchy({ path, onRemove }: { path: string; onRemove: () => void }) {
  const parts = path.split(" › ");
  return (
    <div className="relative">
      {parts.map((part, i) => {
        const style = LEVEL_STYLES[Math.min(i, LEVEL_STYLES.length - 1)];
        const isLeaf = i === parts.length - 1;
        return (
          <div
            key={i}
            className={`border-2 rounded-lg p-2.5 ${style.border} ${style.bg}`}
            style={{ marginLeft: i * 12, marginTop: i === 0 ? 0 : 6 }}
          >
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`text-[10px] font-semibold uppercase tracking-wide shrink-0 ${style.text}`}>
                  {style.label}
                </span>
                <span className={`text-sm font-medium text-[var(--ink)] truncate ${isLeaf ? "font-semibold" : ""}`}>
                  {part}
                </span>
                {isLeaf && (
                  <span className="shrink-0 flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full bg-[var(--accent-orange,#f97316)] text-white font-semibold">
                    <MapPin size={9} />
                    Zugewiesen
                  </span>
                )}
              </div>
              {isLeaf && (
                <button
                  onClick={onRemove}
                  className="shrink-0 text-[var(--ink-faint)] hover:text-rose-500 transition-colors"
                  aria-label="Zuweisung entfernen"
                >
                  <X size={13} />
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
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
      await mutate(null, false);
      await apiRequest(`/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`, {
        method: "DELETE",
      });
    } catch {
      await mutate();
    }
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
        <button
          onClick={() => setChatOpen((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:border-[var(--btn-primary)] hover:text-[var(--btn-primary)] transition-colors"
        >
          {chatOpen ? (
            <X size={12} />
          ) : (
            <>
              <MessageSquare size={12} />
              {assignment ? "Ändern" : "Via Chat zuweisen"}
            </>
          )}
        </button>
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
          <CapabilityHierarchy path={assignment.node_path} onRemove={handleRemove} />
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
            />
          </div>
        )}
      </div>
    </div>
  );
}
