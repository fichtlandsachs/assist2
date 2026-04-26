"use client";

import { useState } from "react";
import useSWR from "swr";
import { ShieldCheck, AlertTriangle, CheckCircle2, Trash2, RefreshCw, Eye } from "lucide-react";
import { fetcher, authFetch } from "@/lib/api/client";

interface DeletedStoryStat {
  total_stories: number;
  deleted_stories: number;
  deleted_percentage: number;
  oldest_deletion: string | null;
  newest_deletion: string | null;
}

export default function DataIntegrityPage() {
  const [stats, setStats] = useState<DeletedStoryStat | null>(null);
  const [loading, setLoading] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purgeMsg, setPurgeMsg] = useState<string | null>(null);

  const loadStats = async () => {
    setLoading(true);
    try {
      const res = await authFetch("/api/v1/platform/integrity/story-stats");
      if (res.ok) setStats(await res.json());
    } finally { setLoading(false); }
  };

  const purgeOld = async (daysOld: number) => {
    if (!confirm(`Alle gelöschten User Stories älter als ${daysOld} Tage dauerhaft löschen?`)) return;
    setPurging(true);
    try {
      const res = await authFetch(`/api/v1/platform/integrity/purge-deleted-stories?days_old=${daysOld}`, {
        method: "DELETE",
      });
      if (res.ok) {
        const d = await res.json();
        setPurgeMsg(`${d.purged} Stories dauerhaft gelöscht`);
        await loadStats();
      }
    } finally { setPurging(false); }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-green-500" />
          Datenintegrität
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Soft-Delete-Kontrolle · Gelöschte User Stories verwalten
        </p>
      </div>

      {/* Guarantee panel */}
      <div className="bg-green-50 border border-green-200 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-2 text-green-800 font-semibold text-sm">
          <ShieldCheck className="h-5 w-5" />
          Datenintegritätsgarantien
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {[
            "Gelöschte Stories werden NIE in der UI angezeigt",
            "Keine Relation zu gelöschten Stories in Epics/Projekten",
            "Conversation Engine nutzt keine gelöschten Stories",
            "RAG-Kontext enthält keine gelöschten Stories",
            "Jira-Sync wird für gelöschte Stories blockiert",
            "Alle Queries filtern is_deleted = false",
            "Soft-Delete trackt: deleted_at, deleted_by_id",
            "Partialindex ix_user_stories_active sichert Performance",
          ].map((g, i) => (
            <div key={i} className="flex items-center gap-2 text-sm text-green-700">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-green-500" />
              {g}
            </div>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-subtle)]">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Soft-Delete Statistik</h2>
          <button onClick={loadStats} disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[var(--bg-hover)] hover:bg-[var(--border-subtle)] rounded-lg text-[var(--ink-mid)] disabled:opacity-60">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Statistik laden
          </button>
        </div>

        {stats ? (
          <div className="p-5 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Gesamt Stories", value: stats.total_stories, color: "text-[var(--ink-strong)]" },
                { label: "Gelöscht (soft)", value: stats.deleted_stories, color: "text-amber-600" },
                { label: "Gelöscht %", value: `${stats.deleted_percentage.toFixed(1)}%`, color: stats.deleted_percentage > 10 ? "text-red-600" : "text-green-600" },
                { label: "Aktiv", value: stats.total_stories - stats.deleted_stories, color: "text-green-600" },
              ].map(kpi => (
                <div key={kpi.label} className="bg-[var(--bg-base)] rounded-lg p-3 border border-[var(--border-subtle)]">
                  <p className="text-xs text-[var(--ink-muted)]">{kpi.label}</p>
                  <p className={`text-xl font-bold mt-1 ${kpi.color}`}>{kpi.value}</p>
                </div>
              ))}
            </div>

            {stats.deleted_stories > 0 && (
              <div className="flex items-center gap-2 text-xs text-[var(--ink-muted)]">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                Älteste Löschung: {stats.oldest_deletion ? new Date(stats.oldest_deletion).toLocaleString("de-DE") : "—"} ·
                Neueste: {stats.newest_deletion ? new Date(stats.newest_deletion).toLocaleString("de-DE") : "—"}
              </div>
            )}

            {/* Purge actions */}
            {stats.deleted_stories > 0 && (
              <div className="space-y-2">
                <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider">Dauerhaft löschen (Hard-Purge)</p>
                <div className="flex flex-wrap gap-2">
                  {[30, 90, 365].map(days => (
                    <button key={days} onClick={() => void purgeOld(days)} disabled={purging}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-red-50 text-red-700 border border-red-200 rounded-lg hover:bg-red-100 disabled:opacity-50">
                      <Trash2 className="h-3.5 w-3.5" />
                      Älter als {days} Tage
                    </button>
                  ))}
                </div>
                <p className="text-xs text-[var(--ink-muted)]">
                  ⚠ Diese Aktion löscht die Daten dauerhaft und ist nicht umkehrbar.
                </p>
              </div>
            )}
          </div>
        ) : (
          <div className="p-8 text-center text-[var(--ink-muted)] text-sm">
            Klicke "Statistik laden" um die aktuellen Werte abzurufen.
          </div>
        )}
      </div>

      {purgeMsg && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-800">
          <Trash2 className="h-4 w-4" /> {purgeMsg}
          <button onClick={() => setPurgeMsg(null)} className="ml-auto">×</button>
        </div>
      )}

      {/* Soft-delete rules documentation */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 space-y-3">
        <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Technische Umsetzung</h2>
        <div className="space-y-2 text-xs text-[var(--ink-muted)] font-mono bg-[var(--bg-base)] rounded-lg p-3">
          <p className="text-green-700 font-semibold"># user_stories Tabelle: Soft-Delete Felder</p>
          <p>is_deleted    BOOLEAN DEFAULT FALSE NOT NULL  -- Haupt-Filter</p>
          <p>deleted_at    TIMESTAMP WITH TIME ZONE NULL   -- Zeitstempel</p>
          <p>deleted_by_id UUID NULL REFERENCES users(id)  -- Verursacher</p>
          <p className="mt-2 text-violet-700 font-semibold"># Partial Index für Performance</p>
          <p>CREATE INDEX ix_user_stories_active</p>
          <p>  ON user_stories (organization_id, updated_at DESC)</p>
          <p>  WHERE is_deleted = false;</p>
          <p className="mt-2 text-blue-700 font-semibold"># Central Filter (app/core/story_filter.py)</p>
          <p>def active_stories():</p>
          <p>  return select(UserStory).where(UserStory.is_deleted == False)</p>
        </div>
      </div>
    </div>
  );
}
