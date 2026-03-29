"use client";

import { useEffect, useState } from "react";
import { fetchComponentStatus } from "@/lib/api";
import type { ComponentStatus } from "@/types";

export default function DashboardPage() {
  const [components, setComponents] = useState<ComponentStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchComponentStatus()
      .then(setComponents)
      .catch(() => setError("Statusprüfung fehlgeschlagen."));

    const interval = setInterval(() => {
      fetchComponentStatus()
        .then(setComponents)
        .catch(() => {});
    }, 30_000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>
          Komponenten
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Status aller assist2-Dienste · wird alle 30 s aktualisiert
        </p>
      </div>

      {error && (
        <p
          className="text-sm p-3 rounded-sm border"
          style={{
            color: "var(--warn)",
            borderColor: "rgba(139,94,82,.3)",
            background: "rgba(139,94,82,.06)",
          }}
        >
          {error}
        </p>
      )}

      {!components && !error && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
          Prüfe Dienste…
        </p>
      )}

      {components && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {components.map((c) => (
            <div
              key={c.name}
              className="p-4 rounded-sm border"
              style={{
                borderColor: c.available ? "var(--paper-rule)" : "rgba(139,94,82,.3)",
                background: c.available ? "var(--paper-warm)" : "rgba(139,94,82,.04)",
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="text-sm font-medium"
                  style={{ color: "var(--ink)" }}
                >
                  {c.name}
                </span>
                <span
                  className="text-xs px-2 py-0.5 rounded-full"
                  style={{
                    background: c.available
                      ? "rgba(82,107,94,.1)"
                      : "rgba(139,94,82,.1)",
                    color: c.available ? "#526b5e" : "var(--warn)",
                  }}
                >
                  {c.available ? "verfügbar" : "nicht verfügbar"}
                </span>
              </div>
              <p className="text-xs mb-3" style={{ color: "var(--ink-faint)" }}>
                {c.label}
              </p>
              {c.available && c.admin_url && (
                <a
                  href={c.admin_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs underline"
                  style={{ color: "var(--ink-mid)" }}
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
