"use client";

import { use, useState } from "react";
import { History, Filter } from "lucide-react";
import { useChangelog, type ChangeLogEntry } from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string }>;
}

const ACTION_CONFIG: Record<string, { label: string; color: string }> = {
  created:    { label: "Erstellt",        color: "bg-blue-100 text-blue-700" },
  updated:    { label: "Bearbeitet",      color: "bg-amber-100 text-amber-700" },
  published:  { label: "Veröffentlicht",  color: "bg-green-100 text-green-700" },
  archived:   { label: "Archiviert",      color: "bg-slate-100 text-slate-500" },
  deleted:    { label: "Gelöscht",        color: "bg-red-100 text-red-700" },
  duplicated: { label: "Dupliziert",      color: "bg-sky-100 text-sky-700" },
};

const ENTITY_TYPES = [
  { value: "", label: "Alle Entitäten" },
  { value: "control", label: "Controls" },
  { value: "gate", label: "Gates" },
  { value: "trigger", label: "Trigger" },
];

function ChangeRow({ entry }: { entry: ChangeLogEntry }) {
  const cfg = ACTION_CONFIG[entry.action] ?? { label: entry.action, color: "bg-slate-100 text-slate-700" };

  return (
    <div className="flex items-start gap-3 px-5 py-3 border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]">
      <div className="shrink-0 mt-0.5">
        <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cfg.color}`}>
          {cfg.label}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--ink-muted)] bg-[var(--bg-base)] px-1.5 py-0.5 rounded">
            {entry.entity_type}
          </span>
          <span className="text-sm font-medium text-[var(--ink-strong)] truncate">
            {entry.entity_slug}
          </span>
        </div>
        {(entry.from_version || entry.to_version) && (
          <p className="text-xs text-[var(--ink-muted)] mt-0.5">
            Version {entry.from_version ?? "–"} → {entry.to_version ?? "–"}
            {entry.from_status && <> · Status: {entry.from_status} → {entry.to_status}</>}
          </p>
        )}
        {entry.change_reason && (
          <p className="text-xs text-[var(--ink-muted)] mt-0.5 italic">"{entry.change_reason}"</p>
        )}
      </div>
      <div className="text-right shrink-0">
        <p className="text-xs font-medium text-[var(--ink-mid)]">{entry.actor_name}</p>
        <p className="text-xs text-[var(--ink-muted)]">
          {new Date(entry.occurred_at).toLocaleDateString("de-DE", {
            day: "2-digit", month: "2-digit", year: "numeric",
            hour: "2-digit", minute: "2-digit"
          })}
        </p>
      </div>
    </div>
  );
}

export default function HistoryPage({ params }: PageProps) {
  const { org } = use(params);
  const [entityType, setEntityType] = useState("");
  const [limit, setLimit] = useState(50);

  const { data, isLoading } = useChangelog({
    entity_type: entityType || undefined,
    limit,
  });

  const entries = data?.entries ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <History className="h-5 w-5 text-violet-500" />
            Änderungshistorie
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            Audit-Trail aller Konfigurationsänderungen
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-[var(--ink-muted)]" />
          <select
            value={entityType}
            onChange={e => setEntityType(e.target.value)}
            className="px-3 py-2 text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none"
          >
            {ENTITY_TYPES.map(et => (
              <option key={et.value} value={et.value}>{et.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-violet-500" />
          </div>
        ) : entries.length === 0 ? (
          <div className="text-center py-16">
            <History className="h-10 w-10 text-slate-200 mx-auto mb-3" />
            <p className="text-sm text-[var(--ink-muted)]">Keine Einträge gefunden.</p>
          </div>
        ) : (
          <>
            <div className="px-5 py-3 border-b border-[var(--border-subtle)] bg-[var(--bg-base)]">
              <p className="text-xs text-[var(--ink-muted)]">{entries.length} Einträge</p>
            </div>
            {entries.map((entry, i) => (
              <ChangeRow key={entry.id ?? i} entry={entry} />
            ))}
            {entries.length >= limit && (
              <div className="px-5 py-3 border-t border-[var(--border-subtle)] text-center">
                <button
                  onClick={() => setLimit(l => l + 50)}
                  className="text-sm text-violet-600 hover:underline"
                >
                  Weitere laden
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
