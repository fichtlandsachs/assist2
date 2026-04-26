"use client";

import Link from "next/link";
import {
  Boxes, MessageSquare, ShieldCheck, Database,
  Plug, Receipt, Server, ShieldAlert,
  ArrowRight, Activity, Users, Building2,
} from "lucide-react";
import useSWR from "swr";
import { fetcher } from "@/lib/api/client";

const COMPONENTS = [
  {
    id: "core", label: "Core", icon: Boxes, color: "text-violet-600", bg: "bg-violet-50",
    href: "/superadmin/core/general",
    description: "Organisationen, Benutzer, Rollen, Artefakte, Feature Flags",
  },
  {
    id: "conversation", label: "Conversation Engine", icon: MessageSquare, color: "text-sky-600", bg: "bg-sky-50",
    href: "/superadmin/conversation/profiles",
    description: "Dialogprofile, Fragebausteine, Antwortsignale, Prompt-Vorlagen",
  },
  {
    id: "compliance", label: "Compliance Engine", icon: ShieldCheck, color: "text-blue-600", bg: "bg-blue-50",
    href: "/superadmin/compliance/frameworks",
    description: "Frameworks, Controls, Risiko-Scoring, Evidence, Gates",
  },
  {
    id: "knowledge", label: "KnowledgeBase / RAG", icon: Database, color: "text-amber-600", bg: "bg-amber-50",
    href: "/superadmin/knowledge/sources",
    description: "Quellen, Trust Engine, Retrieval-Regeln, Index-Verwaltung",
  },
  {
    id: "integration", label: "Integration Layer", icon: Plug, color: "text-emerald-600", bg: "bg-emerald-50",
    href: "/superadmin/integration/overview",
    description: "Docker-Ressourcen, externe Services, Admin-UIs, Connectoren",
  },
  {
    id: "accounting", label: "Accounting", icon: Receipt, color: "text-orange-600", bg: "bg-orange-50",
    href: "/superadmin/accounting/plans",
    description: "Pläne, Komponentenfreischaltungen, Nutzung, Abrechnung",
  },
  {
    id: "resources", label: "Ressourcen", icon: Server, color: "text-slate-600", bg: "bg-slate-50",
    href: "/superadmin/resources/overview",
    description: "Docker Services, Datenbanken, Modelle, Monitoring",
  },
  {
    id: "system", label: "System / Sicherheit", icon: ShieldAlert, color: "text-rose-600", bg: "bg-rose-50",
    href: "/superadmin/system/security",
    description: "Sicherheit, Backup, globale Einstellungen, Audit",
  },
];

export default function SuperadminDashboard() {
  const { data: stats } = useSWR<Record<string, number>>("/api/v1/superadmin/stats", fetcher, {
    revalidateOnFocus: false,
  });

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink-strong)]">HeyKarl Superadmin</h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Plattform-Administration · Komponentenarchitektur
        </p>
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Organisationen", value: stats?.organizations ?? "—", icon: Building2, color: "text-violet-600" },
          { label: "Benutzer",       value: stats?.users ?? "—",         icon: Users,     color: "text-sky-600" },
          { label: "User Stories",   value: stats?.stories ?? "—",       icon: Boxes,     color: "text-emerald-600" },
          { label: "Systemstatus",   value: "OK",                        icon: Activity,  color: "text-green-600" },
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

      {/* Architecture: 8 component tiles */}
      <div>
        <h2 className="text-sm font-semibold text-[var(--ink-strong)] mb-3">Plattform-Komponenten</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
          {COMPONENTS.map(comp => (
            <Link key={comp.id} href={comp.href}
              className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4 hover:border-[var(--accent-red)] transition-colors group">
              <div className="flex items-center gap-3 mb-2">
                <div className={`p-2 rounded-lg ${comp.bg}`}>
                  <comp.icon className={`h-5 w-5 ${comp.color}`} />
                </div>
                <h3 className="text-sm font-semibold text-[var(--ink-strong)] group-hover:text-[var(--accent-red)] transition-colors">
                  {comp.label}
                </h3>
              </div>
              <p className="text-xs text-[var(--ink-muted)] leading-relaxed">{comp.description}</p>
              <div className="flex items-center gap-1 text-xs text-[var(--ink-muted)] mt-3 group-hover:text-[var(--accent-red)]">
                Konfigurieren <ArrowRight className="h-3.5 w-3.5" />
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Architecture note */}
      <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5">
        <h2 className="text-sm font-semibold text-[var(--ink-strong)] mb-3">Architektur-Prinzipien</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2 text-xs text-[var(--ink-muted)]">
          {[
            "Core bleibt fachlich sauber — keine externen Abhängigkeiten",
            "Integration Layer verwaltet ALLE Docker- und externen Ressourcen",
            "Authentik, LiteLLM und n8n gehören zum Integration Layer",
            "KnowledgeBase nutzt externe Quellen nur über den Integration Layer",
            "Compliance Engine ist lose gekoppelt — nur über definierte APIs",
            "Conversation Engine greift nicht direkt auf Compliance-Modelle zu",
            "Gelöschte User Stories werden systemweit nie referenziert",
            "Alle Änderungen sind auditierbar",
          ].map((p, i) => (
            <div key={i} className="flex items-start gap-2 py-1">
              <span className="text-[var(--accent-red)] font-bold shrink-0">→</span>
              {p}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
