"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import { LayoutDashboard, Settings, BookOpen, Inbox, CalendarDays, FileText, ChevronLeft, ChevronRight, X, Shield, Workflow, Folder, Globe, Bell, Star, Zap, Users, type LucideIcon } from "lucide-react";

const PLUGIN_ICONS: Record<string, LucideIcon> = {
  folder: Folder,
  globe: Globe,
  bell: Bell,
  star: Star,
  zap: Zap,
  users: Users,
  file: FileText,
  workflow: Workflow,
};
import { useState } from "react";
import { useAuth } from "@/lib/auth/context";
import { usePluginRegistry } from "@/lib/plugins/registry";
import { SlotRenderer } from "@/lib/plugins/slots";

interface SidebarProps {
  orgSlug: string;
  orgId?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ orgSlug, orgId, mobileOpen = false, onMobileClose }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { navEntries } = usePluginRegistry(orgId ?? "");

  const defaultNavItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard, route: `/${orgSlug}/dashboard` },
    { id: "stories", label: "User Stories", icon: BookOpen, route: `/${orgSlug}/stories` },
    { id: "inbox", label: "Posteingang", icon: Inbox, route: `/${orgSlug}/inbox` },
    { id: "calendar", label: "Kalender", icon: CalendarDays, route: `/${orgSlug}/calendar` },
    { id: "workflows", label: "Workflows", icon: Workflow, route: `/${orgSlug}/workflows` },
    { id: "docs", label: "Dokumentation", icon: FileText, route: `/${orgSlug}/docs` },
    { id: "settings", label: "Einstellungen", icon: Settings, route: `/${orgSlug}/settings` },
    ...(user?.is_superuser
      ? [{ id: "admin", label: "Admin", icon: Shield, route: `/${orgSlug}/admin` }]
      : []),
  ];

  const sidebarContent = (
    <aside className={`flex flex-col bg-slate-900 text-slate-100 h-full transition-all duration-200 ${collapsed ? "w-16" : "w-64"}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-700">
        {!collapsed && <span className="font-semibold text-white truncate">{orgSlug}</span>}
        {/* Mobile close button */}
        <button
          onClick={onMobileClose}
          className="p-1 rounded hover:bg-slate-700 shrink-0 md:hidden"
          aria-label="Sidebar schließen"
        >
          <X size={16} />
        </button>
        {/* Desktop collapse button */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded hover:bg-slate-700 shrink-0 hidden md:flex"
          aria-label={collapsed ? "Sidebar aufklappen" : "Sidebar einklappen"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1 px-2">
        {defaultNavItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.id}
              href={item.route}
              onClick={onMobileClose}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-brand-600 text-white"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}
            >
              <Icon size={18} className="shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}

        {/* Plugin nav entries from registry */}
        {navEntries
          .filter(entry => entry.slot === "sidebar_main")
          .map(entry => {
            const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
            return (
            <Link
              key={entry.id}
              href={`/${orgSlug}${entry.route}`}
              onClick={onMobileClose}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                pathname === `/${orgSlug}${entry.route}`
                  ? "bg-brand-600 text-white"
                  : "text-slate-300 hover:bg-slate-700 hover:text-white"
              }`}
            >
              <PluginIcon size={18} className="shrink-0" />
              {!collapsed && <span className="truncate">{entry.label}</span>}
            </Link>
            );
          })}

        {/* Plugin-Slot: sidebar_main */}
        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={collapsed} />
      </nav>

      {/* User Footer */}
      {user && (
        <div className="p-4 border-t border-slate-700">
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          {!collapsed && (
            <div className="flex items-center gap-2 mt-2">
              <div className="w-8 h-8 rounded-full bg-brand-600 flex items-center justify-center text-xs font-bold shrink-0">
                {user.display_name.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white truncate">{user.display_name}</p>
                <p className="text-xs text-slate-400 truncate">{user.email}</p>
              </div>
              <button
                onClick={() => void logout()}
                className="text-slate-400 hover:text-white text-xs shrink-0"
              >
                Logout
              </button>
            </div>
          )}
        </div>
      )}
    </aside>
  );

  return (
    <>
      {/* Desktop: always visible inline */}
      <div className="hidden md:flex shrink-0">
        {sidebarContent}
      </div>

      {/* Mobile: overlay drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={onMobileClose}
            aria-hidden="true"
          />
          {/* Drawer */}
          <div className="relative z-10 flex shrink-0">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
}
