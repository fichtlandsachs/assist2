"use client";

import { usePathname, useRouter } from "next/navigation";

const NAV = [
  { label: "System",       href: "/settings/system" },
  { label: "Organisation", href: "/settings/organisation" },
];

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="space-y-6 max-w-3xl">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-black" style={{ color: "var(--ink)" }}>Einstellungen</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Globale Konfiguration und Organisations-Integrationen
        </p>
      </div>

      {/* Sub-nav tabs */}
      <div className="flex gap-2">
        {NAV.map(({ label, href }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <button
              key={href}
              onClick={() => router.push(href)}
              className={`neo-btn ${active ? "neo-btn--default" : "neo-btn--outline"}`}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      <div>{children}</div>
    </div>
  );
}
