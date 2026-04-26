"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { use } from "react";
import {
  LayoutDashboard, Shield, Plus, Zap, GitMerge,
  FileCheck, BarChart3, History, PlayCircle, Lock, MessageSquare, Layers,
} from "lucide-react";

interface GovernanceLayoutProps {
  children: React.ReactNode;
  params: Promise<{ org: string }>;
}

const NAV = [
  { label: "Übersicht",         icon: LayoutDashboard, path: ""                   },
  { label: "Controls (gruppiert)", icon: Layers,       path: "/controls"              },
  { label: "Feste Controls",    icon: Lock,            path: "/controls?kind=fixed"   },
  { label: "Zusatz-Controls",   icon: Plus,            path: "/controls?kind=dynamic" },
  { label: "Trigger-Regeln",    icon: Zap,             path: "/triggers"          },
  { label: "Gate-Modelle",      icon: GitMerge,        path: "/gates"             },
  { label: "Nachweis-Katalog",  icon: FileCheck,       path: "/evidence"          },
  { label: "Scoring",           icon: BarChart3,       path: "/scoring"           },
  { label: "Simulation",        icon: PlayCircle,      path: "/simulation"        },
  { label: "Chat-Fragen",       icon: MessageSquare,   path: "/chat-questions"    },
  { label: "Änderungshistorie", icon: History,         path: "/history"           },
];

export default function GovernanceLayout({ children, params }: GovernanceLayoutProps) {
  const { org } = use(params);
  const pathname = usePathname();
  const base = `/${org}/admin/governance`;

  return (
    <div className="flex min-h-screen bg-[var(--bg-base)]">
      {/* Side Navigation */}
      <aside className="w-60 shrink-0 border-r border-[var(--border-subtle)] bg-[var(--bg-card)] flex flex-col">
        {/* Header */}
        <div className="px-4 py-5 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-violet-500 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-[var(--ink-strong)]">Product Governance</p>
              <p className="text-xs text-[var(--ink-muted)]">Control Management</p>
            </div>
          </div>
        </div>

        {/* Nav Items */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {NAV.map(({ label, icon: Icon, path }) => {
            const href = `${base}${path}`;
            const isActive = path === ""
              ? pathname === base
              : pathname.startsWith(`${base}${path.split("?")[0]}`);

            return (
              <Link
                key={path}
                href={href}
                className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-violet-50 text-violet-700 font-medium dark:bg-violet-900/20 dark:text-violet-300"
                    : "text-[var(--ink-mid)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink-strong)]"
                }`}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-[var(--border-subtle)]">
          <Link
            href={`/${org}/admin`}
            className="flex items-center gap-2 px-3 py-2 rounded-md text-xs text-[var(--ink-muted)] hover:text-[var(--ink-mid)] transition-colors"
          >
            ← Zurück zum Admin
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
