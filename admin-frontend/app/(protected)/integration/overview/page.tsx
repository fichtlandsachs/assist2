"use client";

import { useState, useEffect } from "react";
import { fetchConfig } from "@/lib/api";
import type { ConfigMap } from "@/types";

interface ResourceCard {
  key: string; name: string; type: string; location: "docker" | "external";
  description: string; href: string;
  configKeys?: string[];
}

const RESOURCES: ResourceCard[] = [
  { key: "authentik",   name: "Authentik",    type: "Identity Provider",   location: "docker",   description: "SSO & Identity Management",         href: "/integration/authentik" },
  { key: "litellm",     name: "LiteLLM",      type: "AI Gateway",          location: "docker",   description: "AI Model Gateway",                  href: "/integration/litellm",  configKeys: ["litellm.url", "litellm.api_key"] },
  { key: "n8n",         name: "n8n",          type: "Automation",          location: "docker",   description: "Workflow Automation",               href: "/integration/n8n",      configKeys: ["n8n.url", "n8n.api_key"] },
  { key: "nextcloud",   name: "Nextcloud",    type: "File Source",         location: "docker",   description: "File Storage & Collaboration",      href: "/integration/nextcloud",configKeys: ["nextcloud.url", "nextcloud.admin_user"] },
  { key: "stirling",    name: "Stirling PDF", type: "Utility",             location: "docker",   description: "PDF Processing Service",            href: "/integration/stirling" },
  { key: "whisper",     name: "Whisper",      type: "Utility",             location: "docker",   description: "Speech-to-Text",                    href: "/integration/whisper" },
  { key: "postgres",    name: "PostgreSQL",   type: "Datenbank",           location: "docker",   description: "Primäre Datenbank",                 href: "/integration/databases" },
  { key: "redis",       name: "Redis",        type: "Datenbank",           location: "docker",   description: "Cache & Message Queue",             href: "/integration/databases" },
  { key: "jira",        name: "Jira",         type: "Connector",           location: "external", description: "Issue Tracking (Cloud)",             href: "/integration/connectors" },
  { key: "confluence",  name: "Confluence",   type: "Dokumentation",       location: "external", description: "Wiki & Dokumentation",              href: "/integration/documentation" },
  { key: "github",      name: "GitHub",       type: "Connector",           location: "external", description: "Source Control",                    href: "/integration/connectors" },
];

const LOCATION_COLOR = {
  docker:   { bg: "#f3f4f6", text: "#374151", dot: "#7c3aed" },
  external: { bg: "#eff6ff", text: "#1e40af", dot: "#2563eb" },
};

const TYPE_COLOR: Record<string, string> = {
  "Identity Provider": "#7c3aed",
  "AI Gateway": "#0284c7",
  "Automation": "#059669",
  "File Source": "#d97706",
  "Utility": "#475569",
  "Datenbank": "#1d4ed8",
  "Connector": "#e11d48",
  "Dokumentation": "#0d9488",
};

function ConfigStatusDot({ configKey, config }: { configKey: string; config: ConfigMap }) {
  const entry = config[configKey];
  const isSet = entry?.is_secret ? (entry?.is_set ?? false) : !!(entry?.value);
  return (
    <span title={configKey} className="inline-block w-2 h-2 rounded-full"
      style={{ background: isSet ? "#22c55e" : "#e5e7eb" }} />
  );
}

export default function IntegrationOverviewPage() {
  const [config, setConfig] = useState<ConfigMap>({});
  const [filter, setFilter] = useState<"all" | "docker" | "external">("all");

  useEffect(() => {
    fetchConfig().then(setConfig).catch(() => {});
  }, []);

  const filtered = RESOURCES.filter(r => filter === "all" || r.location === filter);
  const docker = RESOURCES.filter(r => r.location === "docker").length;
  const external = RESOURCES.filter(r => r.location === "external").length;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold" style={{ color: "var(--ink)" }}>Integration Layer</h1>
        <p className="text-sm mt-1" style={{ color: "var(--ink-faint)" }}>
          Zentrale Verwaltung aller Docker-Ressourcen und externen Dienste
        </p>
      </div>

      {/* Stats */}
      <div className="flex gap-3 flex-wrap">
        {[
          { label: "Gesamt",  value: RESOURCES.length, color: "var(--ink)" },
          { label: "Docker",  value: docker,            color: "#7c3aed" },
          { label: "Extern",  value: external,          color: "#2563eb" },
        ].map(s => (
          <div key={s.label} className="neo-card px-5 py-3 flex items-center gap-3">
            <span className="text-2xl font-black" style={{ color: s.color }}>{s.value}</span>
            <span className="text-xs" style={{ color: "var(--ink-faint)" }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {(["all", "docker", "external"] as const).map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`neo-btn neo-btn--sm ${filter === f ? "neo-btn--default" : "neo-btn--outline"}`}>
            {f === "all" ? "Alle" : f === "docker" ? "Docker" : "Extern"}
          </button>
        ))}
      </div>

      {/* Resource grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {filtered.map(res => {
          const loc = LOCATION_COLOR[res.location];
          return (
            <a key={res.key} href={res.href}
              className="neo-card p-4 space-y-3 block hover:border-[var(--accent-red)] transition-colors"
              style={{ cursor: "pointer" }}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: loc.dot }} />
                    <h3 className="text-sm font-bold" style={{ color: "var(--ink)" }}>{res.name}</h3>
                  </div>
                  <p className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{res.description}</p>
                </div>
                <div className="flex flex-col gap-1 items-end shrink-0">
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
                    style={{ background: loc.bg, color: loc.text }}>
                    {res.location === "docker" ? "Docker" : "Extern"}
                  </span>
                  <span className="text-[10px] font-medium" style={{ color: TYPE_COLOR[res.type] ?? "var(--ink-faint)" }}>
                    {res.type}
                  </span>
                </div>
              </div>

              {/* Config status dots */}
              {res.configKeys && res.configKeys.length > 0 && (
                <div className="flex items-center gap-1.5">
                  {res.configKeys.map(k => (
                    <ConfigStatusDot key={k} configKey={k} config={config} />
                  ))}
                  <span className="text-[10px]" style={{ color: "var(--ink-faint)" }}>Konfiguration</span>
                </div>
              )}
            </a>
          );
        })}
      </div>
    </div>
  );
}
