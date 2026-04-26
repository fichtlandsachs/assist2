"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getSession, logout } from "@/lib/auth";

interface NavItem { label: string; href: string; matchPrefix?: string; }
interface NavSection { id: string; label: string; icon: React.ReactNode; color: string; items: NavItem[]; }

const NAV: NavSection[] = [
  {
    id: "core", label: "Core", color: "#7c3aed",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>,
    items: [
      { label: "Allgemein",        href: "/core/general" },
      { label: "Organisationen",   href: "/core/organizations" },
      { label: "Rollen & Rechte",  href: "/core/roles" },
      { label: "User Story Engine",href: "/core/stories" },
      { label: "Feature Flags",    href: "/core/feature-flags" },
      { label: "Auditlog",         href: "/core/audit" },
    ],
  },
  {
    id: "conversation", label: "Conversation Engine", color: "#0284c7",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
    items: [
      { label: "Dialogprofile",    href: "/conversation/profiles" },
      { label: "Fragebausteine",   href: "/conversation/questions" },
      { label: "Antwortsignale",   href: "/conversation/signals" },
      { label: "Prompt-Vorlagen",  href: "/conversation/prompts" },
      { label: "Gesprächsregeln",  href: "/conversation/rules" },
      { label: "Testkonsole",      href: "/conversation/testconsole" },
      { label: "Auditlog",         href: "/conversation/audit" },
    ],
  },
  {
    id: "compliance", label: "Compliance Engine", color: "#1d4ed8",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>,
    items: [
      { label: "Frameworks",       href: "/compliance/frameworks" },
      { label: "Controls",         href: "/compliance/controls" },
      { label: "Risiko-Scoring",   href: "/compliance/risk-scoring" },
      { label: "Evidence",         href: "/compliance/evidence" },
      { label: "Gates & Reviews",  href: "/compliance/gates" },
      { label: "Auditlog",         href: "/compliance/audit" },
    ],
  },
  {
    id: "knowledge", label: "KnowledgeBase / RAG", color: "#d97706",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>,
    items: [
      { label: "Quellen",          href: "/knowledge/sources" },
      { label: "Ingest Jobs",      href: "/knowledge/ingest" },
      { label: "Trust Engine",     href: "/knowledge/trust" },
      { label: "Retrieval-Regeln", href: "/knowledge/retrieval" },
      { label: "Index-Verwaltung", href: "/knowledge/index" },
      { label: "Such-Testkonsole", href: "/knowledge/search" },
    ],
  },
  {
    id: "integration", label: "Integration Layer", color: "#059669",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M6 9v3a6 6 0 0 0 6 6h3"/><path d="M18 15v-3a6 6 0 0 0-6-6H9"/></svg>,
    items: [
      { label: "Übersicht",         href: "/integration/overview" },
      { label: "Docker-Ressourcen", href: "/integration/docker" },
      { label: "Externe Ressourcen",href: "/integration/external" },
      { label: "Authentik",         href: "/integration/authentik" },
      { label: "LiteLLM",           href: "/integration/litellm" },
      { label: "n8n",               href: "/integration/n8n" },
      { label: "Nextcloud",         href: "/integration/nextcloud" },
      { label: "Stirling PDF",      href: "/integration/stirling" },
      { label: "Whisper",           href: "/integration/whisper" },
      { label: "Datenbanken",       href: "/integration/databases" },
      { label: "Admin-UIs",         href: "/integration/admin-uis" },
      { label: "Connectoren",       href: "/integration/connectors" },
      { label: "Dokumentationsquellen", href: "/integration/documentation" },
      { label: "Webhooks",          href: "/integration/webhooks" },
      { label: "Health Checks",     href: "/integration/health" },
      { label: "Logs",              href: "/integration/logs" },
      { label: "Secrets",           href: "/integration/secrets" },
    ],
  },
  {
    id: "accounting", label: "Accounting", color: "#ea580c",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>,
    items: [
      { label: "Pläne",                      href: "/accounting/plans" },
      { label: "Komponentenfreischaltungen", href: "/accounting/entitlements" },
      { label: "Nutzung",                    href: "/accounting/usage" },
      { label: "Abrechnung",                 href: "/accounting/billing" },
      { label: "Limits",                     href: "/accounting/limits" },
    ],
  },
  {
    id: "resources", label: "Ressourcen", color: "#475569",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="4" rx="1"/><rect x="2" y="10" width="20" height="4" rx="1"/><rect x="2" y="17" width="20" height="4" rx="1"/><circle cx="18" cy="5" r="1" fill="currentColor" stroke="none"/><circle cx="18" cy="12" r="1" fill="currentColor" stroke="none"/><circle cx="18" cy="19" r="1" fill="currentColor" stroke="none"/></svg>,
    items: [
      { label: "Ressourcenübersicht", href: "/resources/overview" },
      { label: "Docker Services",     href: "/resources/docker-services" },
      { label: "Externe Services",    href: "/resources/external-services" },
      { label: "Datenbanken",         href: "/resources/databases" },
      { label: "Monitoring",          href: "/resources/monitoring" },
    ],
  },
  {
    id: "system", label: "System", color: "#e11d48",
    icon: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
    items: [
      { label: "Sicherheit",            href: "/system/security" },
      { label: "Backup",                href: "/system/backup" },
      { label: "Globale Einstellungen", href: "/settings/system" },
      { label: "Systemstatus",          href: "/dashboard" },
      { label: "Auditlog",              href: "/system/audit" },
    ],
  },
];

export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => {
    const active = NAV.find(s => s.items.some(i => pathname.startsWith(i.href))) ?? NAV[0];
    return new Set([active.id]);
  });

  useEffect(() => {
    const session = getSession();
    if (!session) router.replace("/login");
    else setChecked(true);
  }, [router]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: "var(--paper)" }}>
        <div className="w-4 h-4 rounded-full border-2 border-[var(--accent-red)] border-t-transparent animate-spin" />
      </div>
    );
  }

  const toggle = (id: string) => {
    setExpanded(prev => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  return (
    <div className="flex min-h-screen" style={{ background: "var(--paper)" }}>
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 border-r flex flex-col"
        style={{ borderColor: "var(--paper-rule)", background: "var(--paper-warm)" }}>

        {/* Logo */}
        <div className="px-3 py-4 border-b flex items-center gap-2.5" style={{ borderColor: "var(--paper-rule)" }}>
          <div className="flex items-center justify-center w-7 h-7 rounded-lg border-2 font-bold text-xs select-none"
            style={{ background: "#231F1F", borderColor: "#231F1F", color: "#fff", fontStyle: "italic" }}>
            K
          </div>
          <div>
            <p className="text-xs font-bold tracking-widest uppercase" style={{ color: "var(--ink-faint)", letterSpacing: "0.15em" }}>
              HeyKarl Admin
            </p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
          {NAV.map((section) => {
            const isOpen = expanded.has(section.id);
            const isActive = section.items.some(i =>
              pathname === i.href || pathname.startsWith((i.matchPrefix ?? i.href) + "/")
            );
            return (
              <div key={section.id}>
                <button onClick={() => toggle(section.id)}
                  className="sidebar-nav-item w-full flex items-center gap-2 px-2 py-2 text-left"
                  style={{ color: isActive ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
                  <span style={{ color: section.color }}>{section.icon}</span>
                  <span className="flex-1 text-xs font-semibold">{section.label}</span>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    style={{ transform: isOpen ? "rotate(90deg)" : "none", transition: "transform 0.15s" }}>
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                </button>
                {isOpen && (
                  <div className="ml-4 border-l pl-2 space-y-0.5 mt-0.5" style={{ borderColor: "var(--paper-rule)" }}>
                    {section.items.map(item => {
                      const active = pathname === item.href || pathname.startsWith((item.matchPrefix ?? item.href) + "/");
                      return (
                        <button key={item.href} onClick={() => router.push(item.href)}
                          className={`sidebar-nav-item w-full flex items-center text-left px-2 py-1.5 text-[11px]${active ? " is-active" : ""}`}
                          style={{ color: active ? "var(--sidebar-text-active)" : "var(--sidebar-text)" }}>
                          {item.label}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </nav>

        {/* Footer */}
        <div className="px-3 py-3 border-t" style={{ borderColor: "var(--paper-rule)" }}>
          <button onClick={logout}
            className="text-xs w-full text-left transition-colors"
            style={{ color: "var(--ink-faint)" }}
            onMouseEnter={e => (e.currentTarget.style.color = "var(--ink)")}
            onMouseLeave={e => (e.currentTarget.style.color = "var(--ink-faint)")}>
            Abmelden
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 overflow-auto p-8">
        {children}
      </main>
    </div>
  );
}
