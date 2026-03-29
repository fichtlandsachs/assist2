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
        direct:         "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        interpreted:    "text-[#7a6450] bg-[rgba(122,100,80,.07)]",
        open:           "text-[#4a5568] bg-[rgba(74,85,104,.06)]",
        met:            "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        partial:        "text-[#7a6450] bg-[rgba(122,100,80,.07)]",
        missing:        "text-[#8b5e52] bg-[rgba(139,94,82,.06)]",
        nis2:           "text-[#1c1810] bg-[#ece8e0]",
        kritis:         "text-[#8b5e52] bg-[rgba(139,94,82,.06)]",
        iso:            "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        iso27001:       "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        sop:            "text-[#4a5568] bg-[rgba(74,85,104,.06)]",
        runbook:        "text-[#5a5040] bg-[rgba(90,80,64,.06)]",
        bia:            "text-[#7a6450] bg-[rgba(122,100,80,.07)]",
        incident:       "text-[#8b5e52] bg-[rgba(139,94,82,.06)]",
        richtlinie:     "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        auditiert:      "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        in_bearbeitung: "text-[#7a6450] bg-[rgba(122,100,80,.07)]",
        ausstehend:     "text-[#4a5568] bg-[rgba(74,85,104,.06)]",
        abgelaufen:     "text-[#8b5e52] bg-[rgba(139,94,82,.06)]",
        default:        "text-[#5a5040] bg-[#ece8e0] border-[#cec8bc]",
        outline:        "text-[#5a5040] bg-transparent border-[#cec8bc]",
        rag_direct:     "text-[#526b5e] bg-[rgba(82,107,94,.07)]",
        rag_context:    "text-[#4a5568] bg-[rgba(74,85,104,.06)]",
        llm:            "text-[#5a5040] bg-[#ece8e0] border-[#cec8bc]",
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

export { Badge, badgeVariants };
