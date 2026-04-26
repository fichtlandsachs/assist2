"use client";

import { usePathname, useRouter } from "next/navigation";

const NAV = [
  { label: "Plan-Limits", href: "/accounting/plan-limits" },
];

export default function AccountingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-3xl font-black" style={{ color: "var(--ink)" }}>Accounting</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Plan-Konfiguration und Nutzungsgrenzen
        </p>
      </div>

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

      <div>{children}</div>
    </div>
  );
}
