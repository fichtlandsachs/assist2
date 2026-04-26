// lib/hooks/useGovernance.ts
"use client";

import useSWR, { mutate as globalMutate } from "swr";
import { fetcher, authFetch } from "@/lib/api/client";

const BASE = "/api/v1/governance";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ControlListItem {
  id: string;
  slug: string;
  kind: "fixed" | "dynamic";
  name: string;
  category_id: string | null;
  status: "draft" | "review" | "approved" | "archived";
  gate_phases: string[];
  default_weight: number;
  hard_stop: boolean;
  version: number;
  responsible_role: string | null;
  is_visible_in_frontend: boolean;
  updated_at: string;
  published_at: string | null;
}

export interface ControlDetail extends ControlListItem {
  system_id: string | null;
  short_description: string | null;
  why_relevant: string | null;
  what_to_check: string | null;
  what_to_do: string | null;
  guiding_questions: string[];
  help_text: string | null;
  control_objective: string | null;
  risk_rationale: string | null;
  escalation_logic: string | null;
  scoring_scheme_id: string | null;
  hard_stop_threshold: number;
  requires_trigger: boolean;
  trigger_config: Record<string, unknown>;
  evidence_requirements: EvidenceRequirement[];
  product_scope_ids: string[];
  market_scope_ids: string[];
  customer_segment_ids: string[];
  risk_dimension_ids: string[];
  framework_refs: string[];
  review_interval_days: number;
  last_reviewed_at: string | null;
  audit_notes: string | null;
  created_at: string;
}

export interface EvidenceRequirement {
  evidence_type_id: string;
  requirement: "mandatory" | "optional";
}

export interface GateDefinition {
  id: string;
  phase: string;
  name: string;
  description: string | null;
  min_total_score: number | null;
  hard_stop_threshold: number;
  required_fixed_control_slugs: string[];
  approver_roles: string[];
  is_active: boolean;
  version: number;
  status: string;
  updated_at: string;
  outcomes_config?: Record<string, unknown>;
  escalation_path?: string | null;
}

export interface TriggerRule {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  condition_tree: Record<string, unknown>;
  activates_control_ids: string[];
  priority: number;
  is_active: boolean;
  status: string;
  version: number;
  updated_at: string;
}

export interface EvidenceType {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  format_guidance: string | null;
  is_system: boolean;
  is_active: boolean;
}

export interface ScoringScheme {
  id: string;
  slug: string;
  name: string;
  is_default: boolean;
  scale_min: number;
  scale_max: number;
  scale_labels: ScaleLabel[];
  traffic_light: Record<string, unknown>;
  formula: string | null;
}

export interface ScaleLabel {
  value: number;
  label: string;
  color: string;
  description: string;
}

export interface GovernanceOverview {
  fixed_controls: number;
  dynamic_controls: number;
  active_triggers: number;
  hard_stop_controls: number;
  controls_without_evidence: number;
  draft_controls: number;
  review_controls: number;
  recent_changes: ChangeLogEntry[];
}

export interface ChangeLogEntry {
  id?: string;
  entity_type: string;
  entity_slug: string;
  action: string;
  from_status?: string | null;
  to_status?: string | null;
  from_version?: number | null;
  to_version?: number | null;
  change_reason?: string | null;
  actor_name: string;
  occurred_at: string;
}

export interface SimulationInput {
  product_type?: string;
  market?: string;
  customer_segment?: string;
  failure_criticality?: string;
  revenue_risk?: string;
  cost_risk?: string;
  credit_risk?: string;
  supply_risk?: string;
  quality_risk?: string;
  support_load?: string;
  has_software?: boolean;
  has_cloud?: boolean;
  has_battery?: boolean;
  has_grid_connection?: boolean;
  has_single_source?: boolean;
  new_suppliers?: boolean;
  phase?: string;
  save_as_scenario?: boolean;
  scenario_name?: string;
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useGovernanceOverview() {
  return useSWR<GovernanceOverview>(`${BASE}/overview`, fetcher, {
    refreshInterval: 30000,
  });
}

export function useControls(params?: {
  kind?: string;
  status_filter?: string;
  category_id?: string;
  hard_stop?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
}) {
  const query = new URLSearchParams();
  if (params?.kind) query.set("kind", params.kind);
  if (params?.status_filter) query.set("status_filter", params.status_filter);
  if (params?.category_id) query.set("category_id", params.category_id);
  if (params?.hard_stop !== undefined) query.set("hard_stop", String(params.hard_stop));
  if (params?.search) query.set("search", params.search);
  if (params?.page) query.set("page", String(params.page));
  if (params?.page_size) query.set("page_size", String(params.page_size));

  return useSWR<{ total: number; page: number; page_size: number; items: ControlListItem[] }>(
    `${BASE}/controls?${query.toString()}`,
    fetcher
  );
}

export function useControl(id: string | null) {
  return useSWR<ControlDetail>(id ? `${BASE}/controls/${id}` : null, fetcher);
}

export function useControlVersions(id: string | null) {
  return useSWR<{ id: string; version: number; status: string; change_reason: string | null; created_at: string }[]>(
    id ? `${BASE}/controls/${id}/versions` : null, fetcher
  );
}

export function useGates() {
  return useSWR<GateDefinition[]>(`${BASE}/gates`, fetcher);
}

export function useTriggers(activeOnly = false) {
  return useSWR<TriggerRule[]>(
    `${BASE}/triggers?active_only=${activeOnly}`,
    fetcher
  );
}

export function useEvidenceTypes() {
  return useSWR<EvidenceType[]>(`${BASE}/evidence-types`, fetcher);
}

export function useScoringSchemes() {
  return useSWR<ScoringScheme[]>(`${BASE}/scoring-schemes`, fetcher);
}

export function useCategories() {
  return useSWR<{ id: string; slug: string; name: string; description: string | null }[]>(
    `${BASE}/categories`,
    fetcher
  );
}

export function useChangelog(params?: { entity_type?: string; entity_slug?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.entity_type) query.set("entity_type", params.entity_type);
  if (params?.entity_slug) query.set("entity_slug", params.entity_slug);
  if (params?.limit) query.set("limit", String(params.limit));
  return useSWR<{ entries: ChangeLogEntry[] }>(
    `${BASE}/changelog?${query.toString()}`,
    fetcher
  );
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export async function createControl(data: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/controls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Erstellen");
  }
  await globalMutate((key: string) => typeof key === "string" && key.startsWith(`${BASE}/controls`));
  return res.json();
}

export async function updateControl(id: string, data: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/controls/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Speichern");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/controls`));
  return res.json();
}

export async function publishControl(id: string, changeReason?: string) {
  const res = await authFetch(`${BASE}/controls/${id}/publish`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ change_reason: changeReason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Veröffentlichen");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/controls`));
  return res.json();
}

export async function archiveControl(id: string) {
  const res = await authFetch(`${BASE}/controls/${id}/archive`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Archivieren");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/controls`));
  return res.json();
}

export async function duplicateControl(id: string) {
  const res = await authFetch(`${BASE}/controls/${id}/duplicate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Duplizieren");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/controls`));
  return res.json();
}

export async function runSimulation(input: SimulationInput) {
  const res = await authFetch(`${BASE}/simulation/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Simulationsfehler");
  }
  return res.json();
}

export async function updateGate(id: string, data: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/gates/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Speichern");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/gates`));
  return res.json();
}

export async function createTrigger(data: Record<string, unknown>) {
  const res = await authFetch(`${BASE}/triggers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Erstellen");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(`/triggers`));
  return res.json();
}

export async function runSeed() {
  const res = await authFetch(`${BASE}/seed`, { method: "POST" });
  if (!res.ok) throw new Error("Seed fehlgeschlagen");
  return res.json();
}
