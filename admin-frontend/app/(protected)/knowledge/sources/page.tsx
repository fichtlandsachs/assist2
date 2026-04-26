"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  listExternalSources, createExternalSource, enableExternalSource,
  disableExternalSource, deindexExternalSource, startIngest, startRefresh,
  getRagStats, getChunkStats,
  type ExternalSource, type RagStats,
} from "@/lib/api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function StatusBadge({ enabled }: { enabled: boolean }) {
  return enabled
    ? <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Aktiv</span>
    : <span className="text-xs bg-red-50 text-red-600 px-2 py-0.5 rounded-full">Deaktiviert</span>;
}

function StatCard({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="bg-white border rounded-lg p-4">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </div>
  );
}

// ── Create drawer ─────────────────────────────────────────────────────────────

const DEFAULT_CFG = {
  allowed_domains: [],
  include_url_prefixes: [],
  seed_urls: [],
  dropped_query_params: [],
  crawl_policy: { max_concurrency: 3, request_delay_seconds: 1.0, request_timeout_seconds: 30, max_retries: 3 },
  extraction_policy: { content_selectors: ["article", "main", ".content"], exclude_selectors: ["header", "footer", "nav"], min_content_length: 100 },
  chunking_policy: { target_chunk_tokens: 800, overlap_tokens: 120, max_chunk_tokens: 1200 },
  embedding_policy: { model: "ionos-embed", batch_size: 32, dimensions: 1024 },
  refresh_policy: { schedule_cron: "0 3 * * 0", use_etag: true, use_last_modified: true },
  metadata_defaults: {},
};

function CreateDrawer({ onClose, onSave }: { onClose: () => void; onSave: () => void }) {
  const [form, setForm] = useState({
    source_key: "",
    display_name: "",
    base_url: "",
    visibility_scope: "global",
    config_json: JSON.stringify(DEFAULT_CFG, null, 2),
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true); setErr(null);
    try {
      let config = DEFAULT_CFG;
      try { config = JSON.parse(form.config_json); } catch { setErr("config_json ist kein gültiges JSON"); setSaving(false); return; }
      await createExternalSource({
        source_key: form.source_key,
        display_name: form.display_name,
        base_url: form.base_url,
        visibility_scope: form.visibility_scope,
        config,
      });
      onSave();
    } catch (e: any) { setErr(e?.message || "Fehler"); }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.45)" }}>
      <div className="ml-auto w-full max-w-2xl h-full overflow-y-auto bg-white shadow-2xl flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="font-semibold text-base">Neue Wissensquelle</h2>
          <button onClick={onClose} className="text-2xl text-gray-400 hover:text-gray-700 leading-none">×</button>
        </div>
        <div className="flex-1 px-6 py-5 space-y-4 overflow-y-auto">
          {[
            { key: "source_key", label: "Source Key", placeholder: "sap-help-docs" },
            { key: "display_name", label: "Anzeigename", placeholder: "SAP Help Dokumentation" },
            { key: "base_url", label: "Base URL", placeholder: "https://help.sap.com/docs/" },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
              <input className="w-full border rounded-md px-3 py-2 text-sm" placeholder={placeholder}
                value={(form as any)[key]} onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))} />
            </div>
          ))}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Sichtbarkeit</label>
            <select className="w-full border rounded-md px-3 py-2 text-sm" value={form.visibility_scope}
              onChange={e => setForm(p => ({ ...p, visibility_scope: e.target.value }))}>
              <option value="global">global (alle Orgs)</option>
              <option value="org">org-spezifisch</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Konfiguration (JSON)</label>
            <p className="text-xs text-gray-400 mb-1">
              allowed_domains, include_url_prefixes, seed_urls, crawl_policy, chunking_policy, …
            </p>
            <textarea className="w-full border rounded-md px-3 py-2 text-xs font-mono resize-none" rows={18}
              value={form.config_json} onChange={e => setForm(p => ({ ...p, config_json: e.target.value }))} />
          </div>
          {err && <p className="text-red-600 text-sm">{err}</p>}
          <div className="flex gap-3 pt-2 border-t">
            <button onClick={save} disabled={saving}
              className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {saving ? "Erstellen…" : "Erstellen"}
            </button>
            <button onClick={onClose} className="border px-4 py-2 rounded-md text-sm hover:bg-gray-50">Abbrechen</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Source row actions ────────────────────────────────────────────────────────

function SourceActions({ source, onRefresh }: { source: ExternalSource; onRefresh: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function act(fn: () => Promise<any>, label: string) {
    setBusy(label); setMsg(null);
    try { const r = await fn(); setMsg(r?.message || r?.status || "OK"); }
    catch (e: any) { setMsg(`Fehler: ${e?.message}`); }
    setBusy(null);
    setTimeout(() => { setMsg(null); onRefresh(); }, 1500);
  }

  return (
    <div className="flex flex-col gap-1.5 items-end">
      <div className="flex gap-1.5 flex-wrap justify-end">
        {source.is_enabled ? (
          <>
            <button disabled={!!busy} onClick={() => act(() => startIngest(source.id), "ingest")}
              className="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded hover:bg-blue-100 disabled:opacity-50">
              {busy === "ingest" ? "…" : "Initial Ingest"}
            </button>
            <button disabled={!!busy} onClick={() => act(() => startRefresh(source.id), "refresh")}
              className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded hover:bg-green-100 disabled:opacity-50">
              {busy === "refresh" ? "…" : "Refresh"}
            </button>
            <button disabled={!!busy} onClick={() => act(() => deindexExternalSource(source.id), "deindex")}
              className="text-xs bg-yellow-50 text-yellow-700 border border-yellow-200 px-2 py-1 rounded hover:bg-yellow-100 disabled:opacity-50">
              {busy === "deindex" ? "…" : "De-Index"}
            </button>
            <button disabled={!!busy} onClick={() => act(() => disableExternalSource(source.id), "disable")}
              className="text-xs bg-red-50 text-red-600 border border-red-200 px-2 py-1 rounded hover:bg-red-100 disabled:opacity-50">
              {busy === "disable" ? "…" : "Deaktivieren"}
            </button>
          </>
        ) : (
          <button disabled={!!busy} onClick={() => act(() => enableExternalSource(source.id), "enable")}
            className="text-xs bg-green-50 text-green-700 border border-green-200 px-2 py-1 rounded hover:bg-green-100 disabled:opacity-50">
            {busy === "enable" ? "…" : "Aktivieren + Re-Ingest"}
          </button>
        )}
      </div>
      {msg && <p className="text-xs text-gray-500">{msg}</p>}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function SourcesPage() {
  const [sources, setSources] = useState<ExternalSource[]>([]);
  const [stats, setStats] = useState<RagStats | null>(null);
  const [chunkCounts, setChunkCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  async function load() {
    setLoading(true);
    try {
      setError(null);
      const [srcs, st] = await Promise.all([listExternalSources(), getRagStats().catch(() => null)]);
      setSources(srcs);
      if (st) {
        setStats(st);
        const counts: Record<string, number> = {};
        st.per_source.forEach(s => { counts[s.id] = s.chunk_count; });
        setChunkCounts(counts);
      }
    } catch (e: any) { setError(e?.message || "Fehler"); }
    setLoading(false);
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">KnowledgeBase — Wissensquellen</h1>
          <p className="text-sm text-gray-500 mt-1">Externe Dokumentationsquellen verwalten, indizieren und überwachen</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/knowledge/help#sources"
            className="border px-3 py-2 rounded-md text-sm hover:bg-gray-50"
          >
            Hilfe
          </Link>
          <button onClick={() => setShowCreate(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
            + Neue Quelle
          </button>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard label="Quellen gesamt" value={stats.total_sources} sub={`${stats.enabled_sources} aktiv`} />
          <StatCard label="Chunks gesamt" value={stats.total_chunks.toLocaleString()} sub={`${stats.chunks_with_embedding.toLocaleString()} mit Embedding`} />
          <StatCard label="Ohne Embedding" value={stats.chunks_missing_embedding} sub="müssen noch eingebettet werden" />
          <StatCard label="Aktive Jobs" value={stats.running_runs + stats.pending_runs} sub={`${stats.running_runs} laufend · ${stats.pending_runs} ausstehend`} />
        </div>
      )}

      {loading ? (
        <p className="text-gray-500 py-8 text-center">Lade…</p>
      ) : error ? (
        <div className="bg-yellow-50 border border-yellow-300 rounded-lg p-4">
          <p className="text-yellow-800">⚠️ {error}</p>
          <button onClick={() => void load()} className="mt-2 text-sm text-yellow-700 underline">Neu laden</button>
        </div>
      ) : sources.length === 0 ? (
        <div className="text-center py-12 border rounded-lg bg-gray-50">
          <p className="text-gray-500 mb-3">Noch keine Wissensquellen konfiguriert.</p>
          <button onClick={() => setShowCreate(true)} className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm">
            Erste Quelle anlegen
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {sources.map(source => (
            <div key={source.id} className="bg-white border rounded-lg p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold">{source.display_name}</span>
                    <StatusBadge enabled={source.is_enabled} />
                    <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{source.visibility_scope}</span>
                    {chunkCounts[source.id] !== undefined && (
                      <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded-full">
                        {chunkCounts[source.id].toLocaleString()} Chunks
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-mono text-gray-500 mt-1">{source.source_key}</p>
                  <a href={source.base_url} target="_blank" rel="noreferrer"
                    className="text-xs text-blue-600 hover:underline break-all">{source.base_url}</a>
                  <p className="text-xs text-gray-400 mt-1">
                    Erstellt {new Date(source.created_at).toLocaleDateString("de-DE")} ·
                    Aktualisiert {new Date(source.updated_at).toLocaleDateString("de-DE")}
                  </p>
                </div>
                <SourceActions source={source} onRefresh={load} />
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateDrawer onClose={() => setShowCreate(false)} onSave={() => { setShowCreate(false); void load(); }} />
      )}
    </div>
  );
}
