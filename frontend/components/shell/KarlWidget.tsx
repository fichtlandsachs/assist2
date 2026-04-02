"use client";

import Link from "next/link";
import { Smile } from "lucide-react";
import { useTheme } from "@/lib/theme/context";

interface KarlWidgetProps {
  orgSlug: string;
}

export function KarlWidget({ orgSlug }: KarlWidgetProps) {
  const { theme } = useTheme();
  const isPaperwork = theme === "paperwork";

  if (isPaperwork) {
    return (
      <div className="mx-3 mb-3 px-3 py-2 flex items-center gap-2 rounded-sm"
        style={{ background: "var(--karl-bg)", border: "1px solid var(--karl-border)" }}>
        <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
          style={{ background: "rgba(255,255,255,.1)" }}>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "rgba(255,255,255,.55)", fontWeight: 700 }}>K</span>
        </div>
        <p className="flex-1 truncate"
          style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--karl-text)", letterSpacing: ".04em" }}>
          Ready to ship
        </p>
        <Link href={`/${orgSlug}/ai-workspace`}
          style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--sidebar-logout-text)" }}
          aria-label="KI Workspace">
          →
        </Link>
      </div>
    );
  }

  return (
    <div className="karl-widget mx-4 mb-4 p-5 flex flex-col items-center gap-3 rounded-3xl border-2 border-slate-900"
      style={{ background: "#FFFFFF", boxShadow: "6px 6px 0 rgba(0,0,0,1)" }}>

      <div className="karl-logo relative w-16 h-16 rounded-2xl border-2 border-slate-900 bg-amber-50 flex items-center justify-center overflow-hidden shadow-[2px_2px_0_rgba(0,0,0,1)]">
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(#000 1px, transparent 1px)", backgroundSize: "5px 5px" }} />
        <Smile size={28} strokeWidth={2} className="text-slate-900 relative z-10" />
      </div>

      <p className="text-center leading-snug font-['Architects_Daughter'] text-[14px] text-slate-800">
        "Let's sketch success together!"
      </p>

      <Link href={`/${orgSlug}/ai-workspace`}
        className="w-full text-center px-4 py-2 rounded-xl text-[11px] font-bold tracking-[0.15em] uppercase transition-colors bg-slate-900 text-white hover:bg-rose-500 font-['Architects_Daughter']">
        Talk to Karl
      </Link>
    </div>
  );
}
