"use client";

import { useState } from "react";
import useSWR from "swr";
import {
  PanelTop, ExternalLink, AlertTriangle, CheckCircle2,
  XCircle, RefreshCw, Maximize2, Shield, Clock,
} from "lucide-react";
import { fetcher, authFetch } from "@/lib/api/client";

interface AdminUI {
  key: string;
  name: string;
  type: string;
  iframe_url: string | null;
  external_url: string | null;
  healthcheck_url: string | null;
  status: "active" | "degraded" | "unreachable" | "unknown";
  is_iframe_allowed: boolean;
  requires_superadmin: boolean;
  last_checked: string | null;
}

const BUILT_IN_ADMIN_UIS: AdminUI[] = [
  {
    key: "pgadmin",
    name: "pgAdmin",
    type: "admin_ui",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "phpmyadmin",
    name: "phpMyAdmin",
    type: "admin_ui",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "redis-commander",
    name: "Redis Commander",
    type: "admin_ui",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "authentik-admin",
    name: "Authentik Admin",
    type: "identity_provider",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "n8n",
    name: "n8n UI",
    type: "automation_service",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "litellm",
    name: "LiteLLM UI",
    type: "ai_model_gateway",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "nextcloud",
    name: "Nextcloud Admin",
    type: "file_source",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
  {
    key: "stirling",
    name: "Stirling PDF",
    type: "utility_service",
    iframe_url: null,
    external_url: null,
    healthcheck_url: null,
    status: "unknown",
    is_iframe_allowed: true,
    requires_superadmin: true,
    last_checked: null,
  },
];

function IframeViewer({ ui }: { ui: AdminUI }) {
  const url = ui.iframe_url || ui.external_url;
  const isExternal = !ui.iframe_url && !!ui.external_url;

  if (!url) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 bg-[var(--bg-base)] rounded-lg">
        <PanelTop className="h-10 w-10 text-slate-300" />
        <p className="text-sm text-[var(--ink-muted)] text-center">
          Keine URL konfiguriert.<br />
          Konfiguriere zuerst die iframe_url oder external_url für diese Ressource.
        </p>
      </div>
    );
  }

  if (!ui.is_iframe_allowed) {
    return (
      <div className="h-full flex flex-col items-center justify-center gap-3 bg-[var(--bg-base)] rounded-lg">
        <Shield className="h-10 w-10 text-red-400" />
        <p className="text-sm text-red-600 font-medium">iframe-Einbettung deaktiviert</p>
        <p className="text-xs text-[var(--ink-muted)]">is_iframe_allowed = false</p>
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg text-[var(--ink-mid)] hover:text-[var(--ink-strong)]">
            <ExternalLink className="h-3.5 w-3.5" /> In neuem Tab öffnen
          </a>
        )}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-2">
      {isExternal && (
        <div className="flex items-center gap-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>Externe URL — Inhalte stammen von einem externen System.</span>
        </div>
      )}
      <iframe
        src={url}
        className="flex-1 rounded-lg border border-[var(--border-subtle)] bg-white"
        title={ui.name}
        sandbox="allow-same-origin allow-scripts allow-forms allow-popups"
      />
    </div>
  );
}

export default function AdminUIsPage() {
  const [selected, setSelected] = useState<AdminUI | null>(null);
  const [iframeOpen, setIframeOpen] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const [editUrl, setEditUrl] = useState("");

  const STATUS_ICON = {
    active:      <CheckCircle2 className="h-4 w-4 text-green-500" />,
    degraded:    <AlertTriangle className="h-4 w-4 text-amber-500" />,
    unreachable: <XCircle className="h-4 w-4 text-red-500" />,
    unknown:     <Clock className="h-4 w-4 text-slate-400" />,
  };

  return (
    <div className="h-[calc(100vh-2rem)] flex flex-col gap-4 p-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 shrink-0">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <PanelTop className="h-5 w-5 text-orange-600" />
            Admin-UIs
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            iframe-Einbindung administrativer Oberflächen — nur für Superadmin
          </p>
        </div>
        <div className="flex items-center gap-2 p-2 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800">
          <Shield className="h-4 w-4 shrink-0" />
          Nur für autorisierte Superadmins sichtbar
        </div>
      </div>

      {/* Main content: card grid + iframe panel */}
      <div className={`flex-1 overflow-hidden flex gap-4 ${iframeOpen ? "flex-row" : "flex-col"}`}>

        {/* Cards */}
        <div className={`${iframeOpen ? "w-80 shrink-0 overflow-y-auto" : ""} grid ${iframeOpen ? "grid-cols-1" : "grid-cols-1 sm:grid-cols-2 xl:grid-cols-4"} gap-3 content-start`}>
          {BUILT_IN_ADMIN_UIS.map(ui => {
            const isSelected = selected?.key === ui.key;
            const url = ui.iframe_url || ui.external_url;
            const isExternal = !ui.iframe_url && !!ui.external_url;

            return (
              <div key={ui.key}
                className={`bg-[var(--bg-card)] rounded-xl border p-4 space-y-3 transition-colors
                  ${isSelected ? "border-orange-400 ring-1 ring-orange-300" : "border-[var(--border-subtle)] hover:border-orange-300"}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--ink-strong)]">{ui.name}</h3>
                    <p className="text-xs text-[var(--ink-muted)]">{ui.type.replace("_", " ")}</p>
                  </div>
                  {STATUS_ICON[ui.status]}
                </div>

                {/* URL config */}
                {editing === ui.key ? (
                  <div className="space-y-1.5">
                    <input
                      value={editUrl}
                      onChange={e => setEditUrl(e.target.value)}
                      placeholder="https://pgadmin.example.com"
                      className="w-full px-2 py-1.5 text-xs border border-[var(--border-subtle)] rounded bg-[var(--bg-base)] focus:outline-none"
                    />
                    <div className="flex gap-1.5">
                      <button onClick={() => setEditing(null)}
                        className="flex-1 text-xs px-2 py-1 bg-orange-600 text-white rounded hover:bg-orange-700">
                        Speichern
                      </button>
                      <button onClick={() => setEditing(null)}
                        className="text-xs px-2 py-1 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded text-[var(--ink-muted)]">
                        ×
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-1.5">
                    {url ? (
                      <code className="text-[10px] text-[var(--ink-muted)] bg-[var(--bg-base)] px-2 py-1 rounded truncate block">
                        {url}
                      </code>
                    ) : (
                      <p className="text-[10px] text-slate-400 italic">Keine URL konfiguriert</p>
                    )}
                    <div className="flex gap-1.5 flex-wrap">
                      <button onClick={() => { setEditing(ui.key); setEditUrl(url ?? ""); }}
                        className="text-[11px] px-2 py-1 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded text-[var(--ink-mid)] hover:text-[var(--ink-strong)]">
                        URL konfigurieren
                      </button>
                      {url && ui.is_iframe_allowed && (
                        <button
                          onClick={() => { setSelected(ui); setIframeOpen(true); }}
                          className="flex items-center gap-1 text-[11px] px-2 py-1 bg-orange-50 border border-orange-200 text-orange-700 rounded hover:bg-orange-100">
                          <Maximize2 className="h-3 w-3" /> iframe öffnen
                        </button>
                      )}
                      {url && (
                        <a href={url} target="_blank" rel="noopener noreferrer"
                          className="flex items-center gap-1 text-[11px] px-2 py-1 bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded text-[var(--ink-mid)] hover:text-[var(--ink-strong)]">
                          <ExternalLink className="h-3 w-3" /> Tab
                        </a>
                      )}
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-1.5">
                  <Shield className="h-3 w-3 text-red-400" />
                  <span className="text-[10px] text-[var(--ink-muted)]">Nur Superadmin</span>
                  {isExternal && (
                    <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded ml-auto">Extern</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* iframe panel */}
        {iframeOpen && selected && (
          <div className="flex-1 flex flex-col gap-2 min-w-0">
            <div className="flex items-center gap-3 shrink-0">
              <h2 className="text-sm font-semibold text-[var(--ink-strong)] flex items-center gap-2">
                <PanelTop className="h-4 w-4 text-orange-600" />
                {selected.name}
              </h2>
              <button onClick={() => { setIframeOpen(false); setSelected(null); }}
                className="ml-auto text-xs px-2 py-1 bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded text-[var(--ink-muted)] hover:text-[var(--ink-strong)]">
                Schließen
              </button>
            </div>
            <div className="flex-1">
              <IframeViewer ui={selected} />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
