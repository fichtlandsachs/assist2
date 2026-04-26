"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchComponentStatus } from "@/lib/api";
import type { ComponentStatus } from "@/types";

const EXTERNAL_RESOURCES = [
  {
    key: "github",
    label: "GitHub",
    category: "SCM / Tickets",
    usage: "Repository, Pull Requests, Issues, Actions",
    risk: "Token-Ablauf, Rate-Limits, Rechte auf Repo-Ebene",
    docs: "https://docs.github.com/",
  },
  {
    key: "jira",
    label: "Jira",
    category: "Projektmanagement",
    usage: "Stories, Epics, Status-Sync, Backlog-Integration",
    risk: "API-Token/Permission-Scope, Workflow-Mapping",
    docs: "https://developer.atlassian.com/cloud/jira/platform/rest/v3/",
  },
  {
    key: "confluence",
    label: "Confluence",
    category: "Dokumentation",
    usage: "Wissensimport, RAG-Quellen, Seiten-Sync",
    risk: "Space-Rechte, Content-Restriktionen, API-Quotas",
    docs: "https://developer.atlassian.com/cloud/confluence/rest/v2/",
  },
  {
    key: "nextcloud",
    label: "Nextcloud",
    category: "Dateiablage",
    usage: "Dateiquellen fuer Wissensbasis und Dokumenten-Import",
    risk: "WebDAV-Rechte, Dateigroesse, Timeout/Locking",
    docs: "https://docs.nextcloud.com/",
  },
  {
    key: "authentik",
    label: "Authentik",
    category: "Identity",
    usage: "SSO, OIDC, Rollen und Session-Validierung",
    risk: "Client-ID/Redirect-Mismatch, JWKS/Issuer-Konfiguration",
    docs: "https://goauthentik.io/docs/",
  },
  {
    key: "n8n",
    label: "n8n",
    category: "Automation",
    usage: "Externe Workflows und Integrations-Orchestrierung",
    risk: "Credential-Leaks, unkontrollierte Trigger, Retry-Loops",
    docs: "https://docs.n8n.io/",
  },
  {
    key: "litellm",
    label: "LiteLLM / Provider",
    category: "LLM Gateway",
    usage: "Model Routing fuer Chat, Embeddings, RAG",
    risk: "Provider-Ausfall, Budget-Limits, Modell-Downgrades",
    docs: "https://docs.litellm.ai/",
  },
] as const;

function statusPill(ok: boolean) {
  return ok
    ? "bg-green-100 text-green-700 border-green-200"
    : "bg-red-50 text-red-700 border-red-200";
}

export default function Page() {
  const [statusItems, setStatusItems] = useState<ComponentStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setError(null);
      setStatusItems(await fetchComponentStatus());
    } catch (e: any) {
      setError(e?.message || "Fehler beim Laden");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  const statusMap = useMemo(() => {
    const m = new Map<string, ComponentStatus>();
    for (const s of statusItems) m.set(s.name.toLowerCase(), s);
    return m;
  }, [statusItems]);

  const rows = useMemo(() => {
    return EXTERNAL_RESOURCES.map((res) => {
      const exact = statusMap.get(res.key.toLowerCase());
      const fuzzy = !exact
        ? Array.from(statusMap.entries()).find(([k]) => k.includes(res.key.toLowerCase()))?.[1]
        : undefined;
      const hit = exact ?? fuzzy ?? null;
      return {
        ...res,
        available: hit?.available ?? false,
        adminUrl: hit?.admin_url ?? null,
        runtimeLabel: hit?.label ?? null,
      };
    });
  }, [statusMap]);

  const available = rows.filter((r) => r.available).length;

  return (
    <div className="space-y-5 max-w-6xl">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Integration — Externe Ressourcen</h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>Alle externen Dienste</p>
        </div>
        <button onClick={() => void load()} className="neo-btn neo-btn--outline neo-btn--sm">Neu laden</button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Ressourcen gesamt</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{rows.length}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Verfuegbar</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{available}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Nicht verfuegbar</p>
          <p className="text-2xl font-bold mt-1" style={{ color: "var(--ink)" }}>{rows.length - available}</p>
        </div>
        <div className="neo-card p-3">
          <p className="text-xs" style={{ color: "var(--ink-faint)" }}>Statusquelle</p>
          <p className="text-sm font-semibold mt-2" style={{ color: "var(--ink)" }}>superadmin/status</p>
        </div>
      </div>

      {loading ? (
        <div className="neo-card p-6 text-center" style={{ color: "var(--ink-faint)" }}>
          <p className="text-sm">Lade externe Ressourcen…</p>
        </div>
      ) : error ? (
        <div className="neo-card p-4" style={{ background: "#fef3c7", border: "1px solid #f59e0b" }}>
          <p style={{ color: "#92400e" }}>⚠️ {error}</p>
          <button onClick={() => void load()} className="neo-btn neo-btn--sm neo-btn--outline mt-3">
            Erneut versuchen
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map((r) => (
            <div key={r.key} className="neo-card p-4 space-y-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>{r.label}</h2>
                    <span className="text-xs px-2 py-0.5 rounded-full border" style={{ color: "var(--ink-faint)" }}>
                      {r.category}
                    </span>
                    <span className={`text-xs px-2 py-0.5 rounded-full border ${statusPill(r.available)}`}>
                      {r.available ? "Verfuegbar" : "Down/Unbekannt"}
                    </span>
                  </div>
                  <p className="text-xs mt-1" style={{ color: "var(--ink-faint)" }}>
                    Runtime Label: <span className="font-mono">{r.runtimeLabel ?? "-"}</span>
                  </p>
                </div>
                <div className="flex gap-2">
                  {r.adminUrl ? (
                    <a href={r.adminUrl} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
                      Admin-Link
                    </a>
                  ) : (
                    <span className="text-xs" style={{ color: "var(--ink-faint)" }}>kein Admin-Link</span>
                  )}
                  <a href={r.docs} target="_blank" rel="noreferrer" className="neo-btn neo-btn--outline neo-btn--sm">
                    Dokumentation
                  </a>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="rounded-md p-3" style={{ background: "var(--paper-warm)" }}>
                  <p className="text-xs font-semibold" style={{ color: "var(--ink-mid)" }}>Nutzung</p>
                  <p className="text-xs mt-1" style={{ color: "var(--ink-faint)" }}>{r.usage}</p>
                </div>
                <div className="rounded-md p-3" style={{ background: "var(--paper-warm)" }}>
                  <p className="text-xs font-semibold" style={{ color: "var(--ink-mid)" }}>Betriebsrisiko</p>
                  <p className="text-xs mt-1" style={{ color: "var(--ink-faint)" }}>{r.risk}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="neo-card p-4 space-y-2">
        <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>Betriebshinweise</p>
        <ul className="space-y-1">
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Externe Ressourcen koennen trotz laufender Core-Container ausfallen (Token, Netzwerk, Provider-Stoerung).
          </li>
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Bei Down-Status zuerst Credentials/Scopes pruefen, dann Endpoint-Erreichbarkeit und Rate-Limits.
          </li>
          <li className="text-xs" style={{ color: "var(--ink-faint)" }}>
            - Kombiniere diese Sicht mit Logs und Connector-Seiten fuer Root-Cause-Analyse.
          </li>
        </ul>
      </div>
    </div>
  );
}
