"use client";

import { useEffect, useState } from "react";
import { fetchComponentStatus } from "@/lib/api";
import type { ComponentStatus } from "@/types";

export default function DashboardPage() {
  const [components, setComponents] = useState<ComponentStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchComponentStatus().then(setComponents).catch(() => setError("Statusprüfung fehlgeschlagen."));
    const interval = setInterval(() => {
      fetchComponentStatus().then(setComponents).catch(() => {});
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Komponenten</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Status aller Karl-Dienste · wird alle 30 s aktualisiert
        </p>
      </div>

      {error && (
        <div className="neo-card neo-card--orange p-4 text-sm" style={{ color: "var(--accent-red)" }}>
          {error}
        </div>
      )}

      {!components && !error && (
        <div className="flex items-center gap-2" style={{ color: "var(--ink-faint)" }}>
          <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
          <span className="text-sm">Prüfe Dienste…</span>
        </div>
      )}

      {components && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {components.map((c) => (
            <div key={c.name} className="neo-card p-5 flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <span className="text-sm font-bold" style={{ color: "var(--ink)" }}>{c.name}</span>
                <span
                  className="badge-base"
                  style={c.available
                    ? { color: "var(--green)", background: "rgba(16,185,129,.08)" }
                    : { color: "var(--accent-red)", background: "rgba(var(--accent-red-rgb),.08)" }
                  }
                >
                  {c.available ? "online" : "offline"}
                </span>
              </div>
              <p className="text-xs flex-1" style={{ color: "var(--ink-faint)" }}>{c.label}</p>
              {c.available && c.admin_url && (
                <a
                  href={c.admin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium"
                  style={{ color: "var(--accent-red)" }}
                >
                  Admin-Bereich öffnen →
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
