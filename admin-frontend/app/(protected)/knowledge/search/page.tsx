"use client";

import { useState } from "react";
import Link from "next/link";
import { searchTest, type SearchTestResult } from "@/lib/api";

const TRUST_COLORS: Record<string, string> = {
  V5: "bg-purple-100 text-purple-700",
  V4: "bg-blue-100 text-blue-700",
  V3: "bg-green-100 text-green-700",
  V2: "bg-yellow-100 text-yellow-700",
  V1: "bg-gray-100 text-gray-600",
};

const MODE_LABEL: Record<string, { label: string; cls: string }> = {
  direct:  { label: "Direct Answer", cls: "bg-green-100 text-green-800" },
  context: { label: "Context Match", cls: "bg-blue-100 text-blue-800" },
  none:    { label: "Kein Treffer", cls: "bg-gray-100 text-gray-600" },
};

function ScoreBar({ label, value, color = "bg-blue-500" }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-24 text-gray-500 shrink-0">{label}</span>
      <div className="flex-1 bg-gray-100 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${Math.min(value * 100, 100)}%` }} />
      </div>
      <span className="font-mono w-10 text-right text-gray-700">{value.toFixed(3)}</span>
    </div>
  );
}

function ChunkCard({ chunk, index, isHybrid }: {
  chunk: SearchTestResult["chunks"][number];
  index: number;
  isHybrid: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const trustCls = chunk.trust_class ? TRUST_COLORS[chunk.trust_class] ?? "bg-gray-100 text-gray-600" : "";

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="flex items-start justify-between gap-3 px-4 py-3 bg-gray-50">
        <div className="flex items-center gap-2 flex-wrap flex-1">
          <span className="text-sm font-bold text-gray-500">#{index + 1}</span>
          {isHybrid ? (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              (chunk.final_score ?? 0) >= 0.7 ? "bg-green-100 text-green-700" :
              (chunk.final_score ?? 0) >= 0.4 ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"
            }`}>Score {chunk.final_score?.toFixed(3)}</span>
          ) : (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              (chunk.score ?? 0) >= 0.7 ? "bg-green-100 text-green-700" :
              (chunk.score ?? 0) >= 0.5 ? "bg-blue-100 text-blue-700" : "bg-gray-100 text-gray-600"
            }`}>Score {chunk.score?.toFixed(3)}</span>
          )}
          {chunk.trust_class && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${trustCls}`}>{chunk.trust_class}</span>
          )}
          {chunk.evidence_type && (
            <span className={`text-xs px-2 py-0.5 rounded-full ${
              chunk.evidence_type === "primary" ? "bg-purple-50 text-purple-700" : "bg-gray-50 text-gray-600"
            }`}>{chunk.evidence_type}</span>
          )}
          {chunk.is_global && <span className="text-xs bg-orange-50 text-orange-600 px-2 py-0.5 rounded-full">global</span>}
          {chunk.chunk_type && <span className="text-xs text-gray-400">{chunk.chunk_type}</span>}
        </div>
        <button onClick={() => setExpanded(e => !e)} className="text-xs text-blue-600 hover:underline shrink-0">
          {expanded ? "Weniger" : "Details"}
        </button>
      </div>

      <div className="px-4 py-3 space-y-3">
        {chunk.source_title && <p className="text-sm font-medium text-gray-800">{chunk.source_title}</p>}
        {chunk.source_url && (
          <a href={chunk.source_url} target="_blank" rel="noreferrer"
            className="text-xs text-blue-600 hover:underline break-all">{chunk.source_url}</a>
        )}
        <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{chunk.text}</p>

        {expanded && isHybrid && (
          <div className="border-t pt-3 space-y-2">
            <p className="text-xs font-medium text-gray-600 mb-2">Score-Aufschlüsselung</p>
            {chunk.semantic_score !== undefined && <ScoreBar label="Semantic" value={chunk.semantic_score} color="bg-blue-500" />}
            {chunk.bm25_score !== undefined && <ScoreBar label="BM25 (Keyword)" value={chunk.bm25_score} color="bg-teal-500" />}
            {chunk.final_score !== undefined && <ScoreBar label="Final (RRF)" value={chunk.final_score} color="bg-purple-500" />}
            {chunk.trust_score !== undefined && <ScoreBar label="Trust" value={chunk.trust_score} color="bg-orange-400" />}
            <div className="flex gap-3 flex-wrap text-xs text-gray-500 mt-1">
              {chunk.source_system && <span>System: <span className="text-gray-700">{chunk.source_system}</span></span>}
              {chunk.indexed_at && <span>Indiziert: <span className="text-gray-700">{new Date(chunk.indexed_at).toLocaleDateString("de-DE")}</span></span>}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function SearchTestPage() {
  const [query, setQuery] = useState("");
  const [orgId, setOrgId] = useState("");
  const [useHybrid, setUseHybrid] = useState(true);
  const [minScore, setMinScore] = useState("0.20");
  const [maxChunks, setMaxChunks] = useState("8");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SearchTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<string[]>([]);

  async function search() {
    if (!query.trim()) return;
    setLoading(true); setError(null); setResult(null);
    try {
      const r = await searchTest({
        query,
        org_id: orgId || undefined,
        use_hybrid: useHybrid,
        min_score: parseFloat(minScore) || 0.2,
        max_chunks: parseInt(maxChunks) || 8,
      });
      setResult(r);
      setHistory(h => [query, ...h.filter(q => q !== query)].slice(0, 10));
    } catch (e: any) { setError(e?.message || "Fehler"); }
    setLoading(false);
  }

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase — Such-Testkonsole</h1>
          <p className="text-sm text-gray-500 mt-1">
            Hybrid Retrieval (Semantic + BM25 + Trust) live testen und Chunk-Scores inspizieren
          </p>
        </div>
        <Link
          href="/knowledge/help#search"
          className="border px-3 py-1.5 rounded-md text-sm hover:bg-gray-50 shrink-0"
        >
          Hilfe
        </Link>
      </div>

      {/* Search form */}
      <div className="bg-white border rounded-lg p-4 space-y-4">
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">Suchanfrage</label>
          <div className="flex gap-2">
            <textarea
              className="flex-1 border rounded-md px-3 py-2 text-sm resize-none"
              rows={2}
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey) void search(); }}
              placeholder="z. B. Wie funktioniert die Benutzerauthentifizierung in SAP S/4HANA?"
            />
            <button onClick={() => void search()} disabled={loading || !query.trim()}
              className="bg-blue-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50 self-end">
              {loading ? "Suche…" : "Suchen"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-1">Tipp: Ctrl+Enter zum Suchen</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Retrieval-Modus</label>
            <select className="w-full border rounded-md px-3 py-2 text-sm" value={useHybrid ? "hybrid" : "semantic"}
              onChange={e => setUseHybrid(e.target.value === "hybrid")}>
              <option value="hybrid">Hybrid (Semantic + BM25 + Trust)</option>
              <option value="semantic">Nur Semantic (schneller)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Min Score</label>
            <input type="number" step="0.05" min="0" max="1" className="w-full border rounded-md px-3 py-2 text-sm"
              value={minScore} onChange={e => setMinScore(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Max Chunks</label>
            <input type="number" min="1" max="20" className="w-full border rounded-md px-3 py-2 text-sm"
              value={maxChunks} onChange={e => setMaxChunks(e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Org-ID (optional)</label>
            <input className="w-full border rounded-md px-3 py-2 text-sm font-mono" value={orgId}
              onChange={e => setOrgId(e.target.value)} placeholder="UUID oder leer" />
          </div>
        </div>

        {history.length > 0 && (
          <div className="flex gap-1.5 flex-wrap">
            <span className="text-xs text-gray-400">Verlauf:</span>
            {history.map(q => (
              <button key={q} onClick={() => { setQuery(q); }}
                className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded hover:bg-blue-100">{q}</button>
            ))}
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 text-sm">⚠ {error}</p>
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="flex items-center gap-3 flex-wrap">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${MODE_LABEL[result.mode]?.cls ?? "bg-gray-100"}`}>
              {MODE_LABEL[result.mode]?.label ?? result.mode}
            </span>
            <span className="text-sm text-gray-600">
              {result.chunk_count} Chunk{result.chunk_count !== 1 ? "s" : ""} gefunden ·
              <span className="text-gray-400"> {result.retrieval_type}</span>
            </span>
          </div>

          {/* Guardrail warnings */}
          {result.guardrail_warnings && result.guardrail_warnings.length > 0 && (
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 space-y-1">
              <p className="text-xs font-semibold text-yellow-800">Guardrail-Warnungen</p>
              {result.guardrail_warnings.map((w, i) => <p key={i} className="text-xs text-yellow-700">{w}</p>)}
            </div>
          )}

          {/* Conflicts */}
          {result.conflicts && result.conflicts.length > 0 && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3 space-y-1">
              <p className="text-xs font-semibold text-orange-800">Quellenkonflikte erkannt</p>
              {result.conflicts.map((c, i) => (
                <div key={i} className="text-xs text-orange-700">
                  <span className="font-medium">{c.type}:</span> {c.description}
                </div>
              ))}
            </div>
          )}

          {/* No results */}
          {result.chunk_count === 0 && (
            <div className="text-center py-8 border rounded-lg bg-gray-50">
              <p className="text-gray-500">Keine Chunks über dem Min-Score gefunden.</p>
              <p className="text-xs text-gray-400 mt-1">Versuche einen niedrigeren Min-Score oder andere Keywords.</p>
            </div>
          )}

          {/* Chunks */}
          <div className="space-y-3">
            {result.chunks.map((chunk, i) => (
              <ChunkCard key={i} chunk={chunk} index={i} isHybrid={result.retrieval_type === "hybrid"} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
