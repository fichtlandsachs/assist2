"use client";

import { Bell, Menu } from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { SlotRenderer } from "@/lib/plugins/slots";

interface TopbarProps {
  orgSlug: string;
  orgId?: string;
  onMenuClick?: () => void;
}

export function Topbar({ orgSlug, orgId, onMenuClick }: TopbarProps) {
  const { user } = useAuth();

  return (
    <header className="h-14 flex items-center justify-between px-4 md:px-6 bg-white border-b border-slate-200 shrink-0">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          aria-label="Menü öffnen"
        >
          <Menu size={20} />
        </button>
        {/* Breadcrumb */}
        <span className="text-sm text-slate-500 hidden sm:block">{orgSlug}</span>
      </div>

      <div className="flex items-center gap-3">
        <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />
        <button
          className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 hover:text-slate-700 transition-colors"
          aria-label="Benachrichtigungen"
        >
          <Bell size={18} />
        </button>
        {user && (
          <div
            className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-xs font-bold text-white"
            title={user.display_name}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
        )}
      </div>
    </header>
  );
}
