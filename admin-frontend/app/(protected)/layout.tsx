"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, logout } from "@/lib/auth";

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
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
        <p className="text-sm" style={{ color: "var(--ink-faint)", fontFamily: "var(--font-body)" }}>Lade…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ background: "var(--paper)" }}>
      {/* Header */}
      <header
        className="flex items-center justify-between px-6 py-3 border-b-2 shrink-0"
        style={{
          borderColor: "rgba(35,31,31,0.1)",
          background: "#FFFFFF",
          boxShadow: "0 2px 0 rgba(0,0,0,0.04)",
        }}
      >
        {/* Logo + wordmark */}
        <div className="flex items-center gap-3">
          <div
            className="flex items-center justify-center w-8 h-8 rounded-lg border-2 font-bold text-sm select-none"
            style={{
              background: "#231F1F",
              borderColor: "#231F1F",
              color: "#FFFFFF",
              fontFamily: "var(--font-serif)",
              boxShadow: "3px 3px 0 rgba(0,0,0,0.8)",
              fontStyle: "italic",
            }}
          >
            K
          </div>
          <div>
            <span
              className="text-sm font-semibold tracking-tight"
              style={{ fontFamily: "var(--font-serif)", color: "var(--ink)" }}
            >
              HeyKarl
            </span>
            <span
              className="ml-1.5 text-xs px-1.5 py-0.5 rounded border"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "9px",
                letterSpacing: ".06em",
                textTransform: "uppercase",
                color: "var(--ink-faint)",
                borderColor: "rgba(35,31,31,0.12)",
                background: "var(--paper-warm)",
              }}
            >
              Admin
            </span>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex items-center gap-1">
          {[
            { href: "/dashboard", label: "Komponenten" },
            { href: "/resources", label: "Ressourcen" },
            { href: "/settings/system", label: "Einstellungen" },
          ].map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className="px-3 py-1.5 text-xs rounded-lg border-2 transition-all"
              style={{
                fontFamily: "var(--font-mono)",
                letterSpacing: ".03em",
                color: "var(--ink-mid)",
                borderColor: "transparent",
                textDecoration: "none",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.borderColor = "rgba(35,31,31,0.12)";
                (e.currentTarget as HTMLAnchorElement).style.background = "var(--paper-warm)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLAnchorElement).style.borderColor = "transparent";
                (e.currentTarget as HTMLAnchorElement).style.background = "transparent";
              }}
            >
              {label}
            </a>
          ))}

          <button
            onClick={logout}
            className="ml-2 px-3 py-1.5 text-xs rounded-lg border-2 transition-all"
            style={{
              fontFamily: "var(--font-mono)",
              letterSpacing: ".03em",
              color: "var(--ink-faint)",
              borderColor: "rgba(35,31,31,0.1)",
              background: "transparent",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "rgba(35,31,31,0.2)";
              e.currentTarget.style.color = "var(--ink)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = "rgba(35,31,31,0.1)";
              e.currentTarget.style.color = "var(--ink-faint)";
            }}
          >
            Abmelden
          </button>
        </nav>
      </header>

      <main className="flex-1 flex flex-col p-6 max-w-5xl mx-auto w-full">{children}</main>
    </div>
  );
}
