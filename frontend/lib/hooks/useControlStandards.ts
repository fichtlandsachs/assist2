// lib/hooks/useControlStandards.ts
"use client";

import useSWR from "swr";
import { fetcher, authFetch } from "@/lib/api/client";

const BASE = "/api/v1/governance";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StandardDef {
  id: string;
  slug: string;
  name: string;
  short_name: string;
  description: string | null;
  standard_type: "external" | "internal" | "product_specific" | "customer_specific" | "regulatory";
  color: string | null;
  is_active: boolean;
  display_order: number;
  control_count: number;
}

export interface StandardBadge {
  standard_id: string;
  standard_slug: string;
  standard_name: string;
  section_ref: string | null;
  is_primary: boolean;
  color: string | null;
}

export interface GroupedControl {
  id: string;
  slug: string;
  name: string;
  short_description: string | null;
  kind: "fixed" | "dynamic";
  status: "draft" | "in_review" | "approved" | "archived";
  version: number;
  hard_stop: boolean;
  gate_phases: string[];
  control_family: string | null;
  responsible_role: string | null;
  evidence_requirements: unknown[];
  updated_at: string;
  standards: StandardBadge[];
}

export interface ControlCounts {
  total: number;
  active: number;
  hard_stops: number;
  drafts: number;
  no_evidence: number;
}

export interface FamilyGroup {
  family: string;
  counts: ControlCounts;
  controls: GroupedControl[];
}

export interface CategoryGroup {
  category: string;
  counts: ControlCounts;
  families: FamilyGroup[];
}

export interface StandardGroup {
  standard_id: string;
  standard_slug: string;
  standard_name: string;
  standard_short: string;
  standard_color: string;
  standard_type: string;
  counts: ControlCounts;
  categories: CategoryGroup[];
}

export interface GateGroup {
  gate: string;
  counts: ControlCounts;
  controls: GroupedControl[];
}

export interface GroupedResponse {
  view: "standard" | "category" | "gate";
  groups: (StandardGroup | CategoryGroup | GateGroup)[];
}

export interface GroupedControlsParams {
  view?: "standard" | "category" | "gate";
  standard_id?: string;
  category_id?: string;
  kind?: string;
  hard_stop_only?: boolean;
  active_only?: boolean;
  draft_only?: boolean;
  no_evidence_only?: boolean;
  multi_standard_only?: boolean;
  search?: string;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useStandards() {
  return useSWR<StandardDef[]>(`${BASE}/standards`, fetcher, { revalidateOnFocus: false });
}

function paramsToQuery(p: GroupedControlsParams): string {
  const q = new URLSearchParams();
  if (p.view) q.set("view", p.view);
  if (p.standard_id) q.set("standard_id", p.standard_id);
  if (p.category_id) q.set("category_id", p.category_id);
  if (p.kind) q.set("kind", p.kind);
  if (p.hard_stop_only) q.set("hard_stop_only", "true");
  if (p.active_only) q.set("active_only", "true");
  if (p.draft_only) q.set("draft_only", "true");
  if (p.no_evidence_only) q.set("no_evidence_only", "true");
  if (p.multi_standard_only) q.set("multi_standard_only", "true");
  if (p.search) q.set("search", p.search);
  return q.toString();
}

export function useGroupedControls(params: GroupedControlsParams) {
  const qs = paramsToQuery(params);
  return useSWR<GroupedResponse>(
    `${BASE}/controls-grouped?${qs}`,
    fetcher,
    { revalidateOnFocus: false }
  );
}

export function useControlStandardMappings(controlId: string | null) {
  return useSWR(
    controlId ? `${BASE}/controls/${controlId}/standards` : null,
    fetcher
  );
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export async function seedStandards() {
  const res = await authFetch(`${BASE}/standards/seed`, { method: "POST" });
  if (!res.ok) throw new Error("Seed fehlgeschlagen");
  return res.json();
}

export async function createStandard(data: {
  slug: string; name: string; short_name?: string;
  description?: string; standard_type?: string; color?: string; display_order?: number;
}) {
  const res = await authFetch(`${BASE}/standards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Fehler"); }
  return res.json();
}

export async function addStandardMapping(controlId: string, data: {
  standard_id: string; section_ref?: string; is_primary?: boolean;
}) {
  const res = await authFetch(`${BASE}/controls/${controlId}/standards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || "Fehler"); }
  return res.json();
}

export async function removeStandardMapping(controlId: string, standardId: string) {
  await authFetch(`${BASE}/controls/${controlId}/standards/${standardId}`, { method: "DELETE" });
}

export async function setControlFamily(controlId: string, family: string) {
  const res = await authFetch(`${BASE}/controls/${controlId}/family`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ control_family: family }),
  });
  if (!res.ok) throw new Error("Fehler");
  return res.json();
}
