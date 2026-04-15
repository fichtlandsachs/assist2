"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getSession, logout } from "@/lib/auth";

const NAV = [
  {
    label: "Komponenten",
    href: "/dashboard",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
        <rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
      </svg>
    ),
  },
  {
    label: "Ressourcen",
    href: "/resources",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="3" width="20" height="4" rx="1"/><rect x="2" y="10" width="20" height="4" rx="1"/>
        <rect x="2" y="17" width="20" height="4" rx="1"/>
        <circle cx="18" cy="5" r="1" fill="currentColor" stroke="none"/>
        <circle cx="18" cy="12" r="1" fill="currentColor" stroke="none"/>
        <circle cx="18" cy="19" r="1" fill="currentColor" stroke="none"/>
      </svg>
    ),
  },
  {
    label: "Einstellungen",
    href: "/settings/system",
    matchPrefix: "/settings",
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
    ),
  },
];

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
    } else {
      setChecked(true);
    }
  }, [router]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--paper)" }}>
        <div className="w-4 h-4 rounded-full border-2 border-[var(--accent-red)] border-t-transparent animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen" style={{ background: "var(--paper)" }}>
      {/* Karl sidebar */}
      <aside
        className="w-52 flex-shrink-0 border-r flex flex-col py-6 px-3"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
      >
        {/* Logo */}
        <div className="px-2 mb-6 flex items-center gap-2.5">
          <div
            className="flex items-center justify-center w-7 h-7 rounded-lg border-2 font-bold text-xs select-none flex-shrink-0"
            style={{
              background: "#231F1F",
              borderColor: "#231F1F",
              color: "#FFFFFF",
              fontFamily: "var(--font-serif)",
              boxShadow: "2px 2px 0 rgba(0,0,0,0.8)",
              fontStyle: "italic",
            }}
          >
            K
          </div>
          <div>
            <p className="text-xs font-bold tracking-widest uppercase" style={{ color: "var(--ink-faint)", letterSpacing: "0.15em" }}>
              Admin
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 space-y-0.5">
          {NAV.map(({ label, href, matchPrefix, icon }) => {
            const active = pathname === href || pathname.startsWith(matchPrefix ?? href + "/");
            return (
              <button
                key={href}
                onClick={() => router.push(href)}
                className={`sidebar-nav-item w-full flex items-center gap-2.5 px-2 py-2 text-left${active ? " is-active" : ""}`}
                style={{ color: active ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}
              >
                {icon}
                {label}
              </button>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-2 pt-4 border-t" style={{ borderColor: "var(--paper-rule)" }}>
          <button
            onClick={logout}
            className="text-xs w-full text-left transition-colors"
            style={{ color: "var(--ink-faint)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--ink)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--ink-faint)")}
          >
            Abmelden
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto p-8">
        {children}
      </main>
    </div>
  );
}
