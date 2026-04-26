"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchOrganizations, fetchUsersWithOrgs } from "@/lib/api";
import type { OrgMetrics, UserWithOrgs } from "@/types";

type TabId = "usage" | "assignments";

function UsageBar({ pct, warn }: { pct: number; warn: boolean }) {
  return (
    <div className="neo-progress">
      <div
        className={`neo-progress__bar${warn ? "" : " neo-progress__bar--teal"}`}
        style={{ width: `${Math.min(pct, 100)}%`, background: warn ? "var(--accent-red)" : undefined }}
      />
    </div>
  );
}

const PLAN_LABELS: Record<string, string> = { free: "Free", pro: "Pro", enterprise: "Enterprise" };

/* ── Tab: Auslastung ──────────────────────────────────────────────────────── */
function UsageTab() {
  const [orgs, setOrgs] = useState<OrgMetrics[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchOrganizations().then(setOrgs).catch(() => setError("Ressourcendaten konnten nicht geladen werden."));
  }, []);

  const totalWarnings = orgs?.filter((o) => o.warning).length ?? 0;

  return (
    <div className="space-y-4">
      {totalWarnings > 0 && (
        <span className="badge-base" style={{ color: "var(--accent-red)", background: "rgba(var(--accent-red-rgb),.08)" }}>
          {totalWarnings} Warnung{totalWarnings > 1 ? "en" : ""}
        </span>
      )}

      {error && (
        <div className="neo-card neo-card--orange p-4 text-sm" style={{ color: "var(--accent-red)" }}>{error}</div>
      )}

      {!orgs && !error && <Spinner />}

      {orgs && orgs.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>Keine Organisationen vorhanden.</p>
      )}

      {orgs && orgs.length > 0 && (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table">
            <thead>
              <tr>
                {["Organisation", "Plan", "Status", "Mitglieder", "Stories", "Features", "Letzte Anmeldung", "Letzter Nutzer", "Erstellt"].map((h) => (
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
                  <td className="text-xs" style={{ color: org.last_login_at ? "var(--ink-mid)" : "var(--ink-faint)" }}>
                    {org.last_login_at
                      ? new Date(org.last_login_at).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })
                      : "—"}
                  </td>
                  <td className="text-xs" style={{ color: org.last_active_user ? "var(--ink-mid)" : "var(--ink-faint)" }}>
                    {org.last_active_user ?? "—"}
                  </td>
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

/* ── Tab: Zuordnungen ─────────────────────────────────────────────────────── */
function AssignmentsTab() {
  const [users, setUsers] = useState<UserWithOrgs[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");

  const load = useCallback((q: string) => {
    setUsers(null);
    setError(null);
    fetchUsersWithOrgs(q || undefined)
      .then(setUsers)
      .catch(() => setError("Nutzerdaten konnten nicht geladen werden."));
  }, []);

  useEffect(() => { load(""); }, [load]);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setQuery(search);
    load(search);
  }

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="flex gap-2 max-w-sm">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="E-Mail oder Name…"
          className="neo-input flex-1 text-sm"
        />
        <button type="submit" className="neo-btn neo-btn--sm">Suchen</button>
      </form>

      {error && (
        <div className="neo-card neo-card--orange p-4 text-sm" style={{ color: "var(--accent-red)" }}>{error}</div>
      )}

      {!users && !error && <Spinner />}

      {users && users.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
          {query ? `Keine Nutzer für „${query}" gefunden.` : "Keine Nutzer vorhanden."}
        </p>
      )}

      {users && users.length > 0 && (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table">
            <thead>
              <tr>
                {["Nutzer", "E-Mail", "Status", "Workspaces", "Registriert"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                        style={{ background: "var(--paper-rule2)", color: "var(--ink-mid)" }}>
                        {u.display_name?.[0]?.toUpperCase() ?? "?"}
                      </div>
                      <div>
                        <div className="text-sm font-medium" style={{ color: "var(--ink)" }}>{u.display_name}</div>
                        {u.is_superuser && (
                          <div className="text-xs" style={{ color: "var(--accent-orange)" }}>Superuser</div>
                        )}
                      </div>
                    </div>
                  </td>
                  <td className="text-xs" style={{ color: "var(--ink-mid)" }}>{u.email}</td>
                  <td>
                    <span className="text-xs font-medium" style={{ color: u.is_active ? "var(--green)" : "var(--ink-faint)" }}>
                      {u.is_active ? "aktiv" : "inaktiv"}
                    </span>
                  </td>
                  <td>
                    {u.organizations.length === 0 ? (
                      <span className="text-xs" style={{ color: "var(--ink-faint)" }}>—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {u.organizations.map((org) => (
                          <span key={org.id} className="badge-base text-xs"
                            style={{ color: "var(--ink-mid)", background: "var(--paper-warm)", borderColor: "var(--paper-rule2)" }}
                            title={org.slug}>
                            {org.name}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="text-xs" style={{ color: "var(--ink-faint)" }}>
                    {new Date(u.created_at).toLocaleDateString("de-DE")}
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

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function Spinner() {
  return (
    <div className="flex items-center gap-2" style={{ color: "var(--ink-faint)" }}>
      <div className="w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
      <span className="text-sm">Lade Daten…</span>
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────────────────── */
const TABS: { id: TabId; label: string }[] = [
  { id: "usage",       label: "Auslastung" },
  { id: "assignments", label: "Nutzer & Workspaces" },
];

export default function ResourcesPage() {
  const [tab, setTab] = useState<TabId>("usage");

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Ressourcen</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Nutzung und Zuordnungen je Organisation
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b-2" style={{ borderColor: "var(--paper-rule2)" }}>
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className="px-4 py-2 text-sm font-medium transition-colors"
            style={{
              color: tab === id ? "var(--ink)" : "var(--ink-faint)",
              borderBottom: tab === id ? "2px solid var(--accent-orange)" : "2px solid transparent",
              marginBottom: "-2px",
              background: "transparent",
              cursor: "pointer",
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "usage"       && <UsageTab />}
      {tab === "assignments" && <AssignmentsTab />}
    </div>
  );
}
