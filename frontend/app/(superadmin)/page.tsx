"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import { CheckCircle, XCircle, ExternalLink, Users, Building2, BookOpen } from "lucide-react";

interface ComponentStatus {
  name: string;
  label: string;
  available: boolean;
  admin_url: string;
}

interface OrgMetric {
  id: string;
  name: string;
  member_count: number;
  story_count: number;
  is_active: boolean;
  warning: boolean;
}

function StatCard({ label, value, Icon }: { label: string; value: number | string; Icon: React.ElementType }) {
  return (
    <div
      className="flex items-center gap-4 p-4 rounded-sm border"
      style={{ background: "var(--card)", borderColor: "var(--paper-rule)" }}
    >
      <div className="p-2 rounded bg-[var(--paper-warm)] border border-[var(--paper-rule)]">
        <Icon size={16} className="text-[var(--ink-mid)]" />
      </div>
      <div>
        <p className="text-xs text-[var(--ink-faint)]">{label}</p>
        <p className="text-xl font-semibold text-[var(--ink)]">{value}</p>
      </div>
    </div>
  );
}

export default function SuperadminDashboard() {
  const { data: status } = useSWR<ComponentStatus[]>("/api/v1/superadmin/status", fetcher);
  const { data: orgsData } = useSWR<{ items: OrgMetric[]; total: number }>("/api/v1/superadmin/organizations?page_size=1000", fetcher);
  const { data: users } = useSWR<{ total: number }>("/api/v1/superadmin/users?page_size=1", fetcher);

  const orgs = orgsData?.items ?? [];
  const activeOrgs = orgs.filter((o) => o.is_active).length;
  const totalStories = orgs.reduce((sum, o) => sum + o.story_count, 0);

  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-8">
      <h1 className="text-lg font-semibold text-[var(--ink)]">System-Übersicht</h1>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Benutzer gesamt" value={users?.total ?? "…"} Icon={Users} />
        <StatCard label="Aktive Orgs" value={activeOrgs} Icon={Building2} />
        <StatCard label="Stories gesamt" value={totalStories} Icon={BookOpen} />
      </div>

      <div>
        <h2 className="text-sm font-semibold text-[var(--ink)] mb-3">Komponenten-Status</h2>
        <div className="border border-[var(--paper-rule)] rounded-sm overflow-hidden">
          {!status ? (
            <div className="px-4 py-6 text-sm text-center text-[var(--ink-faint)]">Lade…</div>
          ) : (
            status.map((c) => (
              <div
                key={c.name}
                className="flex items-center justify-between px-4 py-2.5 border-b border-[var(--paper-rule)] last:border-0 hover:bg-[var(--paper-warm)]"
              >
                <div className="flex items-center gap-2.5">
                  {c.available ? (
                    <CheckCircle size={14} className="text-[var(--green)] flex-shrink-0" />
                  ) : (
                    <XCircle size={14} className="text-red-500 flex-shrink-0" />
                  )}
                  <span className="text-sm text-[var(--ink)]">{c.name}</span>
                  <span className="text-xs text-[var(--ink-faint)]">{c.label}</span>
                </div>
                <a
                  href={c.admin_url}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center gap-1 text-xs text-[var(--ink-faint)] hover:text-[var(--ink)]"
                >
                  Admin <ExternalLink size={10} />
                </a>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
