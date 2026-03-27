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
    // Base
    "inline-flex items-center gap-1",
    "font-heading font-600 text-[0.6875rem]",
    "px-2.5 py-0.5",
    "border-2 border-[#0A0A0A]",
    "shadow-[2px_2px_0px_#0A0A0A]",
    "uppercase tracking-[0.04em] leading-[1.4]",
    "whitespace-nowrap",
  ],
  {
    variants: {
      variant: {
        /* ── Compliance status ─────────────────────────── */
        direct: "bg-[#00D4AA] text-[#0A0A0A]",
        interpreted: "bg-[#FFD700] text-[#0A0A0A]",
        open: "bg-[#FF5C00] text-[#0A0A0A]",
        met: "bg-[#22C55E] text-[#0A0A0A]",
        partial: "bg-[#FFD700] text-[#0A0A0A]",
        missing: "bg-[#EF4444] text-white",

        /* ── Framework labels ──────────────────────────── */
        nis2: "bg-[#0A0A0A] text-white border-[#0A0A0A] shadow-[2px_2px_0px_#444]",
        kritis: "bg-[#FF5C00] text-[#0A0A0A]",
        iso: "bg-[#00D4AA] text-[#0A0A0A]",
        iso27001: "bg-[#00D4AA] text-[#0A0A0A]",

        /* ── Document types ────────────────────────────── */
        sop: "bg-[#DBEAFE] text-[#1e40af] border-[#1e40af] shadow-[2px_2px_0px_#1e40af]",
        runbook:
          "bg-[#F3E8FF] text-[#6d28d9] border-[#6d28d9] shadow-[2px_2px_0px_#6d28d9]",
        bia: "bg-[#FEF3C7] text-[#92400e] border-[#92400e] shadow-[2px_2px_0px_#92400e]",
        incident:
          "bg-[#FEE2E2] text-[#991b1b] border-[#991b1b] shadow-[2px_2px_0px_#991b1b]",
        richtlinie:
          "bg-[#DCFCE7] text-[#166534] border-[#166534] shadow-[2px_2px_0px_#166534]",

        /* ── Audit/doc status ──────────────────────────── */
        auditiert:
          "bg-[#22C55E] text-[#0A0A0A]",
        in_bearbeitung:
          "bg-[#FFD700] text-[#0A0A0A]",
        ausstehend:
          "bg-[#FF5C00] text-[#0A0A0A]",
        abgelaufen:
          "bg-[#EF4444] text-white",

        /* ── Generic neutral ───────────────────────────── */
        default:
          "bg-[#F5F0E8] text-[#0A0A0A] border-[#0A0A0A]",
        outline:
          "bg-transparent text-[#0A0A0A] border-[#0A0A0A] shadow-none",
      },
      size: {
        sm: "text-[0.625rem] px-2 py-px",
        default: "text-[0.6875rem] px-2.5 py-0.5",
        lg: "text-xs px-3 py-1",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
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
