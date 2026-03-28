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
        direct:         "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        interpreted:    "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        open:           "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
        met:            "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        partial:        "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        missing:        "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        nis2:           "text-[#1c1810] bg-[#ece8e0]",
        kritis:         "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        iso:            "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        iso27001:       "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        sop:            "text-[#1e3a5f] bg-[rgba(30,58,95,.06)]",
        runbook:        "text-[#5a3a7a] bg-[rgba(90,58,122,.08)]",
        bia:            "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        incident:       "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        richtlinie:     "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        auditiert:      "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        in_bearbeitung: "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        ausstehend:     "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
        abgelaufen:     "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        default:        "text-[#5a5040] bg-[#ece8e0] border-[#cec8bc]",
        outline:        "text-[#5a5040] bg-transparent border-[#cec8bc]",
        rag_direct:     "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        rag_context:    "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
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
