"use client";

import { useEffect, useState } from "react";
import { fetchOrganizations } from "@/lib/api";
import type { OrgMetrics } from "@/types";

function UsageBar({ pct, warn }: { pct: number; warn: boolean }) {
  return (
    <div className="neo-progress">
      <div className={`neo-progress__bar${warn ? "" : " neo-progress__bar--teal"}`}
        style={{ width: `${Math.min(pct, 100)}%`, background: warn ? "var(--accent-red)" : undefined }} />
    </div>
  );
}

const PLAN_LABELS: Record<string, string> = { free: "Free", pro: "Pro", enterprise: "Enterprise" };

export default function ResourcesPage() {
  const [orgs, setOrgs] = useState<OrgMetrics[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganizations().then(setOrgs).catch(() => setError("Ressourcendaten konnten nicht geladen werden."));
  }, []);

  const totalWarnings = orgs?.filter((o) => o.warning).length ?? 0;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Ressourcen</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
            Nutzung je Organisation · Warnung ab 80 % Auslastung
          </p>
        </div>
        {totalWarnings > 0 && (
          <span className="badge-base" style={{ color: "var(--accent-red)", background: "rgba(var(--accent-red-rgb),.08)" }}>
            {totalWarnings} Warnung{totalWarnings > 1 ? "en" : ""}
          </span>
        )}
      </div>

      {error && (
        <div className="neo-card neo-card--orange p-4 text-sm" style={{ color: "var(--accent-red)" }}>{error}</div>
      )}

      {!orgs && !error && (
        <div className="flex items-center gap-2" style={{ color: "var(--ink-faint)" }}>
          <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
          <span className="text-sm">Lade Daten…</span>
        </div>
      )}

      {orgs && orgs.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Keine Organisationen vorhanden.</p>
      )}

      {orgs && orgs.length > 0 && (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table">
            <thead>
              <tr>
                {["Organisation", "Plan", "Status", "Mitglieder", "Stories", "Features", "Erstellt"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orgs.map((org) => (
                <tr key={org.id} style={{ background: org.warning ? "rgba(var(--accent-red-rgb),.03)" : "transparent" }}>
                  <td>
                    <div className="flex items-center gap-2">
                      {org.warning && <span title="Auslastung ≥ 80 %">⚠️</span>}
                      <div>
                        <div className="font-bold text-sm" style={{ color: "var(--ink)" }}>{org.name}</div>
                        <div className="text-xs" style={{ color: "var(--ink-faint)" }}>{org.slug}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className="badge-base" style={{ color: "var(--ink-mid)", background: "var(--paper-warm)", borderColor: "var(--paper-rule2)" }}>
                      {PLAN_LABELS[org.plan] ?? org.plan}
                    </span>
                  </td>
                  <td>
                    <span className="text-xs font-medium" style={{ color: org.is_active ? "var(--green)" : "var(--ink-faint)" }}>
                      {org.is_active ? "aktiv" : "inaktiv"}
                    </span>
                  </td>
                  <td className="min-w-[130px]">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs" style={{ color: "var(--ink-mid)" }}>
                        <span>{org.member_count}</span>
                        <span style={{ color: org.member_usage_pct >= 80 ? "var(--accent-red)" : "var(--ink-faint)" }}>
                          {org.member_limit < 9999 ? `/ ${org.member_limit} (${org.member_usage_pct}%)` : "∞"}
                        </span>
                      </div>
                      {org.member_limit < 9999 && <UsageBar pct={org.member_usage_pct} warn={org.member_usage_pct >= 80} />}
                    </div>
                  </td>
                  <td className="min-w-[130px]">
                    <div className="space-y-1">
                      <div className="flex justify-between text-xs" style={{ color: "var(--ink-mid)" }}>
                        <span>{org.story_count}</span>
                        <span style={{ color: org.story_usage_pct >= 80 ? "var(--accent-red)" : "var(--ink-faint)" }}>
                          {org.story_limit < 9999 ? `/ ${org.story_limit} (${org.story_usage_pct}%)` : "∞"}
                        </span>
                      </div>
                      {org.story_limit < 9999 && <UsageBar pct={org.story_usage_pct} warn={org.story_usage_pct >= 80} />}
                    </div>
                  </td>
                  <td className="text-xs font-medium" style={{ color: "var(--ink-mid)" }}>{org.feature_count}</td>
                  <td className="text-xs" style={{ color: "var(--ink-faint)" }}>
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
