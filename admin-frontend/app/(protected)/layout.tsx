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
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header
        className="flex items-center justify-between px-6 py-3 border-b"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}
      >
        <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
          assist2 Admin
        </span>
        <nav className="flex items-center gap-6">
          <a
            href="/dashboard"
            className="text-sm transition-colors hover:underline"
            style={{ color: "var(--ink-mid)" }}
          >
            Komponenten
          </a>
          <a
            href="/resources"
            className="text-sm transition-colors hover:underline"
            style={{ color: "var(--ink-mid)" }}
          >
            Ressourcen
          </a>
          <a
            href="/settings/system"
            className="text-sm transition-colors hover:underline"
            style={{ color: "var(--ink-mid)" }}
          >
            Einstellungen
          </a>
          <button
            onClick={logout}
            className="text-sm px-3 py-1 rounded-sm border transition-colors hover:bg-[var(--paper-warm)]"
            style={{ borderColor: "var(--paper-rule)", color: "var(--ink-faint)" }}
          >
            Abmelden
          </button>
        </nav>
      </header>
      <main className="flex-1 p-6 max-w-5xl mx-auto w-full">{children}</main>
    </div>
  );
}
