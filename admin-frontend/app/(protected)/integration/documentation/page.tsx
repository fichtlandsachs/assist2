"use client";

import { useEffect, useState, useCallback } from "react";
import {
  listExternalSources, getExternalSource, createExternalSource,
  disableExternalSource, startIngest, startRefresh, retryFailures,
  listRuns, listPages, listFailures, previewPage,
} from "@/lib/api";
import type { ExternalSource, ExternalSourceRun, ExternalSourcePage, PreviewResult } from "@/lib/api";

// ── Source type catalogue ─────────────────────────────────────────────────────

const KNOWN_SOURCES = [
  {
    key: "sap_s4hana_utilities_en_2025_001_shared",
    label: "SAP S/4HANA Utilities",
    domain: "help.sap.com",
    icon: "🟡",
  },
  { key: "atlassian_jira_docs", label: "Atlassian Jira Docs",      domain: "support.atlassian.com", icon: "🔵" },
  { key: "atlassian_confluence_docs", label: "Atlassian Confluence", domain: "support.atlassian.com", icon: "🔵" },
  { key: "github_docs",          label: "GitHub Docs",             domain: "docs.github.com",       icon: "⚫" },
  { key: "custom",               label: "Eigene Quelle…",          domain: "",                      icon: "⚙️" },
];

const STATUS_COLOR: Record<string, string> = {
  done:       "#22c55e",
  success:    "#22c55e",
  running:    "#f59e0b",
  pending:    "#94a3b8",
  failed:     "#ef4444",
  error:      "#ef4444",
  skipped:    "#64748b",
  fetched:    "#3b82f6",
  extracted:  "#8b5cf6",
  indexed:    "#10b981",
};

const statusColor = (s: string) => STATUS_COLOR[s] ?? "#94a3b8";

// ── Helper: relative time ─────────────────────────────────────────────────────
function relTime(iso: string | null): string {
  if (!iso) return "—";
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `vor ${diff}s`;
  if (diff < 3600) return `vor ${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)}h`;
  return `vor ${Math.floor(diff / 86400)}d`;
}

function duration(start: string | null, end: string | null): string {
  if (!start || !end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}min ${Math.floor((ms % 60000) / 1000)}s`;
}

// ── Shared Spinner ────────────────────────────────────────────────────────────
function Spinner({ size = 16 }: { size?: number }) {
  return (
    <div className="inline-block rounded-full border-2 border-current border-t-transparent animate-spin"
      style={{ width: size, height: size }} />
  );
}

// ── CreateSourceDrawer ────────────────────────────────────────────────────────
function CreateSourceDrawer({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [preset, setPreset] = useState(KNOWN_SOURCES[0].key);
  const [displayName, setDisplayName] = useState(KNOWN_SOURCES[0].label);
  const [sourceKey, setSourceKey] = useState(KNOWN_SOURCES[0].key);
  const [baseUrl, setBaseUrl] = useState("https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/");
  const [allowedDomains, setAllowedDomains] = useState("help.sap.com");
  const [seedUrls, setSeedUrls] = useState("https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/?locale=en-US&state=PRODUCTION&version=2025.001");
  const [maxConcurrency, setMaxConcurrency] = useState(2);
  const [requestDelay, setRequestDelay] = useState(1.5);
  const [targetTokens, setTargetTokens] = useState(800);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const PRESETS: Record<string, Partial<{ displayName: string; sourceKey: string; baseUrl: string; allowedDomains: string; seedUrls: string }>> = {
    sap_s4hana_utilities_en_2025_001_shared: {
      displayName: "SAP S/4HANA Utilities Documentation (EN, 2025.001)",
      sourceKey: "sap_s4hana_utilities_en_2025_001_shared",
      baseUrl: "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/",
      allowedDomains: "help.sap.com",
      seedUrls: "https://help.sap.com/docs/SAP_S4HANA_ON-PREMISE/021b182b0c47416c8fafed67ebfd78a9/?locale=en-US&state=PRODUCTION&version=2025.001",
    },
    atlassian_jira_docs: {
      displayName: "Atlassian Jira Documentation",
      sourceKey: "atlassian_jira_docs",
      baseUrl: "https://support.atlassian.com/jira-software-cloud/",
      allowedDomains: "support.atlassian.com",
      seedUrls: "https://support.atlassian.com/jira-software-cloud/",
    },
    atlassian_confluence_docs: {
      displayName: "Atlassian Confluence Documentation",
      sourceKey: "atlassian_confluence_docs",
      baseUrl: "https://support.atlassian.com/confluence-cloud/",
      allowedDomains: "support.atlassian.com",
      seedUrls: "https://support.atlassian.com/confluence-cloud/",
    },
    github_docs: {
      displayName: "GitHub Documentation",
      sourceKey: "github_docs",
      baseUrl: "https://docs.github.com/",
      allowedDomains: "docs.github.com",
      seedUrls: "https://docs.github.com/en",
    },
    custom: { displayName: "", sourceKey: "", baseUrl: "", allowedDomains: "", seedUrls: "" },
  };

  function applyPreset(key: string) {
    setPreset(key);
    const p = PRESETS[key];
    if (!p) return;
    if (p.displayName !== undefined) setDisplayName(p.displayName);
    if (p.sourceKey !== undefined) setSourceKey(p.sourceKey);
    if (p.baseUrl !== undefined) setBaseUrl(p.baseUrl);
    if (p.allowedDomains !== undefined) setAllowedDomains(p.allowedDomains);
    if (p.seedUrls !== undefined) setSeedUrls(p.seedUrls);
  }

  async function handleCreate() {
    setErr(null);
    setSaving(true);
    try {
      await createExternalSource({
        source_key: sourceKey,
        display_name: displayName,
        base_url: baseUrl,
        visibility_scope: "global",
        config: {
          allowed_domains: allowedDomains.split(",").map(s => s.trim()).filter(Boolean),
          include_url_prefixes: [baseUrl],
          seed_urls: seedUrls.split("\n").map(s => s.trim()).filter(Boolean),
          crawl_policy: { max_concurrency: maxConcurrency, request_delay_seconds: requestDelay },
          chunking_policy: { target_chunk_tokens: targetTokens },
        },
      });
      onCreated();
      setOpen(false);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Fehler beim Erstellen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button onClick={() => setOpen(true)} className="neo-btn neo-btn--default neo-btn--sm">
        + Neue Quelle
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex" style={{ background: "rgba(0,0,0,0.4)" }}>
          <div className="ml-auto w-[520px] h-full overflow-y-auto shadow-2xl flex flex-col"
            style={{ background: "var(--paper)", borderLeft: "2px solid var(--paper-rule)" }}>
            <div className="flex items-center justify-between px-6 py-4 border-b"
              style={{ borderColor: "var(--paper-rule)" }}>
              <h2 className="font-bold text-base" style={{ color: "var(--ink)" }}>Dokumentationsquelle erstellen</h2>
              <button onClick={() => setOpen(false)} style={{ color: "var(--ink-faint)", fontSize: 20, lineHeight: 1 }}>×</button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
              {/* Preset */}
              <div>
                <label className="block text-xs font-medium mb-1.5" style={{ color: "var(--ink-mid)" }}>Vorlage</label>
                <div className="grid grid-cols-2 gap-2">
                  {KNOWN_SOURCES.map(s => (
                    <button key={s.key} onClick={() => applyPreset(s.key)}
                      className={`text-left px-3 py-2 rounded-sm border-2 text-xs transition-all
                        ${preset === s.key ? "border-[var(--accent-red)]" : "border-[var(--paper-rule)]"}`}
                      style={{ color: "var(--ink)" }}>
                      <span className="mr-1">{s.icon}</span>
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              <hr style={{ borderColor: "var(--paper-rule)" }} />

              {/* Fields */}
              {[
                { label: "Anzeigename", value: displayName, set: setDisplayName, ph: "SAP S/4HANA Utilities Docs" },
                { label: "Source Key (eindeutig)", value: sourceKey, set: setSourceKey, ph: "sap_s4hana_en_2025" },
                { label: "Basis-URL", value: baseUrl, set: setBaseUrl, ph: "https://help.sap.com/..." },
                { label: "Erlaubte Domains (kommagetrennt)", value: allowedDomains, set: setAllowedDomains, ph: "help.sap.com" },
              ].map(f => (
                <div key={f.label}>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>{f.label}</label>
                  <input type="text" value={f.value} onChange={e => f.set(e.target.value)}
                    placeholder={f.ph} className="neo-input w-full text-sm" />
                </div>
              ))}

              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
                  Seed-URLs (eine pro Zeile)
                </label>
                <textarea value={seedUrls} onChange={e => setSeedUrls(e.target.value)} rows={3}
                  className="neo-input w-full text-xs font-mono resize-none"
                  style={{ background: "var(--paper-warm)" }} />
              </div>

              <hr style={{ borderColor: "var(--paper-rule)" }} />

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Parallelität</label>
                  <input type="number" min={1} max={10} value={maxConcurrency}
                    onChange={e => setMaxConcurrency(Number(e.target.value))} className="neo-input w-full text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Delay (s)</label>
                  <input type="number" min={0.5} max={10} step={0.5} value={requestDelay}
                    onChange={e => setRequestDelay(Number(e.target.value))} className="neo-input w-full text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Chunk Tokens</label>
                  <input type="number" min={200} max={2000} step={100} value={targetTokens}
                    onChange={e => setTargetTokens(Number(e.target.value))} className="neo-input w-full text-sm" />
                </div>
              </div>

              {err && (
                <p className="text-sm p-3 rounded-sm border"
                  style={{ color: "var(--warn)", borderColor: "rgba(139,94,82,.3)", background: "rgba(139,94,82,.06)" }}>
                  {err}
                </p>
              )}
            </div>

            <div className="px-6 py-4 border-t flex items-center gap-3" style={{ borderColor: "var(--paper-rule)" }}>
              <button onClick={() => void handleCreate()} disabled={saving} className="neo-btn neo-btn--default">
                {saving ? <><Spinner size={14} /> Erstellen…</> : "Quelle erstellen"}
              </button>
              <button onClick={() => setOpen(false)} className="neo-btn neo-btn--outline">Abbrechen</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── RunsPanel ─────────────────────────────────────────────────────────────────
function RunsPanel({ sourceId }: { sourceId: string }) {
  const [runs, setRuns] = useState<ExternalSourceRun[] | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setRuns(await listRuns(sourceId)); }
    finally { setLoading(false); }
  }, [sourceId]);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <div className="flex items-center gap-2 py-4" style={{ color: "var(--ink-faint)" }}><Spinner /> Lade Runs…</div>;
  if (!runs?.length) return <p className="text-sm py-4" style={{ color: "var(--ink-faint)" }}>Noch keine Ingest-Runs.</p>;

  return (
    <div className="space-y-2">
      {runs.map(run => {
        const stats = run.stats_json as Record<string, number>;
        return (
          <div key={run.id} className="neo-card p-4 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                style={{ background: statusColor(run.status) + "22", color: statusColor(run.status) }}>
                {run.status}
              </span>
              <span className="text-xs font-medium" style={{ color: "var(--ink-mid)" }}>{run.run_type}</span>
              <span className="text-xs" style={{ color: "var(--ink-faint)" }}>
                {relTime(run.created_at)} · {duration(run.started_at, run.finished_at)}
              </span>
              {run.triggered_by && (
                <span className="text-xs" style={{ color: "var(--ink-faint)" }}>von {run.triggered_by}</span>
              )}
            </div>

            {/* Stats grid */}
            {Object.keys(stats).length > 0 && (
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {Object.entries(stats).map(([k, v]) => (
                  <span key={k} className="text-xs" style={{ color: "var(--ink-mid)" }}>
                    <span style={{ color: "var(--ink-faint)" }}>{k}:</span>{" "}
                    <strong style={{ color: "var(--ink)" }}>{v}</strong>
                  </span>
                ))}
              </div>
            )}

            {run.error_summary && (
              <p className="text-xs font-mono p-2 rounded-sm"
                style={{ background: "rgba(239,68,68,.06)", color: "#ef4444" }}>
                {run.error_summary}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── PagesPanel ────────────────────────────────────────────────────────────────
function PagesPanel({ sourceId, onPreview }: { sourceId: string; onPreview: (url: string) => void }) {
  const [pages, setPages] = useState<ExternalSourcePage[] | null>(null);
  const [tab, setTab] = useState<"all" | "failed">("all");
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = tab === "failed"
        ? await listFailures(sourceId)
        : await listPages(sourceId, statusFilter || undefined, 500);
      setPages(p);
    } finally { setLoading(false); }
  }, [sourceId, tab, statusFilter]);

  useEffect(() => { void load(); }, [load]);

  const filtered = pages?.filter(p =>
    !search || p.canonical_url.toLowerCase().includes(search.toLowerCase())
  ) ?? [];

  const statusGroups = pages
    ? [...new Set(pages.map(p => p.status))].sort()
    : [];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex rounded-sm border overflow-hidden" style={{ borderColor: "var(--paper-rule)" }}>
          {(["all", "failed"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="px-3 py-1.5 text-xs font-medium transition-colors"
              style={{
                background: tab === t ? "var(--accent-red)" : "transparent",
                color: tab === t ? "#fff" : "var(--ink-faint)",
                cursor: "pointer",
              }}>
              {t === "all" ? "Alle Seiten" : "Fehler"}
            </button>
          ))}
        </div>

        {tab === "all" && statusGroups.length > 0 && (
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="neo-input text-xs py-1">
            <option value="">Alle Status</option>
            {statusGroups.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        )}

        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="URL suchen…" className="neo-input text-xs py-1 flex-1 max-w-xs" />

        <button onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">
          ↻ Aktualisieren
        </button>

        <span className="text-xs ml-auto" style={{ color: "var(--ink-faint)" }}>
          {filtered.length} Seiten
        </span>
      </div>

      {loading && <div className="flex items-center gap-2 py-4" style={{ color: "var(--ink-faint)" }}><Spinner /> Lade Seiten…</div>}

      {!loading && filtered.length === 0 && (
        <p className="text-sm py-4" style={{ color: "var(--ink-faint)" }}>Keine Seiten gefunden.</p>
      )}

      {!loading && filtered.length > 0 && (
        <div className="neo-card overflow-hidden p-0">
          <table className="neo-table text-xs">
            <thead>
              <tr>
                <th>Status</th>
                <th>URL</th>
                <th>HTTP</th>
                <th>Methode</th>
                <th>Gercrawlt</th>
                <th>Extrahiert</th>
                <th>Aktion</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.id}>
                  <td>
                    <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold"
                      style={{ background: statusColor(p.status) + "20", color: statusColor(p.status) }}>
                      {p.status}
                    </span>
                  </td>
                  <td style={{ maxWidth: 320 }}>
                    <a href={p.canonical_url} target="_blank" rel="noopener noreferrer"
                      className="truncate block hover:underline"
                      style={{ color: "var(--ink)", maxWidth: 300 }}
                      title={p.canonical_url}>
                      {p.canonical_url.replace(/^https?:\/\//, "").slice(0, 60)}
                      {p.canonical_url.length > 70 ? "…" : ""}
                    </a>
                    {p.error_detail && (
                      <p className="text-[10px] mt-0.5" style={{ color: "#ef4444" }}>{p.error_detail.slice(0, 80)}</p>
                    )}
                  </td>
                  <td style={{ color: p.http_status === 200 ? "var(--green)" : "#ef4444" }}>
                    {p.http_status ?? "—"}
                  </td>
                  <td style={{ color: "var(--ink-faint)" }}>{p.fetch_method ?? "—"}</td>
                  <td style={{ color: "var(--ink-faint)" }}>{relTime(p.fetched_at)}</td>
                  <td style={{ color: "var(--ink-faint)" }}>{relTime(p.extracted_at)}</td>
                  <td>
                    <button onClick={() => onPreview(p.canonical_url)}
                      className="text-[10px] px-2 py-0.5 rounded-sm border transition-colors"
                      style={{ borderColor: "var(--paper-rule)", color: "var(--ink-mid)" }}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--ink)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--ink-mid)")}>
                      Vorschau
                    </button>
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

// ── PreviewPanel ──────────────────────────────────────────────────────────────
function PreviewPanel({ sourceId, url, onClose }: { sourceId: string; url: string; onClose: () => void }) {
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [customUrl, setCustomUrl] = useState(url);

  async function load(u: string) {
    setLoading(true); setErr(null); setResult(null);
    try { setResult(await previewPage(sourceId, u)); }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : "Fehler"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(url); }, [url]);

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.5)" }}>
      <div className="w-full max-w-2xl max-h-[80vh] overflow-y-auto rounded-lg shadow-2xl"
        style={{ background: "var(--paper)", border: "2px solid var(--paper-rule)" }}>
        <div className="flex items-center gap-3 px-5 py-4 border-b" style={{ borderColor: "var(--paper-rule)" }}>
          <h3 className="font-bold text-sm flex-1" style={{ color: "var(--ink)" }}>Seiten-Vorschau (Reverse Engineering)</h3>
          <button onClick={onClose} style={{ color: "var(--ink-faint)", fontSize: 18 }}>×</button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* URL input */}
          <div className="flex gap-2">
            <input value={customUrl} onChange={e => setCustomUrl(e.target.value)}
              onKeyDown={e => e.key === "Enter" && void load(customUrl)}
              className="neo-input flex-1 text-xs font-mono" placeholder="https://…" />
            <button onClick={() => void load(customUrl)} className="neo-btn neo-btn--default neo-btn--sm">
              Analysieren
            </button>
          </div>

          {loading && (
            <div className="flex items-center gap-3 py-6 justify-center" style={{ color: "var(--ink-faint)" }}>
              <Spinner /> <span className="text-sm">Seite wird gecrawlt und extrahiert…</span>
            </div>
          )}

          {err && (
            <p className="text-sm p-3 rounded-sm" style={{ color: "#ef4444", background: "rgba(239,68,68,.06)" }}>{err}</p>
          )}

          {result && (
            <div className="space-y-4">
              {/* Metadata */}
              <div className="grid grid-cols-3 gap-2 text-xs">
                {[
                  { label: "Fetch-Methode", value: result.fetch_method },
                  { label: "Chunks", value: result.chunk_count },
                  { label: "Qualität", value: `${(result.extraction_quality_score * 100).toFixed(0)}%` },
                ].map(m => (
                  <div key={m.label} className="neo-card px-3 py-2 text-center">
                    <p className="font-bold text-base" style={{ color: "var(--ink)" }}>{m.value}</p>
                    <p style={{ color: "var(--ink-faint)" }}>{m.label}</p>
                  </div>
                ))}
              </div>

              {/* Breadcrumb */}
              {result.breadcrumb.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Breadcrumb</p>
                  <p className="text-xs" style={{ color: "var(--ink-faint)" }}>
                    {result.breadcrumb.join(" › ")}
                  </p>
                </div>
              )}

              {/* Title */}
              <div>
                <p className="text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>Extrahierter Titel</p>
                <p className="text-sm font-bold" style={{ color: "var(--ink)" }}>{result.title || "—"}</p>
              </div>

              {/* Headings */}
              {result.headings.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
                    Struktur (Top {result.headings.length} Überschriften)
                  </p>
                  <div className="space-y-0.5">
                    {result.headings.map((h, i) => (
                      <p key={i} className="text-xs font-mono" style={{ color: "var(--ink-faint)" }}>{h}</p>
                    ))}
                  </div>
                </div>
              )}

              {/* Text preview */}
              <div>
                <p className="text-xs font-medium mb-1" style={{ color: "var(--ink-mid)" }}>
                  Text-Preview (erste 500 Zeichen)
                </p>
                <div className="text-xs p-3 rounded-sm font-mono whitespace-pre-wrap"
                  style={{ background: "var(--paper-warm)", color: "var(--ink-mid)", lineHeight: 1.6 }}>
                  {result.plain_text_preview}
                </div>
              </div>

              {/* Canonical URL */}
              <p className="text-[10px] font-mono" style={{ color: "var(--ink-faint)" }}>
                → {result.canonical_url}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── SourceDetail ──────────────────────────────────────────────────────────────
function SourceDetail({ source, onBack, onUpdate }: {
  source: ExternalSource;
  onBack: () => void;
  onUpdate: () => void;
}) {
  const [tab, setTab] = useState<"runs" | "pages" | "config">("runs");
  const [ingestMsg, setIngestMsg] = useState<string | null>(null);
  const [acting, setActing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const cfg = source.config_json as Record<string, unknown>;
  const crawlPolicy = (cfg.crawl_policy ?? {}) as Record<string, unknown>;
  const chunkPolicy = (cfg.chunking_policy ?? {}) as Record<string, unknown>;
  const seedUrls = (cfg.seed_urls ?? []) as string[];

  async function act(fn: () => Promise<{ message: string }>) {
    setActing(true); setIngestMsg(null);
    try {
      const r = await fn();
      setIngestMsg(r.message);
    } catch (e: unknown) {
      setIngestMsg(e instanceof Error ? e.message : "Fehler");
    } finally { setActing(false); }
  }

  async function handleDisable() {
    if (!confirm("Quelle deaktivieren?")) return;
    setActing(true);
    try { await disableExternalSource(source.id); onUpdate(); }
    finally { setActing(false); }
  }

  const TABS = [
    { id: "runs",   label: "Ingest-Runs" },
    { id: "pages",  label: "Gecrawlte Seiten" },
    { id: "config", label: "Konfiguration" },
  ] as const;

  return (
    <div className="space-y-5 max-w-5xl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm">
        <button onClick={onBack} className="hover:underline" style={{ color: "var(--accent-red)" }}>
          ← Dokumentationsquellen
        </button>
        <span style={{ color: "var(--ink-faint)" }}>›</span>
        <span style={{ color: "var(--ink)" }}>{source.display_name}</span>
      </div>

      {/* Header */}
      <div className="neo-card p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>{source.display_name}</h1>
              <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                style={{
                  background: source.is_enabled ? "#22c55e22" : "#94a3b822",
                  color: source.is_enabled ? "#22c55e" : "#94a3b8",
                }}>
                {source.is_enabled ? "Aktiv" : "Deaktiviert"}
              </span>
            </div>
            <p className="text-sm font-mono" style={{ color: "var(--ink-faint)" }}>{source.source_key}</p>
            <a href={source.base_url} target="_blank" rel="noopener noreferrer"
              className="text-xs hover:underline mt-1 block" style={{ color: "var(--accent-red)" }}>
              {source.base_url}
            </a>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 shrink-0">
            <button disabled={acting || !source.is_enabled}
              onClick={() => act(() => startIngest(source.id))}
              className="neo-btn neo-btn--default neo-btn--sm flex items-center gap-1.5">
              {acting ? <Spinner size={12} /> : null}
              Initial-Ingest
            </button>
            <button disabled={acting || !source.is_enabled}
              onClick={() => act(() => startRefresh(source.id))}
              className="neo-btn neo-btn--outline neo-btn--sm">
              Refresh
            </button>
            <button disabled={acting || !source.is_enabled}
              onClick={() => act(() => retryFailures(source.id))}
              className="neo-btn neo-btn--outline neo-btn--sm">
              Fehler wiederholen
            </button>
            <button disabled={acting || !source.is_enabled}
              onClick={() => void handleDisable()}
              className="neo-btn neo-btn--outline neo-btn--sm"
              style={{ color: "#ef4444", borderColor: "#ef444433" }}>
              Deaktivieren
            </button>
          </div>
        </div>

        {ingestMsg && (
          <p className="mt-3 text-xs p-2 rounded-sm" style={{ background: "var(--paper-warm)", color: "var(--ink-mid)" }}>
            {ingestMsg}
          </p>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b-2" style={{ borderColor: "var(--paper-rule2)" }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className="px-4 py-2.5 text-sm font-medium transition-colors"
            style={{
              color: tab === t.id ? "var(--ink)" : "var(--ink-faint)",
              borderBottom: tab === t.id ? "2px solid var(--accent-red)" : "2px solid transparent",
              marginBottom: "-2px", background: "transparent", cursor: "pointer",
            }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "runs" && <RunsPanel sourceId={source.id} />}
      {tab === "pages" && <PagesPanel sourceId={source.id} onPreview={u => setPreviewUrl(u)} />}
      {tab === "config" && (
        <div className="space-y-4">
          {/* Crawl stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: "Parallelität", value: String(crawlPolicy.max_concurrency ?? "—") },
              { label: "Delay (s)",    value: String(crawlPolicy.request_delay_seconds ?? "—") },
              { label: "Timeout (s)",  value: String(crawlPolicy.request_timeout_seconds ?? "—") },
              { label: "Max Retries",  value: String(crawlPolicy.max_retries ?? "—") },
            ].map(m => (
              <div key={m.label} className="neo-card px-4 py-3 text-center">
                <p className="text-lg font-bold" style={{ color: "var(--ink)" }}>{m.value}</p>
                <p className="text-xs" style={{ color: "var(--ink-faint)" }}>{m.label}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: "Chunk-Tokens (Ziel)", value: String(chunkPolicy.target_chunk_tokens ?? "—") },
              { label: "Overlap Tokens",      value: String(chunkPolicy.overlap_tokens ?? "—") },
              { label: "Max Chunk Tokens",    value: String(chunkPolicy.max_chunk_tokens ?? "—") },
            ].map(m => (
              <div key={m.label} className="neo-card px-4 py-3 text-center">
                <p className="text-lg font-bold" style={{ color: "var(--ink)" }}>{m.value}</p>
                <p className="text-xs" style={{ color: "var(--ink-faint)" }}>{m.label}</p>
              </div>
            ))}
          </div>

          {/* Seed URLs */}
          <div className="neo-card p-4">
            <h3 className="text-xs font-bold mb-2" style={{ color: "var(--ink-mid)" }}>Seed-URLs</h3>
            <div className="space-y-1">
              {seedUrls.map((u, i) => (
                <a key={i} href={u} target="_blank" rel="noopener noreferrer"
                  className="text-xs font-mono block hover:underline"
                  style={{ color: "var(--accent-red)" }}>{u}</a>
              ))}
            </div>
          </div>

          {/* Raw JSON */}
          <div className="neo-card p-4">
            <h3 className="text-xs font-bold mb-2" style={{ color: "var(--ink-mid)" }}>Vollständige Konfiguration (JSON)</h3>
            <pre className="text-[10px] font-mono overflow-x-auto whitespace-pre-wrap"
              style={{ color: "var(--ink-faint)", maxHeight: 400, overflowY: "auto" }}>
              {JSON.stringify(source.config_json, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Preview modal */}
      {previewUrl && (
        <PreviewPanel sourceId={source.id} url={previewUrl} onClose={() => setPreviewUrl(null)} />
      )}
    </div>
  );
}

// ── SourceList ────────────────────────────────────────────────────────────────
function SourceList({ sources, onSelect }: { sources: ExternalSource[]; onSelect: (s: ExternalSource) => void }) {
  const TYPE_ICON: Record<string, string> = {
    "help.sap.com": "🟡", "support.atlassian.com": "🔵",
    "docs.github.com": "⚫", "developer.salesforce.com": "🔷",
  };

  return (
    <div className="neo-card overflow-hidden p-0">
      <table className="neo-table">
        <thead>
          <tr>
            <th>Quelle</th>
            <th>Basis-URL</th>
            <th>Typ</th>
            <th>Sichtbarkeit</th>
            <th>Status</th>
            <th>Aktualisiert</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {sources.map(s => {
            let domain = "";
            try { domain = new URL(s.base_url).hostname; } catch { /* ignore */ }
            const icon = TYPE_ICON[domain] ?? "🌐";

            return (
              <tr key={s.id} style={{ cursor: "pointer" }}
                onClick={() => onSelect(s)}>
                <td>
                  <div className="flex items-center gap-2">
                    <span>{icon}</span>
                    <div>
                      <p className="font-semibold text-sm" style={{ color: "var(--ink)" }}>{s.display_name}</p>
                      <p className="text-[10px] font-mono" style={{ color: "var(--ink-faint)" }}>{s.source_key}</p>
                    </div>
                  </div>
                </td>
                <td>
                  <a href={s.base_url} target="_blank" rel="noopener noreferrer"
                    onClick={e => e.stopPropagation()}
                    className="text-xs font-mono truncate block hover:underline"
                    style={{ color: "var(--accent-red)", maxWidth: 260 }}>
                    {domain}
                  </a>
                </td>
                <td>
                  <span className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "var(--paper-warm)", color: "var(--ink-mid)" }}>
                    {s.source_type}
                  </span>
                </td>
                <td className="text-xs" style={{ color: "var(--ink-faint)" }}>{s.visibility_scope}</td>
                <td>
                  <span className="px-2 py-0.5 rounded-full text-xs font-bold"
                    style={{
                      background: s.is_enabled ? "#22c55e22" : "#94a3b822",
                      color: s.is_enabled ? "#22c55e" : "#94a3b8",
                    }}>
                    {s.is_enabled ? "aktiv" : "inaktiv"}
                  </span>
                </td>
                <td className="text-xs" style={{ color: "var(--ink-faint)" }}>
                  {relTime(s.updated_at)}
                </td>
                <td>
                  <button className="neo-btn neo-btn--outline neo-btn--sm"
                    onClick={e => { e.stopPropagation(); onSelect(s); }}>
                    Details →
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────
export default function DocumentationSourcesPage() {
  const [sources, setSources] = useState<ExternalSource[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [selected, setSelected] = useState<ExternalSource | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try { setSources(await listExternalSources()); }
    catch { setErr("Quellen konnten nicht geladen werden."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (selected) {
    return (
      <SourceDetail
        source={selected}
        onBack={() => { setSelected(null); void load(); }}
        onUpdate={() => { setSelected(null); void load(); }}
      />
    );
  }

  return (
    <div className="space-y-5 max-w-5xl">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Dokumentationsquellen</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
            Reverse-Engineering externer Dokumentation · Crawl · Extraktion · Chunking · Embedding
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">↻</button>
          <CreateSourceDrawer onCreated={() => void load()} />
        </div>
      </div>

      {/* Architecture note */}
      <div className="text-xs p-3 rounded-sm border"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)", color: "var(--ink-faint)" }}>
        <strong style={{ color: "var(--ink-mid)" }}>Integration Layer:</strong>{" "}
        Externe Dokumentationsquellen werden gecrawlt, in semantische Chunks zerlegt, eingebettet
        und der KnowledgeBase/RAG als Wissensquellen bereitgestellt. Konfiguration ausschließlich hier.
      </div>

      {err && <p className="text-sm p-3" style={{ color: "#ef4444" }}>{err}</p>}

      {loading && (
        <div className="flex items-center gap-3 py-8" style={{ color: "var(--ink-faint)" }}>
          <Spinner /> <span>Lade Quellen…</span>
        </div>
      )}

      {!loading && sources?.length === 0 && (
        <div className="neo-card p-10 text-center space-y-3">
          <p className="text-3xl">🌐</p>
          <p className="font-bold" style={{ color: "var(--ink)" }}>Noch keine Dokumentationsquellen</p>
          <p className="text-sm" style={{ color: "var(--ink-faint)" }}>
            Erstelle die erste Quelle um externen Dokumentationsinhalt in die KnowledgeBase einzuspeisen.
          </p>
        </div>
      )}

      {!loading && sources && sources.length > 0 && (
        <SourceList sources={sources} onSelect={setSelected} />
      )}
    </div>
  );
}
