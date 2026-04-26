"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listExternalSources, listChunks, getChunkStats, getRagStats,
  type ExternalSource, type ChunkBrowserResult, type RagStats,
} from "@/lib/api";

// ── Chunk browser ─────────────────────────────────────────────────────────────

function ChunkBrowser({ source }: { source: ExternalSource }) {
  const [result, setResult] = useState<ChunkBrowserResult | null>(null);
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const PAGE = 50;

  useEffect(() => {
    const t = setTimeout(() => { setDebouncedQ(q); setOffset(0); }, 400);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setLoading(true);
    listChunks(source.id, debouncedQ || undefined, PAGE, offset)
      .then(setResult)
      .finally(() => setLoading(false));
  }, [source.id, debouncedQ, offset]);

  const total = result?.total ?? 0;
  const pages = Math.ceil(total / PAGE);
  const currentPage = Math.floor(offset / PAGE) + 1;

  return (
    <div className="space-y-3">
      <div className="flex gap-2 items-center">
        <input
          className="flex-1 border rounded-md px-3 py-1.5 text-sm"
          placeholder="Volltext-Suche in Chunks…"
          value={q}
          onChange={e => setQ(e.target.value)}
        />
        {loading && <span className="text-xs text-gray-400">Lade…</span>}
        {result && (
          <span className="text-xs text-gray-500">
            {total.toLocaleString()} Chunk{total !== 1 ? "s" : ""}
            {debouncedQ ? ` (gefiltert)` : ""}
          </span>
        )}
      </div>

      {result && result.chunks.length === 0 && (
        <p className="text-xs text-gray-400 py-4 text-center">Keine Chunks gefunden.</p>
      )}

      {result && result.chunks.length > 0 && (
        <div className="border rounded-lg divide-y divide-gray-100 text-sm">
          {result.chunks.map(chunk => (
            <div key={chunk.id} className="px-4 py-3 space-y-1.5">
              <div className="flex items-start gap-2 justify-between">
                <div className="flex items-center gap-2 flex-wrap flex-1">
                  <span className="text-xs font-mono text-gray-400">#{chunk.chunk_index}</span>
                  {chunk.source_title && <span className="text-xs font-medium text-gray-700">{chunk.source_title}</span>}
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${chunk.has_embedding ? "bg-green-100 text-green-700" : "bg-red-100 text-red-600"}`}>
                    {chunk.has_embedding ? "Embedding OK" : "Kein Embedding"}
                  </span>
                  {chunk.is_global && <span className="text-xs bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded-full">global</span>}
                  <span className="text-xs text-gray-400">{chunk.chunk_text_length} Zeichen</span>
                </div>
                <button onClick={() => setExpanded(e => e === chunk.id ? null : chunk.id)}
                  className="text-xs text-blue-600 hover:underline shrink-0">
                  {expanded === chunk.id ? "Weniger" : "Text"}
                </button>
              </div>
              {chunk.source_url && (
                <a href={chunk.source_url} target="_blank" rel="noreferrer"
                  className="text-xs text-blue-500 hover:underline break-all">{chunk.source_url}</a>
              )}
              {expanded === chunk.id && (
                <pre className="text-xs bg-gray-50 border rounded p-3 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
                  {chunk.chunk_text}
                </pre>
              )}
              <p className="text-xs text-gray-400">
                Indiziert {new Date(chunk.created_at).toLocaleString("de-DE")} · ID {chunk.id.slice(0, 8)}…
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-between text-xs text-gray-500">
          <button disabled={offset === 0} onClick={() => setOffset(o => Math.max(0, o - PAGE))}
            className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">← Zurück</button>
          <span>Seite {currentPage} von {pages}</span>
          <button disabled={offset + PAGE >= total} onClick={() => setOffset(o => o + PAGE)}
            className="px-2 py-1 border rounded disabled:opacity-40 hover:bg-gray-50">Weiter →</button>
        </div>
      )}
    </div>
  );
}

// ── Coverage / embedding audit ────────────────────────────────────────────────

function CoverageAudit({ stats }: { stats: RagStats }) {
  const coveragePercent = stats.total_chunks > 0
    ? Math.round(stats.chunks_with_embedding / stats.total_chunks * 100)
    : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="bg-white border rounded-lg p-4">
          <p className="text-xs text-gray-500">Embedding-Coverage</p>
          <div className="mt-2 flex items-end gap-2">
            <span className="text-3xl font-bold">{coveragePercent}%</span>
          </div>
          <div className="mt-2 bg-gray-100 rounded-full h-2">
            <div className={`h-2 rounded-full ${coveragePercent >= 95 ? "bg-green-500" : coveragePercent >= 70 ? "bg-yellow-400" : "bg-red-400"}`}
              style={{ width: `${coveragePercent}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-1">
            {stats.chunks_with_embedding.toLocaleString()} / {stats.total_chunks.toLocaleString()} Chunks
          </p>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <p className="text-xs text-gray-500">Chunks ohne Embedding</p>
          <p className={`text-3xl font-bold mt-1 ${stats.chunks_missing_embedding > 0 ? "text-red-600" : "text-green-600"}`}>
            {stats.chunks_missing_embedding.toLocaleString()}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {stats.chunks_missing_embedding > 0
              ? "Diese Chunks werden bei RAG-Anfragen ignoriert"
              : "Alle Chunks sind eingebettet"}
          </p>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <p className="text-xs text-gray-500">Aktive Ingest-Jobs</p>
          <p className="text-3xl font-bold mt-1">{stats.running_runs + stats.pending_runs}</p>
          <p className="text-xs text-gray-400 mt-1">
            {stats.running_runs} laufend · {stats.pending_runs} ausstehend
          </p>
        </div>
      </div>

      <div className="bg-white border rounded-lg overflow-hidden">
        <div className="px-4 py-3 border-b bg-gray-50">
          <p className="text-sm font-medium">Chunk-Verteilung nach Quelle</p>
        </div>
        <div className="divide-y divide-gray-100">
          {stats.per_source.map(s => {
            const pct = stats.total_chunks > 0 ? s.chunk_count / stats.total_chunks : 0;
            return (
              <div key={s.id} className="px-4 py-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">{s.display_name}</span>
                    {!s.is_enabled && (
                      <span className="text-xs bg-red-50 text-red-600 px-1.5 py-0.5 rounded-full shrink-0">Deaktiviert</span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-gray-400">{s.source_key}</p>
                </div>
                <div className="w-40 bg-gray-100 rounded-full h-1.5 shrink-0">
                  <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${pct * 100}%` }} />
                </div>
                <span className="text-xs font-mono text-gray-600 w-16 text-right">
                  {s.chunk_count.toLocaleString()}
                </span>
              </div>
            );
          })}
          {stats.per_source.length === 0 && (
            <p className="px-4 py-4 text-sm text-gray-400">Noch keine Quellen mit Chunks.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IndexPage() {
  const [sources, setSources] = useState<ExternalSource[]>([]);
  const [stats, setStats] = useState<RagStats | null>(null);
  const [selectedSource, setSelectedSource] = useState<ExternalSource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<"browser" | "coverage">("coverage");

  async function load() {
    setLoading(true);
    try {
      setError(null);
      const [srcs, st] = await Promise.all([listExternalSources(), getRagStats().catch(() => null)]);
      setSources(srcs);
      if (st) setStats(st);
      if (srcs.length > 0 && !selectedSource) setSelectedSource(srcs[0]);
    } catch (e: any) { setError(e?.message || "Fehler"); }
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase — Index & Coverage</h1>
          <p className="text-sm text-gray-500 mt-1">Chunk-Browser, Embedding-Audit und Index-Coverage-Analyse</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/knowledge/help#index"
            className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe
          </Link>
          <button onClick={() => void load()} className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50">
            Neu laden
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200">
        {([["coverage", "Coverage & Audit"], ["browser", "Chunk-Browser"]] as const).map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === id ? "border-blue-500 text-blue-600" : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>{label}</button>
        ))}
      </div>

      {loading ? (
        <p className="text-gray-500 py-8 text-center">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
        </div>
      ) : tab === "coverage" ? (
        stats ? <CoverageAudit stats={stats} /> : <p className="text-gray-400 text-sm">Keine Statistiken verfügbar.</p>
      ) : (
        <div className="space-y-4">
          {/* Source selector */}
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-gray-600">Quelle:</label>
            <select
              className="border rounded-md px-3 py-1.5 text-sm"
              value={selectedSource?.id ?? ""}
              onChange={e => setSources(ss => {
                const s = ss.find(x => x.id === e.target.value);
                if (s) setSelectedSource(s);
                return ss;
              })}
            >
              {sources.map(s => (
                <option key={s.id} value={s.id}>{s.display_name} ({s.source_key})</option>
              ))}
            </select>
          </div>

          {selectedSource ? (
            <ChunkBrowser source={selectedSource} />
          ) : (
            <p className="text-gray-400 text-sm py-8 text-center">Keine Quellen vorhanden.</p>
          )}
        </div>
      )}
    </div>
  );
}
