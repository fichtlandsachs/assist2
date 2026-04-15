"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth/context";
import { LayoutDashboard, Users, Building2, Settings2 } from "lucide-react";
import Link from "next/link";

const NAV = [
  { label: "Dashboard",      href: "/superadmin",                Icon: LayoutDashboard },
  { label: "Benutzer",       href: "/superadmin/users",          Icon: Users },
  { label: "Organisationen", href: "/superadmin/organizations",  Icon: Building2 },
  { label: "Einstellungen",  href: "/superadmin/settings",       Icon: Settings2 },
];

export default function SuperadminLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && (!user || !user.is_superuser)) {
      router.replace("/");
    }
  }, [user, isLoading, router]);

  if (isLoading || !user?.is_superuser) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--paper)" }}>
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--paper)" }}>
      {/* Sidebar */}
      <aside
        className="w-52 flex-shrink-0 border-r flex flex-col py-6 px-3"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
      >
        <div className="px-2 mb-6">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--ink-faint)]">Superadmin</p>
        </div>
        <nav className="flex-1 space-y-0.5">
          {NAV.map(({ label, href, Icon }) => {
            const active = pathname === href || (href !== "/superadmin" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`sidebar-nav-item flex items-center gap-2.5 px-2 py-2 text-sm transition-colors${active ? " is-active" : ""}`}
                style={{ color: active ? "var(--sidebar-text-active)" : "var(--ink-mid)" }}
              >
                <Icon size={14} />
                {label}
              </Link>
            );
          })}
        </nav>
        <div className="px-2 pt-4 border-t border-[var(--paper-rule)]">
          <p className="text-xs text-[var(--ink-faint)] truncate">{user.email}</p>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto">
        {children}
      </main>
    </div>
  );
}
