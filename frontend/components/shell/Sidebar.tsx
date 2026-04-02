"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Settings, BookOpen, Inbox, CalendarDays, FileText,
  Workflow, Folder, Globe, Bell, Star, Zap, Users, Shield, MessageSquare,
  Smile, X, type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { usePluginRegistry } from "@/lib/plugins/registry";
import { SlotRenderer } from "@/lib/plugins/slots";
import { useTheme } from "@/lib/theme/context";
import { KarlWidget } from "./KarlWidget";

const PLUGIN_ICONS: Record<string, LucideIcon> = {
  folder: Folder, globe: Globe, bell: Bell, star: Star,
  zap: Zap, users: Users, file: FileText, workflow: Workflow,
};

const NAV_COLORS: Record<string, { icon: string; bg: string }> = {
  dashboard:      { icon: "text-rose-500",    bg: "bg-rose-50" },
  "ai-workspace": { icon: "text-indigo-500",  bg: "bg-indigo-50" },
  project:        { icon: "text-teal-500",    bg: "bg-teal-50" },
  stories:        { icon: "text-amber-500",   bg: "bg-amber-50" },
  inbox:          { icon: "text-sky-500",     bg: "bg-sky-50" },
  calendar:       { icon: "text-emerald-500", bg: "bg-emerald-50" },
  workflows:      { icon: "text-violet-500",  bg: "bg-violet-50" },
  docs:           { icon: "text-orange-500",  bg: "bg-orange-50" },
  settings:       { icon: "text-slate-500",   bg: "bg-slate-50" },
  admin:          { icon: "text-red-500",     bg: "bg-red-50" },
};

interface SidebarProps {
  orgSlug: string;
  orgId?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ orgSlug, orgId, mobileOpen = false, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { navEntries } = usePluginRegistry(orgId ?? "");
  const { theme } = useTheme();
  const isPaperwork = theme === "paperwork";

  const navItems = [
    { id: "dashboard",    label: "Dashboard",      icon: LayoutDashboard, route: `/${orgSlug}/dashboard` },
    { id: "ai-workspace", label: "KI Workspace",   icon: MessageSquare,   route: `/${orgSlug}/ai-workspace` },
    { id: "project",      label: "Projekte",       icon: Folder,          route: `/${orgSlug}/project` },
    { id: "stories",      label: "User Stories",   icon: BookOpen,        route: `/${orgSlug}/stories` },
    { id: "inbox",        label: "Posteingang",    icon: Inbox,           route: `/${orgSlug}/inbox` },
    { id: "calendar",     label: "Kalender",       icon: CalendarDays,    route: `/${orgSlug}/calendar` },
    { id: "workflows",    label: "Workflows",      icon: Workflow,        route: `/${orgSlug}/workflows` },
    { id: "docs",         label: "Dokumentation",  icon: FileText,        route: `/${orgSlug}/docs` },
    { id: "settings",     label: "Einstellungen",  icon: Settings,        route: `/${orgSlug}/settings` },
    ...(user?.is_superuser
      ? [{ id: "admin", label: "Admin", icon: Shield, route: `/${orgSlug}/admin` }]
      : []),
  ];

  const paperworkSidebar = (
    <aside
      style={{ background: "var(--binding)", boxShadow: "1px 0 0 var(--sidebar-divider)", width: "var(--sidebar-width)", flexShrink: 0 }}
      className="flex flex-col h-full"
    >
      <div className="flex items-center justify-between px-4"
        style={{ height: "var(--topbar-height)", borderBottom: "1px solid var(--sidebar-divider)" }}>
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "var(--sidebar-org-text)" }}>
          {orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden p-1 rounded"
          style={{ color: "var(--sidebar-text)" }} aria-label="Schließen">
          <X size={14} />
        </button>
      </div>

      <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`flex items-center gap-2.5 px-2 py-1.5 transition-all sidebar-nav-item${isActive ? " is-active" : ""}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
                color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
              <Icon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}
        {navEntries.filter(e => e.slot === "sidebar_main").map(entry => {
          const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
          const route = `/${orgSlug}${entry.route}`;
          const isActive = pathname === route;
          return (
            <Link key={entry.id} href={route} onClick={onMobileClose}
              className={`flex items-center gap-2.5 px-2 py-1.5 transition-all sidebar-nav-item${isActive ? " is-active" : ""}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
                color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
              <PluginIcon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
              <span className="truncate">{entry.label}</span>
            </Link>
          );
        })}
        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      <KarlWidget orgSlug={orgSlug} />

      {user && (
        <div className="px-3 py-3 flex items-center gap-2" style={{ borderTop: "1px solid var(--sidebar-divider)" }}>
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            style={{ background: "var(--sidebar-avatar-bg)", fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--sidebar-avatar-text)" }}>
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate" style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--sidebar-user-text)", letterSpacing: ".04em" }}>
              {user.display_name}
            </p>
          </div>
          <button onClick={() => void logout()}
            style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--sidebar-logout-text)", letterSpacing: ".04em" }}>
            Logout
          </button>
        </div>
      )}
    </aside>
  );

  const agileSidebar = (
    <aside className="w-64 h-full bg-[#fdfaf6] border-r-2 border-slate-900/10 flex flex-col shrink-0 shadow-[4px_0_0_rgba(0,0,0,0.02)]">

      {/* Brand */}
      <div className="relative p-6 pb-6 flex flex-col items-center gap-1.5 border-b-2 border-slate-900/5">
        <div className="karl-logo w-14 h-14 bg-white border-2 border-slate-900 rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] flex items-center justify-center">
          <Smile size={26} strokeWidth={2} className="text-slate-900" />
        </div>
        <span className="font-['Architects_Daughter'] text-2xl text-slate-900 tracking-tight leading-none">Karl</span>
        <span className="text-[9px] font-bold tracking-[0.2em] text-slate-400 uppercase font-['Architects_Daughter']">
          {orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg border-2 border-transparent hover:border-slate-200" aria-label="Schließen">
          <X size={14} className="text-slate-500" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 flex flex-col gap-0.5 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          const colors = NAV_COLORS[item.id] ?? { icon: "text-slate-500", bg: "bg-slate-50" };
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all ${isActive ? "border-slate-900/15 " + colors.bg : "border-transparent"}`}>
                <Icon size={14} strokeWidth={2.5} className={isActive ? colors.icon : "text-slate-400"} />
              </div>
              <span className={`text-[13px] font-bold font-['Architects_Daughter'] truncate ${isActive ? "text-slate-900" : "text-slate-500"}`}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {navEntries.filter(e => e.slot === "sidebar_main").map(entry => {
          const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
          const route = `/${orgSlug}${entry.route}`;
          const isActive = pathname === route;
          return (
            <Link key={entry.id} href={route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 ${isActive ? "border-slate-900/15 bg-slate-50" : "border-transparent"}`}>
                <PluginIcon size={14} strokeWidth={2.5} className={isActive ? "text-slate-600" : "text-slate-400"} />
              </div>
              <span className={`text-[13px] font-bold font-['Architects_Daughter'] truncate ${isActive ? "text-slate-900" : "text-slate-500"}`}>
                {entry.label}
              </span>
            </Link>
          );
        })}

        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      {/* Karl widget */}
      <KarlWidget orgSlug={orgSlug} />

      {/* User footer */}
      {user && (
        <div className="p-3 flex items-center gap-2.5 border-t-2 border-slate-900/5">
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div className="w-8 h-8 rounded-xl border-2 border-slate-900 bg-white shadow-[2px_2px_0_rgba(0,0,0,1)] flex items-center justify-center flex-shrink-0">
            <span className="text-[10px] font-bold text-slate-900 font-['Architects_Daughter']">
              {user.display_name.slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-[11px] font-bold text-slate-700 font-['Architects_Daughter']">
              {user.display_name}
            </p>
          </div>
          <button onClick={() => void logout()}
            className="text-[10px] font-bold text-slate-400 hover:text-rose-500 transition-colors font-['Architects_Daughter']">
            Logout
          </button>
        </div>
      )}
    </aside>
  );

  const sidebarContent = isPaperwork ? paperworkSidebar : agileSidebar;

  return (
    <>
      <div className="hidden md:flex shrink-0">{sidebarContent}</div>
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={onMobileClose} aria-hidden="true" />
          <div className="relative z-10 flex shrink-0">{sidebarContent}</div>
        </div>
      )}
    </>
  );
}
