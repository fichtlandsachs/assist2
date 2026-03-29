"use client";

import { CheckCircle, Trash2 } from "lucide-react";

export interface DoDItemProps {
  text: string;
  done: boolean;
  onToggle: () => void;
  onDelete: () => void;
  /** Disables toggle + delete; used for locked story statuses */
  readOnly?: boolean;
}

/**
 * Single Definition-of-Done checklist entry.
 *
 * Renders a checkbox, item text, and a hover-revealed delete button.
 * Extract from stories/[id]/page.tsx — single source of truth for DoD item UI.
 */
export function DoDItem({ text, done, onToggle, onDelete, readOnly = false }: DoDItemProps) {
  return (
    <div
      className={`flex items-start gap-3 px-3 py-2.5 rounded-sm border transition-colors group ${
        done
          ? "bg-[rgba(82,107,94,.1)] border-[rgba(82,107,94,.3)]"
          : "bg-[#faf9f6] border-[#e2ddd4]"
      }`}
    >
      <button
        type="button"
        onClick={() => !readOnly && onToggle()}
        disabled={readOnly}
        className={`shrink-0 mt-0.5 w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
          done
            ? "bg-[#526b5e] border-[#526b5e]"
            : "border-[#cec8bc] hover:border-[#526b5e] disabled:cursor-default"
        }`}
      >
        {done && <CheckCircle size={10} className="text-white" />}
      </button>

      <span
        className={`flex-1 min-w-0 text-sm break-words ${
          done ? "line-through text-[#a09080]" : "text-[#5a5040]"
        }`}
      >
        {text}
      </span>

      {!readOnly && (
        <button
          type="button"
          onClick={onDelete}
          className="shrink-0 p-0.5 text-[#cec8bc] hover:text-[#8b5e52] opacity-0 group-hover:opacity-100 transition-all rounded-sm"
          aria-label="Kriterium entfernen"
        >
          <Trash2 size={13} />
        </button>
      )}
    </div>
  );
}
