"use client";

import type { CapabilityTreeNode } from "@/types";

const INDENT: Record<string, number> = {
  capability: 0,
  level_1: 16,
  level_2: 32,
  level_3: 48,
};

const TYPE_STYLE: Record<string, string> = {
  capability: "font-bold text-[13px]",
  level_1:    "font-semibold text-[12px]",
  level_2:    "text-[12px]",
  level_3:    "text-[11px]",
};

const DOT_COLOR: Record<string, string> = {
  capability: "bg-rose-500",
  level_1:    "bg-amber-400",
  level_2:    "bg-teal-400",
  level_3:    "bg-slate-300",
};

function TreeNode({ node, depth = 0 }: { node: CapabilityTreeNode; depth?: number }) {
  return (
    <div>
      <div
        className="flex items-center gap-2 py-1 px-2 rounded hover:bg-[var(--paper-warm)] transition-colors"
        style={{ paddingLeft: `${INDENT[node.node_type] + 8}px` }}
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${DOT_COLOR[node.node_type]}`} />
        <span
          className={`${TYPE_STYLE[node.node_type]}`}
          style={{ color: node.node_type === "capability" ? "var(--ink)" : "var(--ink-mid)" }}
        >
          {node.title}
        </span>
        {node.story_count !== undefined && node.story_count > 0 && (
          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-600 font-medium">
            {node.story_count}
          </span>
        )}
      </div>
      {node.children.map((child) => (
        <TreeNode key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export function CapabilityTreePreview({ nodes }: { nodes: CapabilityTreeNode[] }) {
  if (nodes.length === 0) {
    return (
      <p className="text-sm text-[var(--ink-faint)] text-center py-8">
        Keine Knoten zum Anzeigen.
      </p>
    );
  }
  return (
    <div className="space-y-1 max-h-[320px] overflow-y-auto pr-1">
      {nodes.map((node) => (
        <TreeNode key={node.id} node={node} />
      ))}
    </div>
  );
}
