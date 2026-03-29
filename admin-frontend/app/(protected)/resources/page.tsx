"use client";

import { useEffect, useState } from "react";
import { fetchOrganizations } from "@/lib/api";
import type { OrgMetrics } from "@/types";

function UsageBar({ pct, warn }: { pct: number; warn: boolean }) {
  const clamped = Math.min(pct, 100);
  return (
    <div
      className="w-full h-1.5 rounded-full"
      style={{ background: "var(--paper-rule)" }}
    >
      <div
        className="h-1.5 rounded-full transition-all"
        style={{
          width: `${clamped}%`,
          background: warn ? "var(--warn)" : "#526b5e",
        }}
      />
    </div>
  );
}

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  enterprise: "Enterprise",
};

export default function ResourcesPage() {
  const [orgs, setOrgs] = useState<OrgMetrics[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganizations()
      .then(setOrgs)
      .catch(() => setError("Ressourcendaten konnten nicht geladen werden."));
  }, []);

  const totalWarnings = orgs?.filter((o) => o.warning).length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>
            Ressourcenübersicht
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
            Nutzung je Organisation · Warnung ab 80 % Auslastung
          </p>
        </div>
        {totalWarnings > 0 && (
          <span
            className="text-xs px-3 py-1 rounded-full"
            style={{ background: "rgba(139,94,82,.1)", color: "var(--warn)" }}
          >
            {totalWarnings} Warnung{totalWarnings > 1 ? "en" : ""}
          </span>
        )}
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

      {!orgs && !error && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Lade Daten…</p>
      )}

      {orgs && orgs.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
          Keine Organisationen vorhanden.
        </p>
      )}

      {orgs && orgs.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr style={{ borderBottom: "1px solid var(--paper-rule)" }}>
                {["Organisation", "Plan", "Status", "Mitglieder", "Stories", "Features", "Erstellt"].map((h) => (
                  <th
                    key={h}
                    className="text-left py-2 pr-4 font-medium text-xs uppercase tracking-wide"
                    style={{ color: "var(--ink-faint)" }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orgs.map((org) => (
                <tr
                  key={org.id}
                  style={{
                    borderBottom: "1px solid var(--paper-rule)",
                    background: org.warning ? "rgba(139,94,82,.03)" : "transparent",
                  }}
                >
                  <td className="py-3 pr-4">
                    <div className="flex items-center gap-2">
                      {org.warning && <span title="Auslastung ≥ 80 %">⚠️</span>}
                      <div>
                        <div className="font-medium" style={{ color: "var(--ink)" }}>
                          {org.name}
                        </div>
                        <div className="text-xs" style={{ color: "var(--ink-faint)" }}>
                          {org.slug}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ background: "var(--paper-rule)", color: "var(--ink-mid)" }}
                    >
                      {PLAN_LABELS[org.plan] ?? org.plan}
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className="text-xs"
                      style={{ color: org.is_active ? "#526b5e" : "var(--ink-faint)" }}
                    >
                      {org.is_active ? "aktiv" : "inaktiv"}
                    </span>
                  </td>
                  <td className="py-3 pr-4 min-w-[120px]">
                    <div className="space-y-1">
                      <div
                        className="flex justify-between text-xs"
                        style={{ color: "var(--ink-mid)" }}
                      >
                        <span>{org.member_count}</span>
                        <span
                          style={{
                            color:
                              org.member_usage_pct >= 80
                                ? "var(--warn)"
                                : "var(--ink-faint)",
                          }}
                        >
                          {org.member_limit < 9999
                            ? `/ ${org.member_limit} (${org.member_usage_pct}%)`
                            : "unbegrenzt"}
                        </span>
                      </div>
                      {org.member_limit < 9999 && (
                        <UsageBar
                          pct={org.member_usage_pct}
                          warn={org.member_usage_pct >= 80}
                        />
                      )}
                    </div>
                  </td>
                  <td className="py-3 pr-4 min-w-[120px]">
                    <div className="space-y-1">
                      <div
                        className="flex justify-between text-xs"
                        style={{ color: "var(--ink-mid)" }}
                      >
                        <span>{org.story_count}</span>
                        <span
                          style={{
                            color:
                              org.story_usage_pct >= 80
                                ? "var(--warn)"
                                : "var(--ink-faint)",
                          }}
                        >
                          {org.story_limit < 9999
                            ? `/ ${org.story_limit} (${org.story_usage_pct}%)`
                            : "unbegrenzt"}
                        </span>
                      </div>
                      {org.story_limit < 9999 && (
                        <UsageBar
                          pct={org.story_usage_pct}
                          warn={org.story_usage_pct >= 80}
                        />
                      )}
                    </div>
                  </td>
                  <td
                    className="py-3 pr-4 text-xs"
                    style={{ color: "var(--ink-mid)" }}
                  >
                    {org.feature_count}
                  </td>
                  <td className="py-3 text-xs" style={{ color: "var(--ink-faint)" }}>
                    {new Date(org.created_at).toLocaleDateString("de-DE")}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
