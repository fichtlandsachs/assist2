import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/**
 * Neobrutalist badge system for assist2.
 *
 * Status variants (compliance tracking):
 *   direct      — teal bg  — DIRECT mapping to regulation
 *   interpreted — yellow   — INTERPRETED / inferred mapping
 *   open        — orange   — OPEN / pending item
 *   met         — green    — requirement MET
 *   partial     — yellow   — PARTIAL compliance
 *   missing     — red      — MISSING / not covered
 *
 * Framework variants:
 *   nis2        — black bg, white text
 *   kritis      — orange bg, black text
 *   iso         — teal bg, black text
 *
 * Doc-type variants:
 *   sop         — blue tint
 *   runbook     — purple tint
 *   bia         — amber tint
 *   incident    — red tint
 *   richtlinie  — green tint
 */
const badgeVariants = cva(
  [
    "inline-flex items-center gap-1",
    "[font-family:var(--font-mono)] font-medium text-[7px]",
    "px-2 py-[2px]",
    "border-[0.5px] border-current",
    "rounded-[10px]",
    "uppercase tracking-[.08em] leading-[1.4]",
    "whitespace-nowrap",
  ],
  {
    variants: {
      variant: {
        direct:         "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        interpreted:    "text-[var(--brown)] bg-[rgba(122,100,80,.07)]",
        open:           "text-[var(--navy)] bg-[rgba(74,85,104,.06)]",
        met:            "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        partial:        "text-[var(--brown)] bg-[rgba(122,100,80,.07)]",
        missing:        "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.06)]",
        nis2:           "text-[var(--ink)] bg-[var(--paper-rule2)]",
        kritis:         "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.06)]",
        iso:            "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        iso27001:       "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        sop:            "text-[var(--navy)] bg-[rgba(74,85,104,.06)]",
        runbook:        "text-[var(--ink-mid)] bg-[rgba(90,80,64,.06)]",
        bia:            "text-[var(--brown)] bg-[rgba(122,100,80,.07)]",
        incident:       "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.06)]",
        richtlinie:     "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        auditiert:      "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        in_bearbeitung: "text-[var(--brown)] bg-[rgba(122,100,80,.07)]",
        ausstehend:     "text-[var(--navy)] bg-[rgba(74,85,104,.06)]",
        abgelaufen:     "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.06)]",
        default:        "text-[var(--ink-mid)] bg-[var(--paper-rule2)] border-[var(--ink-faintest)]",
        outline:        "text-[var(--ink-mid)] bg-transparent border-[var(--ink-faintest)]",
        rag_direct:     "text-[var(--green)] bg-[rgba(82,107,94,.07)]",
        rag_context:    "text-[var(--navy)] bg-[rgba(74,85,104,.06)]",
        llm:            "text-[var(--ink-mid)] bg-[var(--paper-rule2)] border-[var(--ink-faintest)]",

        // ── Story / Feature ──────────────────────────────────────
        priority_low:      "text-[var(--green)] bg-[rgba(82,107,94,.08)]",
        priority_medium:   "text-[var(--navy)] bg-[rgba(74,85,104,.06)]",
        priority_high:     "text-[var(--brown)] bg-[rgba(122,100,80,.08)]",
        priority_critical: "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)]",

        status_draft:       "text-[var(--ink-faint)] bg-[rgba(160,144,128,.08)]",
        status_in_review:   "text-[var(--brown)] bg-[rgba(122,100,80,.08)]",
        status_ready:       "text-[var(--green)] bg-[rgba(82,107,94,.08)]",
        status_in_progress: "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)]",
        status_testing:     "text-[#6b4fa0] bg-[rgba(107,79,160,.08)]",
        status_done:        "text-[var(--green)] bg-[rgba(82,107,94,.14)]",
        status_archived:    "text-[var(--ink-faint)] bg-[rgba(160,144,128,.06)]",

        quality_high: "text-[var(--green)] bg-[rgba(82,107,94,.08)]",
        quality_mid:  "text-[var(--brown)] bg-[rgba(122,100,80,.08)]",
        quality_low:  "text-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)]",

        story_points: "text-[var(--ink-faint)] bg-[var(--paper-warm)] border-[var(--paper-rule)]",
        dor_passed:   "text-[var(--green)] bg-[rgba(82,107,94,.08)]",
      },
      size: {
        sm:      "text-[6px] px-1.5 py-px",
        default: "text-[7px] px-2 py-[2px]",
        lg:      "text-[8px] px-2.5 py-1",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {
  /** Optional dot indicator color (CSS color string). */
  dot?: string;
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant, size, dot, children, ...props }, ref) => (
    <span
      ref={ref}
      className={cn(badgeVariants({ variant, size, className }))}
      {...props}
    >
      {dot && (
        <span
          className="inline-block w-1.5 h-1.5 rounded-full border border-current flex-shrink-0"
          style={{ backgroundColor: dot }}
        />
      )}
      {children}
    </span>
  )
);
Badge.displayName = "Badge";

/* ── Convenience exports ─────────────────────────────────────────── */

/** NIS2 framework badge */
export function Nis2Badge({ className }: { className?: string }) {
  return (
    <Badge variant="nis2" className={className}>
      NIS2
    </Badge>
  );
}

/** KRITIS framework badge */
export function KritisBadge({ className }: { className?: string }) {
  return (
    <Badge variant="kritis" className={className}>
      KRITIS
    </Badge>
  );
}

/** ISO 27001 framework badge */
export function IsoBadge({ className }: { className?: string }) {
  return (
    <Badge variant="iso27001" className={className}>
      ISO 27001
    </Badge>
  );
}

/** Compliance status badge — MET / PARTIAL / MISSING */
export function ComplianceBadge({
  status,
  className,
}: {
  status: "MET" | "PARTIAL" | "MISSING";
  className?: string;
}) {
  const variantMap = {
    MET: "met",
    PARTIAL: "partial",
    MISSING: "missing",
  } as const;
  const labelMap = {
    MET: "Erfüllt",
    PARTIAL: "Teilweise",
    MISSING: "Fehlend",
  };
  return (
    <Badge variant={variantMap[status]} className={className}>
      {labelMap[status]}
    </Badge>
  );
}

/** Document type badge */
export function DocTypeBadge({
  type,
  className,
}: {
  type: "SOP" | "Runbook" | "BIA" | "Incident" | "Richtlinie";
  className?: string;
}) {
  const variantMap = {
    SOP: "sop",
    Runbook: "runbook",
    BIA: "bia",
    Incident: "incident",
    Richtlinie: "richtlinie",
  } as const;
  return (
    <Badge variant={variantMap[type]} className={className}>
      {type}
    </Badge>
  );
}

/** Document audit-status badge */
export function DocStatusBadge({
  status,
  className,
}: {
  status: "auditiert" | "in_bearbeitung" | "ausstehend" | "abgelaufen";
  className?: string;
}) {
  const labelMap = {
    auditiert: "Auditiert",
    in_bearbeitung: "In Bearbeitung",
    ausstehend: "Ausstehend",
    abgelaufen: "Abgelaufen",
  };
  return (
    <Badge variant={status} className={className}>
      {labelMap[status]}
    </Badge>
  );
}

// ── Story / Feature convenience exports ───────────────────────────

import type { StoryPriority, StoryStatus } from "@/types";
import { AlertTriangle } from "lucide-react";

const PRIORITY_VARIANT: Record<StoryPriority, "priority_low" | "priority_medium" | "priority_high" | "priority_critical"> = {
  low:      "priority_low",
  medium:   "priority_medium",
  high:     "priority_high",
  critical: "priority_critical",
};

const PRIORITY_LABEL: Record<StoryPriority, string> = {
  low: "Niedrig", medium: "Mittel", high: "Hoch", critical: "Kritisch",
};

const STATUS_VARIANT: Record<StoryStatus, "status_draft" | "status_in_review" | "status_ready" | "status_in_progress" | "status_testing" | "status_done" | "status_archived"> = {
  draft:       "status_draft",
  in_review:   "status_in_review",
  ready:       "status_ready",
  in_progress: "status_in_progress",
  testing:     "status_testing",
  done:        "status_done",
  archived:    "status_archived",
};

const STATUS_LABEL: Record<StoryStatus, string> = {
  draft:       "Entwurf",
  in_review:   "Überarbeitung",
  ready:       "Bereit",
  in_progress: "In Arbeit",
  testing:     "Test",
  done:        "Fertig",
  archived:    "Archiviert",
};

/** Priority badge — low / medium / high / critical */
export function PriorityBadge({ priority, className }: { priority: StoryPriority; className?: string }) {
  return (
    <Badge variant={PRIORITY_VARIANT[priority]} className={className}>
      {PRIORITY_LABEL[priority]}
    </Badge>
  );
}

/** Story / Feature status badge */
export function StatusBadge({ status, className }: { status: StoryStatus; className?: string }) {
  return (
    <Badge variant={STATUS_VARIANT[status]} className={className}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

/** Story points badge — "X SP" */
export function StoryPointsBadge({ points, className }: { points: number; className?: string }) {
  return (
    <Badge variant="story_points" className={className}>
      {points} SP
    </Badge>
  );
}

/** Quality score badge — colour depends on score value */
export function QualityScoreBadge({ score, className }: { score: number | null; className?: string }) {
  if (score === null) {
    return (
      <Badge variant="quality_low" className={cn("gap-0.5 opacity-40", className)}>
        — Score
      </Badge>
    );
  }
  const variant = score >= 80 ? "quality_high" : score >= 60 ? "quality_mid" : "quality_low";
  return (
    <Badge variant={variant} className={cn("gap-0.5", className)}>
      {score < 80 && <AlertTriangle size={8} />}
      {score}
    </Badge>
  );
}

/** Definition of Ready passed badge */
export function DoRBadge({ className }: { className?: string }) {
  return (
    <Badge variant="dor_passed" className={className}>
      ✓ DoR
    </Badge>
  );
}

export { Badge, badgeVariants };
