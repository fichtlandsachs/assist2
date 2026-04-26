"use client";

import { useState } from "react";
import { use } from "react";
import Link from "next/link";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import { useOrg } from "@/lib/hooks/useOrg";
import {
  Shield, AlertTriangle, CheckCircle2, Clock,
  ArrowUpRight, TrendingDown,
} from "lucide-react";

interface Props {
  params: Promise<{ org: string }>;
}

interface AssessmentRow {
  id: string;
  object_type: string;
  object_id: string;
  object_name: string;
  compliance_status: string;
  traffic_light: string;
  overall_score: number | null;
  total_controls: number;
  hard_stop_critical: number;
  not_assessed_controls: number;
  updated_at: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string }> = {
  compliant:           { label: "Compliant",              color: "bg-green-100 text-green-800" },
  partially_compliant: { label: "Eingeschränkt",          color: "bg-amber-100 text-amber-800" },
  non_compliant:       { label: "Nicht Compliant",        color: "bg-red-100 text-red-800"     },
  not_assessed:        { label: "Nicht bewertet",         color: "bg-slate-100 text-slate-600" },
};

const TL_DOT: Record<string, string> = {
  green:  "bg-green-500",
  yellow: "bg-amber-500",
  red:    "bg-red-500",
  grey:   "bg-slate-300",
};

export default function AdminCompliancePage({ params }: Props) {
  const { org: orgSlug } = use(params);
  const { org } = useOrg(orgSlug);
  const [search, setSearch] = useState("");

  const { data: assessments, isLoading } = useSWR<AssessmentRow[]>(
    org ? `/api/v1/compliance/assessments?org_id=${org.id}` : null,
    fetcher,
    { revalidateOnFocus: false }
  );

  const filtered = (assessments ?? []).filter(a =>
    !search || a.object_name.toLowerCase().includes(search.toLowerCase())
  );

  const totalCompliant    = (assessments ?? []).filter(a => a.compliance_status === "compliant").length;
  const totalNonCompliant = (assessments ?? []).filter(a => a.compliance_status === "non_compliant").length;
  const totalCriticalHS   = (assessments ?? []).reduce((s, a) => s + (a.hard_stop_critical ?? 0), 0);
  const totalNotAssessed  = (assessments ?? []).filter(a => a.compliance_status === "not_assessed").length;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink-strong)]">Compliance-Übersicht</h1>
        <p className="text-sm text-[var(--ink-muted)] mt-1">
          Alle aktiven Compliance-Bewertungen auf Projekt- und Produktebene.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Compliant", value: totalCompliant, icon: CheckCircle2, color: "bg-green-100 text-green-600" },
          { label: "Nicht Compliant", value: totalNonCompliant, icon: TrendingDown, color: "bg-red-100 text-red-600", highlight: totalNonCompliant > 0 },
          { label: "Hard-Stop kritisch", value: totalCriticalHS, icon: AlertTriangle, color: "bg-red-100 text-red-600", highlight: totalCriticalHS > 0 },
          { label: "Nicht bewertet", value: totalNotAssessed, icon: Clock, color: "bg-slate-100 text-slate-500" },
        ].map(({ label, value, icon: Icon, color, highlight }) => (
          <div key={label} className={`flex items-center gap-3 p-4 rounded-xl border ${highlight ? "border-red-200 bg-red-50" : "border-[var(--border-subtle)] bg-[var(--bg-card)]"}`}>
            <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <p className="text-xl font-bold text-[var(--ink-strong)]">{value}</p>
              <p className="text-xs text-[var(--ink-muted)]">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Search */}
      <input
        type="text" placeholder="Objekt suchen…" value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full max-w-xs px-3 py-2 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
      />

      {/* Table */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-[var(--bg-base)] border-b border-[var(--border-subtle)]">
            <tr>
              {["Objekt", "Typ", "Status", "Score", "Controls", "Hard-Stops", "Zuletzt"].map(h => (
                <th key={h} className="text-left px-4 py-2.5 text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wide">{h}</th>
              ))}
              <th />
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr><td colSpan={8} className="text-center py-8 text-[var(--ink-muted)] text-sm">Lade…</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-8 text-[var(--ink-muted)] text-sm">
                {search ? "Keine Treffer." : "Noch keine Bewertungen vorhanden."}
              </td></tr>
            ) : (
              filtered.map(a => {
                const cfg = STATUS_CONFIG[a.compliance_status] ?? STATUS_CONFIG.not_assessed;
                const dot = TL_DOT[a.traffic_light] ?? TL_DOT.grey;
                return (
                  <tr key={a.id} className="border-b border-[var(--border-subtle)] hover:bg-[var(--bg-hover)]">
                    <td className="px-4 py-3 font-medium text-[var(--ink-strong)]">{a.object_name}</td>
                    <td className="px-4 py-3 text-xs text-[var(--ink-muted)]">
                      {a.object_type === "project" ? "Projekt" : a.object_type === "product" ? "Produkt" : a.object_type}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${dot}`} />
                        <span className={`px-2 py-0.5 rounded text-xs font-medium ${cfg.color}`}>{cfg.label}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">
                      {a.overall_score !== null ? a.overall_score : "–"}
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--ink-muted)]">{a.total_controls}</td>
                    <td className="px-4 py-3">
                      {a.hard_stop_critical > 0 ? (
                        <span className="flex items-center gap-1 text-red-600 text-sm font-medium">
                          <AlertTriangle className="h-3.5 w-3.5" /> {a.hard_stop_critical}
                        </span>
                      ) : (
                        <span className="text-sm text-[var(--ink-muted)]">0</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--ink-muted)]">
                      {new Date(a.updated_at).toLocaleDateString("de-DE")}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/${orgSlug}/${a.object_type}/${a.object_id}`}
                        className="flex items-center gap-1 text-xs text-violet-600 hover:underline">
                        Ansehen <ArrowUpRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
