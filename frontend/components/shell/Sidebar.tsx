"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Settings, BookOpen, Inbox, CalendarDays, FileText,
  Workflow, Folder, Globe, Bell, Star, Zap, Users, Shield, MessageSquare,
  X, type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth/context";
import { usePluginRegistry } from "@/lib/plugins/registry";
import { SlotRenderer } from "@/lib/plugins/slots";

const PLUGIN_ICONS: Record<string, LucideIcon> = {
  folder: Folder, globe: Globe, bell: Bell, star: Star,
  zap: Zap, users: Users, file: FileText, workflow: Workflow,
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

  const navItems = [
    { id: "dashboard",    label: "Dashboard",      icon: LayoutDashboard, route: `/${orgSlug}/dashboard` },
    { id: "ai-workspace", label: "KI Workspace",   icon: MessageSquare,   route: `/${orgSlug}/ai-workspace` },
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

  const sidebarContent = (
    <aside
      style={{
        background: "var(--binding)",
        boxShadow: "1px 0 0 var(--sidebar-divider)",
        width: "200px",
        flexShrink: 0,
      }}
      className="flex flex-col h-full"
    >
      {/* Org header */}
      <div
        className="flex items-center justify-between px-4"
        style={{ height: "var(--topbar-height)", borderBottom: "1px solid var(--sidebar-divider)" }}
      >
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "var(--sidebar-org-text)" }}>
          {orgSlug}
        </span>
        <button
          onClick={onMobileClose}
          className="md:hidden p-1 rounded"
          style={{ color: "rgba(255,255,255,.4)" }}
          aria-label="Sidebar schließen"
        >
          <X size={14} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.id}
              href={item.route}
              onClick={onMobileClose}
              className="flex items-center gap-2.5 px-2 py-1.5 rounded-sm transition-all"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "9px",
                letterSpacing: ".08em",
                textTransform: "uppercase",
                color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                background: isActive ? "var(--sidebar-text-active-bg)" : "transparent",
                borderLeft: isActive ? `2px solid var(--sidebar-active-border)` : "2px solid transparent",
              }}
            >
              <Icon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}

        {/* Plugin nav entries */}
        {navEntries
          .filter(entry => entry.slot === "sidebar_main")
          .map(entry => {
            const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
            const route = `/${orgSlug}${entry.route}`;
            const isActive = pathname === route;
            return (
              <Link
                key={entry.id}
                href={route}
                onClick={onMobileClose}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-sm transition-all"
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "9px",
                  letterSpacing: ".08em",
                  textTransform: "uppercase",
                  color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)",
                  background: isActive ? "var(--sidebar-text-active-bg)" : "transparent",
                  borderLeft: isActive ? `2px solid var(--sidebar-active-border)` : "2px solid transparent",
                }}
              >
                <PluginIcon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
                <span className="truncate">{entry.label}</span>
              </Link>
            );
          })}

        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      {/* User footer */}
      {user && (
        <div
          className="px-3 py-3 flex items-center gap-2"
          style={{ borderTop: "1px solid var(--sidebar-divider)" }}
        >
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            style={{
              background: "var(--sidebar-avatar-bg)",
              fontFamily: "var(--font-mono)", fontSize: "8px",
              color: "var(--sidebar-avatar-text)",
            }}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate" style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--sidebar-user-text)", letterSpacing: ".04em" }}>
              {user.display_name}
            </p>
          </div>
          <button
            onClick={() => void logout()}
            style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--sidebar-logout-text)", letterSpacing: ".04em" }}
          >
            Logout
          </button>
        </div>
      )}
    </aside>
  );

  return (
    <>
      {/* Desktop */}
      <div className="hidden md:flex shrink-0">{sidebarContent}</div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={onMobileClose} aria-hidden="true" />
          <div className="relative z-10 flex shrink-0">{sidebarContent}</div>
        </div>
      )}
    </>
  );
}
