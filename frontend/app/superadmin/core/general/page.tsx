"use client";

import { useState } from "react";
import { Boxes, Settings2, Building2, Shield, BookOpen, ClipboardList, ToggleRight, Menu, ScrollText } from "lucide-react";
import Link from "next/link";

const TABS = [
  { id: "general",   label: "Allgemein",          icon: Settings2,    href: "/superadmin/core/general" },
  { id: "orgs",      label: "Organisationen",      icon: Building2,    href: "/superadmin/organizations" },
  { id: "roles",     label: "Rollen & Rechte",     icon: Shield,       href: "/superadmin/core/roles" },
  { id: "artifacts", label: "Artefakte",            icon: BookOpen,     href: "/superadmin/core/artifacts" },
  { id: "stories",   label: "User Story Engine",   icon: ClipboardList,href: "/superadmin/core/stories" },
  { id: "flags",     label: "Feature Flags",        icon: ToggleRight,  href: "/superadmin/platform/features" },
  { id: "menus",     label: "Menüs & Navigation",  icon: Menu,         href: "/superadmin/core/menus" },
  { id: "audit",     label: "Auditlog",             icon: ScrollText,   href: "/superadmin/core/audit" },
];

export default function CoreGeneralPage() {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-violet-100">
          <Boxes className="h-6 w-6 text-violet-600" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)]">HeyKarl Core</h1>
          <p className="text-sm text-[var(--ink-muted)]">
            Fachliche Grundlogik — Organisationen, Benutzer, Rollen, Artefakte, Feature Flags
          </p>
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex flex-wrap gap-2 border-b border-[var(--border-subtle)] pb-3">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <Link key={tab.id} href={tab.href}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-[var(--ink-mid)] hover:bg-[var(--bg-hover)] hover:text-[var(--ink-strong)] transition-colors">
              <Icon className="h-4 w-4" />
              {tab.label}
            </Link>
          );
        })}
      </div>

      {/* Platform settings info */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[
          {
            title: "Organisationen & Mandanten",
            desc: "Verwaltung aller Organisationen, Mandantenkonfiguration, Komponentenfreischaltung.",
            href: "/superadmin/organizations",
            icon: Building2, color: "text-violet-600",
          },
          {
            title: "Benutzer & Rollen",
            desc: "Globale Benutzerverwaltung, Rollendefinitionen, Berechtigungsmodell.",
            href: "/superadmin/users",
            icon: Shield, color: "text-sky-600",
          },
          {
            title: "Feature Flags",
            desc: "Globale Feature-Defaults und Override-Policies pro Komponente.",
            href: "/superadmin/platform/features",
            icon: ToggleRight, color: "text-emerald-600",
          },
          {
            title: "Datenintegrität",
            desc: "Soft-Delete-Kontrolle für User Stories. Systemweite Integritätsgarantien.",
            href: "/superadmin/platform/integrity",
            icon: ScrollText, color: "text-rose-600",
          },
        ].map(card => (
          <Link key={card.href} href={card.href}
            className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4 hover:border-violet-300 transition-colors group">
            <div className="flex items-center gap-2 mb-2">
              <card.icon className={`h-5 w-5 ${card.color}`} />
              <h3 className="text-sm font-semibold text-[var(--ink-strong)] group-hover:text-violet-600">{card.title}</h3>
            </div>
            <p className="text-xs text-[var(--ink-muted)]">{card.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
