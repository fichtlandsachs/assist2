"use client";

import { useState } from "react";
import {
  Plug, Container, ExternalLink, KeyRound, Bot, Workflow, Cloud,
  FileText, MessageSquare, Database, PanelTop, Activity,
  CheckCircle2, XCircle, AlertTriangle, Clock, RefreshCw,
  Globe, Server,
} from "lucide-react";
import Link from "next/link";

interface Resource {
  key: string; name: string; type: string; location: "docker" | "external";
  status: "active" | "degraded" | "unreachable" | "unknown";
  href: string; icon: React.ElementType; description: string;
}

const BUILT_IN_RESOURCES: Resource[] = [
  { key: "authentik",     name: "Authentik",     type: "identity_provider",    location: "docker",   status: "active",    href: "/superadmin/integration/authentik",    icon: KeyRound,      description: "SSO / Identity Provider" },
  { key: "litellm",       name: "LiteLLM",       type: "ai_model_gateway",     location: "docker",   status: "active",    href: "/superadmin/integration/litellm",      icon: Bot,           description: "AI Model Gateway" },
  { key: "n8n",           name: "n8n",           type: "automation_service",   location: "docker",   status: "active",    href: "/superadmin/integration/n8n",          icon: Workflow,      description: "Workflow Automation" },
  { key: "nextcloud",     name: "Nextcloud",     type: "file_source",          location: "docker",   status: "unknown",   href: "/superadmin/integration/nextcloud",    icon: Cloud,         description: "File Storage & Collaboration" },
  { key: "stirling",      name: "Stirling PDF",  type: "utility_service",      location: "docker",   status: "unknown",   href: "/superadmin/integration/stirling",     icon: FileText,      description: "PDF Processing" },
  { key: "whisper",       name: "Whisper",       type: "utility_service",      location: "docker",   status: "unknown",   href: "/superadmin/integration/whisper",      icon: MessageSquare, description: "Speech-to-Text" },
  { key: "postgres",      name: "PostgreSQL",    type: "database",             location: "docker",   status: "active",    href: "/superadmin/integration/databases",    icon: Database,      description: "Primary Database" },
  { key: "redis",         name: "Redis",         type: "database",             location: "docker",   status: "active",    href: "/superadmin/integration/databases",    icon: Database,      description: "Cache & Queue" },
  { key: "pgadmin",       name: "pgAdmin",       type: "admin_ui",             location: "docker",   status: "unknown",   href: "/superadmin/integration/admin-uis",    icon: PanelTop,      description: "PostgreSQL Admin UI" },
  { key: "phpmyadmin",    name: "phpMyAdmin",    type: "admin_ui",             location: "docker",   status: "unknown",   href: "/superadmin/integration/admin-uis",    icon: PanelTop,      description: "MySQL/MariaDB Admin UI" },
  { key: "redis-cmd",     name: "Redis Commander",type: "admin_ui",            location: "docker",   status: "unknown",   href: "/superadmin/integration/admin-uis",    icon: PanelTop,      description: "Redis Admin UI" },
  { key: "jira",          name: "Jira",          type: "api_connector",        location: "external", status: "unknown",   href: "/superadmin/integration/connectors",   icon: Globe,         description: "Issue Tracking" },
  { key: "confluence",    name: "Confluence",    type: "documentation_source", location: "external", status: "unknown",   href: "/superadmin/integration/documentation",icon: Globe,         description: "Wiki & Documentation" },
  { key: "github",        name: "GitHub",        type: "api_connector",        location: "external", status: "unknown",   href: "/superadmin/integration/connectors",   icon: Globe,         description: "Source Control" },
];

const TYPE_LABELS: Record<string, string> = {
  identity_provider: "Identity Provider",
  ai_model_gateway: "AI Gateway",
  automation_service: "Automation",
  file_source: "File Source",
  utility_service: "Utility",
  database: "Datenbank",
  admin_ui: "Admin UI",
  api_connector: "Connector",
  documentation_source: "Dokumentation",
};

const TYPE_COLOR: Record<string, string> = {
  identity_provider: "bg-violet-100 text-violet-700",
  ai_model_gateway: "bg-sky-100 text-sky-700",
  automation_service: "bg-emerald-100 text-emerald-700",
  file_source: "bg-amber-100 text-amber-700",
  utility_service: "bg-slate-100 text-slate-600",
  database: "bg-blue-100 text-blue-700",
  admin_ui: "bg-orange-100 text-orange-700",
  api_connector: "bg-rose-100 text-rose-700",
  documentation_source: "bg-teal-100 text-teal-700",
};

function StatusBadge({ status }: { status: Resource["status"] }) {
  const map = {
    active:      { icon: CheckCircle2, color: "text-green-600", label: "Aktiv" },
    degraded:    { icon: AlertTriangle, color: "text-amber-500", label: "Degradiert" },
    unreachable: { icon: XCircle, color: "text-red-500", label: "Nicht erreichbar" },
    unknown:     { icon: Clock, color: "text-slate-400", label: "Unbekannt" },
  };
  const { icon: Icon, color, label } = map[status];
  return (
    <span className={`flex items-center gap-1 text-xs font-medium ${color}`}>
      <Icon className="h-3.5 w-3.5" /> {label}
    </span>
  );
}

export default function IntegrationOverviewPage() {
  const [filter, setFilter] = useState<"all" | "docker" | "external">("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const dockerResources = BUILT_IN_RESOURCES.filter(r => r.location === "docker");
  const externalResources = BUILT_IN_RESOURCES.filter(r => r.location === "external");
  const adminUIs = BUILT_IN_RESOURCES.filter(r => r.type === "admin_ui");

  const filtered = BUILT_IN_RESOURCES.filter(r =>
    (filter === "all" || r.location === filter) &&
    (typeFilter === "all" || r.type === typeFilter)
  );

  const types = [...new Set(BUILT_IN_RESOURCES.map(r => r.type))];

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <Plug className="h-5 w-5 text-emerald-600" />
          Integration Layer — Übersicht
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Zentrale Verwaltung aller Docker- und externen Ressourcen
        </p>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Gesamt Ressourcen", value: BUILT_IN_RESOURCES.length, icon: Server, color: "text-[var(--ink-strong)]" },
          { label: "Docker Services", value: dockerResources.length, icon: Container, color: "text-violet-600" },
          { label: "Externe Services", value: externalResources.length, icon: ExternalLink, color: "text-sky-600" },
          { label: "Admin-UIs", value: adminUIs.length, icon: PanelTop, color: "text-orange-600" },
        ].map(kpi => (
          <div key={kpi.label} className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4">
            <div className="flex items-center gap-2 mb-1">
              <kpi.icon className={`h-4 w-4 ${kpi.color}`} />
              <span className="text-xs text-[var(--ink-muted)]">{kpi.label}</span>
            </div>
            <p className={`text-2xl font-bold ${kpi.color}`}>{kpi.value}</p>
          </div>
        ))}
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {[
          { label: "Docker-Ressourcen", href: "/superadmin/integration/docker", icon: Container, color: "bg-violet-50 border-violet-200 text-violet-700" },
          { label: "Externe Ressourcen", href: "/superadmin/integration/external", icon: ExternalLink, color: "bg-sky-50 border-sky-200 text-sky-700" },
          { label: "Admin-UIs", href: "/superadmin/integration/admin-uis", icon: PanelTop, color: "bg-orange-50 border-orange-200 text-orange-700" },
          { label: "Health Checks", href: "/superadmin/integration/health", icon: Activity, color: "bg-green-50 border-green-200 text-green-700" },
        ].map(link => (
          <Link key={link.href} href={link.href}
            className={`flex items-center gap-2 px-3 py-2.5 rounded-lg border text-sm font-medium hover:opacity-80 transition-opacity ${link.color}`}>
            <link.icon className="h-4 w-4" />
            {link.label}
          </Link>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex rounded-lg overflow-hidden border border-[var(--border-subtle)]">
          {(["all", "docker", "external"] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors
                ${filter === f ? "bg-emerald-600 text-white" : "bg-[var(--bg-card)] text-[var(--ink-muted)] hover:bg-[var(--bg-hover)]"}`}>
              {f === "all" ? "Alle" : f === "docker" ? "Docker" : "Extern"}
            </button>
          ))}
        </div>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="px-2.5 py-1.5 text-xs bg-[var(--bg-card)] border border-[var(--border-subtle)] rounded-lg focus:outline-none">
          <option value="all">Alle Typen</option>
          {types.map(t => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
        </select>
        <span className="text-xs text-[var(--ink-muted)] ml-auto">{filtered.length} Ressourcen</span>
      </div>

      {/* Resource grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
        {filtered.map(res => {
          const Icon = res.icon;
          return (
            <Link key={res.key} href={res.href}
              className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4 hover:border-emerald-300 transition-colors group">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className={`p-2 rounded-lg ${res.location === "docker" ? "bg-violet-100" : "bg-sky-100"}`}>
                    <Icon className={`h-4 w-4 ${res.location === "docker" ? "text-violet-600" : "text-sky-600"}`} />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-[var(--ink-strong)] group-hover:text-emerald-600 transition-colors">
                      {res.name}
                    </h3>
                    <p className="text-xs text-[var(--ink-muted)]">{res.description}</p>
                  </div>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${res.location === "docker" ? "bg-violet-100 text-violet-700" : "bg-sky-100 text-sky-700"}`}>
                    {res.location === "docker" ? "Docker" : "Extern"}
                  </span>
                  <StatusBadge status={res.status} />
                </div>
              </div>
              <div className="mt-3">
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${TYPE_COLOR[res.type] ?? "bg-slate-100 text-slate-600"}`}>
                  {TYPE_LABELS[res.type] ?? res.type}
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
