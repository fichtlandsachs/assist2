"use client";

import Link from "next/link";
import {
  LayoutDashboard,
  FileText,
  ShieldCheck,
  Activity,
  GitBranch,
  ArrowDownToLine,
  ArrowUpFromLine,
  LayoutTemplate,
  Settings,
  LogOut,
  ChevronRight,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

/* ── Types ───────────────────────────────────────────────────────── */
interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ size?: number | string; className?: string }>;
  badge?: string | number;
  badgeVariant?: "orange" | "teal" | "yellow";
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

/* ── Nav config ──────────────────────────────────────────────────── */
const navGroups: NavGroup[] = [
  {
    heading: "Hauptmenü",
    items: [
      {
        label: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
      },
      {
        label: "Dokumente",
        href: "/documents",
        icon: FileText,
        badge: 3,
        badgeVariant: "orange",
      },
      {
        label: "Compliance",
        href: "/compliance",
        icon: ShieldCheck,
      },
      {
        label: "BCM",
        href: "/bcm",
        icon: Activity,
      },
      {
        label: "Diagramme",
        href: "/diagrams",
        icon: GitBranch,
      },
    ],
  },
  {
    heading: "Integrationen",
    items: [
      {
        label: "Jira Import",
        href: "/jira",
        icon: ArrowDownToLine,
      },
      {
        label: "Confluence Export",
        href: "/confluence",
        icon: ArrowUpFromLine,
      },
    ],
  },
  {
    heading: "System",
    items: [
      {
        label: "Templates",
        href: "/templates",
        icon: LayoutTemplate,
      },
      {
        label: "Einstellungen",
        href: "/settings",
        icon: Settings,
      },
    ],
  },
];

/* ── NavLink ─────────────────────────────────────────────────────── */
function NavLink({
  item,
  active,
}: {
  item: NavItem;
  active: boolean;
}) {
  const badgeColorMap = {
    orange: "bg-[#FF5C00] text-[#0A0A0A]",
    teal: "bg-[#00D4AA] text-[#0A0A0A]",
    yellow: "bg-[#FFD700] text-[#0A0A0A]",
  };

  return (
    <Link
      href={item.href}
      className={cn(
        "sidebar-link",
        active && "sidebar-link--active"
      )}
    >
      <item.icon
        size={18}
        className={cn(
          "flex-shrink-0",
          active ? "text-[#0A0A0A]" : "text-[#6B6B6B]"
        )}
      />
      <span className="flex-1 truncate">{item.label}</span>
      {item.badge !== undefined && (
        <span
          className={cn(
            "inline-flex items-center justify-center",
            "min-w-[1.25rem] h-5 px-1",
            "text-[0.625rem] font-heading font-700",
            "border border-[#0A0A0A]",
            item.badgeVariant
              ? badgeColorMap[item.badgeVariant]
              : "bg-[#0A0A0A] text-white"
          )}
        >
          {item.badge}
        </span>
      )}
      {active && (
        <ChevronRight size={14} className="flex-shrink-0 text-[#0A0A0A]" />
      )}
    </Link>
  );
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
interface SidebarProps {
  activePath?: string;
}

export function Sidebar({ activePath = "" }: SidebarProps) {
  return (
    <aside
      className="fixed left-0 top-0 bottom-0 w-sidebar bg-white border-r-2 border-[#0A0A0A] flex flex-col z-40 overflow-y-auto"
      style={{ width: "var(--sidebar-width)" }}
    >
      {/* Logo ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-4 py-4 border-b-2 border-[#0A0A0A] flex-shrink-0">
        <div className="w-8 h-8 bg-[#FF5C00] border-2 border-[#0A0A0A] flex items-center justify-center shadow-[2px_2px_0px_#0A0A0A]">
          <Zap size={16} className="text-[#0A0A0A]" />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="font-heading font-800 text-[1.05rem] text-[#0A0A0A] tracking-tight">
            assist<span className="text-[#FF5C00]">2</span>
          </span>
          <span className="text-[0.55rem] font-heading font-700 text-[#6B6B6B] uppercase tracking-widest leading-none">
            BCM Platform
          </span>
        </div>
      </div>

      {/* Nav groups ───────────────────────────────────────────── */}
      <nav className="flex-1 py-3 overflow-y-auto">
        {navGroups.map((group, gi) => (
          <div key={group.heading} className={cn(gi > 0 && "mt-1")}>
            {/* Group heading */}
            <div className="px-4 pt-4 pb-1.5">
              <span className="text-[0.625rem] font-heading font-700 text-[#6B6B6B] uppercase tracking-[0.1em]">
                {group.heading}
              </span>
            </div>

            {/* Items */}
            <div className="space-y-0.5 px-2">
              {group.items.map((item) => {
                const isActive =
                  activePath === item.href ||
                  (item.href !== "/dashboard" &&
                    activePath.startsWith(item.href));
                return (
                  <NavLink key={item.href} item={item} active={isActive} />
                );
              })}
            </div>

            {/* Divider after each group except last */}
            {gi < navGroups.length - 1 && (
              <div className="mx-4 mt-3 border-t border-[rgba(10,10,10,0.1)]" />
            )}
          </div>
        ))}
      </nav>

      {/* Compliance score strip ───────────────────────────────── */}
      <div className="mx-3 mb-3 p-3 bg-[#F5F0E8] border-2 border-[#0A0A0A] flex-shrink-0">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-heading font-600 text-[#0A0A0A]">
            Compliance Score
          </span>
          <span className="text-xs font-heading font-800 text-[#FF5C00]">
            67%
          </span>
        </div>
        <div className="neo-progress">
          <div className="neo-progress__bar" style={{ width: "67%" }} />
        </div>
        <div className="text-[0.625rem] text-[#6B6B6B] mt-1.5">
          8 offene Punkte · NIS2
        </div>
      </div>

      {/* User footer ──────────────────────────────────────────── */}
      <div className="border-t-2 border-[#0A0A0A] p-3 flex-shrink-0">
        <div className="flex items-center gap-3">
          {/* Avatar */}
          <div className="w-9 h-9 bg-[#FFD700] border-2 border-[#0A0A0A] flex items-center justify-center flex-shrink-0 font-heading font-800 text-sm text-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A]">
            SM
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-heading font-600 text-sm truncate">
              Sarah Müller
            </div>
            <div className="text-xs text-[#6B6B6B] truncate">
              Admin
            </div>
          </div>
          <button
            className="w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center hover:bg-[#F5F0E8] transition-colors flex-shrink-0"
            title="Abmelden"
          >
            <LogOut size={14} className="text-[#6B6B6B]" />
          </button>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;
