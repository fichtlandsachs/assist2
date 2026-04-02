"use client";

import { Menu } from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { usePathname } from "next/navigation";
import { SlotRenderer } from "@/lib/plugins/slots";
import { useTheme } from "@/lib/theme/context";
import { useEffect, useState } from "react";

interface TopbarProps {
  orgSlug: string;
  orgId?: string;
  onMenuClick?: () => void;
}

const PAGE_TITLES: Record<string, string> = {
  dashboard:      "Dashboard",
  "ai-workspace": "KI Workspace",
  stories:        "User Stories",
  inbox:          "Posteingang",
  calendar:       "Kalender",
  workflows:      "Workflows",
  docs:           "Dokumentation",
  settings:       "Einstellungen",
  admin:          "Administration",
};

export function Topbar({ orgSlug, orgId, onMenuClick }: TopbarProps) {
  const { user } = useAuth();
  const pathname = usePathname();
  const { theme } = useTheme();
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const segment = pathname.split("/")[2] ?? "dashboard";
  const pageTitle = PAGE_TITLES[segment] ?? segment;
  const isPaperwork = theme === "paperwork";

  if (isPaperwork) {
    return (
      <header className="flex items-center justify-between px-4 shrink-0"
        style={{ height: "var(--topbar-height)", background: "var(--paper-warm)", borderBottom: "var(--topbar-border)" }}>
        <div className="flex items-center gap-3">
          <button onClick={onMenuClick} className="md:hidden p-1.5 rounded" style={{ color: "var(--ink-faint)" }} aria-label="Menü öffnen">
            <Menu size={16} />
          </button>
          <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "17px", color: "var(--ink)" }}>
            {pageTitle}
          </span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faint)", letterSpacing: ".06em" }}>
            {orgSlug}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />
          {clock && (
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faintest)", letterSpacing: ".06em" }}>
              {clock}
            </span>
          )}
          {user && (
            <div className="w-6 h-6 rounded-full flex items-center justify-center"
              style={{ background: "var(--paper-rule2)", border: "0.5px solid var(--ink-faintest)", fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-mid)" }}
              title={user.display_name}>
              {user.display_name.slice(0, 2).toUpperCase()}
            </div>
          )}
        </div>
      </header>
    );
  }

  /* ── src_agile header ── */
  return (
    <header className="h-16 border-b-2 border-slate-900/5 flex items-center justify-between px-5 lg:px-8 bg-[#FDFBF7]/80 backdrop-blur-md sticky top-0 z-30 shrink-0">

      {/* Left: breadcrumb */}
      <div className="flex items-center gap-3">
        <button onClick={onMenuClick}
          className="lg:hidden p-2 rounded-xl border-2 border-transparent hover:border-slate-900/20 active:border-slate-900 transition-colors"
          aria-label="Menü öffnen">
          <Menu size={18} className="text-slate-700" />
        </button>
        <span className="font-['Architects_Daughter'] font-bold tracking-widest text-[10px] text-[#B8B3AE] uppercase">
          Karl
        </span>
        <span className="text-[#B8B3AE] text-[10px]">/</span>
        <span className="font-['Architects_Daughter'] text-[10px] font-bold tracking-widest text-rose-500 uppercase">
          {pageTitle}
        </span>
      </div>

      {/* Right: slot + clock + avatar */}
      <div className="flex items-center gap-4">
        <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />

        {clock && (
          <div className="hidden sm:flex flex-col items-end">
            <span className="font-['Architects_Daughter'] text-[10px] font-bold text-slate-900">{clock}</span>
          </div>
        )}

        {user && (
          <div className="w-10 h-10 rounded-xl border-2 border-slate-900 bg-white shadow-[2px_2px_0_rgba(0,0,0,1)] flex items-center justify-center flex-shrink-0"
            title={user.display_name}>
            <span className="text-[11px] font-bold text-slate-900 font-['Architects_Daughter']">
              {user.display_name.slice(0, 2).toUpperCase()}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
