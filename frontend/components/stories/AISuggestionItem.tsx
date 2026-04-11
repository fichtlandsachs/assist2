"use client";

import { FileText, GripVertical, Plus, Sparkles, X } from "lucide-react";
import { useT } from "@/lib/i18n/context";

export interface Source {
  title: string;
  url: string;
  type: string; // "karl_story" | "nextcloud" | "jira" | "confluence"
}

export type AISuggestionSource = "doc" | "ki";

export interface AISuggestionItemProps {
  text: string;
  category?: string | null;
  sources?: Source[];
  onAdd: () => void;
  onReject?: () => void;
  /** MIME type for drag data (e.g. "application/x-dod-suggestion"). Omit to disable drag. */
  dragType?: string;
}

/**
 * Single AI suggestion entry.
 *
 * Shows source badges: if sources.length > 0 → linked org-source badges;
 * if sources is empty or undefined → ✦ KI badge (pure LLM, no org context).
 */
export function AISuggestionItem({ text, category, sources, onAdd, onReject, dragType }: AISuggestionItemProps) {
  const { t } = useT();
  function handleDragStart(e: React.DragEvent) {
    if (!dragType) return;
    e.dataTransfer.setData(dragType, text);
    e.dataTransfer.setData("text/plain", text);
    e.dataTransfer.effectAllowed = "copy";
  }

  const hasSources = sources && sources.length > 0;

  return (
    <div
      draggable={!!dragType}
      onDragStart={dragType ? handleDragStart : undefined}
      className={`relative flex items-start gap-2 px-3 py-2.5 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)] hover:border-[rgba(var(--accent-red-rgb),.3)] transition-colors group${dragType ? " cursor-grab active:cursor-grabbing" : ""}`}
    >
      {dragType && <GripVertical size={13} className="shrink-0 mt-0.5 text-[var(--ink-faintest)] group-hover:text-[var(--ink-faint)]" />}
      <div className="flex-1 min-w-0">
        {category && (
          <div className="flex items-center gap-1.5 mb-1">
            <span className="shrink-0 px-1.5 py-0.5 bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)] rounded-sm text-[7px] font-medium uppercase tracking-[.06em] [font-family:var(--font-mono)]">
              {category}
            </span>
          </div>
        )}
        <span className="text-sm text-[var(--ink-mid)] break-words leading-snug">{text}</span>

        {/* Source badges */}
        <div className="flex flex-wrap items-center gap-1 mt-1.5">
          {hasSources ? (
            sources.map((s, i) => (
              <a
                key={i}
                href={s.url}
                target={s.type === "karl_story" ? "_self" : "_blank"}
                rel="noopener noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faint)] hover:text-[var(--accent-red)] border border-[var(--paper-rule)] rounded-sm px-1.5 py-0.5 transition-colors"
              >
                <FileText size={9} />
                {s.title}
              </a>
            ))
          ) : (
            <span className="inline-flex items-center gap-1 text-[10px] text-[var(--ink-faintest)] border border-[var(--paper-rule)] rounded-sm px-1.5 py-0.5">
              <Sparkles size={9} />
              KI
            </span>
          )}
        </div>
      </div>

      {/* Reject button — top-right, revealed on hover */}
      {onReject && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onReject(); }}
          aria-label={t("ai_suggest_reject")}
          className="absolute top-[6px] right-[26px] w-[18px] h-[18px] flex items-center justify-center text-[var(--ink-faintest)] hover:text-[var(--accent-red)] rounded-sm opacity-0 group-hover:opacity-100 transition-all"
        >
          <X size={10} />
        </button>
      )}

      {/* Plus button — top-right corner, revealed on hover */}
      <button
        type="button"
        onClick={onAdd}
        aria-label={t("ai_suggest_accept")}
        className="absolute top-[6px] right-[6px] w-[18px] h-[18px] flex items-center justify-center bg-[rgba(var(--accent-red-rgb),.08)] border-[0.5px] border-[rgba(var(--accent-red-rgb),.3)] text-[var(--accent-red)] rounded-sm opacity-0 group-hover:opacity-100 transition-all hover:bg-[var(--accent-red)] hover:text-white"
      >
        <Plus size={10} />
      </button>
    </div>
  );
}
