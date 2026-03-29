# Notebook Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the neobrutalist design system with a paper/notebook aesthetic across all pages, rebuild the shell (Sidebar, Topbar), and add a new AI Workspace page with backend-integrated streaming chat.

**Architecture:** Update `globals.css` and `tailwind.config.ts` to replace all design tokens; rewrite `Sidebar` and `Topbar` components; update `Button`, `Card`, `Badge` UI primitives; add `/api/v1/ai/chat` (SSE) and `/api/v1/ai/extract-story` backend endpoints; create `/[org]/ai-workspace` frontend page.

**Tech Stack:** Next.js 15, React 19, Tailwind CSS 4, FastAPI, anthropic Python SDK (already in project), Lora + Crimson Pro + JetBrains Mono (Google Fonts)

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `frontend/app/globals.css` | Modify | Replace design tokens + utility classes |
| `frontend/tailwind.config.ts` | Modify | Replace color/font/shadow theme |
| `frontend/app/layout.tsx` | Modify | Swap Space Grotesk for Lora/Crimson Pro/JetBrains Mono |
| `frontend/app/[org]/layout.tsx` | Modify | Update wrapper background + main ruled-line background |
| `frontend/components/shell/Sidebar.tsx` | Modify | Rebuild to binding/notebook style |
| `frontend/components/shell/Topbar.tsx` | Modify | Rebuild to paper header style |
| `frontend/components/ui/button.tsx` | Modify | Update to paper aesthetic |
| `frontend/components/ui/card.tsx` | Modify | Update to paper aesthetic |
| `frontend/components/ui/badge.tsx` | Modify | Update to paper aesthetic (pill, mono font) |
| `backend/app/routers/ai.py` | Modify | Add `/ai/chat` SSE + `/ai/extract-story` endpoints |
| `backend/tests/unit/test_ai_chat.py` | Create | Unit tests for the two new endpoints |
| `frontend/app/[org]/ai-workspace/page.tsx` | Create | Two-column AI chat + Story panel page |

---

## Task 1: Replace design tokens

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tailwind.config.ts`

- [ ] **Step 1: Replace globals.css**

```css
@import "tailwindcss";

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --paper:        #faf9f6;
  --paper-warm:   #f7f4ee;
  --paper-rule:   #e2ddd4;
  --paper-rule2:  #ece8e0;
  --margin-red:   #e8b4b0;
  --ink:          #1c1810;
  --ink-mid:      #5a5040;
  --ink-faint:    #a09080;
  --ink-faintest: #cec8bc;
  --accent-red:   #c0392b;
  --green:        #2d6a4f;
  --brown:        #8b4513;
  --navy:         #1e3a5f;
  --binding:      #2a2018;
  --line-h:       28px;
  --font-serif:   'Lora', serif;
  --font-body:    'Crimson Pro', serif;
  --font-mono:    'JetBrains Mono', monospace;
  --sidebar-width: 200px;
  --topbar-height: 48px;
}

html {
  scroll-behavior: smooth;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  background:
    repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,0,0,.03) 39px, rgba(0,0,0,.03) 40px),
    repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,0,0,.03) 39px, rgba(0,0,0,.03) 40px),
    #c8c2b8;
  color: var(--ink);
  font-family: var(--font-body);
  font-size: 1rem;
  line-height: 1.6;
  min-height: 100vh;
}

h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-serif);
  font-style: italic;
  font-weight: 400;
  line-height: 1.2;
  color: var(--ink);
}

a { color: inherit; text-decoration: none; }
img, video { max-width: 100%; height: auto; }
button { cursor: pointer; font-family: var(--font-body); }
::selection { background-color: var(--accent-red); color: var(--paper); }

/* ── Paper utility classes (used by existing pages) ── */
.neo-card {
  background: var(--paper);
  border: 1px solid var(--paper-rule);
  border-radius: 2px;
  transition: border-color .15s;
}
.neo-card:hover { border-color: var(--ink-faintest); }
.neo-card--flat { background: var(--paper); border: 1px solid var(--paper-rule); }
.neo-card--orange { background: var(--paper); border: 1px solid var(--paper-rule); border-left: 3px solid #c0392b; }
.neo-card--yellow { background: var(--paper); border: 1px solid var(--paper-rule); border-left: 3px solid var(--brown); }
.neo-card--teal   { background: var(--paper); border: 1px solid var(--paper-rule); border-left: 3px solid var(--green); }

.neo-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
  font-family: var(--font-mono); font-size: 9px; letter-spacing: .06em; text-transform: uppercase;
  padding: 5px 12px; border-radius: 2px;
  border: 0.5px solid var(--ink-faintest);
  background: transparent; color: var(--ink-mid);
  cursor: pointer; transition: all .12s; user-select: none;
}
.neo-btn:hover { background: var(--paper-rule2); color: var(--ink); border-color: var(--ink-faint); }
.neo-btn:active { opacity: .7; }
.neo-btn--default { background: var(--ink); color: var(--paper); border-color: var(--ink); }
.neo-btn--default:hover { background: var(--ink-mid); }
.neo-btn--outline { background: transparent; color: var(--ink); }
.neo-btn--orange  { background: var(--accent-red); color: var(--paper); border-color: var(--accent-red); }
.neo-btn--orange:hover { background: #a93226; }
.neo-btn--ghost   { background: transparent; border-color: transparent; box-shadow: none; }
.neo-btn--ghost:hover { background: rgba(28,24,16,.06); }
.neo-btn--sm { font-size: 8px; padding: 3px 8px; }
.neo-btn--lg { font-size: 10px; padding: 7px 16px; }

/* ── Badge utility classes ── */
.badge-base {
  display: inline-flex; align-items: center; gap: 3px;
  font-family: var(--font-mono); font-size: 7px; letter-spacing: .08em;
  text-transform: uppercase; font-weight: 500;
  padding: 2px 8px; border-radius: 10px;
  border: 0.5px solid currentColor;
}
.badge-met         { color: var(--green); background: rgba(45,106,79,.1); }
.badge-partial     { color: var(--brown); background: rgba(139,69,19,.1); }
.badge-missing     { color: var(--accent-red); background: rgba(192,57,43,.08); }
.badge-open        { color: var(--navy); background: rgba(30,58,95,.08); }
.badge-direct      { color: var(--green); background: rgba(45,106,79,.1); }
.badge-interpreted { color: var(--brown); background: rgba(139,69,19,.1); }
.badge-nis2        { color: var(--ink); background: var(--paper-rule2); }
.badge-kritis      { color: var(--accent-red); background: rgba(192,57,43,.08); }

/* ── Input ── */
.neo-input {
  background: var(--paper-warm);
  border: 1px solid var(--paper-rule);
  border-radius: 2px;
  padding: 6px 10px;
  font-family: var(--font-body); font-size: 14px;
  color: var(--ink); width: 100%; outline: none;
  transition: border-color .15s;
}
.neo-input:focus { border-color: var(--ink-faint); }
.neo-input::placeholder { color: var(--ink-faintest); }

/* ── Table ── */
.neo-table { width: 100%; border-collapse: collapse; }
.neo-table th {
  font-family: var(--font-mono); font-size: 8px; letter-spacing: .1em;
  text-transform: uppercase; font-weight: 500;
  padding: 8px 12px; color: var(--ink-mid);
  border-bottom: 1px solid var(--ink-faintest); text-align: left;
}
.neo-table td {
  padding: 10px 12px; font-size: 14px;
  border-bottom: 1px solid var(--paper-rule); color: var(--ink);
}
.neo-table tr:last-child td { border-bottom: none; }
.neo-table tr:hover td { background: rgba(255,255,255,.5); }

/* ── Sidebar nav (legacy class, overridden by shell component) ── */
.sidebar-link {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px;
  font-family: var(--font-mono); font-size: 9px; letter-spacing: .08em;
  text-transform: uppercase; color: rgba(255,255,255,.45);
  cursor: pointer; text-decoration: none;
  transition: all .12s; border-radius: 0;
}
.sidebar-link:hover { background: rgba(255,255,255,.06); color: rgba(255,255,255,.8); }
.sidebar-link--active { color: rgba(255,255,255,.95); border-left: 2px solid var(--paper); }

/* ── Section divider ── */
.section-divider { border: none; border-top: 1px solid var(--paper-rule); }

/* ── Progress ── */
.neo-progress { height: 4px; background: var(--paper-rule); border-radius: 2px; overflow: hidden; }
.neo-progress__bar { height: 100%; background: var(--green); transition: width .4s ease; }
.neo-progress__bar--teal   { background: var(--green); }
.neo-progress__bar--yellow { background: var(--brown); }

/* ── Heatmap ── */
.heatmap-cell { width: 100%; aspect-ratio: 1; border: 0.5px solid var(--paper-rule); transition: transform .1s ease; }
.heatmap-cell:hover { transform: scale(1.15); z-index: 10; position: relative; }
.heatmap-high { background: #4a9e6b; }
.heatmap-mid  { background: #c4a35a; }
.heatmap-low  { background: rgba(192,57,43,.65); }
.heatmap-none { background: var(--paper-rule2); }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 3px; height: 3px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--paper-rule); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--ink-faintest); }

/* ── Focus ── */
:focus-visible { outline: 1.5px solid var(--accent-red); outline-offset: 2px; }

/* ── Animations ── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes slideInLeft {
  from { opacity: 0; transform: translateX(-12px); }
  to   { opacity: 1; transform: translateX(0); }
}
@keyframes inkIn {
  from { opacity: 0; transform: translateY(3px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-fade-in-up  { animation: fadeInUp 0.4s ease forwards; }
.animate-slide-in-left { animation: slideInLeft 0.3s ease forwards; }
.animate-ink-in      { animation: inkIn 0.18s ease both; }
```

- [ ] **Step 2: Replace tailwind.config.ts**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: {
          DEFAULT: "#faf9f6",
          warm:    "#f7f4ee",
          rule:    "#e2ddd4",
          rule2:   "#ece8e0",
        },
        ink: {
          DEFAULT:  "#1c1810",
          mid:      "#5a5040",
          faint:    "#a09080",
          faintest: "#cec8bc",
        },
        binding: "#2a2018",
        accent:  "#c0392b",
        "margin-red": "#e8b4b0",
        // Section accents
        "col-story":   "#2d6a4f",
        "col-accept":  "#1e3a5f",
        "col-test":    "#6b3a2a",
        "col-release": "#5a3a7a",
        // Keep status for compliance pages
        status: {
          met:     "#4a9e6b",
          partial: "#c4a35a",
          missing: "#c0392b",
          open:    "#1e3a5f",
        },
      },
      fontFamily: {
        serif:   ["'Lora'", "serif"],
        body:    ["'Crimson Pro'", "serif"],
        mono:    ["'JetBrains Mono'", "monospace"],
        heading: ["'Lora'", "serif"],
        sans:    ["Inter", "system-ui", "sans-serif"],
      },
      spacing: {
        "18":     "4.5rem",
        "22":     "5.5rem",
        sidebar:  "200px",
        topbar:   "48px",
      },
      keyframes: {
        "ink-in": {
          "0%":   { opacity: "0", transform: "translateY(3px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%":   { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-left": {
          "0%":   { opacity: "0", transform: "translateX(-12px)" },
          "100%": { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        "ink-in":        "ink-in 0.18s ease both",
        "fade-in":       "fade-in 0.4s ease forwards",
        "slide-in-left": "slide-in-left 0.3s ease forwards",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/globals.css frontend/tailwind.config.ts
git commit -m "feat(design): replace neobrutalist tokens with paper/notebook design system"
```

---

## Task 2: Update fonts in root layout

**Files:**
- Modify: `frontend/app/layout.tsx`

- [ ] **Step 1: Update layout.tsx — replace fonts**

Replace the entire file:

```tsx
import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "assist2 — Compliance-Dokumentation. Automatisiert. Auditierbar.",
    template: "%s | assist2",
  },
  description:
    "assist2 ist die Compliance-Dokumentationsplattform für NIS2, KRITIS und ISO27001. Automatisierte Prozessdokumentation, BCM-Management und auditierbare Nachweise — ohne Halluzinationen.",
  keywords: ["NIS2", "KRITIS", "BCM", "Business Continuity Management", "Compliance", "Dokumentation", "ISO27001", "IT-Sicherheit", "ISMS", "Auditierung"],
  authors: [{ name: "assist2 GmbH" }],
  creator: "assist2 GmbH",
  metadataBase: new URL("https://assist2.io"),
  openGraph: {
    type: "website", locale: "de_DE", url: "https://assist2.io", siteName: "assist2",
    title: "assist2 — Compliance-Dokumentation. Automatisiert. Auditierbar.",
    description: "Die Compliance-Plattform für NIS2 & KRITIS. Prozessdokumentation, BCM und Audit-Trail ohne Aufwand.",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "assist2 — Compliance Platform" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "assist2 — Compliance. Automatisiert.",
    description: "NIS2, KRITIS und ISO27001 Compliance-Dokumentation. Automatisiert und auditierbar.",
    images: ["/og-image.png"],
  },
  robots: {
    index: true, follow: true,
    googleBot: { index: true, follow: true, "max-video-preview": -1, "max-image-preview": "large", "max-snippet": -1 },
  },
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "any" }, { url: "/icon.svg", type: "image/svg+xml" }],
    apple: "/apple-touch-icon.png",
  },
  manifest: "/site.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#faf9f6",
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Lora:ital,wght@0,400;0,500;1,400;1,500&family=Crimson+Pro:ital,wght@0,300;0,400;1,300;1,400&family=JetBrains+Mono:wght@300;400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased" style={{ fontFamily: "var(--font-body)", color: "var(--ink)" }}>
        {children}
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Update org layout background**

In `frontend/app/[org]/layout.tsx`, replace these two lines:

Old:
```tsx
  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
```

New:
```tsx
  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--paper)" }}>
```

Also update the loading spinner:

Old:
```tsx
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500" />
```

New:
```tsx
      <div className="animate-spin rounded-full h-8 w-8" style={{ borderBottom: "2px solid var(--ink-mid)" }} />
```

And update `<main>` to add ruled-line background:

Old:
```tsx
        <main className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6">
```

New:
```tsx
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6"
          style={{
            background: `repeating-linear-gradient(180deg, transparent, transparent calc(var(--line-h) - 1px), var(--paper-rule) calc(var(--line-h) - 1px), var(--paper-rule) var(--line-h)) var(--paper)`
          }}
        >
```

- [ ] **Step 3: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/\[org\]/layout.tsx
git commit -m "feat(design): update root and org layouts for notebook aesthetic"
```

---

## Task 3: Rebuild Sidebar

**Files:**
- Modify: `frontend/components/shell/Sidebar.tsx`

- [ ] **Step 1: Rewrite Sidebar.tsx**

Replace the entire file:

```tsx
"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, Settings, BookOpen, Inbox, CalendarDays, FileText,
  Workflow, Folder, Globe, Bell, Star, Zap, Users, Shield, MessageSquare,
  X, type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth/context";
import { usePluginRegistry } from "@/lib/plugins/registry";
import { SlotRenderer } from "@/lib/plugins/slots";

const PLUGIN_ICONS: Record<string, LucideIcon> = {
  folder: Folder, globe: Globe, bell: Bell, star: Star,
  zap: Zap, users: Users, file: FileText, workflow: Workflow,
};

interface SidebarProps {
  orgSlug: string;
  orgId?: string;
  mobileOpen?: boolean;
  onMobileClose?: () => void;
}

export function Sidebar({ orgSlug, orgId, mobileOpen = false, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const { navEntries } = usePluginRegistry(orgId ?? "");

  const navItems = [
    { id: "dashboard",    label: "Dashboard",      icon: LayoutDashboard, route: `/${orgSlug}/dashboard` },
    { id: "ai-workspace", label: "KI Workspace",   icon: MessageSquare,   route: `/${orgSlug}/ai-workspace` },
    { id: "stories",      label: "User Stories",   icon: BookOpen,        route: `/${orgSlug}/stories` },
    { id: "inbox",        label: "Posteingang",    icon: Inbox,           route: `/${orgSlug}/inbox` },
    { id: "calendar",     label: "Kalender",       icon: CalendarDays,    route: `/${orgSlug}/calendar` },
    { id: "workflows",    label: "Workflows",      icon: Workflow,        route: `/${orgSlug}/workflows` },
    { id: "docs",         label: "Dokumentation",  icon: FileText,        route: `/${orgSlug}/docs` },
    { id: "settings",     label: "Einstellungen",  icon: Settings,        route: `/${orgSlug}/settings` },
    ...(user?.is_superuser
      ? [{ id: "admin", label: "Admin", icon: Shield, route: `/${orgSlug}/admin` }]
      : []),
  ];

  const sidebarContent = (
    <aside
      style={{
        background: "var(--binding)",
        borderRight: "1.5px solid transparent",
        backgroundClip: "padding-box",
        boxShadow: "1px 0 0 #5a4a30",
        width: "200px",
        flexShrink: 0,
      }}
      className="flex flex-col h-full"
    >
      {/* Org header */}
      <div
        className="flex items-center justify-between px-4"
        style={{ height: "var(--topbar-height)", borderBottom: "1px solid rgba(255,255,255,.08)" }}
      >
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "13px", color: "rgba(255,255,255,.7)" }}>
          {orgSlug}
        </span>
        <button
          onClick={onMobileClose}
          className="md:hidden p-1 rounded"
          style={{ color: "rgba(255,255,255,.4)" }}
          aria-label="Sidebar schließen"
        >
          <X size={14} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2 overflow-y-auto">
        {navItems.map(item => {
          const isActive = pathname === item.route || pathname.startsWith(item.route + "/");
          const Icon = item.icon;
          return (
            <Link
              key={item.id}
              href={item.route}
              onClick={onMobileClose}
              className="flex items-center gap-2.5 px-2 py-1.5 rounded-sm transition-all"
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: "9px",
                letterSpacing: ".08em",
                textTransform: "uppercase",
                color: isActive ? "rgba(255,255,255,.95)" : "rgba(255,255,255,.4)",
                background: isActive ? "rgba(255,255,255,.08)" : "transparent",
                borderLeft: isActive ? "2px solid var(--paper)" : "2px solid transparent",
              }}
            >
              <Icon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
              <span className="truncate">{item.label}</span>
            </Link>
          );
        })}

        {/* Plugin nav entries */}
        {navEntries
          .filter(entry => entry.slot === "sidebar_main")
          .map(entry => {
            const PluginIcon = PLUGIN_ICONS[entry.icon?.toLowerCase()] ?? Folder;
            const route = `/${orgSlug}${entry.route}`;
            const isActive = pathname === route;
            return (
              <Link
                key={entry.id}
                href={route}
                onClick={onMobileClose}
                className="flex items-center gap-2.5 px-2 py-1.5 rounded-sm transition-all"
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: "9px",
                  letterSpacing: ".08em",
                  textTransform: "uppercase",
                  color: isActive ? "rgba(255,255,255,.95)" : "rgba(255,255,255,.4)",
                  background: isActive ? "rgba(255,255,255,.08)" : "transparent",
                  borderLeft: isActive ? "2px solid var(--paper)" : "2px solid transparent",
                }}
              >
                <PluginIcon size={13} style={{ flexShrink: 0, opacity: isActive ? 1 : 0.6 }} />
                <span className="truncate">{entry.label}</span>
              </Link>
            );
          })}

        <SlotRenderer slotId="sidebar_main" orgSlug={orgSlug} orgId={orgId} collapsed={false} />
      </nav>

      {/* User footer */}
      {user && (
        <div
          className="px-3 py-3 flex items-center gap-2"
          style={{ borderTop: "1px solid rgba(255,255,255,.08)" }}
        >
          <SlotRenderer slotId="sidebar_bottom" orgSlug={orgSlug} orgId={orgId} />
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0"
            style={{
              background: "rgba(255,255,255,.12)",
              fontFamily: "var(--font-mono)", fontSize: "8px",
              color: "rgba(255,255,255,.7)",
            }}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate" style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "rgba(255,255,255,.6)", letterSpacing: ".04em" }}>
              {user.display_name}
            </p>
          </div>
          <button
            onClick={() => void logout()}
            style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "rgba(255,255,255,.3)", letterSpacing: ".04em" }}
          >
            Logout
          </button>
        </div>
      )}
    </aside>
  );

  return (
    <>
      {/* Desktop */}
      <div className="hidden md:flex shrink-0">{sidebarContent}</div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          <div className="absolute inset-0 bg-black/50" onClick={onMobileClose} aria-hidden="true" />
          <div className="relative z-10 flex shrink-0">{sidebarContent}</div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/shell/Sidebar.tsx
git commit -m "feat(shell): rebuild Sidebar to paper/notebook binding style"
```

---

## Task 4: Rebuild Topbar

**Files:**
- Modify: `frontend/components/shell/Topbar.tsx`

- [ ] **Step 1: Rewrite Topbar.tsx**

Replace the entire file:

```tsx
"use client";

import { Menu } from "lucide-react";
import { useAuth } from "@/lib/auth/context";
import { usePathname } from "next/navigation";
import { SlotRenderer } from "@/lib/plugins/slots";
import { useEffect, useState } from "react";

interface TopbarProps {
  orgSlug: string;
  orgId?: string;
  onMenuClick?: () => void;
}

const PAGE_TITLES: Record<string, string> = {
  dashboard:    "Dashboard",
  "ai-workspace": "KI Workspace",
  stories:      "User Stories",
  inbox:        "Posteingang",
  calendar:     "Kalender",
  workflows:    "Workflows",
  docs:         "Dokumentation",
  settings:     "Einstellungen",
  admin:        "Administration",
};

export function Topbar({ orgSlug, orgId, onMenuClick }: TopbarProps) {
  const { user } = useAuth();
  const pathname = usePathname();
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  // Derive page title from pathname
  const segment = pathname.split("/")[2] ?? "dashboard";
  const pageTitle = PAGE_TITLES[segment] ?? segment;

  return (
    <header
      className="flex items-center justify-between px-4 shrink-0"
      style={{
        height: "var(--topbar-height)",
        background: "var(--paper-warm)",
        borderBottom: "1.5px solid var(--ink)",
      }}
    >
      {/* Left */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMenuClick}
          className="md:hidden p-1.5 rounded"
          style={{ color: "var(--ink-faint)" }}
          aria-label="Menü öffnen"
        >
          <Menu size={16} />
        </button>
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "17px", color: "var(--ink)" }}>
          {pageTitle}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faint)", letterSpacing: ".06em" }}>
          {orgSlug}
        </span>
      </div>

      {/* Right */}
      <div className="flex items-center gap-3">
        <SlotRenderer slotId="topbar_right" orgSlug={orgSlug} orgId={orgId} />
        {clock && (
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faintest)", letterSpacing: ".06em" }}>
            {clock}
          </span>
        )}
        {user && (
          <div
            className="w-6 h-6 rounded-full flex items-center justify-center"
            style={{
              background: "var(--paper-rule2)",
              border: "0.5px solid var(--ink-faintest)",
              fontFamily: "var(--font-mono)", fontSize: "8px",
              color: "var(--ink-mid)",
            }}
            title={user.display_name}
          >
            {user.display_name.slice(0, 2).toUpperCase()}
          </div>
        )}
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/shell/Topbar.tsx
git commit -m "feat(shell): rebuild Topbar to paper header style with live clock"
```

---

## Task 5: Update Button component

**Files:**
- Modify: `frontend/components/ui/button.tsx`

- [ ] **Step 1: Rewrite button.tsx**

Replace the entire file:

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "inline-flex items-center justify-center gap-2",
    "cursor-pointer select-none whitespace-nowrap",
    "transition-all duration-[120ms]",
    "disabled:pointer-events-none disabled:opacity-35",
    "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#c0392b] focus-visible:ring-offset-1",
  ],
  {
    variants: {
      variant: {
        default: [
          "rounded-sm border-[0.5px] border-[#1c1810]",
          "bg-[#1c1810] text-[#faf9f6]",
          "hover:bg-[#5a5040]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        outline: [
          "rounded-sm border-[0.5px] border-[#cec8bc]",
          "bg-transparent text-[#5a5040]",
          "hover:bg-[#ece8e0] hover:border-[#a09080] hover:text-[#1c1810]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        orange: [
          "rounded-sm border-[0.5px] border-[#c0392b]",
          "bg-[#c0392b] text-[#faf9f6]",
          "hover:bg-[#a93226]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        yellow: [
          "rounded-sm border-[0.5px] border-[#8b4513]",
          "bg-[rgba(139,69,19,.1)] text-[#8b4513]",
          "hover:bg-[rgba(139,69,19,.18)]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        teal: [
          "rounded-sm border-[0.5px] border-[#2d6a4f]",
          "bg-[rgba(45,106,79,.1)] text-[#2d6a4f]",
          "hover:bg-[rgba(45,106,79,.18)]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        ghost: [
          "bg-transparent border-transparent",
          "text-[#5a5040] hover:bg-[rgba(28,24,16,.06)] hover:text-[#1c1810]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
        destructive: [
          "rounded-sm border-[0.5px] border-[#c0392b]",
          "bg-[#c0392b] text-[#faf9f6]",
          "hover:bg-[#a93226]",
          "[font-family:var(--font-mono)] text-[9px] tracking-[.05em] uppercase",
        ],
      },
      size: {
        sm:      "text-[8px] px-2.5 py-[3px]",
        default: "text-[9px] px-3 py-[5px]",
        lg:      "text-[10px] px-4 py-[7px]",
        icon:    "h-8 w-8 p-0 text-xs",
        "icon-sm": "h-6 w-6 p-0 text-xs",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/button.tsx
git commit -m "feat(ui): update Button to paper/notebook aesthetic"
```

---

## Task 6: Update Card component

**Files:**
- Modify: `frontend/components/ui/card.tsx`

- [ ] **Step 1: Update card.tsx — replace base classes and accent colors**

Replace these three sections at the top of the file:

Old `accentClasses`:
```tsx
const accentClasses: Record<CardAccent, string> = {
  orange: "border-l-[4px] border-l-[#FF5C00]",
  yellow: "border-l-[4px] border-l-[#FFD700]",
  teal:   "border-l-[4px] border-l-[#00D4AA]",
  none:   "",
};
```

New `accentClasses`:
```tsx
const accentClasses: Record<CardAccent, string> = {
  orange: "border-l-[3px] border-l-[#c0392b]",
  yellow: "border-l-[3px] border-l-[#8b4513]",
  teal:   "border-l-[3px] border-l-[#2d6a4f]",
  none:   "",
};
```

Old `Card` base classes:
```tsx
        "bg-white border-2 border-[#0A0A0A]",
        flat ? "shadow-none" : "shadow-neo",
        hover && !flat
          ? "transition-[transform,box-shadow] duration-150 ease-out hover:-translate-x-px hover:-translate-y-px hover:shadow-neo-lg"
          : "",
```

New `Card` base classes:
```tsx
        "border border-[#e2ddd4] rounded-sm",
        flat ? "bg-[#faf9f6]" : "bg-[#faf9f6]",
        hover && !flat
          ? "transition-[border-color] duration-150 hover:border-[#cec8bc]"
          : "",
```

Old `CardFooter` border:
```tsx
      "flex items-center gap-3 px-6 py-4 border-t-2 border-[#0A0A0A]",
```

New `CardFooter` border:
```tsx
      "flex items-center gap-3 px-6 py-4 border-t border-[#e2ddd4]",
```

Old `CardDivider`:
```tsx
    className={cn("border-0 border-t-2 border-[#0A0A0A] mx-6", className)}
```

New `CardDivider`:
```tsx
    className={cn("border-0 border-t border-[#e2ddd4] mx-6", className)}
```

Old `CardTitle`:
```tsx
      "font-heading font-700 text-xl leading-tight text-[#0A0A0A]",
```

New `CardTitle`:
```tsx
      "[font-family:var(--font-serif)] italic font-normal text-xl leading-tight text-[#1c1810]",
```

Old `CardDescription`:
```tsx
      "text-sm text-[#6B6B6B] leading-relaxed",
```

New `CardDescription`:
```tsx
      "text-sm text-[#a09080] leading-relaxed [font-family:var(--font-body)]",
```

Old `StatCard` label:
```tsx
          "text-xs font-heading font-600 text-[#6B6B6B] uppercase tracking-widest",
```

New `StatCard` label:
```tsx
          "[font-family:var(--font-mono)] text-[8px] text-[#a09080] uppercase tracking-widest",
```

Old `StatCard` icon box:
```tsx
          "w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center bg-[#F5F0E8]",
```

New `StatCard` icon box:
```tsx
          "w-8 h-8 border border-[#e2ddd4] rounded-sm flex items-center justify-center bg-[#f7f4ee]",
```

Old `StatCard` value:
```tsx
          "font-heading font-800 text-4xl text-[#0A0A0A] leading-none mb-1",
```

New `StatCard` value:
```tsx
          "[font-family:var(--font-serif)] italic font-normal text-4xl text-[#1c1810] leading-none mb-1",
```

Old `StatCard` subtext:
```tsx
          "text-sm text-[#6B6B6B] mt-1",
```

New `StatCard` subtext:
```tsx
          "text-sm text-[#a09080] mt-1 [font-family:var(--font-body)]",
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/card.tsx
git commit -m "feat(ui): update Card to paper aesthetic"
```

---

## Task 7: Update Badge component

**Files:**
- Modify: `frontend/components/ui/badge.tsx`

- [ ] **Step 1: Replace badgeVariants base and all variant classes**

Replace the entire `badgeVariants` definition (lines 28–93):

```tsx
const badgeVariants = cva(
  [
    "inline-flex items-center gap-1",
    "[font-family:var(--font-mono)] font-medium text-[7px]",
    "px-2 py-[2px]",
    "border-[0.5px] border-current",
    "rounded-[10px]",
    "uppercase tracking-[.08em] leading-[1.4]",
    "whitespace-nowrap",
  ],
  {
    variants: {
      variant: {
        direct:          "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        interpreted:     "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        open:            "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
        met:             "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        partial:         "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        missing:         "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        nis2:            "text-[#1c1810] bg-[#ece8e0]",
        kritis:          "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        iso:             "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        iso27001:        "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        sop:             "text-[#1e3a5f] bg-[rgba(30,58,95,.06)]",
        runbook:         "text-[#5a3a7a] bg-[rgba(90,58,122,.08)]",
        bia:             "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        incident:        "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        richtlinie:      "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        auditiert:       "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        in_bearbeitung:  "text-[#8b4513] bg-[rgba(139,69,19,.1)]",
        ausstehend:      "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
        abgelaufen:      "text-[#c0392b] bg-[rgba(192,57,43,.08)]",
        default:         "text-[#5a5040] bg-[#ece8e0] border-[#cec8bc]",
        outline:         "text-[#5a5040] bg-transparent border-[#cec8bc]",
        // RAG source badges
        rag_direct:      "text-[#2d6a4f] bg-[rgba(45,106,79,.1)]",
        rag_context:     "text-[#1e3a5f] bg-[rgba(30,58,95,.08)]",
        llm:             "text-[#5a5040] bg-[#ece8e0] border-[#cec8bc]",
      },
      size: {
        sm:      "text-[6px] px-1.5 py-px",
        default: "text-[7px] px-2 py-[2px]",
        lg:      "text-[8px] px-2.5 py-1",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/ui/badge.tsx
git commit -m "feat(ui): update Badge to paper aesthetic (pill, mono font)"
```

---

## Task 8: Backend — /ai/chat SSE and /ai/extract-story endpoints

**Files:**
- Create: `backend/tests/unit/test_ai_chat.py`
- Modify: `backend/app/routers/ai.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_ai_chat.py`:

```python
"""Tests for /ai/chat and /ai/extract-story endpoints."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user import User


@pytest.fixture
def mock_user():
    u = MagicMock(spec=User)
    u.id = "00000000-0000-0000-0000-000000000001"
    u.email = "test@example.com"
    u.display_name = "Test User"
    return u


@pytest.fixture
def auth_override(mock_user):
    from app.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_stream_returns_sse(auth_override):
    """POST /ai/chat streams text/event-stream with data lines."""

    async def fake_text_stream():
        yield "Hallo "
        yield "Welt"

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=MagicMock(text_stream=fake_text_stream()))
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream = MagicMock(return_value=mock_stream_cm)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/ai/chat",
                json={"messages": [{"role": "user", "content": "Hallo"}], "mode": "chat"},
                headers={"Authorization": "Bearer fake"},
            ) as response:
                assert response.status_code == 200
                assert "text/event-stream" in response.headers["content-type"]
                chunks = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        chunks.append(line[6:])
                assert "[DONE]" in chunks
                text_chunks = [c for c in chunks if c not in ("[DONE]", "[ERROR]")]
                assert len(text_chunks) > 0


@pytest.mark.asyncio
async def test_chat_stream_rejects_unknown_mode(auth_override):
    """Unknown mode falls back to chat system prompt (no error)."""

    async def fake_text_stream():
        yield "OK"

    mock_stream_cm = AsyncMock()
    mock_stream_cm.__aenter__ = AsyncMock(return_value=MagicMock(text_stream=fake_text_stream()))
    mock_stream_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.stream = MagicMock(return_value=mock_stream_cm)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/ai/chat",
                json={"messages": [{"role": "user", "content": "Test"}], "mode": "unknown_mode"},
                headers={"Authorization": "Bearer fake"},
            ) as response:
                assert response.status_code == 200


@pytest.mark.asyncio
async def test_extract_story_returns_json(auth_override):
    """POST /ai/extract-story returns structured JSON with story sections."""
    payload = json.dumps({
        "story": ["Als Nutzer möchte ich einloggen, damit ich Zugang habe."],
        "accept": ["Gegeben ein Nutzer, wenn er einloggt, dann wird er weitergeleitet."],
        "tests": ["TC-01: Login mit gültigen Daten"],
        "release": ["v1.0: Login implementiert"],
    })

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=payload)]

    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        MockClient.return_value.messages.create = AsyncMock(return_value=mock_response)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/extract-story",
                json={"transcript": "Nutzer: Ich möchte einloggen können.\nKI: Das ist eine Login-User-Story."},
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "story" in data
        assert "accept" in data
        assert "tests" in data
        assert "release" in data
        assert isinstance(data["story"], list)


@pytest.mark.asyncio
async def test_extract_story_short_transcript_returns_empty(auth_override):
    """Transcripts under 80 chars return empty arrays without calling Anthropic."""
    with patch("app.routers.ai.anthropic.AsyncAnthropic") as MockClient:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/v1/ai/extract-story",
                json={"transcript": "kurz"},
                headers={"Authorization": "Bearer fake"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data == {"story": [], "accept": [], "tests": [], "release": []}
        MockClient.assert_not_called()
```

- [ ] **Step 2: Run tests — confirm they fail**

```bash
docker exec assist2-backend pytest tests/unit/test_ai_chat.py -v 2>&1 | tail -20
```

Expected: `FAILED` — endpoints not yet defined (`404` or import errors).

- [ ] **Step 3: Add endpoints to backend/app/routers/ai.py**

Replace the entire file:

```python
"""AI utility routes — transcription, chat streaming, story extraction."""
import json
import logging
from typing import AsyncIterator

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import get_settings
from app.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Transcription (unchanged) ────────────────────────────────────────────────

@router.post("/ai/transcribe")
async def transcribe(
    file: UploadFile,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Proxy audio file to faster-whisper and return transcribed text."""
    settings = get_settings()
    audio = await file.read()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.WHISPER_URL}/v1/audio/transcriptions",
                files={"file": (file.filename, audio, file.content_type)},
                data={"model": "whisper-1", "language": "de"},
            )
            resp.raise_for_status()
            return {"text": resp.json().get("text", "")}
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        logger.warning("Whisper service error: %s", e)
        raise HTTPException(status_code=503, detail="Transkriptions-Service nicht erreichbar")


# ── Chat streaming ───────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "Du bist ein präziser KI-Assistent für einen erfahrenen Python-Architekten "
        "(FastAPI, Docker, Microservices). Antworte direkt, technisch korrekt, ohne Füllwörter. "
        "Backtick-Code nur wo nötig. Kein Markdown außer `inline code`. Deutsch bevorzugt."
    ),
    "docs": (
        "Du bist ein Dokumentenanalyse-Experte. Extrahiere Kernaussagen strukturiert, "
        "benenne Risiken und offene Punkte klar. Kurze Absätze. Deutsch."
    ),
    "tasks": (
        "Du hilfst beim Task-Management für einen Software-Architekten. Zerlege Anfragen "
        "in konkrete priorisierte Tasks. Nummerierte Liste nach Priorität. Kurz, präzise. Deutsch."
    ),
}

EXTRACT_SYSTEM_PROMPT = (
    "Du bist ein präziser Business-Analyst. Analysiere das Gespräch und extrahiere strukturierte "
    "Informationen für ein User-Story-Dokument.\n\n"
    "Antworte NUR mit validem JSON, kein Text davor oder danach, keine Markdown-Backticks.\n\n"
    'Format: {"story": [...], "accept": [...], "tests": [...], "release": [...]}\n\n'
    'story: 1-3 User Stories "Als ... möchte ich ... damit ..."\n'
    'accept: 2-5 Akzeptanzkriterien "Gegeben ... wenn ... dann ..."\n'
    "tests: 2-4 Testfälle \"TC-01: ...\"\n"
    "release: 1-3 Release-Note-Einträge\n"
    "Leere Arrays [] wenn nicht genug Kontext. Kein Markdown, nur JSON."
)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    mode: str = "chat"
    org_id: str | None = None


class ExtractStoryRequest(BaseModel):
    transcript: str
    org_id: str | None = None


@router.post("/ai/chat")
async def chat_stream(
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream an AI chat response as Server-Sent Events."""
    settings = get_settings()
    system_prompt = CHAT_SYSTEM_PROMPTS.get(body.mode, CHAT_SYSTEM_PROMPTS["chat"])
    messages = [{"role": m.role, "content": m.content} for m in body.messages]

    async def event_generator() -> AsyncIterator[str]:
        try:
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            async with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    # Escape newlines so each SSE data line stays on one line
                    yield f"data: {text.replace(chr(10), '\\n')}\n\n"
        except Exception as e:
            logger.error("Chat stream error: %s", e)
            yield "data: [ERROR]\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/ai/extract-story")
async def extract_story(
    body: ExtractStoryRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Extract structured User Story data from a conversation transcript."""
    if len(body.transcript.strip()) < 80:
        return {"story": [], "accept": [], "tests": [], "release": []}

    settings = get_settings()
    try:
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=800,
            system=EXTRACT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Gespräch:\n\n{body.transcript}"}],
        )
        text = response.content[0].text if response.content else ""
        clean = text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean)
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning("Story extraction parse error: %s", e)
        return {"story": [], "accept": [], "tests": [], "release": []}
    except Exception as e:
        logger.warning("Story extraction error: %s", e)
        return {"story": [], "accept": [], "tests": [], "release": []}
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
docker exec assist2-backend pytest tests/unit/test_ai_chat.py -v 2>&1 | tail -20
```

Expected output:
```
PASSED tests/unit/test_ai_chat.py::test_chat_stream_returns_sse
PASSED tests/unit/test_ai_chat.py::test_chat_stream_rejects_unknown_mode
PASSED tests/unit/test_ai_chat.py::test_extract_story_returns_json
PASSED tests/unit/test_ai_chat.py::test_extract_story_short_transcript_returns_empty
4 passed
```

- [ ] **Step 5: Restart backend to pick up changes**

```bash
docker restart assist2-backend && sleep 5
docker exec assist2-backend curl -s http://localhost:8000/health
```

Expected: `{"status":"ok",...}`

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/ai.py backend/tests/unit/test_ai_chat.py
git commit -m "feat(api): add /ai/chat SSE streaming and /ai/extract-story endpoints"
```

---

## Task 9: AI Workspace frontend page

**Files:**
- Create: `frontend/app/[org]/ai-workspace/page.tsx`

- [ ] **Step 1: Create the page**

Create `frontend/app/[org]/ai-workspace/page.tsx`:

```tsx
"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { API_BASE, getAccessToken } from "@/lib/api/client";
import { apiRequest } from "@/lib/api/client";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  role: "user" | "ai";
  content: string;
  time: string;
  streaming?: boolean;
}

interface StoryData {
  story: string[];
  accept: string[];
  tests: string[];
  release: string[];
}

type ChatMode = "chat" | "docs" | "tasks";

// ─── Config ───────────────────────────────────────────────────────────────────

const MODES: { id: ChatMode; label: string; icon: string; ph: string; chips: string[] }[] = [
  {
    id: "chat", label: "Konversation", icon: "✦", ph: "Notiz eingeben…",
    chips: ["JWT Refresh Token in HttpOnly Cookie?", "FastAPI Auth Middleware mit Dependency Injection", "Docker multi-stage für Python optimieren"],
  },
  {
    id: "docs", label: "Dokumente", icon: "◈", ph: "Dokumenteninhalt einfügen…",
    chips: ["Auf Kernaussagen und Risiken analysieren", "In drei Punkten zusammenfassen", "Welche offenen Fragen bleiben?"],
  },
  {
    id: "tasks", label: "Aufgaben", icon: "◇", ph: "Aufgabe beschreiben…",
    chips: ["Tasks für JWT-Auth-System", "Was fehlt in einem Production-Ready Python-Service?", "Sprint-Planung für nächste Woche"],
  },
];

const SECTIONS: { id: keyof StoryData; label: string; color: string; stripe: string }[] = [
  { id: "story",   label: "User Story",        color: "#2d6a4f", stripe: "#2d6a4f" },
  { id: "accept",  label: "Akzeptanzkriterien", color: "#1e3a5f", stripe: "#1e3a5f" },
  { id: "tests",   label: "Testfälle",          color: "#6b3a2a", stripe: "#6b3a2a" },
  { id: "release", label: "Release Notes",      color: "#5a3a7a", stripe: "#5a3a7a" },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function renderText(text: string) {
  return text.split(/(`[^`\n]+`)/g).map((p, i) =>
    p.startsWith("`") && p.endsWith("`")
      ? <code key={i} style={{ fontFamily: "var(--font-mono)", fontSize: "11px", background: "rgba(28,24,16,.07)", border: "0.5px solid var(--ink-faintest)", borderRadius: "2px", padding: "0 4px", color: "var(--green)" }}>{p.slice(1, -1)}</code>
      : p
  );
}

async function streamChat(
  messages: { role: string; content: string }[],
  mode: ChatMode,
  orgId: string | undefined,
  onChunk: (text: string) => void,
): Promise<string> {
  const token = getAccessToken();
  const res = await fetch(`${API_BASE}/api/v1/ai/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ messages, mode, org_id: orgId ?? null }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let full = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    for (const line of dec.decode(value).split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const raw = line.slice(6).trim();
      if (raw === "[DONE]" || raw === "[ERROR]") continue;
      const text = raw.replace(/\\n/g, "\n");
      if (text) { full += text; onChunk(full); }
    }
  }
  return full;
}

async function extractStoryFromBackend(
  messages: ChatMessage[],
  orgId: string | undefined,
): Promise<StoryData | null> {
  const transcript = messages
    .filter(m => !m.streaming)
    .map(m => `${m.role === "ai" ? "KI" : "Nutzer"}: ${m.content}`)
    .join("\n\n");
  if (transcript.trim().length < 80) return null;

  try {
    const result = await apiRequest<StoryData>("/api/v1/ai/extract-story", {
      method: "POST",
      body: JSON.stringify({ transcript, org_id: orgId ?? null }),
    });
    return result;
  } catch {
    return null;
  }
}

// ─── Story Section ────────────────────────────────────────────────────────────

function StorySection({
  section, items, onUpdate,
}: {
  section: typeof SECTIONS[number];
  items: string[];
  onUpdate: (items: string[]) => void;
}) {
  const [open, setOpen] = useState(true);
  const [draft, setDraft] = useState("");

  const addItem = () => {
    const txt = draft.trim();
    if (!txt) return;
    onUpdate([...items, txt]);
    setDraft("");
  };

  return (
    <div style={{ marginBottom: 0 }}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{ display: "flex", alignItems: "center", gap: "6px", padding: "6px 12px 4px", cursor: "pointer" }}
        className="hover:bg-[rgba(0,0,0,.02)]"
      >
        <div style={{ width: "3px", height: "14px", background: section.stripe, borderRadius: "1px", flexShrink: 0 }} />
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".1em", textTransform: "uppercase", fontWeight: 500, color: section.color, flex: 1 }}>
          {section.label}
        </span>
        <span style={{ fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--ink-faintest)", background: "var(--paper-rule2)", padding: "1px 5px", borderRadius: "10px" }}>
          {items.length}
        </span>
        <span style={{ fontSize: "8px", color: "var(--ink-faintest)", transition: "transform .15s", transform: open ? "rotate(90deg)" : "none" }}>▶</span>
      </div>

      {open && (
        <>
          <div style={{ padding: "0 10px 4px 20px" }}>
            {items.map((txt, idx) => (
              <div key={idx} className="group" style={{ display: "flex", alignItems: "flex-start", gap: "6px", padding: "3px 0", borderBottom: "0.5px solid rgba(0,0,0,.04)" }}>
                <div style={{ width: "4px", height: "4px", borderRadius: "50%", background: section.stripe, flexShrink: 0, marginTop: "7px" }} />
                <textarea
                  value={txt}
                  onChange={e => { const n = [...items]; n[idx] = e.target.value; onUpdate(n); }}
                  rows={Math.max(1, Math.ceil(txt.length / 50))}
                  style={{ flex: 1, fontFamily: "var(--font-body)", fontSize: "12px", lineHeight: "1.5", color: "var(--ink)", background: "transparent", border: "none", outline: "none", resize: "none", padding: 0, width: "100%" }}
                />
                <button
                  onClick={() => onUpdate(items.filter((_, i) => i !== idx))}
                  className="opacity-0 group-hover:opacity-100 hover:text-[#c0392b] transition-opacity"
                  style={{ fontSize: "10px", color: "var(--ink-faintest)", cursor: "pointer", flexShrink: 0, background: "none", border: "none", padding: "0 2px", lineHeight: 1 }}
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "5px", padding: "4px 10px 2px 20px" }}>
            <input
              value={draft}
              onChange={e => setDraft(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addItem()}
              placeholder={`+ ${section.label} hinzufügen…`}
              style={{ flex: 1, fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "11px", background: "transparent", border: "none", outline: "none", color: "var(--ink)", borderBottom: "0.5px solid transparent", padding: "2px 0", transition: "border-color .12s" }}
              onFocus={e => (e.target.style.borderBottomColor = "var(--ink-faintest)")}
              onBlur={e => (e.target.style.borderBottomColor = "transparent")}
            />
            <button onClick={addItem} style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ink-faintest)", cursor: "pointer", background: "none", border: "none", padding: "0 2px", transition: "color .12s" }}>+</button>
          </div>
        </>
      )}
      <div style={{ height: "0.5px", background: "var(--paper-rule)", margin: "2px 12px" }} />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AIWorkspacePage({ params }: { params: { org: string } }) {
  const { org } = useOrg(params.org);

  const [mode, setMode] = useState<ChatMode>("chat");
  const [byMode, setByMode] = useState<Record<ChatMode, ChatMessage[]>>({ chat: [], docs: [], tasks: [] });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [story, setStory] = useState<StoryData>({ story: [], accept: [], tests: [], release: [] });
  const [savingStory, setSavingStory] = useState(false);

  const chatRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const msgs = byMode[mode];
  const cur = MODES.find(m => m.id === mode)!;
  const hasStoryContent = SECTIONS.some(s => story[s.id].length > 0);

  // Auto-scroll
  useEffect(() => {
    if (chatRef.current) chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [byMode, mode]);

  const resize = () => {
    if (!taRef.current) return;
    taRef.current.style.height = "auto";
    taRef.current.style.height = Math.min(taRef.current.scrollHeight, 80) + "px";
  };

  const upd = (fn: (prev: ChatMessage[]) => ChatMessage[]) =>
    setByMode(p => ({ ...p, [mode]: fn(p[mode]) }));

  const updateSection = (id: keyof StoryData, items: string[]) =>
    setStory(p => ({ ...p, [id]: items }));

  const mergeStory = (extracted: StoryData) => {
    setStory(prev => {
      const next = { ...prev };
      for (const s of SECTIONS) {
        const incoming = extracted[s.id];
        if (Array.isArray(incoming) && incoming.length > 0) {
          const manual = prev[s.id].filter(
            item => !incoming.some(inc => inc.trim().toLowerCase() === item.trim().toLowerCase())
          );
          next[s.id] = [...incoming, ...manual];
        }
      }
      return next;
    });
  };

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setError(null);

    const ts = new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    const uMsg: ChatMessage = { role: "user", content: text, time: ts };
    const next = [...msgs, uMsg];
    upd(() => next);
    setInput("");
    if (taRef.current) taRef.current.style.height = "auto";
    setLoading(true);

    const apiMsgs = next.map(m => ({ role: m.role === "ai" ? "assistant" : "user", content: m.content }));
    const ph: ChatMessage = { role: "ai", content: "", time: ts, streaming: true };
    setByMode(p => ({ ...p, [mode]: [...next, ph] }));

    let finalMsgs = next;
    try {
      let finalText = "";
      await streamChat(apiMsgs, mode, org?.id, (partial) => {
        finalText = partial;
        setByMode(p => {
          const a = [...p[mode]];
          a[a.length - 1] = { ...ph, content: partial };
          return { ...p, [mode]: a };
        });
      });

      const aiMsg: ChatMessage = { role: "ai", content: finalText, time: ts, streaming: false };
      finalMsgs = [...next, aiMsg];
      setByMode(p => { const a = [...p[mode]]; a[a.length - 1] = aiMsg; return { ...p, [mode]: a }; });

      setAnalyzing(true);
      extractStoryFromBackend(finalMsgs, org?.id).then(extracted => {
        if (extracted) mergeStory(extracted);
        setAnalyzing(false);
      }).catch(() => setAnalyzing(false));

    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Fehler");
      upd(p => p.slice(0, -1));
      setAnalyzing(false);
    } finally {
      setLoading(false);
    }
  };

  const saveStory = async () => {
    if (!org || !story.story.length) return;
    setSavingStory(true);
    try {
      await apiRequest("/api/v1/user-stories/", {
        method: "POST",
        body: JSON.stringify({
          title: story.story[0]?.slice(0, 80) ?? "Neue Story",
          description: story.story.join("\n"),
          acceptance_criteria: story.accept.join("\n"),
          status: "draft",
          org_id: org.id,
        }),
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setSavingStory(false);
    }
  };

  const exportMd = () => {
    const lines: string[] = [];
    SECTIONS.forEach(s => {
      if (story[s.id].length) {
        lines.push(`## ${s.label}\n`);
        story[s.id].forEach(item => lines.push(`- ${item}`));
        lines.push("");
      }
    });
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "userstory.md";
    a.click();
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const tabColors: Record<ChatMode, string> = { chat: "#2d6a4f", docs: "#8b4513", tasks: "#1e3a5f" };

  return (
    <div style={{ display: "flex", height: "100%", gap: 0, overflow: "hidden" }}>

      {/* ── Left: Chat panel ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--paper)", position: "relative", overflow: "hidden" }}>
        {/* Ruled lines overlay */}
        <div style={{ position: "absolute", inset: "96px 0 0", backgroundImage: "repeating-linear-gradient(180deg, transparent, transparent calc(var(--line-h) - 1px), var(--paper-rule) calc(var(--line-h) - 1px), var(--paper-rule) var(--line-h))", pointerEvents: "none", zIndex: 0 }} />
        {/* Margin line */}
        <div style={{ position: "absolute", left: "52px", top: 0, bottom: 0, width: "1px", background: "var(--margin-red)", pointerEvents: "none", zIndex: 1 }} />

        {/* Tabs */}
        <div style={{ position: "relative", zIndex: 2, display: "flex", alignItems: "flex-end", padding: "0 0 0 66px", background: "var(--paper-warm)", borderBottom: "0.5px solid var(--paper-rule)", gap: "2px", flexShrink: 0 }}>
          {MODES.map(m => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              style={{
                fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".08em", textTransform: "uppercase",
                padding: mode === m.id ? "4px 11px 5px" : "4px 11px",
                cursor: "pointer", border: "0.5px solid transparent", borderBottom: "none",
                borderRadius: "2px 2px 0 0",
                color: mode === m.id ? "#fff" : "var(--ink-faint)",
                background: mode === m.id ? tabColors[m.id] : "transparent",
                position: "relative", bottom: mode === m.id ? "-0.5px" : 0,
                transition: "all .12s",
              }}
            >
              <span style={{ marginRight: "4px" }}>{m.icon}</span>{m.label}
            </button>
          ))}
        </div>

        {/* Messages */}
        <div ref={chatRef} style={{ position: "relative", zIndex: 2, flex: 1, overflowY: "auto", padding: "10px 16px 6px 66px", display: "flex", flexDirection: "column", gap: 0 }}>
          {msgs.length === 0 ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "6px", opacity: .2, userSelect: "none" }}>
              <div style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "32px", color: "var(--ink-faint)" }}>{cur.icon}</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--ink-faint)", letterSpacing: ".08em" }}>{cur.label} · bereit</div>
            </div>
          ) : (
            msgs.map((m, i) => (
              <div key={i} style={{ display: "flex", gap: "9px", padding: "3px 0", minHeight: "var(--line-h)", alignItems: "flex-start", position: "relative", flexDirection: m.role === "user" ? "row-reverse" : "row" }}>
                <span style={{ position: "absolute", left: "-44px", fontFamily: "var(--font-mono)", fontSize: "7px", color: "var(--ink-faintest)", top: "7px", width: "38px", textAlign: "right" }}>{m.time}</span>
                <div style={{ width: "20px", height: "20px", borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "7px", fontFamily: "var(--font-mono)", flexShrink: 0, marginTop: "4px", background: m.role === "ai" ? "#eaf0ea" : "var(--paper-rule2)", color: m.role === "ai" ? "var(--green)" : "var(--ink-mid)", border: `0.5px solid ${m.role === "ai" ? "#c0d4b8" : "var(--ink-faintest)"}` }}>
                  {m.role === "ai" ? "KI" : "FW"}
                </div>
                <div style={{ flex: 1, fontFamily: m.role === "user" ? "var(--font-serif)" : "var(--font-body)", fontStyle: m.role === "user" ? "italic" : "normal", fontSize: m.role === "user" ? "13.5px" : "14.5px", lineHeight: "var(--line-h)", color: m.role === "user" ? "var(--ink-mid)" : "var(--ink)", textAlign: m.role === "user" ? "right" : "left", paddingTop: "2px" }}>
                  {m.streaming && m.content === ""
                    ? <div style={{ display: "inline-flex", gap: "3px", alignItems: "center", paddingTop: "9px" }}>
                        {[0, 180, 360].map(d => <span key={d} style={{ width: "4px", height: "4px", borderRadius: "50%", background: "var(--ink-faint)", animation: `tp .85s ease-in-out ${d}ms infinite`, display: "inline-block" }} />)}
                      </div>
                    : renderText(m.content)
                  }
                  {m.streaming && m.content !== "" && <span style={{ color: "var(--accent-red)", animation: "blink .5s step-end infinite" }}>|</span>}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Chips */}
        {msgs.length === 0 && (
          <div style={{ position: "relative", zIndex: 2, display: "flex", flexWrap: "wrap", gap: "4px", padding: "5px 16px 4px 66px" }}>
            {cur.chips.map((s, i) => (
              <button key={i} onClick={() => { setInput(s); taRef.current?.focus(); }} style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "11px", padding: "2px 8px", border: "0.5px solid var(--ink-faintest)", borderRadius: "2px", color: "var(--ink-faint)", cursor: "pointer", background: "transparent", transition: "all .12s" }}>
                {s}
              </button>
            ))}
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ position: "relative", zIndex: 2, margin: "4px 16px 4px 66px", padding: "5px 10px", borderLeft: "2px solid var(--accent-red)", background: "rgba(192,57,43,.05)", fontFamily: "var(--font-mono)", fontSize: "9px", color: "var(--accent-red)" }}>
            ⚠ {error}
          </div>
        )}

        {/* Input zone */}
        <div style={{ position: "relative", zIndex: 2, borderTop: "1px solid var(--paper-rule)", padding: "9px 14px 11px 66px", background: "var(--paper)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: "8px" }}>
            <textarea
              ref={taRef}
              rows={1}
              placeholder={cur.ph}
              value={input}
              disabled={loading}
              onChange={e => { setInput(e.target.value); resize(); }}
              onKeyDown={handleKey}
              style={{ flex: 1, fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "14px", color: "var(--ink)", background: "transparent", border: "none", borderBottom: "1px solid var(--ink-faintest)", outline: "none", resize: "none", minHeight: "26px", maxHeight: "80px", lineHeight: "1.55", padding: "3px 0 2px", transition: "border-color .15s" }}
            />
            <button
              onClick={send}
              disabled={loading || !input.trim()}
              style={{ width: "28px", height: "28px", borderRadius: "2px", background: loading || !input.trim() ? "var(--ink-faintest)" : "var(--ink)", border: "none", display: "flex", alignItems: "center", justifyContent: "center", cursor: loading || !input.trim() ? "not-allowed" : "pointer", flexShrink: 0, transition: "all .12s" }}
            >
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#faf9f6" strokeWidth="2.2" strokeLinecap="round">
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
          <div style={{ marginTop: "4px", fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".04em", color: "var(--ink-faintest)", display: "flex", justifyContent: "space-between" }}>
            <span>↵ Senden · ⇧↵ Neue Zeile</span>
            <span>claude-sonnet · {cur.label}</span>
          </div>
        </div>

        <style>{`
          @keyframes tp { 0%,100%{opacity:.15;transform:scale(.7)} 50%{opacity:1;transform:scale(1)} }
          @keyframes blink { 50%{opacity:0} }
        `}</style>
      </div>

      {/* ── Right: Story document ── */}
      <div style={{ width: "320px", flexShrink: 0, background: "var(--paper-warm)", borderLeft: "1.5px solid var(--ink)", display: "flex", flexDirection: "column", overflow: "hidden", position: "relative" }}>
        {/* Ruled lines */}
        <div style={{ position: "absolute", inset: "48px 0 0", backgroundImage: "repeating-linear-gradient(180deg, transparent, transparent calc(var(--line-h) - 1px), var(--paper-rule2) calc(var(--line-h) - 1px), var(--paper-rule2) var(--line-h))", pointerEvents: "none", zIndex: 0 }} />
        {/* Faint margin line */}
        <div style={{ position: "absolute", left: "28px", top: 0, bottom: 0, width: ".5px", background: "rgba(232,180,176,.35)", pointerEvents: "none", zIndex: 1 }} />

        {/* Header */}
        <div style={{ position: "relative", zIndex: 2, borderBottom: "1.5px solid var(--ink)", padding: "0 12px", height: "48px", display: "flex", alignItems: "center", gap: "8px", background: "var(--paper-warm)", flexShrink: 0 }}>
          <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "14px", color: "var(--ink)" }}>Notizen</span>
          {analyzing && (
            <div style={{ display: "inline-flex", alignItems: "center", gap: "5px", fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".06em", color: "var(--accent-red)", opacity: .8, animation: "fadePulse 1.2s ease-in-out infinite" }}>
              <div style={{ width: "4px", height: "4px", borderRadius: "50%", background: "var(--accent-red)" }} />
              analysiert…
            </div>
          )}
          <div style={{ marginLeft: "auto", display: "flex", gap: "4px" }}>
            {hasStoryContent && (
              <button
                onClick={saveStory}
                disabled={savingStory || !org}
                style={{ fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".06em", padding: "3px 7px", borderRadius: "2px", border: "0.5px solid var(--green)", background: "rgba(45,106,79,.08)", color: "var(--green)", cursor: "pointer", transition: "all .12s" }}
              >
                {savingStory ? "…" : "↑ Story"}
              </button>
            )}
            <button
              onClick={exportMd}
              style={{ fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".06em", padding: "3px 7px", borderRadius: "2px", border: "0.5px solid var(--ink-faintest)", background: "transparent", color: "var(--ink-faint)", cursor: "pointer", transition: "all .12s" }}
            >
              ↓ .md
            </button>
          </div>
        </div>

        {/* Sections scroll */}
        <div style={{ flex: 1, overflowY: "auto", position: "relative", zIndex: 2, padding: "10px 0 16px" }}>
          {!hasStoryContent ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "40px 20px", gap: "8px", opacity: .25, userSelect: "none" }}>
              <div style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "28px", color: "var(--ink-faint)" }}>◇</div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: "8px", color: "var(--ink-faint)", letterSpacing: ".1em", textAlign: "center", lineHeight: "1.7" }}>
                Beginne das Gespräch links.<br />Die User Story entsteht<br />automatisch hier.
              </div>
            </div>
          ) : (
            SECTIONS.map(s => (
              <StorySection key={s.id} section={s} items={story[s.id]} onUpdate={items => updateSection(s.id, items)} />
            ))
          )}
        </div>

        <style>{`@keyframes fadePulse { 0%,100%{opacity:.4} 50%{opacity:.9} }`}</style>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/app/\[org\]/ai-workspace/page.tsx
git commit -m "feat(workspace): add AI Workspace page with streaming chat and story panel"
```

---

## Task 10: Restart and smoke test

- [ ] **Step 1: Rebuild frontend container**

```bash
docker restart assist2-frontend && sleep 8
docker ps --format "table {{.Names}}\t{{.Status}}" | grep assist2
```

Expected: `assist2-frontend` shows `(healthy)`.

- [ ] **Step 2: Verify backend endpoints are reachable**

```bash
docker exec assist2-backend curl -s http://localhost:8000/docs | grep -o '"operationId":"[^"]*"' | grep -E 'chat|extract'
```

Expected output includes:
```
"operationId":"chat_stream_api_v1_ai_chat_post"
"operationId":"extract_story_api_v1_ai_extract_story_post"
```

- [ ] **Step 3: Final commit — restart containers**

```bash
docker restart assist2-backend assist2-worker
git log --oneline -8
```

Expected: 8 commits from this feature branch visible.
