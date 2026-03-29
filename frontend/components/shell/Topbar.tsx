"use client";

import { Menu } from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { usePathname } from "next/navigation";
import { SlotRenderer } from "@/lib/plugins/slots";
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
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const segment = pathname.split("/")[2] ?? "dashboard";
  const pageTitle = PAGE_TITLES[segment] ?? segment;

  return (
    <header
      className="flex items-center justify-between px-4 shrink-0"
      style={{
        height: "var(--topbar-height)",
        background: "var(--paper-warm)",
        borderBottom: "1.5px solid var(--ink)",
      }}
    >
      {/* Left */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="md:hidden p-1.5 rounded"
          style={{ color: "var(--ink-faint)" }}
          aria-label="Menü öffnen"
        >
          <Menu size={16} />
        </button>
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "17px", color: "var(--ink)" }}>
          {pageTitle}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faint)", letterSpacing: ".06em" }}>
          {orgSlug}
        </span>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />
        {clock && (
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faintest)", letterSpacing: ".06em" }}>
            {clock}
          </span>
        )}
        {user && (
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{
              background: "var(--paper-rule2)",
              border: "0.5px solid var(--ink-faintest)",
              fontFamily: "var(--font-mono)", fontSize: "8px",
              color: "var(--ink-mid)",
            }}
            title={user.display_name}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
        )}
      </div>
    </header>
  );
}
