"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { fetchOrganizations } from "@/lib/api";
import type { OrgMetrics } from "@/types";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [orgs, setOrgs] = useState<OrgMetrics[]>([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    fetchOrganizations().then(setOrgs).catch(() => {});
  }, []);

  const filtered = orgs.filter(
    (o) =>
      o.name.toLowerCase().includes(search.toLowerCase()) ||
      o.slug.toLowerCase().includes(search.toLowerCase())
  );

  const isSystem = pathname === "/settings/system" || pathname.startsWith("/settings/system");
  const activeSlug = pathname.startsWith("/settings/orgs/")
    ? pathname.split("/settings/orgs/")[1]?.split("/")[0]
    : null;

  return (
    <div className="flex flex-1 overflow-hidden" style={{ minHeight: 0 }}>
      {/* Sidebar */}
      <aside
        className="flex flex-col shrink-0 border-r overflow-y-auto"
        style={{
          width: 240,
          borderColor: "var(--paper-rule)",
          background: "var(--paper-warm)",
        }}
      >
        {/* System link */}
        <button
          onClick={() => router.push("/settings/system")}
          className="flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors text-left border-l-2"
          style={{
            borderLeftColor: isSystem ? "var(--accent-red)" : "transparent",
            background: isSystem ? "rgba(139,60,60,0.06)" : "transparent",
            color: isSystem ? "var(--accent-red)" : "var(--ink-mid)",
          }}
        >
          System
        </button>

        {/* Orgs section */}
        <div
          className="px-4 pt-4 pb-1 text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--ink-faint)" }}
        >
          Organisationen
        </div>

        <div className="px-3 pb-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Suchen…"
            className="w-full px-2 py-1.5 text-xs rounded-sm border outline-none"
            style={{
              borderColor: "var(--paper-rule)",
              background: "var(--card)",
              color: "var(--ink)",
            }}
          />
        </div>

        <div className="flex flex-col">
          {filtered.map((org) => {
            const isActive = activeSlug === org.slug;
            return (
              <button
                key={org.id}
                onClick={() => router.push(`/settings/orgs/${org.slug}`)}
                className="flex items-center gap-2 px-4 py-2 text-sm text-left transition-colors border-l-2"
                style={{
                  borderLeftColor: isActive ? "var(--accent-red)" : "transparent",
                  background: isActive ? "rgba(139,60,60,0.06)" : "transparent",
                  color: isActive ? "var(--accent-red)" : "var(--ink-mid)",
                }}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ background: org.is_active ? "#526b5e" : "var(--ink-faintest)" }}
                />
                <span className="truncate">{org.name}</span>
              </button>
            );
          })}
          {filtered.length === 0 && (
            <p className="px-4 py-2 text-xs" style={{ color: "var(--ink-faint)" }}>
              {search ? "Keine Treffer" : "Keine Organisationen"}
            </p>
          )}
        </div>
      </aside>

      {/* Content panel */}
      <main className="flex-1 overflow-y-auto p-6">{children}</main>
    </div>
  );
}
