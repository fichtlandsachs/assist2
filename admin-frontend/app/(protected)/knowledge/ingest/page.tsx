"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listExternalSources, listRuns, listFailures, retryFailures, listPages,
  type ExternalSource, type ExternalSourceRun, type ExternalSourcePage,
} from "@/lib/api";

const STATUS_COLORS: Record<string, string> = {
  pending:   "bg-yellow-100 text-yellow-700",
  running:   "bg-blue-100 text-blue-700",
  done:      "bg-green-100 text-green-700",
  completed: "bg-green-100 text-green-700",
  failed:    "bg-red-100 text-red-700",
  partial:   "bg-orange-100 text-orange-700",
};

function StatusBadge({ status }: { status: string }) {
  const cls = STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600";
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>{status}</span>;
}

function fmt(dt: string | null) {
  if (!dt) return "—";
  return new Date(dt).toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function duration(start: string | null, end: string | null) {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

// ── Failure detail panel ──────────────────────────────────────────────────────

function FailuresPanel({ sourceId }: { sourceId: string }) {
  const [failures, setFailures] = useState<ExternalSourcePage[]>([]);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    listFailures(sourceId).then(setFailures).finally(() => setLoading(false));
  }, [sourceId]);

  async function retry() {
    setRetrying(true); setMsg(null);
    try {
      const r = await retryFailures(sourceId);
      setMsg(r.message);
    } catch (e: any) { setMsg(`Fehler: ${e?.message}`); }
    setRetrying(false);
  }

  if (loading) return <p className="text-xs text-gray-400 py-2">Lade Fehler…</p>;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-red-700">{failures.length} fehlgeschlagene Seiten</p>
        {failures.length > 0 && (
          <button onClick={retry} disabled={retrying}
            className="text-xs bg-red-50 text-red-700 border border-red-200 px-2 py-1 rounded hover:bg-red-100 disabled:opacity-50">
            {retrying ? "…" : "Alle erneut versuchen"}
          </button>
        )}
      </div>
      {msg && <p className="text-xs text-green-700">{msg}</p>}
      {failures.length > 0 && (
        <div className="max-h-48 overflow-y-auto border rounded divide-y divide-gray-100">
          {failures.slice(0, 50).map(p => (
            <div key={p.id} className="px-3 py-2">
              <p className="text-xs font-mono text-gray-700 truncate">{p.canonical_url}</p>
              {p.error_detail && <p className="text-xs text-red-500 mt-0.5">{p.error_detail}</p>}
              <p className="text-xs text-gray-400">HTTP {p.http_status ?? "?"} · {fmt(p.fetched_at)}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page coverage panel ───────────────────────────────────────────────────────

function CoveragePanel({ sourceId }: { sourceId: string }) {
  const [pages, setPages] = useState<ExternalSourcePage[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    listPages(sourceId, undefined, 200).then(setPages).finally(() => setLoading(false));
  }, [sourceId]);

  const counts: Record<string, number> = {};
  pages.forEach(p => { counts[p.status] = (counts[p.status] || 0) + 1; });

  const visible = filter === "all" ? pages : pages.filter(p => p.status === filter);

  if (loading) return <p className="text-xs text-gray-400 py-2">Lade Seiten…</p>;

  return (
    <div className="mt-3 space-y-2">
      <div className="flex gap-2 flex-wrap">
        {["all", ...Object.keys(counts)].map(s => (
          <button key={s} onClick={() => setFilter(s)}
            className={`text-xs px-2 py-0.5 rounded-full border ${filter === s ? "bg-gray-800 text-white border-gray-800" : "text-gray-600 hover:bg-gray-50"}`}>
            {s} ({s === "all" ? pages.length : counts[s]})
          </button>
        ))}
      </div>
      <div className="max-h-64 overflow-y-auto border rounded divide-y divide-gray-100 text-xs">
        {visible.slice(0, 200).map(p => (
          <div key={p.id} className="px-3 py-1.5 flex items-center gap-2">
            <StatusBadge status={p.status} />
            <a href={p.canonical_url} target="_blank" rel="noreferrer"
              className="font-mono text-blue-600 hover:underline truncate flex-1">{p.canonical_url}</a>
            <span className="text-gray-400 shrink-0">{fmt(p.fetched_at)}</span>
          </div>
        ))}
        {visible.length > 200 && <p className="px-3 py-2 text-gray-400">… und {visible.length - 200} weitere</p>}
      </div>
    </div>
  );
}

// ── Run card ──────────────────────────────────────────────────────────────────

function RunCard({ run }: { run: ExternalSourceRun }) {
  const stats = run.stats_json as Record<string, number>;
  return (
    <div className="border rounded-lg p-3 space-y-2">
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          <span className="text-sm font-medium capitalize">{run.run_type} Run</span>
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          <span>Start: {fmt(run.started_at)}</span>
          <span>Ende: {fmt(run.finished_at)}</span>
          <span>Dauer: {duration(run.started_at, run.finished_at)}</span>
        </div>
      </div>
      {Object.keys(stats).length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {Object.entries(stats).map(([k, v]) => (
            <div key={k} className="text-xs">
              <span className="text-gray-500">{k}:</span> <span className="font-medium">{v}</span>
            </div>
          ))}
        </div>
      )}
      {run.error_summary && (
        <div className="bg-red-50 border border-red-200 rounded p-2">
          <p className="text-xs text-red-700">{run.error_summary}</p>
        </div>
      )}
      <p className="text-xs text-gray-400">Ausgelöst von {run.triggered_by || "System"} · Run-ID: {run.id.slice(0, 8)}…</p>
    </div>
  );
}

// ── Source accordion ──────────────────────────────────────────────────────────

function SourceSection({ source }: { source: ExternalSource }) {
  const [open, setOpen] = useState(false);
  const [runs, setRuns] = useState<ExternalSourceRun[]>([]);
  const [runsLoading, setRunsLoading] = useState(false);
  const [tab, setTab] = useState<"runs" | "failures" | "coverage">("runs");

  async function loadRuns() {
    if (runs.length > 0) return;
    setRunsLoading(true);
    try { setRuns(await listRuns(source.id)); }
    catch { /* ignore */ }
    setRunsLoading(false);
  }

  function toggle() {
    if (!open) void loadRuns();
    setOpen(o => !o);
  }

  const lastRun = runs[0];
  const hasFailures = lastRun?.stats_json && (lastRun.stats_json as any).failed > 0;

  return (
    <div className="bg-white border rounded-lg overflow-hidden">
      <button onClick={toggle} className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium">{source.display_name}</span>
          <span className="text-xs font-mono text-gray-400">{source.source_key}</span>
          {lastRun && <StatusBadge status={lastRun.status} />}
          {hasFailures && <span className="text-xs text-red-600">⚠ Fehler</span>}
        </div>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t px-4 py-3">
          <div className="flex gap-3 border-b pb-2 mb-3">
            {(["runs", "failures", "coverage"] as const).map(t => (
              <button key={t} onClick={() => setTab(t)}
                className={`text-xs font-medium pb-1 border-b-2 ${tab === t ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500"}`}>
                {t === "runs" ? "Runs" : t === "failures" ? "Fehler" : "Seiten-Coverage"}
              </button>
            ))}
          </div>

          {tab === "runs" && (
            runsLoading ? <p className="text-xs text-gray-400">Lade…</p>
            : runs.length === 0 ? <p className="text-xs text-gray-400">Keine Runs.</p>
            : <div className="space-y-2">{runs.map(r => <RunCard key={r.id} run={r} />)}</div>
          )}
          {tab === "failures" && <FailuresPanel sourceId={source.id} />}
          {tab === "coverage" && <CoveragePanel sourceId={source.id} />}
        </div>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IngestPage() {
  const [sources, setSources] = useState<ExternalSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  async function load() {
    try {
      setError(null);
      setSources(await listExternalSources());
    } catch (e: any) { setError(e?.message || "Fehler"); }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    let iv: ReturnType<typeof setInterval> | null = null;
    if (autoRefresh) iv = setInterval(() => void load(), 10000);
    return () => { if (iv) clearInterval(iv); };
  }, [autoRefresh]);

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase — Ingest Monitor</h1>
          <p className="text-sm text-gray-500 mt-1">Crawl-Jobs, Runs, Fehler und Seiten-Coverage aller Quellen</p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/knowledge/help#ingest"
            className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe
          </Link>
          <label className="flex items-center gap-1.5 text-sm cursor-pointer">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            Auto-Refresh (10s)
          </label>
          <button onClick={() => void load()} className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50">
            Neu laden
          </button>
        </div>
      </div>

      {loading ? (
        <p className="text-gray-500 py-8 text-center">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
        </div>
      ) : sources.length === 0 ? (
        <p className="text-gray-400 text-sm py-10 text-center border rounded-lg bg-gray-50">
          Keine Quellen vorhanden. Zuerst eine Quelle unter "Wissensquellen" anlegen.
        </p>
      ) : (
        <div className="space-y-3">
          {sources.map(s => <SourceSection key={s.id} source={s} />)}
        </div>
      )}
    </div>
  );
}
