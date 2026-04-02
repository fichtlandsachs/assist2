"use client";

import Link from "next/link";
import { Smile } from "lucide-react";
import { useTheme } from "@/lib/theme/context";

interface KarlWidgetProps {
  orgSlug: string;
}

export function KarlWidget({ orgSlug }: KarlWidgetProps) {
  const { theme } = useTheme();
  const isAgile = theme === "agile";

  if (isAgile) {
    return (
      <div
        className="karl-widget mx-4 mb-4 p-4 flex flex-col items-center gap-3 rounded-3xl"
        style={{
          background: "var(--karl-bg)",
          border: "2px solid var(--karl-border)",
          boxShadow: "var(--karl-shadow)",
        }}
      >
        <div
          className="karl-logo w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{
            background: "#f1efe9",
            border: "2px solid #231F1F",
            boxShadow: "2px 2px 0 rgba(0,0,0,1)",
          }}
        >
          <Smile size={22} strokeWidth={2} color="#231F1F" />
        </div>
        <p
          className="text-center text-[13px] leading-snug"
          style={{ fontFamily: "'Gochi Hand', cursive", color: "var(--karl-text)" }}
        >
          "Let's sketch success together!"
        </p>
        <Link
          href={`/${orgSlug}/ai-workspace`}
          className="w-full text-center px-4 py-2 rounded-xl text-[11px] font-bold transition-colors hover:opacity-80"
          style={{
            background: "var(--karl-btn-bg)",
            color: "var(--karl-btn-text)",
            fontFamily: "'Inter', sans-serif",
            letterSpacing: ".03em",
          }}
        >
          Talk to Karl
        </Link>
      </div>
    );
  }

  // Paperwork: compact strip
  return (
    <div
      className="mx-3 mb-3 px-3 py-2 flex items-center gap-2 rounded-sm"
      style={{
        background: "var(--karl-bg)",
        border: "1px solid var(--karl-border)",
      }}
    >
      <div
        className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
        style={{ background: "rgba(255,255,255,.1)" }}
      >
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: "7px",
            color: "rgba(255,255,255,.55)",
            fontWeight: 700,
          }}
        >
          K
        </span>
      </div>
      <p
        className="flex-1 truncate"
        style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--karl-text)", letterSpacing: ".04em" }}
      >
        Ready to ship
      </p>
      <Link
        href={`/${orgSlug}/ai-workspace`}
        style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--sidebar-logout-text)" }}
        aria-label="KI Workspace öffnen"
      >
        →
      </Link>
    </div>
  );
}
