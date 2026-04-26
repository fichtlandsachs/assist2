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

interface TreeNode {
  id: string;
  title: string;
  node_type: string;
  children: TreeNode[];
}

function isOnAssignedPath(node: TreeNode, assignedId: string | null): boolean {
  if (!assignedId) return false;
  if (node.id === assignedId) return true;
  return node.children.some((c) => isOnAssignedPath(c, assignedId));
}

function Level3Item({
  node,
  assignedId,
  onRemove,
}: {
  node: TreeNode;
  assignedId: string | null;
  onRemove: () => void;
}) {
  const assigned = node.id === assignedId;
  return (
    <div
      className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-colors ${
        assigned
          ? "bg-[var(--accent-orange,#f97316)] text-white font-semibold"
          : "text-[var(--ink-mid)] hover:bg-[var(--paper-warm)]"
      }`}
    >
      {assigned && <MapPin size={9} className="shrink-0" />}
      <span className="truncate flex-1">{node.title}</span>
      {assigned && (
        <button
          onClick={onRemove}
          className="shrink-0 ml-0.5 opacity-80 hover:opacity-100 transition-opacity"
          aria-label="Zuweisung entfernen"
        >
          <X size={10} />
        </button>
      )}
    </div>
  );
}

function Level2Block({
  node,
  assignedId,
  onRemove,
}: {
  node: TreeNode;
  assignedId: string | null;
  onRemove: () => void;
}) {
  const onPath = isOnAssignedPath(node, assignedId);
  return (
    <div
      className={`rounded border px-2 py-1.5 ${
        onPath
          ? "border-[var(--green,#527b5e)] bg-[rgba(82,123,94,.06)]"
          : "border-[var(--paper-rule)] bg-[var(--paper-warm)]"
      }`}
    >
      <p className={`text-[10px] font-semibold uppercase tracking-wide mb-1 ${
        onPath ? "text-[var(--green,#527b5e)]" : "text-[var(--ink-faint)]"
      }`}>
        {node.title}
      </p>
      {node.children.length > 0 ? (
        <div className="space-y-0.5">
          {node.children.map((l3) => (
            <Level3Item key={l3.id} node={l3} assignedId={assignedId} onRemove={onRemove} />
          ))}
        </div>
      ) : (
        <p className="text-[10px] text-[var(--ink-faintest)] italic">—</p>
      )}
    </div>
  );
}

function Level1Card({
  node,
  assignedId,
  onRemove,
}: {
  node: TreeNode;
  assignedId: string | null;
  onRemove: () => void;
}) {
  const onPath = isOnAssignedPath(node, assignedId);
  return (
    <div
      className={`rounded-lg border-2 p-3 flex flex-col gap-2 min-w-0 ${
        onPath
          ? "border-[var(--accent-orange,#f97316)] bg-[rgba(249,115,22,.04)]"
          : "border-[var(--paper-rule)] bg-[var(--card)]"
      }`}
    >
      <p className={`text-xs font-bold truncate ${
        onPath ? "text-[var(--accent-orange,#f97316)]" : "text-[var(--ink-mid)]"
      }`}>
        {node.title}
      </p>
      <div className="space-y-1.5">
        {node.children.map((l2) => (
          <Level2Block key={l2.id} node={l2} assignedId={assignedId} onRemove={onRemove} />
        ))}
        {node.children.length === 0 && (
          <p className="text-[10px] text-[var(--ink-faintest)] italic">Keine Unterprozesse</p>
        )}
      </div>
    </div>
  );
}

function CapabilitySection({
  node,
  assignedId,
  onRemove,
}: {
  node: TreeNode;
  assignedId: string | null;
  onRemove: () => void;
}) {
  const onPath = isOnAssignedPath(node, assignedId);
  return (
    <div>
      <div className={`flex items-center gap-1.5 mb-2 pb-1.5 border-b-2 ${
        onPath ? "border-[var(--navy,#2d3a8c)]" : "border-[var(--paper-rule)]"
      }`}>
        <span className={`text-[10px] font-bold uppercase tracking-widest ${
          onPath ? "text-[var(--navy,#2d3a8c)]" : "text-[var(--ink-faint)]"
        }`}>
          Capability
        </span>
        <span className={`text-sm font-semibold ${
          onPath ? "text-[var(--navy,#2d3a8c)]" : "text-[var(--ink-mid)]"
        }`}>
          {node.title}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
        {node.children.map((l1) => (
          <Level1Card key={l1.id} node={l1} assignedId={assignedId} onRemove={onRemove} />
        ))}
        {node.children.length === 0 && (
          <p className="text-xs text-[var(--ink-faint)] col-span-full italic">Keine Level-1-Prozesse definiert.</p>
        )}
      </div>
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

  const { data: tree, isLoading: treeLoading } = useSWR<TreeNode[]>(
    `/api/v1/capabilities/orgs/${orgId}/tree`,
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
              {assignment
                ? assignment.node_path
                : "Noch keine Capability zugewiesen"}
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

      {/* BCM Overview */}
      <div className="px-4 sm:px-6 py-4 space-y-6">
        {isLoading || treeLoading ? (
          <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)]">
            <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
            Lade…
          </div>
        ) : !tree || tree.length === 0 ? (
          <p className="text-sm text-[var(--ink-faint)]">Noch keine Capability Map eingerichtet.</p>
        ) : (
          tree.map((cap) => (
            <CapabilitySection
              key={cap.id}
              node={cap}
              assignedId={assignment?.node_id ?? null}
              onRemove={handleRemove}
            />
          ))
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
