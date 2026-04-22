"use client";

import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { CapabilityTreeNode, Control, ControlWithAssessment, NodeType } from "@/types";
import { MATURITY_CONFIG, EFFECTIVENESS_CONFIG } from "@/types";
import { ChevronRight, ShieldCheck, Layers, Pencil } from "lucide-react";
import { ControlEditor } from "./ControlEditor";

interface Props {
  orgId: string;
}

// ─── Styling per node_type ──────────────────────────────────────────────────

const NODE_TYPE_STYLE: Record<NodeType, { border: string; bg: string; label: string; titleSize: string }> = {
  capability: {
    border: "border-[#1e3a5f]",
    bg: "bg-[#1e3a5f]/5",
    label: "Capability",
    titleSize: "text-[13px] font-black",
  },
  level_1: {
    border: "border-orange-400",
    bg: "bg-orange-50/60",
    label: "L1",
    titleSize: "text-[12px] font-bold",
  },
  level_2: {
    border: "border-emerald-500",
    bg: "bg-emerald-50/50",
    label: "L2",
    titleSize: "text-[11px] font-semibold",
  },
  level_3: {
    border: "border-[var(--paper-rule)]",
    bg: "bg-[var(--card)]",
    label: "L3",
    titleSize: "text-[10px] font-medium",
  },
};

// ─── Right panel: controls for selected node ────────────────────────────────

function NodeControlsPanel({
  orgId,
  node,
  onEdit,
}: {
  orgId: string;
  node: CapabilityTreeNode;
  onEdit: (control: Control) => void;
}) {
  const { data, isLoading } = useSWR<ControlWithAssessment[]>(
    `/api/v1/capabilities/orgs/${orgId}/nodes/${node.id}/controls`,
    fetcher
  );

  const items = data ?? [];

  return (
    <div className="space-y-3">
      {/* Panel header */}
      <div className="flex items-start gap-2 pb-2 border-b border-[var(--paper-rule)]">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span
              className={`text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wide
                ${NODE_TYPE_STYLE[node.node_type].bg}
                ${NODE_TYPE_STYLE[node.node_type].border}
                border text-[var(--ink-mid)]`}
            >
              {NODE_TYPE_STYLE[node.node_type].label}
            </span>
            <h3 className="text-[13px] font-black text-[var(--ink)] truncate">{node.title}</h3>
          </div>
          {node.description && (
            <p className="text-[10px] text-[var(--ink-faint)] mt-0.5 leading-snug line-clamp-2">
              {node.description}
            </p>
          )}
        </div>
        {items.length > 0 && (
          <span className="flex-shrink-0 px-1.5 py-0.5 rounded-full bg-[var(--paper-warm)] text-[10px] font-bold text-[var(--ink-mid)]">
            {items.length}
          </span>
        )}
      </div>

      {/* Controls list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--ink)]" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-[11px] text-[var(--ink-faint)] italic py-4 text-center">
          Kein Control zugewiesen.
        </p>
      ) : (
        <div className="space-y-2">
          {items.map((item) => {
            const { control, assessment } = item;
            const isInherited = assessment.inherited_from_id !== null;
            const mat = MATURITY_CONFIG[assessment.maturity_level];
            const eff = EFFECTIVENESS_CONFIG[assessment.effectiveness] ?? EFFECTIVENESS_CONFIG["not_assessed"];
            const refs: string[] = control.framework_refs ?? [];
            return (
              <div
                key={`${control.id}-${item.applies_via_node_id}`}
                className="p-3 rounded-lg border border-[var(--paper-rule)] bg-[var(--card)] space-y-1"
              >
                {/* Title + badges */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-bold ${mat.bg} ${mat.color}`}
                  >
                    {assessment.maturity_level} · {mat.label}
                  </span>
                  <span className="flex-1 text-[12px] font-semibold text-[var(--ink)] truncate">
                    {control.title}
                  </span>
                  <span className={`flex items-center gap-1 text-[9px] font-medium ${eff.color}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${eff.dot}`} />
                    {eff.label}
                  </span>
                  <button
                    onClick={() => onEdit(control)}
                    className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[9px] font-medium text-[var(--ink-faint)] hover:text-[var(--ink)] hover:bg-[var(--paper-warm)] transition-colors"
                    title="Bearbeiten"
                  >
                    <Pencil size={9} />
                    Bearbeiten
                  </button>
                </div>

                {/* Framework refs */}
                {refs.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {refs.map((ref) => (
                      <span
                        key={ref}
                        className="px-1 py-0.5 rounded bg-[var(--paper-warm)] text-[8px] font-medium text-[var(--ink-faint)]"
                      >
                        {ref}
                      </span>
                    ))}
                  </div>
                )}

                {/* Gap / coverage note */}
                {(assessment.coverage_note || assessment.gap_description) && (
                  <p className="text-[10px] text-[var(--ink-mid)] leading-snug">
                    <span className="font-semibold text-[var(--ink-faint)]">Gap: </span>
                    {assessment.coverage_note || assessment.gap_description}
                  </p>
                )}

                {/* Inherited note */}
                {isInherited && (
                  <p className="text-[9px] text-[var(--ink-faint)] italic">
                    (aus übergeordneter Capability)
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Compact tree node ───────────────────────────────────────────────────────

function TreeNodeItem({
  node,
  depth,
  selectedNodeId,
  onSelect,
}: {
  node: CapabilityTreeNode;
  depth: number;
  selectedNodeId: string | null;
  onSelect: (id: string, node: CapabilityTreeNode) => void;
}) {
  const style = NODE_TYPE_STYLE[node.node_type];
  const isSelected = selectedNodeId === node.id;
  const isLeaf = node.node_type === "level_3";

  if (isLeaf) {
    return (
      <button
        type="button"
        onClick={() => onSelect(node.id, node)}
        className={`w-full text-left px-2 py-1 rounded text-[10px] font-medium transition-colors border
          ${isSelected
            ? "bg-[var(--accent-red)]/10 border-[var(--accent-red)]/40 text-[var(--accent-red)]"
            : "bg-[var(--card)] border-[var(--paper-rule)] text-[var(--ink-mid)] hover:border-[var(--ink)]/20 hover:text-[var(--ink)]"
          }`}
      >
        {node.title}
      </button>
    );
  }

  return (
    <div
      className={`rounded-lg border-2 ${style.border} ${style.bg} p-2 space-y-1.5`}
    >
      {/* Node header: clickable title */}
      <button
        type="button"
        onClick={() => onSelect(node.id, node)}
        className={`w-full text-left flex items-center gap-1 group transition-colors ${
          isSelected ? "text-[var(--accent-red)]" : "text-[var(--ink)]"
        }`}
      >
        <ChevronRight
          size={10}
          className={`flex-shrink-0 transition-transform ${isSelected ? "rotate-90 text-[var(--accent-red)]" : "text-[var(--ink-faint)]"}`}
        />
        <span className={`${style.titleSize} truncate leading-snug`}>{node.title}</span>
      </button>

      {/* Children */}
      {node.children && node.children.length > 0 && (
        <div className={`space-y-1 ${depth > 0 ? "ml-2" : ""}`}>
          {node.children.map((child) => (
            <TreeNodeItem
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedNodeId={selectedNodeId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

export function ControlCapabilityMap({ orgId }: Props) {
  const [selectedNode, setSelectedNode] = useState<CapabilityTreeNode | null>(null);
  const [editingControl, setEditingControl] = useState<Control | null>(null);

  const { data: tree, isLoading: treeLoading, mutate } = useSWR<CapabilityTreeNode[]>(
    orgId ? `/api/v1/capabilities/orgs/${orgId}/tree` : null,
    fetcher
  );

  const isLoading = treeLoading;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-[var(--ink)]" />
      </div>
    );
  }

  if (!tree || tree.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--paper-warm)] px-4 py-6 text-[12px] text-[var(--ink-faint)] text-center">
        Noch keine Capability Map eingerichtet.
      </div>
    );
  }

  function handleSelect(id: string, node: CapabilityTreeNode) {
    setSelectedNode((prev) => (prev?.id === id ? null : node));
  }

  return (
    <div className="grid grid-cols-5 gap-4 items-start">
      {/* Left: BCM tree (40%) */}
      <div className="col-span-2 space-y-3">
        <div className="flex items-center gap-1.5 mb-1">
          <Layers size={13} className="text-[var(--ink-faint)]" />
          <span className="text-[10px] font-bold tracking-[0.12em] uppercase text-[var(--ink-faint)]">
            Capability Map
          </span>
        </div>
        {tree.map((root) => (
          <TreeNodeItem
            key={root.id}
            node={root}
            depth={0}
            selectedNodeId={selectedNode?.id ?? null}
            onSelect={handleSelect}
          />
        ))}
      </div>

      {/* Right: control detail panel (60%) */}
      <div className="col-span-3">
        {editingControl !== null ? (
          <div className="bg-[var(--card)] border-2 border-[var(--paper-rule)] rounded-xl overflow-hidden" style={{ minHeight: "480px" }}>
            <ControlEditor
              control={editingControl}
              orgId={orgId}
              onSaved={() => { setEditingControl(null); mutate(); }}
              onClose={() => setEditingControl(null)}
            />
          </div>
        ) : selectedNode ? (
          <div className="bg-[var(--card)] border-2 border-[var(--paper-rule)] rounded-xl p-4">
            <NodeControlsPanel orgId={orgId} node={selectedNode} onEdit={setEditingControl} />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-16 gap-2 text-[var(--ink-faint)]">
            <ShieldCheck size={28} className="opacity-30" />
            <p className="text-[11px]">Capability-Node auswählen, um Controls zu sehen.</p>
          </div>
        )}
      </div>
    </div>
  );
}
