"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Settings, BookOpen, Inbox, CalendarDays, FileText,
  Workflow, Folder, Globe, Bell, Star, Zap, Users, Shield, MessageSquare,
  X, HardDrive, ChevronRight, ShieldCheck, Sparkles, type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { usePluginRegistry } from "@/lib/plugins/registry";
import { SlotRenderer } from "@/lib/plugins/slots";
import { useTheme } from "@/lib/theme/context";
import { KarlWidget } from "./KarlWidget";
import { useState } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";

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
  dateien:        { icon: "text-cyan-500",    bg: "bg-cyan-50" },
};

interface SidebarProps {
  orgSlug: string;
  orgId?: string;
  orgName?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ orgSlug, orgId, orgName, mobileOpen = false, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { navEntries } = usePluginRegistry(orgId ?? "");
  const { theme } = useTheme();
  const isPaperwork = theme === "paperwork";
  const isKarl = theme === "karl";
  const isWorkspacePath = pathname.startsWith(`/${orgSlug}/ai-workspace`) || pathname.startsWith(`/${orgSlug}/project`) || pathname.startsWith(`/${orgSlug}/stories`) || pathname.startsWith(`/${orgSlug}/docs`) || pathname.startsWith(`/${orgSlug}/nextcloud`) || pathname.startsWith(`/${orgSlug}/compliance`);
  const isSettingsPath = pathname.startsWith(`/${orgSlug}/settings`) || pathname.startsWith(`/${orgSlug}/workflows`);
  const searchParams = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
  const currentTab = searchParams?.get("tab") ?? "";
  const [workspaceManualOpen, setWorkspaceManualOpen] = useState(false);
  const [settingsManualOpen, setSettingsManualOpen] = useState(false);
  const workspaceOpen = isWorkspacePath || workspaceManualOpen;
  const settingsOpen = isSettingsPath || settingsManualOpen;

  // Check whether mail/calendar are configured (at least one connection exists)
  const { data: mailConnections } = useSWR<{ id: string }[]>(
    orgId ? `/api/v1/inbox/connections?org_id=${orgId}` : null,
    fetcher
  );
  const { data: calendarConnections } = useSWR<{ id: string }[]>(
    orgId ? `/api/v1/calendar/connections?org_id=${orgId}` : null,
    fetcher
  );
  const mailConfigured = (mailConnections?.length ?? 0) > 0;
  const calendarConfigured = (calendarConnections?.length ?? 0) > 0;

  // Level-1 nav (no Projekte, no User Stories — those are in workspace submenu)
  const navItems = [
    { id: "dashboard",    label: "Dashboard",   icon: LayoutDashboard, route: `/${orgSlug}/dashboard` },
    ...(mailConfigured
      ? [{ id: "inbox",    label: "Posteingang", icon: Inbox,        route: `/${orgSlug}/inbox` }]
      : []),
    ...(calendarConfigured
      ? [{ id: "calendar", label: "Kalender",    icon: CalendarDays, route: `/${orgSlug}/calendar` }]
      : []),
    ...(user?.is_superuser
      ? [{ id: "admin", label: "Admin", icon: Shield, route: `/${orgSlug}/admin` }]
      : []),
  ];

  // Workspace sub-items
  const workspaceSubItems = [
    { id: "ai-workspace", label: "Chat",          icon: MessageSquare, route: `/${orgSlug}/ai-workspace` },
    { id: "project",      label: "Projekte",      icon: Folder,        route: `/${orgSlug}/project` },
    { id: "stories",      label: "User Stories",  icon: BookOpen,      route: `/${orgSlug}/stories` },
    { id: "compliance",   label: "Compliance",    icon: ShieldCheck,   route: `/${orgSlug}/compliance` },
    { id: "dateien",      label: "Dateien",        icon: HardDrive,    route: `/${orgSlug}/nextcloud` },
    { id: "docs",         label: "Dokumentation", icon: FileText,      route: `/${orgSlug}/docs` },
  ];

  // Settings sub-items (deep-link via ?tab= param)
  const settingsSubItems = [
    { id: "settings-general",    label: "Organisation", icon: Settings,    route: `/${orgSlug}/settings?tab=general` },
    { id: "settings-user",       label: "Benutzer",    icon: Users,       route: `/${orgSlug}/settings?tab=user` },
    { id: "settings-email",      label: "E-Mail",      icon: Inbox,       route: `/${orgSlug}/settings?tab=email` },
    { id: "settings-calendar",   label: "Kalender",    icon: CalendarDays, route: `/${orgSlug}/settings?tab=calendar` },
    { id: "settings-jira",       label: "Jira",        icon: Zap,         route: `/${orgSlug}/settings?tab=jira` },
    { id: "settings-confluence", label: "Confluence",  icon: Globe,       route: `/${orgSlug}/settings?tab=confluence` },
    { id: "settings-ai",        label: "KI",          icon: Sparkles,    route: `/${orgSlug}/settings?tab=ai` },
    { id: "workflows",           label: "Workflows",   icon: Workflow,    route: `/${orgSlug}/workflows` },
  ];

  const paperworkSidebar = (
    <aside
      style={{ background: "var(--binding)", boxShadow: "1px 0 0 var(--sidebar-divider)", width: "var(--sidebar-width)", flexShrink: 0 }}
      className="flex flex-col h-full"
    >
      <div className="flex items-center justify-between px-4"
        style={{ height: "var(--topbar-height)", borderBottom: "1px solid var(--sidebar-divider)" }}>
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "var(--sidebar-org-text)" }}>
          {orgName ?? orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden p-1 rounded"
          style={{ color: "var(--sidebar-text)" }} aria-label="Schließen">
          <X size={14} />
        </button>
      </div>

      <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2 overflow-y-auto">
        {/* Dashboard */}
        {navItems.slice(0, 1).map(item => {
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

        {/* Workspace accordion */}
        <button onClick={() => setWorkspaceManualOpen(o => !o)}
          className="flex items-center gap-2.5 px-2 py-1.5 w-full transition-all sidebar-nav-item"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
            color: workspaceOpen ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
          <MessageSquare size={13} style={{ flexShrink: 0, opacity: workspaceOpen ? 1 : 0.6 }} />
          <span className="truncate flex-1 text-left">Workspace</span>
          <ChevronRight size={10} style={{ transition: "transform .15s", transform: workspaceOpen ? "rotate(90deg)" : "none", opacity: .5 }} />
        </button>
        {workspaceOpen && workspaceSubItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`flex items-center gap-2.5 pl-6 pr-2 py-1.5 transition-all sidebar-nav-item${isActive ? " is-active" : ""}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
                color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
              <Icon size={11} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.5 }} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}

        {/* Remaining level-1 items (Posteingang, Kalender, Dateien, Admin) */}
        {navItems.slice(1).map(item => {
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

        {/* Settings accordion */}
        <button onClick={() => setSettingsManualOpen(o => !o)}
          className="flex items-center gap-2.5 px-2 py-1.5 w-full transition-all sidebar-nav-item"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
            color: settingsOpen ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
          <Settings size={13} style={{ flexShrink: 0, opacity: settingsOpen ? 1 : 0.6 }} />
          <span className="truncate flex-1 text-left">Einstellungen</span>
          <ChevronRight size={10} style={{ transition: "transform .15s", transform: settingsOpen ? "rotate(90deg)" : "none", opacity: .5 }} />
        </button>
        {settingsOpen && settingsSubItems.map(item => {
          const [itemPath, itemQuery] = item.route.split("?");
          const itemTab = new URLSearchParams(itemQuery ?? "").get("tab") ?? "";
          const isActive = itemTab
            ? pathname === itemPath && currentTab === itemTab
            : pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`flex items-center gap-2.5 pl-6 pr-2 py-1.5 transition-all sidebar-nav-item${isActive ? " is-active" : ""}`}
              style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase",
                color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
              <Icon size={11} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.5 }} />
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

      <KarlWidget orgSlug={orgSlug} onMobileClose={onMobileClose} />

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
      <div className="relative p-5 pb-4 flex flex-col items-center gap-1.5 border-b-2 border-slate-900/5">
        <div className="karl-logo w-14 h-14 bg-amber-50 border-2 border-slate-900 rounded-xl shadow-[4px_4px_0_rgba(0,0,0,1)] overflow-hidden flex items-center justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
        </div>
        <span className="font-['Architects_Daughter'] text-lg text-slate-900 tracking-tight leading-none truncate max-w-[160px]">
          {user?.display_name ?? "Karl"}
        </span>
        <span className="text-[9px] font-bold tracking-[0.2em] text-slate-400 uppercase font-['Architects_Daughter'] truncate max-w-[160px]">
          {orgName ?? orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg border-2 border-transparent hover:border-slate-200" aria-label="Schließen">
          <X size={14} className="text-slate-500" />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 flex flex-col gap-0.5 overflow-y-auto">
        {/* Dashboard */}
        {navItems.slice(0, 1).map(item => {
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

        {/* Workspace accordion */}
        <button onClick={() => setWorkspaceManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all ${workspaceOpen ? "border-slate-900/15 bg-indigo-50" : "border-transparent"}`}>
            <MessageSquare size={14} strokeWidth={2.5} className={workspaceOpen ? "text-indigo-500" : "text-slate-400"} />
          </div>
          <span className={`text-[13px] font-bold font-['Architects_Daughter'] truncate flex-1 text-left ${workspaceOpen ? "text-slate-900" : "text-slate-500"}`}>
            Workspace
          </span>
          <ChevronRight size={12} className={`text-slate-400 transition-transform ${workspaceOpen ? "rotate-90" : ""}`} />
        </button>
        {workspaceOpen && workspaceSubItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          const colors = NAV_COLORS[item.id] ?? { icon: "text-slate-500", bg: "bg-slate-50" };
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full bg-slate-300 shrink-0" />
              <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all ${isActive ? "border-slate-900/15 " + colors.bg : "border-transparent"}`}>
                <Icon size={12} strokeWidth={2.5} className={isActive ? colors.icon : "text-slate-400"} />
              </div>
              <span className={`text-[12px] font-bold font-['Architects_Daughter'] truncate ${isActive ? "text-slate-900" : "text-slate-500"}`}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {/* Remaining level-1 items (Posteingang, Kalender, Dateien, Admin) */}
        {navItems.slice(1).map(item => {
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

        {/* Settings accordion */}
        <button onClick={() => setSettingsManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all ${settingsOpen ? "border-slate-900/15 bg-slate-50" : "border-transparent"}`}>
            <Settings size={14} strokeWidth={2.5} className={settingsOpen ? "text-slate-500" : "text-slate-400"} />
          </div>
          <span className={`text-[13px] font-bold font-['Architects_Daughter'] truncate flex-1 text-left ${settingsOpen ? "text-slate-900" : "text-slate-500"}`}>
            Einstellungen
          </span>
          <ChevronRight size={12} className={`text-slate-400 transition-transform ${settingsOpen ? "rotate-90" : ""}`} />
        </button>
        {settingsOpen && settingsSubItems.map(item => {
          const [itemPath, itemQuery] = item.route.split("?");
          const itemTab = new URLSearchParams(itemQuery ?? "").get("tab") ?? "";
          const isActive = itemTab
            ? pathname === itemPath && currentTab === itemTab
            : pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          const colors = NAV_COLORS[item.id] ?? { icon: "text-slate-500", bg: "bg-slate-50" };
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full bg-slate-300 shrink-0" />
              <div className={`w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all ${isActive ? "border-slate-900/15 " + colors.bg : "border-transparent"}`}>
                <Icon size={12} strokeWidth={2.5} className={isActive ? colors.icon : "text-slate-400"} />
              </div>
              <span className={`text-[12px] font-bold font-['Architects_Daughter'] truncate ${isActive ? "text-slate-900" : "text-slate-500"}`}>
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

      <KarlWidget orgSlug={orgSlug} onMobileClose={onMobileClose} />

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

  const karlSidebar = (
    <aside className="flex flex-col h-full shrink-0"
      style={{ width: "var(--sidebar-width)", background: "#FFFFFF", borderRight: "2px solid #0A0A0A" }}>

      {/* Brand */}
      <div className="relative p-5 pb-4 flex flex-col items-center gap-1.5"
        style={{ borderBottom: "2px solid #0A0A0A" }}>
        <div className="karl-logo w-14 h-14 border-2 rounded-xl overflow-hidden flex items-center justify-center"
          style={{ background: "#FFF5EE", borderColor: "#0A0A0A", boxShadow: "4px 4px 0 #0A0A0A" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
        </div>
        <span className="text-lg tracking-tight leading-none truncate max-w-[160px]"
          style={{ color: "#0A0A0A" }}>
          {user?.display_name ?? "Karl"}
        </span>
        <span className="text-[9px] font-bold tracking-[0.2em] uppercase truncate max-w-[160px]"
          style={{ color: "#6B6B6B" }}>
          {orgName ?? orgSlug}
        </span>
        <button onClick={onMobileClose} className="md:hidden absolute top-3 right-3 p-1.5 rounded-lg"
          style={{ border: "2px solid rgba(10,10,10,0.2)" }} aria-label="Schließen">
          <X size={14} style={{ color: "#6B6B6B" }} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 flex flex-col gap-0.5 overflow-y-auto">
        {navItems.slice(0, 1).map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        <button onClick={() => setWorkspaceManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
            style={{ borderColor: workspaceOpen ? "#0A0A0A" : "transparent", background: workspaceOpen ? "#EFF6FF" : "transparent" }}>
            <MessageSquare size={14} strokeWidth={2.5} style={{ color: workspaceOpen ? "#3B82F6" : "#6B6B6B" }} />
          </div>
          <span className="text-[13px] font-bold truncate flex-1 text-left"
            style={{ color: workspaceOpen ? "#0A0A0A" : "#3A3A3A" }}>
            Workspace
          </span>
          <ChevronRight size={12} style={{ color: "#A0A0A0", transition: "transform .15s", transform: workspaceOpen ? "rotate(90deg)" : "none" }} />
        </button>
        {workspaceOpen && workspaceSubItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full shrink-0" style={{ background: "#A0A0A0" }} />
              <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={12} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[12px] font-bold truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        {navItems.slice(1).map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2.5 px-3 py-2 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {item.label}
              </span>
            </Link>
          );
        })}

        <button onClick={() => setSettingsManualOpen(o => !o)}
          className="sidebar-nav-item flex items-center gap-2.5 px-3 py-2 w-full transition-all">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2 transition-all"
            style={{ borderColor: settingsOpen ? "#0A0A0A" : "transparent", background: settingsOpen ? "#F5F5F5" : "transparent" }}>
            <Settings size={14} strokeWidth={2.5} style={{ color: "#6B6B6B" }} />
          </div>
          <span className="text-[13px] font-bold truncate flex-1 text-left"
            style={{ color: settingsOpen ? "#0A0A0A" : "#3A3A3A" }}>
            Einstellungen
          </span>
          <ChevronRight size={12} style={{ color: "#A0A0A0", transition: "transform .15s", transform: settingsOpen ? "rotate(90deg)" : "none" }} />
        </button>
        {settingsOpen && settingsSubItems.map(item => {
          const [itemPath, itemQuery] = item.route.split("?");
          const itemTab = new URLSearchParams(itemQuery ?? "").get("tab") ?? "";
          const isActive = itemTab
            ? pathname === itemPath && currentTab === itemTab
            : pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link key={item.id} href={item.route} onClick={onMobileClose}
              className={`sidebar-nav-item flex items-center gap-2 pl-5 pr-3 py-1.5 transition-all${isActive ? " is-active" : ""}`}>
              <div className="w-1 h-1 rounded-full shrink-0" style={{ background: "#A0A0A0" }} />
              <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0 border-2 transition-all"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <Icon size={12} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[12px] font-bold truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
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
              <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 border-2"
                style={{ borderColor: isActive ? "#0A0A0A" : "transparent", background: isActive ? "#FFF5EE" : "transparent" }}>
                <PluginIcon size={14} strokeWidth={2.5} style={{ color: isActive ? "#FF5C00" : "#6B6B6B" }} />
              </div>
              <span className="text-[13px] font-bold truncate"
                style={{ color: isActive ? "#FFFFFF" : "#3A3A3A" }}>
                {entry.label}
              </span>
            </Link>
          );
        })}

        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      <KarlWidget orgSlug={orgSlug} onMobileClose={onMobileClose} />

      {user && (
        <div className="p-3 flex items-center gap-2.5" style={{ borderTop: "2px solid #0A0A0A" }}>
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: "rgba(255,92,0,0.1)", border: "2px solid #0A0A0A", boxShadow: "2px 2px 0 #0A0A0A" }}>
            <span className="text-[10px] font-bold" style={{ color: "#0A0A0A" }}>
              {user.display_name.slice(0, 2).toUpperCase()}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-[11px] font-bold" style={{ color: "#3A3A3A" }}>
              {user.display_name}
            </p>
          </div>
          <button onClick={() => void logout()}
            className="text-[10px] font-bold transition-colors"
            style={{ color: "#A0A0A0" }}>
            Logout
          </button>
        </div>
      )}
    </aside>
  );

  const sidebarContent = isPaperwork ? paperworkSidebar : isKarl ? karlSidebar : agileSidebar;

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
