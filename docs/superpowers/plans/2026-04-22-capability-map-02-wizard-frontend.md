# Capability Map — Sub-Plan 2: Setup Wizard Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a capability-map onboarding wizard that intercepts the org layout for new orgs (`initialization_status === "not_initialized"`), walks the admin through Screen 1 (welcome/CTA) and Screen 2 (Excel upload / template / demo data with live tree preview), then advances the org to `capability_setup_validated` so the user reaches the normal dashboard.

**Architecture:** A `SetupWizard` component is rendered instead of `{children}` inside the existing `app/[org]/layout.tsx` when `initialization_status` is `not_initialized` or `capability_setup_in_progress`. The wizard has two internal screens. After confirming the tree the init status is patched to `capability_setup_validated`; the wizard unmounts and the user sees the normal dashboard. All API calls go through `lib/api/capabilities.ts`. Frontend types for capability nodes live in `types/index.ts`.

**Tech Stack:** Next.js 14 App Router · React `useState`/`useCallback` · SWR · TypeScript · Tailwind CSS + existing design tokens (`var(--ink)`, `var(--card)`, `var(--accent-orange)`, etc.)

---

## File Map

**Create:**
- `frontend/lib/api/capabilities.ts` — API helpers for capability endpoints
- `frontend/lib/hooks/useInitStatus.ts` — SWR hook for org init status
- `frontend/components/setup/SetupWizard.tsx` — wizard shell (screen router)
- `frontend/components/setup/WelcomeScreen.tsx` — Screen 1: welcome card
- `frontend/components/setup/CapabilitySetupScreen.tsx` — Screen 2: import tabs + tree preview
- `frontend/components/setup/CapabilityTreePreview.tsx` — recursive tree renderer

**Modify:**
- `frontend/types/index.ts` — add `initialization_status` to Organization; add CapabilityTreeNode, ImportValidationResult, OrgInitStatus types
- `frontend/app/[org]/layout.tsx` — inject wizard gate using useInitStatus

---

## Task 1: Frontend types for capability map

**Files:**
- Modify: `frontend/types/index.ts`

- [ ] **Step 1: Add types at end of file**

Open `frontend/types/index.ts` and append at the bottom:

```typescript
// ─── Capability Map ───────────────────────────────────────────────────────────
export type OrgInitializationStatus =
  | "not_initialized"
  | "capability_setup_in_progress"
  | "capability_setup_validated"
  | "entry_chat_in_progress"
  | "initialized";

export interface OrgInitStatus {
  initialization_status: OrgInitializationStatus;
  initialization_completed_at: string | null;
  capability_map_version: number;
}

export type NodeType = "capability" | "level_1" | "level_2" | "level_3";

export interface CapabilityTreeNode {
  id: string;
  node_type: NodeType;
  title: string;
  description: string | null;
  sort_order: number;
  is_active: boolean;
  story_count?: number;
  children: CapabilityTreeNode[];
}

export interface ImportIssue {
  row: number | null;
  level: "error" | "warning";
  message: string;
}

export interface ImportValidationResult {
  is_valid: boolean;
  error_count: number;
  warning_count: number;
  capability_count: number;
  level_1_count: number;
  level_2_count: number;
  level_3_count: number;
  node_count: number;
  issues: ImportIssue[];
  preview: CapabilityTreeNode[];
}

export interface CapabilityTemplate {
  key: string;
  label: string;
  description: string;
  node_count: number;
}
```

Also extend the `Organization` interface (already in the file) to add `initialization_status`:

Find this block:
```typescript
export interface Organization {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  plan: "free" | "pro" | "enterprise";
  is_active: boolean;
  max_members: number | null;
  created_at: string;
}
```

Replace with:
```typescript
export interface Organization {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  plan: "free" | "pro" | "enterprise";
  is_active: boolean;
  max_members: number | null;
  created_at: string;
  initialization_status: OrgInitializationStatus;
}
```

- [ ] **Step 2: Verify TypeScript compiles (no new errors)**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no new errors related to the added types.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/types/index.ts
git commit -m "feat(capability-map): add frontend types for wizard"
```

---

## Task 2: Capability API client

**Files:**
- Create: `frontend/lib/api/capabilities.ts`

- [ ] **Step 1: Write the file**

```typescript
// frontend/lib/api/capabilities.ts
import { apiRequest } from "@/lib/api/client";
import type {
  OrgInitStatus,
  OrgInitializationStatus,
  CapabilityTreeNode,
  ImportValidationResult,
  CapabilityTemplate,
} from "@/types";

export async function fetchOrgInitStatus(orgId: string): Promise<OrgInitStatus> {
  return apiRequest<OrgInitStatus>(`/api/v1/capabilities/orgs/${orgId}/init-status`);
}

export async function advanceOrgInitStatus(
  orgId: string,
  status: OrgInitializationStatus,
  source?: string,
): Promise<OrgInitStatus> {
  return apiRequest<OrgInitStatus>(`/api/v1/capabilities/orgs/${orgId}/init-status`, {
    method: "PATCH",
    body: JSON.stringify({ status, source }),
  });
}

export async function fetchCapabilityTree(orgId: string): Promise<CapabilityTreeNode[]> {
  const data = await apiRequest<{ items: CapabilityTreeNode[] }>(
    `/api/v1/capabilities/orgs/${orgId}/tree`,
  );
  return data.items;
}

export async function fetchCapabilityTemplates(): Promise<CapabilityTemplate[]> {
  const data = await apiRequest<{ items: CapabilityTemplate[] }>(
    `/api/v1/capabilities/templates`,
  );
  return data.items;
}

export async function importDemo(orgId: string, dryRun: boolean): Promise<ImportValidationResult> {
  return apiRequest<ImportValidationResult>(
    `/api/v1/capabilities/orgs/${orgId}/import/demo?dry_run=${dryRun}`,
    { method: "POST" },
  );
}

export async function importTemplate(
  orgId: string,
  key: string,
  dryRun: boolean,
): Promise<ImportValidationResult> {
  return apiRequest<ImportValidationResult>(
    `/api/v1/capabilities/orgs/${orgId}/import/template/${key}?dry_run=${dryRun}`,
    { method: "POST" },
  );
}

export async function importExcel(
  orgId: string,
  file: File,
  dryRun: boolean,
): Promise<ImportValidationResult> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/capabilities/orgs/${orgId}/import/excel?dry_run=${dryRun}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Upload failed" }));
    throw err;
  }
  return res.json() as Promise<ImportValidationResult>;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors in capabilities.ts.

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/lib/api/capabilities.ts
git commit -m "feat(capability-map): add capability API client helpers"
```

---

## Task 3: useInitStatus hook

**Files:**
- Create: `frontend/lib/hooks/useInitStatus.ts`

- [ ] **Step 1: Write the hook**

```typescript
// frontend/lib/hooks/useInitStatus.ts
import useSWR from "swr";
import type { OrgInitStatus } from "@/types";
import { fetcher } from "@/lib/api/client";

export function useInitStatus(orgId: string | undefined) {
  const { data, error, isLoading, mutate } = useSWR<OrgInitStatus>(
    orgId ? `/api/v1/capabilities/orgs/${orgId}/init-status` : null,
    fetcher,
    { revalidateOnFocus: false },
  );
  return {
    initStatus: data,
    isLoading,
    error,
    mutate,
    needsSetup:
      data?.initialization_status === "not_initialized" ||
      data?.initialization_status === "capability_setup_in_progress",
  };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/lib/hooks/useInitStatus.ts
git commit -m "feat(capability-map): add useInitStatus SWR hook"
```

---

## Task 4: CapabilityTreePreview component

**Files:**
- Create: `frontend/components/setup/CapabilityTreePreview.tsx`

This renders a nested tree from `ImportValidationResult.preview` or live tree data. Each node is indented by level. Capabilities are bold headers; level_1/2/3 nodes are indented progressively.

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/setup/CapabilityTreePreview.tsx
"use client";

import type { CapabilityTreeNode } from "@/types";

const INDENT: Record<string, number> = {
  capability: 0,
  level_1: 16,
  level_2: 32,
  level_3: 48,
};

const TYPE_STYLE: Record<string, string> = {
  capability: "font-bold text-[13px]",
  level_1:    "font-semibold text-[12px]",
  level_2:    "text-[12px]",
  level_3:    "text-[11px]",
};

const DOT_COLOR: Record<string, string> = {
  capability: "bg-rose-500",
  level_1:    "bg-amber-400",
  level_2:    "bg-teal-400",
  level_3:    "bg-slate-300",
};

function TreeNode({ node, depth = 0 }: { node: CapabilityTreeNode; depth?: number }) {
  return (
    <div>
      <div
        className="flex items-center gap-2 py-1 px-2 rounded hover:bg-[var(--paper-warm)] transition-colors"
        style={{ paddingLeft: `${INDENT[node.node_type] + 8}px` }}
      >
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${DOT_COLOR[node.node_type]}`} />
        <span
          className={`${TYPE_STYLE[node.node_type]}`}
          style={{ color: node.node_type === "capability" ? "var(--ink)" : "var(--ink-mid)" }}
        >
          {node.title}
        </span>
        {node.story_count !== undefined && node.story_count > 0 && (
          <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-rose-100 text-rose-600 font-medium">
            {node.story_count}
          </span>
        )}
      </div>
      {node.children.map((child) => (
        <TreeNode key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}

export function CapabilityTreePreview({ nodes }: { nodes: CapabilityTreeNode[] }) {
  if (nodes.length === 0) {
    return (
      <p className="text-sm text-[var(--ink-faint)] text-center py-8">
        Keine Knoten zum Anzeigen.
      </p>
    );
  }
  return (
    <div className="space-y-1 max-h-[320px] overflow-y-auto pr-1">
      {nodes.map((node) => (
        <TreeNode key={node.id} node={node} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/components/setup/CapabilityTreePreview.tsx
git commit -m "feat(capability-map): add CapabilityTreePreview component"
```

---

## Task 5: WelcomeScreen (Screen 1)

**Files:**
- Create: `frontend/components/setup/WelcomeScreen.tsx`

Screen 1 is shown when `initialization_status === "not_initialized"`. It shows a welcome card explaining the capability map, and a "Setup starten" button that advances the org to `capability_setup_in_progress` and moves to Screen 2.

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/setup/WelcomeScreen.tsx
"use client";

import { useState } from "react";
import { Map, ArrowRight } from "lucide-react";
import { advanceOrgInitStatus } from "@/lib/api/capabilities";

interface Props {
  orgId: string;
  orgName: string;
  onNext: () => void;
}

export function WelcomeScreen({ orgId, orgName, onNext }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setLoading(true);
    setError(null);
    try {
      await advanceOrgInitStatus(orgId, "capability_setup_in_progress");
      onNext();
    } catch {
      setError("Fehler beim Starten. Bitte versuche es erneut.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex-1 flex items-center justify-center p-6">
      <div
        className="w-full max-w-lg bg-[var(--card)] border-2 border-[var(--ink)] rounded-2xl p-8 shadow-[6px_6px_0_rgba(0,0,0,1)]"
        style={{ background: "var(--card)" }}
      >
        {/* Icon */}
        <div className="w-14 h-14 rounded-2xl bg-rose-500 border-2 border-[var(--ink)] flex items-center justify-center mb-6 shadow-[3px_3px_0_rgba(0,0,0,1)]">
          <Map size={26} className="text-white" />
        </div>

        {/* Heading */}
        <h1 className="text-2xl font-bold mb-2" style={{ color: "var(--ink)" }}>
          Willkommen bei {orgName}
        </h1>
        <p className="text-sm mb-6" style={{ color: "var(--ink-mid)" }}>
          Bevor du loslegen kannst, richten wir kurz deine <strong>Business Capability Map</strong> ein.
          Sie bildet die Grundlage für alle Projekte, Epics und User Stories in deinem Workspace.
        </p>

        {/* Steps overview */}
        <div className="space-y-3 mb-8">
          {[
            { n: "1", text: "Capability Map hochladen oder Vorlage wählen" },
            { n: "2", text: "Vorschau prüfen und bestätigen" },
            { n: "3", text: "Ersten Eintrag per Chat anlegen" },
          ].map(({ n, text }) => (
            <div key={n} className="flex items-start gap-3">
              <span
                className="w-6 h-6 rounded-full border-2 border-[var(--ink)] flex items-center justify-center text-[11px] font-bold flex-shrink-0"
                style={{ background: "var(--accent-orange)", color: "var(--ink)" }}
              >
                {n}
              </span>
              <span className="text-sm pt-0.5" style={{ color: "var(--ink-mid)" }}>{text}</span>
            </div>
          ))}
        </div>

        {error && (
          <p className="text-sm text-rose-600 mb-4">{error}</p>
        )}

        <button
          onClick={handleStart}
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--ink)] font-bold text-sm shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ background: "var(--accent-orange)", color: "var(--ink)" }}
        >
          {loading ? "Wird gestartet…" : "Setup starten"}
          {!loading && <ArrowRight size={16} />}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/components/setup/WelcomeScreen.tsx
git commit -m "feat(capability-map): add WelcomeScreen wizard step"
```

---

## Task 6: CapabilitySetupScreen (Screen 2)

**Files:**
- Create: `frontend/components/setup/CapabilitySetupScreen.tsx`

Screen 2 has three tabs: Demo-Daten, Vorlage (template), Excel-Upload. Selecting a tab runs a dry-run import and shows the tree preview with issue counts. A "Bestätigen" button runs the real import and advances status to `capability_setup_validated`.

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/setup/CapabilitySetupScreen.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { Upload, Layers, Sparkles, CheckCircle, AlertTriangle, ChevronRight } from "lucide-react";
import {
  importDemo,
  importTemplate,
  importExcel,
  fetchCapabilityTemplates,
  advanceOrgInitStatus,
} from "@/lib/api/capabilities";
import { CapabilityTreePreview } from "./CapabilityTreePreview";
import type { ImportValidationResult, CapabilityTemplate } from "@/types";

type TabId = "demo" | "template" | "excel";

interface Props {
  orgId: string;
  onDone: () => void;
}

export function CapabilitySetupScreen({ orgId, onDone }: Props) {
  const [tab, setTab] = useState<TabId>("demo");
  const [templates, setTemplates] = useState<CapabilityTemplate[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportValidationResult | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load templates
  useEffect(() => {
    fetchCapabilityTemplates()
      .then((items) => {
        setTemplates(items);
        if (items.length > 0) setSelectedTemplate(items[0].key);
      })
      .catch(() => {/* non-critical */});
  }, []);

  // Auto-preview for demo tab
  useEffect(() => {
    if (tab === "demo") {
      runDryRun();
    } else {
      setPreview(null);
    }
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function runDryRun() {
    setLoadingPreview(true);
    setPreview(null);
    setError(null);
    try {
      let result: ImportValidationResult;
      if (tab === "demo") {
        result = await importDemo(orgId, true);
      } else if (tab === "template" && selectedTemplate) {
        result = await importTemplate(orgId, selectedTemplate, true);
      } else if (tab === "excel" && selectedFile) {
        result = await importExcel(orgId, selectedFile, true);
      } else {
        return;
      }
      setPreview(result);
    } catch (e: unknown) {
      const msg = (e as { error?: string })?.error ?? "Fehler bei der Vorschau.";
      setError(msg);
    } finally {
      setLoadingPreview(false);
    }
  }

  async function handleConfirm() {
    setConfirming(true);
    setError(null);
    try {
      // Real import (dry_run=false)
      let source: string;
      if (tab === "demo") {
        await importDemo(orgId, false);
        source = "demo";
      } else if (tab === "template" && selectedTemplate) {
        await importTemplate(orgId, selectedTemplate, false);
        source = "template";
      } else if (tab === "excel" && selectedFile) {
        await importExcel(orgId, selectedFile, false);
        source = "excel";
      } else {
        setError("Bitte wähle eine Option.");
        setConfirming(false);
        return;
      }
      await advanceOrgInitStatus(orgId, "capability_setup_validated", source);
      onDone();
    } catch (e: unknown) {
      const msg = (e as { error?: string })?.error ?? "Fehler beim Importieren.";
      setError(msg);
    } finally {
      setConfirming(false);
    }
  }

  const canPreview =
    tab === "demo" ||
    (tab === "template" && selectedTemplate != null) ||
    (tab === "excel" && selectedFile != null);

  const canConfirm = preview?.is_valid && !loadingPreview;

  return (
    <div className="flex-1 flex items-start justify-center p-6">
      <div className="w-full max-w-2xl space-y-4">
        {/* Header */}
        <div>
          <h1 className="text-xl font-bold" style={{ color: "var(--ink)" }}>
            Business Capability Map einrichten
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--ink-mid)" }}>
            Wähle eine Quelle für deine initiale Capability-Struktur.
          </p>
        </div>

        {/* Tab bar */}
        <div
          className="flex gap-1 p-1 rounded-xl border-2 border-[var(--ink)]"
          style={{ background: "var(--paper-warm)" }}
        >
          {([
            { id: "demo" as TabId, label: "Demo-Daten", icon: Sparkles },
            { id: "template" as TabId, label: "Vorlage", icon: Layers },
            { id: "excel" as TabId, label: "Excel-Upload", icon: Upload },
          ] as { id: TabId; label: string; icon: React.ElementType }[]).map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className="flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all"
              style={{
                background: tab === id ? "var(--card)" : "transparent",
                color: tab === id ? "var(--ink)" : "var(--ink-faint)",
                boxShadow: tab === id ? "2px 2px 0 rgba(0,0,0,.8)" : "none",
                border: tab === id ? "1.5px solid var(--ink)" : "1.5px solid transparent",
              }}
            >
              <Icon size={14} />
              {label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div
          className="bg-[var(--card)] border-2 border-[var(--ink)] rounded-2xl p-5 shadow-[4px_4px_0_rgba(0,0,0,1)]"
        >
          {tab === "demo" && (
            <p className="text-sm mb-4" style={{ color: "var(--ink-mid)" }}>
              Wir laden eine Beispiel-Capability-Map mit drei Hauptbereichen (Digitale Transformation, Produkt &amp; Entwicklung, Betrieb &amp; Infrastruktur) — ideal zum Ausprobieren.
            </p>
          )}

          {tab === "template" && (
            <div className="space-y-2 mb-4">
              <p className="text-sm mb-3" style={{ color: "var(--ink-mid)" }}>
                Wähle eine vorgefertigte Vorlage als Ausgangspunkt:
              </p>
              {templates.map((tpl) => (
                <button
                  key={tpl.key}
                  onClick={() => {
                    setSelectedTemplate(tpl.key);
                    setPreview(null);
                  }}
                  className="w-full text-left p-3 rounded-xl border-2 transition-all"
                  style={{
                    borderColor: selectedTemplate === tpl.key ? "var(--accent-orange)" : "var(--paper-rule2)",
                    background: selectedTemplate === tpl.key ? "rgba(var(--accent-orange-rgb),.06)" : "var(--paper-warm)",
                  }}
                >
                  <div className="font-medium text-sm" style={{ color: "var(--ink)" }}>{tpl.label}</div>
                  <div className="text-xs mt-0.5" style={{ color: "var(--ink-faint)" }}>{tpl.description} · {tpl.node_count} Knoten</div>
                </button>
              ))}
              {selectedTemplate && (
                <button
                  onClick={runDryRun}
                  disabled={loadingPreview}
                  className="mt-2 px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  {loadingPreview ? "Lade Vorschau…" : "Vorschau laden"}
                </button>
              )}
            </div>
          )}

          {tab === "excel" && (
            <div className="mb-4">
              <p className="text-sm mb-3" style={{ color: "var(--ink-mid)" }}>
                Lade eine Excel-Datei (.xlsx) hoch. Benötigte Spalten: <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Capability</code>, <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 1</code>, <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 2</code> (optional: <code className="text-xs bg-[var(--paper-warm)] px-1 rounded">Level 3</code>).
              </p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setSelectedFile(f);
                  setPreview(null);
                }}
              />
              <div className="flex items-center gap-3">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  Datei wählen
                </button>
                {selectedFile && (
                  <span className="text-sm" style={{ color: "var(--ink-mid)" }}>{selectedFile.name}</span>
                )}
              </div>
              {selectedFile && (
                <button
                  onClick={runDryRun}
                  disabled={loadingPreview}
                  className="mt-3 px-4 py-2 text-sm rounded-lg border-2 border-[var(--ink)] font-medium shadow-[2px_2px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-50"
                  style={{ background: "var(--paper-warm)", color: "var(--ink)" }}
                >
                  {loadingPreview ? "Validiere…" : "Prüfen & Vorschau"}
                </button>
              )}
            </div>
          )}

          {/* Validation result summary */}
          {preview && (
            <div className="mb-4 space-y-3">
              <div className="flex items-center gap-3 flex-wrap">
                <div
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium"
                  style={{
                    background: preview.is_valid ? "rgba(16,185,129,.08)" : "rgba(239,68,68,.08)",
                    borderColor: preview.is_valid ? "rgba(16,185,129,.3)" : "rgba(239,68,68,.3)",
                    color: preview.is_valid ? "#059669" : "#dc2626",
                  }}
                >
                  {preview.is_valid ? <CheckCircle size={14} /> : <AlertTriangle size={14} />}
                  {preview.is_valid ? "Valide" : `${preview.error_count} Fehler`}
                </div>
                <span className="text-xs" style={{ color: "var(--ink-faint)" }}>
                  {preview.capability_count} Capabilities · {preview.node_count} Knoten gesamt
                </span>
                {preview.warning_count > 0 && (
                  <span className="text-xs text-amber-600">{preview.warning_count} Warnungen</span>
                )}
              </div>

              {preview.issues.filter((i) => i.level === "error").length > 0 && (
                <div className="space-y-1">
                  {preview.issues.filter((i) => i.level === "error").slice(0, 5).map((issue, idx) => (
                    <div key={idx} className="text-xs text-rose-600 flex gap-1.5">
                      <span>•</span>
                      <span>{issue.row != null ? `Zeile ${issue.row}: ` : ""}{issue.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Tree preview */}
          {loadingPreview && (
            <div className="flex items-center gap-2 py-6 justify-center" style={{ color: "var(--ink-faint)" }}>
              <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
              <span className="text-sm">Lade Vorschau…</span>
            </div>
          )}

          {preview && preview.preview.length > 0 && (
            <div>
              <p className="text-xs font-bold uppercase tracking-widest mb-2" style={{ color: "var(--ink-faint)" }}>
                Vorschau
              </p>
              <CapabilityTreePreview nodes={preview.preview} />
            </div>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="text-sm text-rose-600 px-1">{error}</div>
        )}

        {/* Confirm button */}
        <div className="flex justify-end">
          <button
            onClick={handleConfirm}
            disabled={!canConfirm || confirming}
            className="flex items-center gap-2 px-6 py-3 rounded-xl border-2 border-[var(--ink)] font-bold text-sm shadow-[3px_3px_0_rgba(0,0,0,1)] hover:shadow-none hover:translate-x-px hover:translate-y-px transition-all disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-[3px_3px_0_rgba(0,0,0,1)] disabled:translate-x-0 disabled:translate-y-0"
            style={{ background: canConfirm ? "var(--accent-orange)" : "var(--paper-warm)", color: "var(--ink)" }}
          >
            {confirming ? "Wird übernommen…" : "Capability Map bestätigen"}
            {!confirming && <ChevronRight size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -30
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/components/setup/CapabilitySetupScreen.tsx
git commit -m "feat(capability-map): add CapabilitySetupScreen with tabs and tree preview"
```

---

## Task 7: SetupWizard shell

**Files:**
- Create: `frontend/components/setup/SetupWizard.tsx`

The shell routes between Screen 1 (WelcomeScreen) and Screen 2 (CapabilitySetupScreen) using internal state. After Screen 2 completes, it calls `onComplete` to let the layout re-fetch init status.

- [ ] **Step 1: Create the component**

```tsx
// frontend/components/setup/SetupWizard.tsx
"use client";

import { useState } from "react";
import { WelcomeScreen } from "./WelcomeScreen";
import { CapabilitySetupScreen } from "./CapabilitySetupScreen";
import type { OrgInitializationStatus } from "@/types";

type WizardScreen = "welcome" | "capability-setup";

interface Props {
  orgId: string;
  orgName: string;
  currentStatus: OrgInitializationStatus;
  onComplete: () => void;
}

export function SetupWizard({ orgId, orgName, currentStatus, onComplete }: Props) {
  const [screen, setScreen] = useState<WizardScreen>(
    currentStatus === "capability_setup_in_progress" ? "capability-setup" : "welcome",
  );

  return (
    <div className="flex flex-col min-h-full">
      {/* Progress indicator */}
      <div className="flex items-center gap-2 px-2 pb-4">
        {(["welcome", "capability-setup"] as WizardScreen[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-full border-2 border-[var(--ink)] flex items-center justify-center text-[10px] font-bold"
              style={{
                background: screen === s || (s === "welcome" && screen === "capability-setup")
                  ? "var(--accent-orange)"
                  : "var(--paper-warm)",
                color: "var(--ink)",
              }}
            >
              {i + 1}
            </div>
            <span
              className="text-xs font-medium hidden sm:inline"
              style={{ color: screen === s ? "var(--ink)" : "var(--ink-faint)" }}
            >
              {s === "welcome" ? "Willkommen" : "Capability Map"}
            </span>
            {i < 1 && <div className="w-8 h-px" style={{ background: "var(--paper-rule2)" }} />}
          </div>
        ))}
      </div>

      {screen === "welcome" && (
        <WelcomeScreen
          orgId={orgId}
          orgName={orgName}
          onNext={() => setScreen("capability-setup")}
        />
      )}

      {screen === "capability-setup" && (
        <CapabilitySetupScreen
          orgId={orgId}
          onDone={onComplete}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -20
```

- [ ] **Step 3: Commit**

```bash
cd /opt/assist2
git add frontend/components/setup/SetupWizard.tsx
git commit -m "feat(capability-map): add SetupWizard shell component"
```

---

## Task 8: Wire wizard gate into org layout

**Files:**
- Modify: `frontend/app/[org]/layout.tsx`

When `needsSetup` is true (init status is `not_initialized` or `capability_setup_in_progress`), render the `SetupWizard` inside the main content area instead of `{children}`. After the wizard completes, call `mutate()` on the init status SWR key so it re-fetches and `needsSetup` becomes false.

- [ ] **Step 1: Update imports and add wizard gate**

The current `frontend/app/[org]/layout.tsx` content:

```tsx
"use client";

import { useAuth } from "@/lib/auth/context";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { Breadcrumb } from "@/components/shell/Breadcrumb";
import { useOrg } from "@/lib/hooks/useOrg";
```

Replace the imports section and add the wizard gate. Full new file:

```tsx
"use client";

import { useAuth } from "@/lib/auth/context";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { Sidebar } from "@/components/shell/Sidebar";
import { Topbar } from "@/components/shell/Topbar";
import { Breadcrumb } from "@/components/shell/Breadcrumb";
import { useOrg } from "@/lib/hooks/useOrg";
import { useInitStatus } from "@/lib/hooks/useInitStatus";
import { SetupWizard } from "@/components/setup/SetupWizard";

export default function OrgLayout({
  children,
  params
}: {
  children: React.ReactNode;
  params: Promise<{ org: string }>;
}) {
  const resolvedParams = use(params);
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const { org } = useOrg(resolvedParams.org);
  const { needsSetup, initStatus, mutate: mutateInitStatus } = useInitStatus(org?.id);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isAuthenticated, isLoading, router]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-8 w-8" style={{ borderBottom: "2px solid var(--ink-mid)" }} />
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "var(--paper)" }}>
      <Sidebar
        orgSlug={resolvedParams.org}
        orgId={org?.id}
        orgName={org?.name}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />
      <div className="flex flex-col flex-1 overflow-hidden min-w-0">
        <Topbar
          orgSlug={resolvedParams.org}
          orgId={org?.id}
          onMenuClick={() => setMobileSidebarOpen(true)}
        />
        <main
          className="flex-1 overflow-y-auto overflow-x-hidden p-4 md:p-6 relative"
          style={{ background: "var(--main-content-bg)" }}
        >
          {/* Subtle dot grid overlay (src_agile style) */}
          <div className="dot-grid-overlay pointer-events-none absolute inset-0 opacity-[0.03]"
            style={{ backgroundImage: "radial-gradient(#000 0.5px, transparent 0.5px)", backgroundSize: "30px 30px" }} />
          <div className="relative min-h-full flex flex-col">
            {needsSetup && org && initStatus ? (
              <SetupWizard
                orgId={org.id}
                orgName={org.name}
                currentStatus={initStatus.initialization_status}
                onComplete={() => mutateInitStatus()}
              />
            ) : (
              <>
                <Breadcrumb orgSlug={resolvedParams.org} />
                {children}
              </>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /opt/assist2/frontend && npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors.

- [ ] **Step 3: Build the frontend to catch any remaining issues**

```bash
cd /opt/assist2/frontend && npm run build 2>&1 | tail -30
```

Expected: Build succeeds (may show prerender warnings for dynamic pages — those are fine).

- [ ] **Step 4: Commit**

```bash
cd /opt/assist2
git add frontend/app/\[org\]/layout.tsx
git commit -m "feat(capability-map): wire setup wizard gate into org layout"
```

---

## Task 9: Rebuild frontend container

**Files:** (no code changes — Docker only)

- [ ] **Step 1: Rebuild**

```bash
cd /opt/assist2/infra && docker compose -f docker-compose.yml up -d --build frontend
```

- [ ] **Step 2: Check container is healthy**

```bash
docker logs heykarl-frontend --tail 20 2>&1
```

Expected: no crash, Next.js server running.

- [ ] **Step 3: Smoke-test in browser**

Open the app as a user belonging to a newly created org (or temporarily patch an existing org's `initialization_status` to `not_initialized` in the DB). Verify:
1. The wizard gate appears (WelcomeScreen shown, not the dashboard)
2. "Setup starten" advances to Screen 2
3. Demo tab shows tree preview
4. Confirming advances status and shows the normal dashboard

To patch an org for testing (run inside postgres container):
```sql
UPDATE organizations SET initialization_status = 'not_initialized' WHERE slug = '<your-org-slug>';
```

- [ ] **Step 4: Commit**

No new code — this step is verification only.
