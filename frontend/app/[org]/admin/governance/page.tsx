"use client";

import { use, useState } from "react";
import Link from "next/link";
import {
  Shield, Lock, Plus, Zap, AlertTriangle,
  FileX, Clock, CheckCircle2, RefreshCw, ArrowRight,
} from "lucide-react";
import { useGovernanceOverview, runSeed } from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string }>;
}

function StatCard({
  label, value, icon: Icon, color, href, org,
}: {
  label: string;
  value: number | string;
  icon: React.ElementType;
  color: string;
  href?: string;
  org: string;
}) {
  const card = (
    <div className={`bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 flex items-center gap-4 ${href ? "hover:border-violet-300 transition-colors cursor-pointer" : ""}`}>
      <div className={`w-11 h-11 rounded-lg flex items-center justify-center ${color}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <p className="text-2xl font-bold text-[var(--ink-strong)]">{value}</p>
        <p className="text-sm text-[var(--ink-muted)]">{label}</p>
      </div>
      {href && <ArrowRight className="h-4 w-4 text-[var(--ink-muted)] ml-auto" />}
    </div>
  );
  if (href) return <Link href={`/${org}/admin/governance${href}`}>{card}</Link>;
  return card;
}

function ActionBadge({ text, variant }: { text: string; variant: "red" | "amber" | "blue" | "green" }) {
  const cls = {
    red:   "bg-red-50 text-red-700 border-red-200",
    amber: "bg-amber-50 text-amber-700 border-amber-200",
    blue:  "bg-blue-50 text-blue-700 border-blue-200",
    green: "bg-green-50 text-green-700 border-green-200",
  }[variant];
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${cls}`}>
      {text}
    </span>
  );
}

const ACTION_LABELS: Record<string, { label: string; variant: "red" | "amber" | "blue" | "green" }> = {
  created:    { label: "Erstellt",        variant: "blue"  },
  updated:    { label: "Bearbeitet",      variant: "amber" },
  published:  { label: "Veröffentlicht",  variant: "green" },
  archived:   { label: "Archiviert",      variant: "red"   },
  deleted:    { label: "Gelöscht",        variant: "red"   },
  duplicated: { label: "Dupliziert",      variant: "blue"  },
};

export default function GovernanceDashboard({ params }: PageProps) {
  const { org } = use(params);
  const { data: overview, isLoading, mutate } = useGovernanceOverview();
  const [seeding, setSeeding] = useState(false);
  const [seedMsg, setSeedMsg] = useState<string | null>(null);

  const handleSeed = async () => {
    setSeeding(true);
    setSeedMsg(null);
    try {
      await runSeed();
      setSeedMsg("Seed-Daten erfolgreich geladen.");
      mutate();
    } catch {
      setSeedMsg("Fehler beim Laden der Seed-Daten.");
    } finally {
      setSeeding(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-violet-500" />
      </div>
    );
  }

  const ov = overview;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <Shield className="h-6 w-6 text-violet-500" />
            Product Governance
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-1">
            Konfigurationszentrale für das Produktprüfmodell — Controls, Gates, Trigger, Scoring
          </p>
        </div>
        <button
          onClick={handleSeed}
          disabled={seeding}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-violet-50 text-violet-700 border border-violet-200 hover:bg-violet-100 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 ${seeding ? "animate-spin" : ""}`} />
          Seed-Daten laden
        </button>
      </div>

      {seedMsg && (
        <div className={`p-3 rounded-lg text-sm ${seedMsg.includes("Fehler") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {seedMsg}
        </div>
      )}

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Feste Controls" value={ov?.fixed_controls ?? 0}
          icon={Lock} color="bg-slate-100 text-slate-600"
          href="/controls?kind=fixed" org={org}
        />
        <StatCard
          label="Zusatz-Controls" value={ov?.dynamic_controls ?? 0}
          icon={Plus} color="bg-violet-100 text-violet-600"
          href="/controls?kind=dynamic" org={org}
        />
        <StatCard
          label="Aktive Trigger" value={ov?.active_triggers ?? 0}
          icon={Zap} color="bg-amber-100 text-amber-600"
          href="/triggers" org={org}
        />
        <StatCard
          label="Hard-Stop Controls" value={ov?.hard_stop_controls ?? 0}
          icon={AlertTriangle} color="bg-red-100 text-red-600"
          org={org}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard
          label="Ohne Nachweis" value={ov?.controls_without_evidence ?? 0}
          icon={FileX} color="bg-orange-100 text-orange-600" org={org}
        />
        <StatCard
          label="Im Entwurf" value={ov?.draft_controls ?? 0}
          icon={Clock} color="bg-sky-100 text-sky-600" org={org}
        />
        <StatCard
          label="In Prüfung" value={ov?.review_controls ?? 0}
          icon={CheckCircle2} color="bg-teal-100 text-teal-600" org={org}
        />
      </div>

      {/* Alerts */}
      {(ov?.draft_controls ?? 0) > 0 && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 border border-amber-200">
          <Clock className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800">
              {ov?.draft_controls} Control{ov?.draft_controls !== 1 ? "s" : ""} im Entwurfsstatus
            </p>
            <p className="text-xs text-amber-700 mt-0.5">
              Entwürfe sind noch nicht veröffentlicht und in keinem Gate aktiv.
              <Link href={`/${org}/admin/governance/controls?status_filter=draft`} className="ml-1 underline">
                Anzeigen →
              </Link>
            </p>
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: "Neues Control anlegen",  desc: "Zusätzliches Control erstellen", href: "/controls/new", color: "bg-violet-500" },
          { label: "Trigger konfigurieren",  desc: "Trigger-Regeln verwalten",       href: "/triggers",     color: "bg-amber-500" },
          { label: "Simulation ausführen",   desc: "Prüfmodell testen",              href: "/simulation",   color: "bg-teal-500"  },
        ].map(({ label, desc, href, color }) => (
          <Link key={href} href={`/${org}/admin/governance${href}`}>
            <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 hover:border-violet-300 transition-colors group">
              <div className={`w-8 h-8 rounded-md ${color} flex items-center justify-center mb-3`}>
                <ArrowRight className="h-4 w-4 text-white" />
              </div>
              <p className="text-sm font-semibold text-[var(--ink-strong)] group-hover:text-violet-700">{label}</p>
              <p className="text-xs text-[var(--ink-muted)] mt-0.5">{desc}</p>
            </div>
          </Link>
        ))}
      </div>

      {/* Recent Changes */}
      {(ov?.recent_changes?.length ?? 0) > 0 && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
          <div className="px-5 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
            <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Letzte Änderungen</h2>
            <Link href={`/${org}/admin/governance/history`} className="text-xs text-violet-600 hover:underline">
              Alle anzeigen →
            </Link>
          </div>
          <div className="divide-y divide-[var(--border-subtle)]">
            {ov?.recent_changes.slice(0, 8).map((entry, i) => {
              const badge = ACTION_LABELS[entry.action] ?? { label: entry.action, variant: "blue" as const };
              return (
                <div key={i} className="px-5 py-3 flex items-center gap-3">
                  <ActionBadge text={badge.label} variant={badge.variant} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[var(--ink-strong)] truncate">
                      <span className="text-[var(--ink-muted)] text-xs mr-1">[{entry.entity_type}]</span>
                      {entry.entity_slug}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs text-[var(--ink-muted)]">{entry.actor_name}</p>
                    <p className="text-xs text-[var(--ink-muted)]">
                      {new Date(entry.occurred_at).toLocaleDateString("de-DE")}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!ov || (ov.fixed_controls === 0 && ov.dynamic_controls === 0) && (
        <div className="text-center py-16 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
          <Shield className="h-12 w-12 text-[var(--ink-muted)] mx-auto mb-4" />
          <p className="text-[var(--ink-strong)] font-medium">Noch keine Governance-Daten</p>
          <p className="text-sm text-[var(--ink-muted)] mt-1 mb-4">
            Lade die Seed-Daten um Basiskonfiguration zu initialisieren.
          </p>
          <button
            onClick={handleSeed}
            disabled={seeding}
            className="px-4 py-2 bg-violet-600 text-white rounded-lg text-sm hover:bg-violet-700 transition-colors"
          >
            Seed-Daten laden
          </button>
        </div>
      )}
    </div>
  );
}
